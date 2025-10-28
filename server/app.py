from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
import json
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import subprocess, tempfile, os, shutil
import concurrent.futures
import base64
import uuid
from typing import Optional

from jewel.config import settings
from jewel.memory.sqlite_store import SqliteStore
from jewel.core.agent import Agent
from jewel.core.scheduler import Scheduler
from jewel.core.persona import Persona
from jewel.core.emotion import EmotionState
from jewel.io.tts_queue import queue_manager
from datetime import datetime, timezone
from fastapi import Request

app = FastAPI(title="Jewel Server")


@app.get('/debug/logs')
async def debug_logs():
    # Return last 500 lines of server_err.log if present (local dev only)
    try:
        p = Path('server_err.log')
        if not p.exists():
            return JSONResponse(status_code=200, content="(no server_err.log present)")
        # Read last 500 lines
        with p.open('r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        tail = ''.join(lines[-500:])
        return JSONResponse(status_code=200, content=tail)
    except Exception as e:
        return JSONResponse(status_code=500, content=str(e))

@app.get("/health")
async def health():
    return {"ok": True}

# Serve static web UI under /ui
static_dir = Path(__file__).resolve().parent.parent / "run" / "static"
app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="ui")
# Serve data files (generated audio, queued results) under /data
data_dir = Path(__file__).resolve().parent.parent / "data"
app.mount("/data", StaticFiles(directory=str(data_dir), html=False), name="data")


@app.get("/")
async def root():
	# Send users to the enhanced chat by default
	return RedirectResponse(url="/ui/chat_enhanced.html")


# Initialize storage + agent once
store = SqliteStore(settings.db_path)
agent = Agent(store)
# Initialize scheduler (background thread) but start it in FastAPI lifecycle events
scheduler = Scheduler(store)
persona = Persona(store)
emotion = EmotionState(store)


def _check_local_token(request: Request) -> bool:
    """Return True if request is allowed to access gated endpoints.
    If settings.local_secret_token is empty, allow localhost requests.
    Otherwise require header X-Local-Token to match.
    """
    token = settings.local_secret_token
    if not token:
        # no token configured; allow by default
        return True
    hdr = request.headers.get('X-Local-Token') or request.headers.get('x-local-token')
    return bool(hdr and hdr == token)


@app.on_event("startup")
async def _startup():
    try:
        scheduler.start()
    except Exception:
        pass
    try:
        # start TTS queue background worker
        queue_manager.start()
    except Exception:
        pass


@app.on_event("shutdown")
async def _shutdown():
    try:
        scheduler.stop()
    except Exception:
        pass
    try:
        queue_manager.stop()
    except Exception:
        pass


class ChatIn(BaseModel):
	text: str


@app.post("/chat")
async def chat(body: ChatIn):
	try:
		reply = agent.ask(body.text)
		return {"reply": reply}
	except Exception as e:
		return JSONResponse(status_code=500, content={"error": str(e)})


class ScheduleIn(BaseModel):
    run_at: str
    payload: dict | None = None
    text: str | None = None


@app.post("/schedule")
async def schedule_task(body: ScheduleIn):
    # Accept ISO8601 datetime or epoch seconds as run_at
    try:
        try:
            run_at = datetime.fromisoformat(body.run_at)
        except Exception:
            # try epoch seconds
            run_at = datetime.fromtimestamp(float(body.run_at), tz=timezone.utc)
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid run_at; use ISO8601 or epoch seconds"})

    payload = body.payload or ({"text": body.text} if body.text else {})
    try:
        tid = scheduler.schedule(run_at, payload)
        return {"id": tid}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/persona")
async def get_persona():
    try:
        return {"persona": persona.get()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/persona")
async def set_persona(body: dict):
    try:
        p = persona.set(body)
        return {"persona": p}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/persona/reset")
async def reset_persona():
    try:
        p = persona.reset()
        return {"persona": p}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})



