"""Text normalization and fingerprints used for duplicate detection."""

from __future__ import annotations

import hashlib
import re
import unicodedata


APOSTROPHES = "'\u2018\u2019\u201b\u2032\u02bc\uff07"


def normalize_text(text: str) -> str:
    """Produce a stable representation of text for duplicate detection."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate(str.maketrans({character: "'" for character in APOSTROPHES}))
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )
    text = re.sub(r"\s+", " ", text.casefold()).strip()
    # A space before the final punctuation of a natural-language question is
    # typographic noise. Other punctuation is kept because it can be part of
    # technical identifiers, operators, or syntax.
    return re.sub(r"\s+([?!])$", r"\1", text)


def fingerprint(text: str) -> str:
    """Return the SHA-256 fingerprint of normalized text."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def question_fingerprint(question: str) -> str:
    """Return the fingerprint derived from a question only."""
    return fingerprint(question)


def content_fingerprint(question: str, answer: str) -> str:
    """Return the fingerprint derived from a question and its answer."""
    content = f"{normalize_text(question)}\x1f{normalize_text(answer)}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
