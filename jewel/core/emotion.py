import json
import time
from typing import Dict, Any

DEFAULT = {"valence": 0.0, "arousal": 0.0, "tags": []}

class EmotionState:
    """Lightweight emotion state with simple decay.

    - valence: -1 (very negative) .. +1 (very positive)
    - arousal: 0 .. 1 (calm .. excited)
    - tags: list of descriptive words ("happy", "curious")
    """

    def __init__(self, store):
        self.store = store
        self.key = "emotion"

    def _read(self) -> Dict[str, Any]:
        try:
            raw = self.store.get(self.key)
            if not raw:
                return DEFAULT.copy()
            return json.loads(raw)
        except Exception:
            return DEFAULT.copy()

    def _write(self, obj: Dict[str, Any]):
        try:
            self.store.set(self.key, json.dumps(obj))
        except Exception:
            pass

    def get(self) -> Dict[str, Any]:
        s = self._read()
        # optional simple decay toward neutral over time could be added later
        return s

    def trigger(self, delta_valence: float = 0.0, delta_arousal: float = 0.0, tag: str | None = None) -> Dict[str, Any]:
        s = self._read()
        v = float(s.get("valence", 0.0))
        a = float(s.get("arousal", 0.0))
        v = max(-1.0, min(1.0, v + delta_valence))
        a = max(0.0, min(1.0, a + delta_arousal))
        tags = list(s.get("tags", []) or [])
        if tag:
            if tag not in tags:
                tags.append(tag)
        new = {"valence": v, "arousal": a, "tags": tags, "updated_at": int(time.time())}
        self._write(new)
        return new

    def reset(self):
        self._write(DEFAULT.copy())
        return DEFAULT.copy()
