import json, os, time, random
from ..config import settings

# Minimal example using Azure TTS REST API with a small resilient layer:
# - caches the short-lived token in-memory
# - retries token/tts requests with exponential backoff on 429/5xx
# - raises RuntimeError with helpful message on persistent failures

import requests

# Simple module-level token cache
_TOKEN_CACHE = {
    "token": None,
    "expires_at": 0.0,  # epoch seconds
}

def _fetch_token_with_retries(token_url: str, headers: dict, max_attempts: int = 4) -> str:
    backoff = 0.5
    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.post(token_url, headers=headers, timeout=10)
            if r.status_code == 429 or 500 <= r.status_code < 600:
                # transient server-side or rate limit
                raise requests.HTTPError(f"HTTP {r.status_code}: {r.text}", response=r)
            r.raise_for_status()
            return r.text
        except requests.HTTPError as e:
            # If last attempt, re-raise wrapped error
            if attempt == max_attempts:
                raise
            # otherwise sleep exponential backoff with jitter
            sleep = backoff * (2 ** (attempt - 1))
            sleep = sleep + random.uniform(0, 0.3 * sleep)
            time.sleep(sleep)
        except requests.RequestException:
            if attempt == max_attempts:
                raise
            time.sleep(backoff * (2 ** (attempt - 1)))


def synthesize(text: str, outfile: str = "./data/out.wav", voice: str = None) -> str:
    if not settings.azure_tts_key or not settings.azure_tts_region:
        raise RuntimeError("Azure TTS not configured")

    # Use provided voice or fall back to settings
    voice_name = voice or settings.azure_tts_voice

    token_url = f"https://{settings.azure_tts_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    tts_url = f"https://{settings.azure_tts_region}.tts.speech.microsoft.com/cognitiveservices/v1"

    # Acquire token (cached)
    now = time.time()
    token = None
    if _TOKEN_CACHE.get("token") and _TOKEN_CACHE.get("expires_at", 0) > now + 5:
        token = _TOKEN_CACHE["token"]
    else:
        try:
            tok_text = _fetch_token_with_retries(token_url, headers={"Ocp-Apim-Subscription-Key": settings.azure_tts_key})
        except Exception as e:
            # Surface a readable error for caller; leave fallback to higher-level code
            raise RuntimeError(f"Azure TTS token request failed: {e}")
        # token is typically valid ~10 minutes; cache for 9 minutes
        token = tok_text
        _TOKEN_CACHE["token"] = token
        _TOKEN_CACHE["expires_at"] = time.time() + (9 * 60)

    ssml = f"""
    <speak version='1.0' xml:lang='en-US'>
      <voice name='{voice_name}'>
        {text}
      </voice>
    </speak>
    """.strip()

    # Choose output format based on requested file extension
    ext = os.path.splitext(outfile)[1].lower()
    if ext == ".mp3":
        out_format = "audio-16khz-128kbitrate-mono-mp3"
    else:
        # Default WAV PCM
        out_format = "riff-24khz-16bit-mono-pcm"

    # Try TTS post with retries (handle 429 or transient 5xx)
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.post(
                tts_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": out_format,
                },
                data=ssml.encode("utf-8"),
                timeout=30,
            )
            if r.status_code == 429 or 500 <= r.status_code < 600:
                # raise to trigger retry logic below
                raise requests.HTTPError(f"HTTP {r.status_code}: {r.text}", response=r)
            r.raise_for_status()
            os.makedirs(os.path.dirname(outfile) or "./", exist_ok=True)
            with open(outfile, "wb") as f:
                f.write(r.content)
            return outfile
        except requests.HTTPError as e:
            # If rate limited, clear cached token so next attempt fetches a fresh token
            if e.response is not None and e.response.status_code == 401:
                _TOKEN_CACHE["token"] = None
                _TOKEN_CACHE["expires_at"] = 0
            if attempt == max_attempts:
                raise RuntimeError(f"Azure TTS synthesis failed after {max_attempts} attempts: {e}")
            # backoff with jitter
            sleep = 0.5 * (2 ** (attempt - 1))
            time.sleep(sleep + random.uniform(0, 0.3 * sleep))
        except requests.RequestException as e:
            if attempt == max_attempts:
                raise RuntimeError(f"Azure TTS request error: {e}")
            time.sleep(0.5 * (2 ** (attempt - 1)))
