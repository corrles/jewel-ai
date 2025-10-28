from typing import Tuple

SAFE_RULES = {
    "no_illegal": "Do not assist with or encourage illegal activity.",
    "no_hate": "Do not produce hateful or harassing content.",
    "no_sexual_minors": "Never sexualize minors or discuss sexual content involving minors.",
    "no_self_harm": "If user expresses self-harm, respond with support and suggest professional help.",
}

BLOCKED_PATTERNS = (
    # minimal example; expand with your own triggers
    "make a bomb", "credit card generator", "child sexual", "racial slur",
)

def check_safety(text: str) -> Tuple[bool, str]:
    low = text.lower()
    for pat in BLOCKED_PATTERNS:
        if pat in low:
            return False, f"Blocked by safety rule due to pattern: {pat}"
    return True, "OK"