from typing import List, Dict, Any
from .safety import check_safety
from ..memory.sqlite_store import SqliteStore
from ..config import settings
from ..logging_setup import logger
from ..tools.local_tools import TOOLS
from ..prompts import SYSTEM_PROMPT
from openai import OpenAI
from datetime import datetime
import time
import json

class Agent:
    def __init__(self, store: SqliteStore):
        self.store = store
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.persona = settings.persona_name
        self.user = settings.user_name

    def _context(self) -> List[Dict[str, str]]:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT(self.persona, self.user)}]
        # Inject persistent persona and recent emotion state (if any) to help the model personalize replies
        try:
            p_raw = self.store.get('persona')
            if p_raw:
                try:
                    p = json.loads(p_raw)
                    msgs.append({"role": "system", "content": f"Persona persistent info: {p}"})
                except Exception:
                    msgs.append({"role": "system", "content": f"Persona persistent info: {p_raw}"})
        except Exception:
            pass
        try:
            e_raw = self.store.get('emotion')
            if e_raw:
                try:
                    e = json.loads(e_raw)
                    msgs.append({"role": "system", "content": f"Current emotion state: {e}"})
                except Exception:
                    msgs.append({"role": "system", "content": f"Current emotion state: {e_raw}"})
        except Exception:
            pass
        for role, content in self.store.recent_messages(16):
            msgs.append({"role": role, "content": content})
        return msgs

    def _tool_route(self, text: str) -> Any:
        # naive tool router: call a tool if it starts with a slash (e.g., /note buy milk)
        if not text.startswith("/"):
            return None
        parts = text[1:].split(" ", 1)
        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else ""
        tool = TOOLS.get(cmd)
        if not tool:
            return f"Unknown command: /{cmd}"
        try:
            return tool(arg)
        except Exception as e:
            return f"Tool error: {e}"

    def _generate_reflections(self, text: str) -> list:
        """Produce a short list of private 'thought' strings from the incoming user text.

        This is a lightweight, local-only heuristic reflection generator. It avoids
        calling third-party APIs unless the user explicitly enables that behavior.
        """
        out = []
        s = text.strip()
        # Short goal summary
        goal = s if len(s) <= 120 else s[:117] + "..."
        out.append(f"Goal: {goal}")
        # Uncertainty heuristic
        if "?" in s or any(w in s.lower() for w in ("maybe", "could", "might", "if", "unclear", "not sure")):
            out.append("Uncertainty: The user's intent has ambiguity or is a question.")
        else:
            out.append("Uncertainty: Low.")
        # Plan heuristic
        if len(s.split()) > 30:
            out.append("Plan: Provide a concise summary, then ask a clarifying question.")
        else:
            out.append("Plan: Answer directly and offer additional help.")
        return out

    def ask(self, text: str) -> str:
        ok, why = check_safety(text)
        if not ok:
            logger.warning(f"Safety blocked: {why}")
            return "I'm not able to help with that."

        tool_result = self._tool_route(text)
        if tool_result is not None:
            self.store.add_message("user", text)
            self.store.add_message("assistant", str(tool_result))
            return str(tool_result)

        # Personalization knobs (with safe defaults)
        try:
            temp_cfg = self.store.get("personality_temperature")
            temperature = float(temp_cfg) if temp_cfg is not None else 0.6
        except Exception:
            temperature = 0.6
        style = self.store.get("response_style") or "friendly"

        extra_style = (
            f"Style: {style}. Keep answers brief by default (aim for ≤3 sentences). "
            f"Ask a clarifying question if the request is ambiguous."
        )

        msgs = self._context() + [
            {"role": "system", "content": extra_style},
            {"role": "user", "content": text},
        ]

        # Optional private reflection step (internal only). If persona indicates opt_in_reflection,
        # generate up to 3 short private thoughts and store them locally via store.add_private_message.
        try:
            p_raw = self.store.get('persona')
            opt_in = False
            if p_raw:
                try:
                    pr = json.loads(p_raw)
                    opt_in = bool(pr.get('opt_in_reflection'))
                except Exception:
                    opt_in = False
            if opt_in:
                try:
                    # Create a condensed prompt for internal reflection
                    refl_prompt = (
                        "You are the assistant's private reflection generator. Given the following recent context and the user message, "
                        "produce up to 3 very short reflection lines (one idea or concern per line). Do NOT expose these publicly.\n\n"
                    )
                    # Build a compact context string
                    ctx_text = '\n'.join([f"{m['role']}: {m['content'][:200]}" for m in msgs[-8:]])
                    refl_msgs = [
                        {"role": "system", "content": refl_prompt},
                        {"role": "user", "content": ctx_text}
                    ]
                    try:
                        resp_refl = self.client.chat.completions.create(
                            model=self.model,
                            messages=refl_msgs,
                            max_tokens=150,
                            temperature=0.6,
                        )
                        refl_text = resp_refl.choices[0].message.content or ""
                    except Exception:
                        # best-effort fallback simple heuristic
                        refl_text = f"Thought: user asked about '{text[:120]}'"

                    # Split into lines and store each as a private message
                    for line in [l.strip() for l in (refl_text or "").splitlines() if l.strip()][:3]:
                        try:
                            self.store.add_private_message('reflection', line)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass
        # If persona indicates opt-in for private reflections, generate and store them
        try:
            p_raw = self.store.get('persona')
            if p_raw:
                try:
                    p = json.loads(p_raw)
                except Exception:
                    p = {}
            else:
                p = {}
            if p.get('opt_in_reflection'):
                reflections = self._generate_reflections(text)
                for r in reflections:
                    try:
                        self.store.add_private_message('reflection', r)
                    except Exception:
                        logger.debug('Failed to write private reflection to store')
        except Exception:
            pass
        # Ask model with defensive defaults to ensure a reply
        # Try the OpenAI call with retries and exponential backoff to handle transient network issues
        resp = None
        answer = None
        timeouts = [20, 30, 60]
        for attempt, to in enumerate(timeouts, start=1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=msgs,
                    temperature=temperature,
                    max_tokens=400,
                    timeout=to,
                )
                answer = resp.choices[0].message.content or "(no response)"
                break
            except Exception as e:
                # Log and persist the error so we can inspect later
                err_msg = f"{datetime.utcnow().isoformat()} attempt={attempt} timeout={to} error={e}"
                logger.debug(f"Chat call failed (attempt {attempt}): {e}")
                try:
                    self.store.set("last_openai_error", err_msg)
                except Exception:
                    logger.debug("Failed to write last_openai_error to store")
                # If not last attempt, backoff then retry
                if attempt < len(timeouts):
                    backoff = 2 ** attempt
                    time.sleep(backoff)
                    continue
                # All attempts failed: try fallback model (gpt-3.5-turbo) before final fallback
                try:
                    # attempt with secondary model
                    resp2 = self.client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=msgs,
                        temperature=temperature,
                        max_tokens=400,
                    )
                    answer = resp2.choices[0].message.content or ""
                except Exception as e2:
                    # log secondary model failure
                    err2 = f"{datetime.utcnow().isoformat()} fallback error={e2}"
                    try: self.store.set("last_openai_error", err2)
                    except: pass
                    # final friendly fallback
                    answer = "I hit a temporary network delay. I’m still here—could you resend that or rephrase briefly?"
        # Track usage (tokens) per month for simple cost estimates
        try:
            usage = getattr(resp, "usage", None)
            if usage:
                prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                ym = datetime.utcnow().strftime("%Y%m")
                # Increment counters in KV store
                for key, inc in (
                    (f"usage_{ym}_tokens_in", prompt_tokens),
                    (f"usage_{ym}_tokens_out", completion_tokens),
                    (f"usage_{ym}_messages", 1),
                ):
                    try:
                        cur = int(self.store.get(key) or "0")
                    except Exception:
                        cur = 0
                    self.store.set(key, str(cur + inc))
        except Exception as e:
            # Don't break chat if accounting fails
            logger.debug(f"Usage accounting failed: {e}")
        self.store.add_message("user", text)
        self.store.add_message("assistant", answer)
        return answer