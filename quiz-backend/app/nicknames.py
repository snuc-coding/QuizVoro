"""
nicknames.py — Nickname rules for players (Developer 2).

Names are shown on the projector, so they are cleaned and checked before anyone
joins. Uniqueness within a game is checked by participant_service (and enforced
by a database constraint), not here.

The blocked list lives in blocked_words.txt next to this file:
    word    blocks the name when it appears as a separate word, after undoing letter
            swaps ("Big Dick", "BigDick", "b1tch" are caught; "Dickson" is not)
    *word   blocks it anywhere inside the name. Only for words that never occur inside
            real names: "*ass" would block Hassan and Bassam.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

MAX_NICKNAME_LENGTH = 16
BLOCKED_FILE = Path(__file__).with_name("blocked_words.txt")

# Undo common letter swaps before matching: b1tch -> bitch, $h!t -> shit.
_LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b",
     "@": "a", "$": "s", "!": "i", "|": "i"}
)
_SPACES = re.compile(r"\s+")
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")
_NOT_LETTERS = re.compile(r"[^a-z]+")


class NicknameRejected(ValueError):
    """The message is safe to show to the player."""


def clean_nickname(raw: str) -> str:
    """Normalise full-width/look-alike forms, drop invisible characters, collapse spaces."""
    text = unicodedata.normalize("NFKC", raw)
    # Category C* = control, format (zero-width space, right-to-left override), private use.
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("C"))
    return _SPACES.sub(" ", text).strip()


def nickname_key(nickname: str) -> str:
    """The form used for uniqueness: 'Rathi', 'RATHI' and ' rathi ' are the same name."""
    return clean_nickname(nickname).casefold()


def _plain(text: str) -> str:
    return text.casefold().translate(_LEET)


def _squash(text: str) -> str:
    return _NOT_LETTERS.sub("", _plain(text))


def _words(text: str) -> set[str]:
    return {w for w in _NOT_LETTERS.split(_plain(_CAMEL.sub(" ", text))) if w}


@lru_cache(maxsize=1)
def _blocked() -> tuple[frozenset[str], tuple[str, ...]]:
    words: set[str] = set()
    fragments: list[str] = []
    if BLOCKED_FILE.is_file():
        for line in BLOCKED_FILE.read_text(encoding="utf-8").splitlines():
            entry = line.strip()
            if not entry or entry.startswith("#"):
                continue
            if entry.startswith("*"):
                if fragment := _squash(entry[1:]):
                    fragments.append(fragment)
            elif word := _squash(entry):
                words.add(word)
    return frozenset(words), tuple(fragments)


def check_nickname(raw: str) -> str:
    """Return the cleaned nickname, or raise NicknameRejected with a friendly message."""
    name = clean_nickname(raw)
    if not name:
        raise NicknameRejected("Enter a nickname.")
    if len(name) > MAX_NICKNAME_LENGTH:
        raise NicknameRejected(f"Keep your nickname to {MAX_NICKNAME_LENGTH} characters.")
    if not any(ch.isalnum() for ch in name):
        raise NicknameRejected("Use at least one letter or number.")
    words, fragments = _blocked()
    if words & _words(name) or any(f in _squash(name) for f in fragments):
        raise NicknameRejected("Please pick a different nickname.")
    return name