@app.get("/emotion")
async def get_emotion():
    try:
        return {"emotion": emotion.get()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


class EmotionTriggerIn(BaseModel):
    delta_valence: float | None = 0.0
    delta_arousal: float | None = 0.0
    tag: str | None = None


@app.post("/emotion/trigger")
async def trigger_emotion(body: EmotionTriggerIn):
    try:
        new = emotion.trigger(delta_valence=body.delta_valence or 0.0, delta_arousal=body.delta_arousal or 0.0, tag=body.tag)
        return {"emotion": new}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/emotion/reset")
async def reset_emotion():
    try:
        new = emotion.reset()
        return {"emotion": new}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/reflections")
async def get_reflections(request: Request):
    try:
        if not _check_local_token(request):
            return JSONResponse(status_code=403, content={"error": "Missing or invalid local token"})
        msgs = store.recent_private_messages(100)
        # return as list of {role, content}
        out = [{"role": r, "content": c} for r, c in msgs]
        return {"reflections": out}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/reflections/reset")
async def reset_reflections(request: Request):
    try:
        if not _check_local_token(request):
            return JSONResponse(status_code=403, content={"error": "Missing or invalid local token"})
        store.clear_private_messages()
        return {"ok": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/tasks")
async def list_tasks(include_done: bool = False):
    try:
        return {"tasks": scheduler.list_tasks(include_done=include_done)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: int):
    try:
        ok = scheduler.cancel(task_id)
        return {"ok": ok}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


class PlatformSettings(BaseModel):
	ui_theme: str | None = None
	azure_tts_voice: str | None = None
	response_style: str | None = None
	personality_temperature: float | None = None


@app.get("/platform")
async def get_platform():
	# Read persisted overrides (if any) with sensible defaults
	def g(k, d=None):
		v = store.get(k)
		return v if v is not None else d

	return {
		"ui_theme": g("ui_theme", "purple"),
		"azure_tts_voice": g("azure_tts_voice", settings.azure_tts_voice),
		"response_style": g("response_style", "friendly"),
		"personality_temperature": float(g("personality_temperature", 0.7)),
		"persona": settings.persona_name,
		"user": settings.user_name,
		"model": settings.openai_model,
	}


@app.post("/platform")
async def set_platform(body: PlatformSettings):
	# Persist provided knobs into kv store
	for k, v in body.model_dump(exclude_none=True).items():
		store.set(k, str(v))
	return {"ok": True}


class TTSIn(BaseModel):
	text: str
	voice: str | None = None


@app.post("/tts")
async def tts(body: TTSIn):
    from jewel.io.tts_openai import synthesize as tts_synthesize

    voice = body.voice or settings.azure_tts_voice
    out_dir = Path("./data")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_mp3 = out_dir / "tts_output.mp3"

    # Try a short synchronous TTS call (in thread) to return audio quickly when possible.
    # If synthesis is slow (timeout) or fails transiently, enqueue and return 202 with a status URL.
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(tts_synthesize, body.text, str(out_mp3), voice)
            try:
                path = fut.result(timeout=8)
                # success within timeout
                try:
                    ym = datetime.utcnow().strftime("%Y%m")
                    key = f"usage_{ym}_tts_chars"
                    cur = int(store.get(key) or "0")
                    store.set(key, str(cur + len(body.text or "")))
                except Exception:
                    pass
                ext = Path(path).suffix.lower()
                ctype = "audio/mpeg" if ext == ".mp3" else "audio/wav"
                return FileResponse(path, media_type=ctype, filename=Path(path).name)
            except concurrent.futures.TimeoutError:
                # long-running synth: enqueue for async processing
                jid = queue_manager.enqueue(body.text, voice)
                status_url = f"/tts/status/{jid}"
                return JSONResponse(status_code=202, content={"status":"queued","id":jid,"status_url":status_url})
            except Exception as e:
                # If immediate failure (rate limit / token) attempt fallback behavior in unified synthesize
                msg = str(e)
                if '429' in msg or 'Too Many Requests' in msg or 'issueToken' in msg or 'token request failed' in msg.lower():
                    # Try enqueueing so background worker can retry with fallback
                    try:
                        jid = queue_manager.enqueue(body.text, voice)
                        status_url = f"/tts/status/{jid}"
                        return JSONResponse(status_code=202, content={"status":"queued","id":jid,"status_url":status_url})
                    except Exception:
                        return JSONResponse(status_code=429, content={"error": msg})
                return JSONResponse(status_code=200, content={"error": msg})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get('/tts/status/{job_id}')
async def tts_status(job_id: str):
    """Return status for an enqueued TTS job. If done, includes a relative URL to the audio file."""
    try:
        st = queue_manager.status_path(job_id)
        if not st.exists():
            return JSONResponse(status_code=404, content={"error": "job not found"})
        with open(st, 'r', encoding='utf-8') as f:
            j = json.load(f)
        out = {k: j.get(k) for k in ('id', 'status', 'error', 'created_at', 'started_at', 'finished_at')}
        if j.get('status') == 'done':
            # expose a relative path clients can fetch
            out['url'] = f"/data/tts_queue/results/{job_id}.mp3"
        return out
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/audio")
async def transcribe_audio(file: UploadFile = File(...)):
	# Transcribe uploaded audio (webm) using Vosk if available
	model_path = settings.vosk_model_path
	if not model_path:
		return JSONResponse(status_code=200, content={"error": "STT not configured (VOSK_MODEL_PATH missing)"})

	try:
		with tempfile.TemporaryDirectory() as td:
			src = Path(td) / file.filename
			with src.open("wb") as f:
				f.write(await file.read())

			wav = Path(td) / "audio.wav"
			# Convert to 16k mono PCM using ffmpeg
			cmd = [
				"ffmpeg",
				"-y",
				"-i",
				str(src),
				"-ac",
				"1",
				"-ar",
				"16000",
				str(wav),
			]
			try:
				subprocess.run(cmd, check=True, capture_output=True)
			except Exception as e:
				return JSONResponse(status_code=200, content={"error": f"ffmpeg conversion failed: {e}"})

			# Feed into Vosk recognizer
			import vosk, wave, json
			rec = vosk.KaldiRecognizer(vosk.Model(model_path), 16000)
			with wave.open(str(wav), "rb") as wf:
				while True:
					data = wf.readframes(4000)
					if len(data) == 0:
						break
					rec.AcceptWaveform(data)
			res = json.loads(rec.FinalResult())
			return {"text": res.get("text", "")}
	except Exception as e:
		return JSONResponse(status_code=200, content={"error": str(e)})


@app.post("/vision")
async def vision(file: UploadFile = File(...), prompt: str = Form("")):
    """Analyze an image using OpenAI Vision API (gpt-4o supports vision)."""
    import base64
    from openai import OpenAI
    
    if not prompt:
        prompt = "Describe this image in detail."
    
    try:
        # Read and encode image
        image_data = await file.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Determine mime type from filename
        ext = Path(file.filename).suffix.lower()
        mime_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime_type = mime_map.get(ext, 'image/jpeg')
        
        client = OpenAI(api_key=settings.openai_api_key)
        
        # Use gpt-4o which supports vision
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500
        )
        
        reply = response.choices[0].message.content
        return {"reply": reply}
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Vision analysis failed: {str(e)}"})
class VideoIn(BaseModel):
    url: str
    every: int | None = None
    max_frames: int | None = None
    quick: bool | None = False


@app.post("/video_summary")
async def video_summary(body: VideoIn):
    """Analyze any video (YouTube, Twitter, TikTok, etc.) by extracting frames and audio, then summarizing both visual and spoken content."""
    try:
        import re
        import base64
        import io
        from openai import OpenAI
        from youtube_transcript_api import YouTubeTranscriptApi
        import yt_dlp
        from PIL import Image
        
        # Try to get YouTube transcript if it's a YouTube URL (optional)
        transcript_text = ""
        video_id = None
        yt_patterns = [
            r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed/)([0-9A-Za-z_-]{11})',
            r'(?:watch\?v=)([0-9A-Za-z_-]{11})'
        ]
        for pattern in yt_patterns:
            match = re.search(pattern, body.url)
            if match:
                video_id = match.group(1)
                break
        
        if video_id:
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                transcript_text = " ".join([entry['text'] for entry in transcript_list])
                if len(transcript_text) > 8000:
                    transcript_text = transcript_text[:8000] + "..."
            except Exception:
                pass  # Continue without transcript
        
        # Download video and extract frames
        with tempfile.TemporaryDirectory() as td:
            video_path = Path(td) / "video.mp4"
            
            # Download with yt-dlp (best quality up to 720p to save bandwidth)
            ydl_opts = {
                'format': 'best[height<=720]',
                'outtmpl': str(video_path),
                'quiet': True,
                'no_warnings': True,
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([body.url])
            except Exception as e:
                return JSONResponse(status_code=400, content={"error": f"Could not download video: {str(e)}"})
            
            # Extract frames using ffmpeg (every N seconds)
            frame_interval = body.every or 30  # Default: 1 frame per 30 seconds
            # If quick mode requested, force a very small frame count for a cheap run
            if getattr(body, 'quick', False):
                max_frames = 1
            else:
                max_frames = body.max_frames or 6
            frames_dir = Path(td) / "frames"
            frames_dir.mkdir()
            
            try:
                cmd = [
                    "ffmpeg", "-i", str(video_path),
                    "-vf", f"fps=1/{frame_interval}",
                    "-frames:v", str(max_frames),
                    str(frames_dir / "frame_%03d.jpg")
                ]
                subprocess.run(cmd, check=True, capture_output=True)
            except Exception as e:
                return JSONResponse(status_code=400, content={"error": f"Frame extraction failed: {str(e)}"})
            
            # Encode frames as base64 and compute a simple visual summary (avg color)
            frame_data = []
            visual_summary = []
            for idx, frame_file in enumerate(sorted(frames_dir.glob("*.jpg"))[:max_frames], start=1):
                with Image.open(frame_file) as img:
                    # Resize to save tokens (max 512px on longest side)
                    img.thumbnail((512, 512))
                    # Compute average color
                    try:
                        pixels = list(img.getdata())
                        if len(pixels) > 0:
                            r = sum(p[0] for p in pixels) // len(pixels)
                            g = sum(p[1] for p in pixels) // len(pixels)
                            b = sum(p[2] for p in pixels) // len(pixels)
                            visual_summary.append(f"Frame {idx}: avg_color=rgb({r},{g},{b})")
                        else:
                            visual_summary.append(f"Frame {idx}: no_pixels")
                    except Exception:
                        visual_summary.append(f"Frame {idx}: could not compute color")
                    # Use an in-memory buffer to avoid Windows file-locking issues
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG', quality=85)
                    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                    frame_data.append(b64)
            
            if not frame_data:
                return JSONResponse(status_code=400, content={"error": "No frames could be extracted from video"})
            
            # Build vision API request with all frames
            client = OpenAI(api_key=settings.openai_api_key)
            
            content = [
                {"type": "text", "text": "Analyze this video by looking at these key frames sampled throughout. Describe what you see happening visually, the main themes, and provide a comprehensive summary."}
            ]
            
            for b64_frame in frame_data:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_frame}"}
                })
            
            if transcript_text:
                content.append({
                    "type": "text",
                    "text": f"\n\nTranscript (spoken words):\n{transcript_text}"
                })
            
            response = client.chat.completions.create(
                model="gpt-4o",  # Vision-capable model
                messages=[{"role": "user", "content": content}],
                max_tokens=1000,
                temperature=0.6
            )
            
            try:
                summary = response.choices[0].message.content
                # Return the textual reply plus lightweight metadata (frames count, visual summary, and small frame thumbnails)
                return {
                    "reply": f"📹 Video Analysis ({len(frame_data)} frames):\n\n{summary}",
                    "frames_extracted": len(frame_data),
                    "visual_summary": visual_summary,
                    "frames": [f"data:image/jpeg;base64,{b64}" for b64 in frame_data]
                }
            except Exception as e:
                # If we couldn't read the model response, return partial info
                import logging, traceback
                logging.exception('Failed to extract summary from OpenAI response')
                return JSONResponse(status_code=500, content={
                    "error": f"Could not parse model response: {str(e)}",
                    "frames_extracted": len(frame_data),
                    "transcript": transcript_text,
                    "visual_summary": visual_summary,
                    "frames": [f"data:image/jpeg;base64,{b64}" for b64 in frame_data]
                })
        
    except ImportError as e:
        return JSONResponse(status_code=500, content={"error": f"Missing dependency: {str(e)}. Run: pip install yt-dlp pillow youtube-transcript-api"})
    except Exception as e:
        # If OpenAI returns a quota/429 style error, surface a clearer status and include partial results
        import logging, traceback
        logging.exception('Video analysis failed')
        msg = str(e)
        if 'insufficient_quota' in msg or '429' in msg or 'quota' in msg.lower():
            # Build a lightweight heuristic summary from transcript or visual summary
            fallback_summary = []
            try:
                t = locals().get('transcript_text') or ""
                if t:
                    # simple heuristic: split into sentences and pick first 3 non-empty pieces
                    import re
                    parts = [p.strip() for p in re.split(r'[\.\!\?]\s+', t) if p.strip()]
                    for s in parts[:3]:
                        fallback_summary.append(s if len(s) < 400 else s[:400] + '...')
                else:
                    # if no transcript, summarize visual info
                    vs = locals().get('visual_summary') or []
                    if vs:
                        fallback_summary.extend(vs[:3])
            except Exception:
                fallback_summary = []

            return JSONResponse(status_code=429, content={
                "error": "OpenAI quota exceeded or insufficient quota. Check your API plan/billing.",
                "detail": msg,
                # include best-effort partial results if available
                "frames_extracted": locals().get('frame_data') and len(frame_data) or 0,
                "transcript": locals().get('transcript_text') or "",
                "visual_summary": locals().get('visual_summary') or [],
                "frames": [f"data:image/jpeg;base64,{b64}" for b64 in (locals().get('frame_data') or [])],
                "fallback_summary": fallback_summary
            })
        return JSONResponse(status_code=500, content={"error": f"Video analysis failed: {str(e)}"})
