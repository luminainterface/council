import re

# Regex catches common template / placeholder tokens (case-insensitive, multiline)
_PAT = re.compile(
    r"\b(template|todo|unsupported|custom_function|<<<.*?>>>|\{\{.*?\}\})\b",
    flags=re.I | re.S | re.M,
)

def is_stub(text: str) -> bool:
    """Return True if the generation contains boiler-plate or unsupported tags."""
    return bool(_PAT.search(text))

def scrub(text: str, score: float | None) -> float:
    """
    If `text` is a stub, force confidence → 0.0.
    Otherwise return the original score (or None if router sets it later).
    """
    return 0.0 if is_stub(text) else (score if score is not None else None) 