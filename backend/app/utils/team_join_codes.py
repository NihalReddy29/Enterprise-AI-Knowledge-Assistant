"""Helpers for human-readable team join codes."""

import secrets
import string

from sqlalchemy.orm import Session

from app.models.team import Team

# Exclude ambiguous characters (0/O, 1/I/L).
_JOIN_ALPHABET = "".join(
    ch for ch in (string.ascii_uppercase + string.digits) if ch not in "O0I1L"
)


def normalize_join_code(code: str) -> str:
    """Normalize user input to canonical XXXX-XXXX form."""
    clean = code.strip().upper().replace("-", "").replace(" ", "")
    if len(clean) != 8 or not all(ch in _JOIN_ALPHABET for ch in clean):
        raise ValueError("Join code must be 8 characters (format: XXXX-XXXX)")
    return f"{clean[:4]}-{clean[4:]}"


def generate_join_code(db: Session) -> str:
    """Generate a unique join code for a team."""
    for _ in range(32):
        raw = "".join(secrets.choice(_JOIN_ALPHABET) for _ in range(8))
        code = f"{raw[:4]}-{raw[4:]}"
        exists = db.query(Team.id).filter(Team.join_code == code).first()
        if not exists:
            return code
    raise RuntimeError("Could not generate a unique team join code")
