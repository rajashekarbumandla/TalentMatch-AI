"""
Resume / JD text preprocessing.

Goal: make text from different PDF and Word layouts look the same, *without*
destroying technical terms. We deliberately do NOT lowercase, remove punctuation
or remove stop-words, because "C++", "C#", ".NET", "Node.js", "CI/CD" and the
difference between "Java" and "JavaScript" all depend on case and symbols.

What clean_text() does:
- Unicode NFKC normalisation (ligatures like "ﬁ" -> "fi", non-breaking spaces -> spaces)
- removes invisible characters (zero-width spaces, soft hyphens, control characters)
- en/em dashes -> "-"  (so "2019–2021" and "2019 - 2021" look the same)
- bullet symbols at the start of a line -> "- "; bullets inside a line -> " | "
- collapses repeated spaces and blank lines
"""
import re
import unicodedata

# Symbols commonly used as bullets in resumes (including Word's private-use bullet glyphs).
BULLET_CHARS = "•●▪■□◦○◆◇►▸▹‣⁃∙➢➣➤✓✔❖➔→"
_LEADING_BULLET = re.compile(rf"^\s*(?:[{re.escape(BULLET_CHARS)}*]|-(?=\s))\s*")
_INLINE_BULLET = re.compile(rf"\s*[{re.escape(BULLET_CHARS)}]\s*")
_DASHES = re.compile("[‐‑‒–—―−]")
_INVISIBLE = re.compile("[​‌‍⁠﻿­]")
_SPACES = re.compile(r"[ \t\f\v]+")
_MANY_BLANK_LINES = re.compile(r"\n{3,}")


def _is_private_use(char: str) -> bool:
    return unicodedata.category(char) == "Co"


def clean_line(line: str) -> str:
    # Word "Symbol" font bullets arrive as private-use characters (e.g. U+F0B7).
    line = "".join("•" if _is_private_use(ch) else ch for ch in line)
    line = _SPACES.sub(" ", line).strip()
    if not line:
        return ""
    if _LEADING_BULLET.match(line):
        line = "- " + _LEADING_BULLET.sub("", line, count=1)
    line = _INLINE_BULLET.sub(" | ", line)
    return line.strip(" |") if line != "- " else ""


def clean_text(text: str | None) -> str:
    """Normalise raw extracted text while preserving technical terms and line structure."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _INVISIBLE.sub("", text)
    text = _DASHES.sub("-", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Drop remaining control characters except newlines and tabs.
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch) != "Cc")

    lines = [clean_line(line) for line in text.split("\n")]
    text = "\n".join(lines)
    return _MANY_BLANK_LINES.sub("\n\n", text).strip()