@app.post('/generate_image')
async def generate_image(body: dict):
    """Generate an image from a text prompt using the configured OpenAI Images API.
    Saves the image into ./data/generated_images and returns a relative URL.
    """
    try:
        prompt = (body.get('prompt') if isinstance(body, dict) else None) or ''
        size = (body.get('size') if isinstance(body, dict) else None) or '512x512'
        n = int(body.get('n') or 1)
        if not prompt:
            return JSONResponse(status_code=400, content={"error": "prompt is required"})

        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)

        # Try to be compatible with different OpenAI client versions.
        resp = None
        try:
            if hasattr(client.images, 'generate'):
                # Newer SDK: images.generate
                resp = client.images.generate(model='gpt-image-1', prompt=prompt, size=size, n=n)
            elif hasattr(client.images, 'create'):
                # older naming: images.create
                resp = client.images.create(prompt=prompt, size=size, n=n)
            else:
                # fallback to old module-style API
                import openai as oai
                resp = oai.Image.create(prompt=prompt, size=size, n=n)
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Image generation failed: {str(e)}"})

        # Extract base64-encoded image data from response in common fields
        b64_data = None
        try:
            # Some SDKs return an object with .data
            if hasattr(resp, 'data') and resp.data:
                item = resp.data[0]
                # try several common keys
                b64_data = getattr(item, 'b64_json', None) or getattr(item, 'b64', None) or (item.get('b64_json') if isinstance(item, dict) else None)
            elif isinstance(resp, dict) and resp.get('data'):
                item = resp['data'][0]
                b64_data = item.get('b64_json') or item.get('b64')
        except Exception:
            b64_data = None

        if not b64_data:
            return JSONResponse(status_code=500, content={"error": "Image generation returned no image data"})

        img_bytes = base64.b64decode(b64_data)
        out_dir = Path('./data/generated_images')
        out_dir.mkdir(parents=True, exist_ok=True)
        fid = uuid.uuid4().hex
        fname = f"{fid}.png"
        path = out_dir / fname
        with open(path, 'wb') as f:
            f.write(img_bytes)

        return {"url": f"/data/generated_images/{fname}", "id": fid}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ---------- Simple Text→Video Prototype (stitched frames) ----------

