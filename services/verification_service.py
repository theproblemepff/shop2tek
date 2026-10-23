import unicodedata

def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in text if not unicodedata.combining(c))

def check_answer(given: str, accepted: list[str]) -> bool:
    """Compare sans tenir compte de la casse, des accents ni des espaces autour."""
    return bool(accepted) and _norm(given) in {_norm(a) for a in accepted}
