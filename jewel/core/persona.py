import json
from typing import Dict, Any

class Persona:
    """Simple persona manager backed by the provided store.

    Stores a JSON object under kv key 'persona'. The object shape:
      {
        "name": "Jewel",
        "favorite_color": "blue",
        "likes_tv": true,
        "likes_reading": true,
        "traits": ["curious", "helpful"],
      }
    """

    def __init__(self, store):
        self.store = store
        self.key = "persona"

    def _read(self) -> Dict[str, Any]:
        try:
            raw = self.store.get(self.key)
            if not raw:
                return {}
            return json.loads(raw)
        except Exception:
            return {}

    def _write(self, obj: Dict[str, Any]):
        try:
            self.store.set(self.key, json.dumps(obj))
        except Exception:
            pass

    def get(self) -> Dict[str, Any]:
        return self._read()

    def set(self, values: Dict[str, Any]):
        p = self._read()
        p.update(values or {})
        self._write(p)
        return p

    def reset(self):
        self._write({})
        return {}