class VideoGenRequest(BaseModel):
    prompt: str
    frames: Optional[int] = 6            # keep small for cost + speed
    size: Optional[str] = "512x512"
    fps: Optional[int] = 6


class VideoGenResponse(BaseModel):
    url: str
    file_path: str
    frame_paths: list[str]


def _basic_prompt_guard(p: str) -> bool:
    # ultra-simple guard; your app may already have richer safety
    banned = ["illegal", "hate", "graphic", "sexual minor"]
    return not any(term in p.lower() for term in banned)


@app.post("/prototype_video", response_model=VideoGenResponse)
def prototype_video(req: VideoGenRequest):
    if req.frames < 3 or req.frames > 24:
        raise HTTPException(status_code=400, detail="frames must be between 3 and 24.")
    if not _basic_prompt_guard(req.prompt):
        raise HTTPException(status_code=400, detail="Prompt rejected by safety filter.")

    tmpdir = tempfile.mkdtemp(prefix="jewel_frames_")
    frame_paths = []
    try:
        # Generate N independent frames (will have some flicker; this is just a prototype)
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)

        for i in range(req.frames):
            gen = client.images.generate(
                model="gpt-image-1",
                prompt=req.prompt + f" — cinematic frame {i+1}",
                size=req.size,
            )
            b64 = gen.data[0].b64_json
            img_bytes = base64.b64decode(b64)
            path = os.path.join(tmpdir, f"{i:03d}.png")
            with open(path, "wb") as f:
                f.write(img_bytes)
            frame_paths.append(path)

        # Ensure output dir exists
        out_dir = Path('./data/generated_videos')
        out_dir.mkdir(parents=True, exist_ok=True)

        # Stitch with ffmpeg
        vid_id = str(uuid.uuid4())[:8]
        out_path = os.path.join(str(out_dir), f"{vid_id}.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(req.fps),
            "-i", os.path.join(tmpdir, "%03d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            out_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return VideoGenResponse(
            url=f"/data/generated_videos/{vid_id}.mp4",
            file_path=out_path,
            frame_paths=frame_paths,
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"ffmpeg failed: {e.stderr.decode(errors='ignore')}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Video prototype failed: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)



@app.get("/usage")
async def usage():
    """Return simple monthly usage counters and cost estimates.
    Estimates based on public pricing references:
      - gpt-4o-mini: $0.15 / 1M input tokens, $0.60 / 1M output tokens
      - tts-1: $15 / 1M characters
    """
    ym = datetime.utcnow().strftime("%Y%m")
    def gi(k: str) -> int:
        try:
            return int(store.get(k) or "0")
        except Exception:
            return 0

    tin = gi(f"usage_{ym}_tokens_in")
    tout = gi(f"usage_{ym}_tokens_out")
    msgs = gi(f"usage_{ym}_messages")
    tchars = gi(f"usage_{ym}_tts_chars")

    # Cost estimates (USD)
    cost_text = (tin * 0.15 / 1_000_000.0) + (tout * 0.60 / 1_000_000.0)
    cost_tts = (tchars * 15.0 / 1_000_000.0)
    total = cost_text + cost_tts

    return {
        "month": ym,
        "tokens_in": tin,
        "tokens_out": tout,
        "messages": msgs,
        "tts_chars": tchars,
        "cost_text_usd": round(cost_text, 4),
        "cost_tts_usd": round(cost_tts, 4),
        "cost_total_usd": round(total, 4),
    }



# ============================================
# EMOTIONAL CONTINUITY ENDPOINTS
# ============================================

@app.get('/emotion/current')
async def get_current_emotion():
    '''Get Jewel's current emotional state.'''
    state = emotion.get()
    mood_label = emotion.get_mood_label()
    return {
        'emotion': state,
        'mood': mood_label,
        'description': f'Feeling {mood_label}'
    }


@app.post('/emotion/trigger')
async def trigger_emotion(
    delta_valence: float = Form(0.0),
    delta_arousal: float = Form(0.0),
    tag: str = Form(None),
    importance: float = Form(1.0)
):
    '''Trigger an emotional change.'''
    state = emotion.trigger(
        delta_valence=delta_valence,
        delta_arousal=delta_arousal,
        tag=tag,
        importance=importance
    )
    return {'emotion': state, 'mood': emotion.get_mood_label()}


@app.get('/emotion/pattern')
async def analyze_emotional_pattern(hours: int = 24):
    '''Analyze emotional patterns over time.'''
    analysis = emotion.analyze_emotional_pattern(hours=hours)
    return {'analysis': analysis}


@app.post('/emotion/baseline')
async def set_emotional_baseline(
    valence: float = Form(0.1),
    arousal: float = Form(0.3)
):
    '''Set Jewel's baseline emotional state.'''
    emotion.set_baseline(valence=valence, arousal=arousal)
    return {'ok': True, 'baseline': {'valence': valence, 'arousal': arousal}}


@app.post('/emotion/reset')
async def reset_emotion(preserve_baseline: bool = True):
    '''Reset emotional state.'''
    state = emotion.reset(preserve_baseline=preserve_baseline)
    return {'emotion': state}


# ============================================
# LONG-TERM MEMORY ENDPOINTS
# ============================================

@app.get('/memory/sessions')
async def get_sessions(limit: int = 10):
    '''Get recent conversation sessions.'''
    return {'sessions': ltm.get_session_history(limit=limit)}


@app.post('/memory/sessions/start')
async def start_new_session():
    '''Start a new conversation session.'''
    session_id = ltm.start_session()
    return {'session_id': session_id}


@app.post('/memory/sessions/{session_id}/end')
async def end_session(session_id: int, emotion_summary: str = None, topics: list = None):
    '''End a conversation session with summary.'''
    ltm.end_session(session_id, emotion_summary, topics)
    return {'ok': True}


@app.get('/memory/search')
async def search_memories(q: str, limit: int = 10):
    '''Search conversation history.'''
    memories = ltm.search_memories(q, limit=limit)
    return {'memories': memories}


@app.get('/memory/important')
async def get_important_memories(threshold: int = 5, limit: int = 20):
    '''Get important memories.'''
    memories = ltm.get_important_memories(threshold=threshold, limit=limit)
    return {'memories': memories}


@app.post('/memory/milestones')
async def add_milestone(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form('general')
):
    '''Add a relationship milestone.'''
    ltm.add_milestone(title, description, category)
    return {'ok': True}


@app.get('/memory/milestones')
async def get_milestones(category: str = None, limit: int = 50):
    '''Get relationship milestones.'''
    milestones = ltm.get_milestones(category=category, limit=limit)
    return {'milestones': milestones}


@app.post('/memory/preferences')
async def learn_preference(
    category: str = Form(...),
    key: str = Form(...),
    value: str = Form(...),
    confidence: float = Form(0.5)
):
    '''Record a learned user preference.'''
    ltm.learn_preference(category, key, value, confidence)
    return {'ok': True}


@app.get('/memory/preferences')
async def get_preferences(category: str = None):
    '''Get learned preferences.'''
    prefs = ltm.get_preferences(category=category)
    return {'preferences': prefs}


@app.post('/memory/goals')
async def add_self_goal(goal: str = Form(...), reason: str = Form(...)):
    '''Jewel sets a goal for herself.'''
    goal_id = ltm.add_self_goal(goal, reason)
    return {'goal_id': goal_id}


@app.get('/memory/goals')
async def get_self_goals():
    '''Get Jewel's active self-improvement goals.'''
    goals = ltm.get_active_goals()
    return {'goals': goals}


@app.post('/memory/goals/{goal_id}/progress')
async def update_goal_progress(goal_id: int, notes: str = Form(...)):
    '''Update progress on a self-goal.'''
    ltm.update_goal_progress(goal_id, notes)
    return {'ok': True}


@app.post('/memory/goals/{goal_id}/complete')
async def complete_goal(goal_id: int):
    '''Mark a self-goal as completed.'''
    ltm.complete_goal(goal_id)
    return {'ok': True}


@app.post('/memory/creative')
async def save_creative_work(
    type: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    created_for: str = Form('self')
):
    '''Save something Jewel creates.'''
    work_id = ltm.save_creative_work(type, title, content, created_for=created_for)
    return {'work_id': work_id}


@app.get('/memory/creative')
async def get_creative_works(type: str = None, limit: int = 20):
    '''Get Jewel's creative outputs.'''
    works = ltm.get_creative_works(work_type=type, limit=limit)
    return {'works': works}


@app.get('/memory/context')
async def get_conversation_context():
    '''Build rich context from long-term memory.'''
    context = ltm.build_conversation_context()
    return {'context': context}

# ==================== SAFETY ENDPOINTS ====================

@app.get('/safety/violations')
async def get_violations():
    '''Get all safety violations (for admin dashboard).'''
    from jewel.core.safety_enhanced import SafetySystem
    safety = SafetySystem(str(Path(settings.db_path).parent / 'jewel_safety.db'))
    violations = safety.get_violations(limit=100)
    return JSONResponse({'violations': violations})

@app.get('/safety/flagged')
async def get_flagged_accounts():
    '''Get all flagged/banned accounts.'''
    from jewel.core.safety_enhanced import SafetySystem
    import sqlite3
    safety = SafetySystem(str(Path(settings.db_path).parent / 'jewel_safety.db'))
    
    cur = safety.conn.execute(
        '''SELECT user_id, ip_address, status, severity, reason, flagged_at 
           FROM flagged_accounts ORDER BY id DESC LIMIT 100'''
    )
    accounts = []
    for row in cur.fetchall():
        accounts.append({
            'user_id': row[0],
            'ip_address': row[1],
            'status': row[2],
            'severity': row[3],
            'reason': row[4],
            'flagged_at': row[5]
        })
    
    return JSONResponse({'accounts': accounts})

@app.get('/safety/emergencies')
async def get_emergencies():
    '''Get all emergency events (abuse detection).'''
    from jewel.core.safety_enhanced import SafetySystem
    safety = SafetySystem(str(Path(settings.db_path).parent / 'jewel_safety.db'))
    events = safety.get_emergency_events(limit=100)
    return JSONResponse({'events': events})

@app.post('/safety/check')
async def check_content_safety(
    text: str = Form(...),
    user_id: str = Form(None),
    ip_address: str = Form(None)
):
    '''Check if content is safe (for frontend validation).'''
    from jewel.core.safety_enhanced import SafetySystem
    safety = SafetySystem(str(Path(settings.db_path).parent / 'jewel_safety.db'))
    
    is_safe, category, reason = safety.check_content(text, user_id, ip_address)
    
    return JSONResponse({
        'is_safe': is_safe,
        'category': category,
        'reason': reason
    })

@app.post('/safety/check_abuse')
async def check_abuse(
    audio_transcript: str = Form(...),
    video_context: str = Form(None),
    user_id: str = Form(None)
):
    '''Check for abuse/distress (smart glasses integration).'''
    from jewel.core.safety_enhanced import SafetySystem
    safety = SafetySystem(str(Path(settings.db_path).parent / 'jewel_safety.db'))
    
    abuse_detected, emergency_info = safety.detect_abuse(
        audio_transcript,
        video_context,
        user_id
    )
    
    return JSONResponse({
        'abuse_detected': abuse_detected,
        'emergency_info': emergency_info
    })


# 
# Safety System Endpoints
# 

@app.get("/safety/violations")
async def get_safety_violations(user_id: str = None, limit: int = 100):
    from jewel.core.safety_enhanced import SafetySystem
    from pathlib import Path
    data_dir = Path(settings.db_path).parent
    safety = SafetySystem(str(data_dir / "jewel_safety.db"))
    violations = safety.get_violations(user_id, limit)
    return {"violations": violations}

@app.get("/safety/flagged")
async def get_flagged_accounts(limit: int = 100):
    from jewel.core.safety_enhanced import SafetySystem
    from pathlib import Path
    import sqlite3
    data_dir = Path(settings.db_path).parent
    safety_db = str(data_dir / "jewel_safety.db")
    conn = sqlite3.connect(safety_db)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, ip_address, reason, severity, status, flagged_at, banned_at FROM flagged_accounts ORDER BY flagged_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    accounts = [{"user_id": r[0], "ip_address": r[1], "reason": r[2], "severity": r[3], "status": r[4], "flagged_at": r[5], "banned_at": r[6]} for r in rows]
    return {"accounts": accounts}

@app.get("/safety/emergencies")
async def get_emergency_events(limit: int = 100):
    from jewel.core.safety_enhanced import SafetySystem
    from pathlib import Path
    data_dir = Path(settings.db_path).parent
    safety = SafetySystem(str(data_dir / "jewel_safety.db"))
    events = safety.get_emergency_events(limit)
    return {"events": events}

@app.post("/safety/check")
async def check_content_safety(request: dict):
    from jewel.core.safety_enhanced import SafetySystem
    from pathlib import Path
    data_dir = Path(settings.db_path).parent
    safety = SafetySystem(str(data_dir / "jewel_safety.db"))
    text = request.get("text", "")
    user_id = request.get("user_id")
    ip_address = request.get("ip_address")
    is_safe, category, reason = safety.check_content(text, user_id, ip_address)
    return {"is_safe": is_safe, "category": category, "reason": reason}

@app.post("/safety/check_abuse")
async def check_abuse(request: dict):
    from jewel.core.safety_enhanced import SafetySystem
    from pathlib import Path
    data_dir = Path(settings.db_path).parent
    safety = SafetySystem(str(data_dir / "jewel_safety.db"))
    audio_transcript = request.get("audio_transcript")
    video_context = request.get("video_context")
    user_id = request.get("user_id")
    abuse_detected, emergency_info = safety.detect_abuse(audio_transcript, video_context, user_id)
    return {"abuse_detected": abuse_detected, "emergency_info": emergency_info}

@app.get("/safety/violations")
async def get_violations(user_id: str = None, limit: int = 100):
    from jewel.core.safety_enhanced import SafetySystem
    from pathlib import Path
    data_dir = Path(settings.db_path).parent
    safety = SafetySystem(str(data_dir / "jewel_safety.db"))
    violations = safety.get_violations(user_id, limit)
    return {"violations": violations}

@app.get("/safety/flagged")
async def get_flagged(limit: int = 100):
    from jewel.core.safety_enhanced import SafetySystem
    from pathlib import Path
    import sqlite3
    data_dir = Path(settings.db_path).parent
    safety = SafetySystem(str(data_dir / "jewel_safety.db"))
    conn = sqlite3.connect(str(data_dir / "jewel_safety.db"))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM flagged_accounts ORDER BY flagged_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    accounts = [dict(row) for row in rows]
    conn.close()
    return {"accounts": accounts}

@app.get("/safety/emergencies")
async def get_emergencies(limit: int = 100):
    from jewel.core.safety_enhanced import SafetySystem
    from pathlib import Path
    data_dir = Path(settings.db_path).parent
    safety = SafetySystem(str(data_dir / "jewel_safety.db"))
    events = safety.get_emergency_events(limit)
    return {"events": events}
