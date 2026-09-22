"""
Turns AI-generated markdown notes + the transcript's timed segments into:

  - sections: every H2/H3 heading with a best-effort video timestamp, so the
    frontend can highlight/scroll the notes panel in sync with playback.
  - concept_slides: one swipeable flashcard per H2 section (title + key
    bullets + timestamp), for the "Concept Slides" carousel.

No extra AI calls are needed for either - both are derived purely from the
markdown structure and simple word-overlap matching against the transcript.
"""
from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE)
_QUOTE_RE = re.compile(r"^>\s?(.+)$", re.MULTILINE)
_INLINE_MARKUP_RE = re.compile(r"[*_`]")

_STOPWORDS = {
    "the", "and", "that", "with", "this", "from", "have", "were", "was",
    "for", "its", "into", "about", "which", "their", "also", "using",
    "used", "use", "your", "these", "those", "will", "where", "when",
    "then", "than", "such", "some", "more", "most", "each", "other",
}


def _significant_words(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    return {w for w in words if len(w) > 4 and w not in _STOPWORDS}


def _extract_headings(markdown_text: str) -> list[dict]:
    matches = list(_HEADING_RE.finditer(markdown_text))
    headings = []
    for i, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_text)
        headings.append(
            {
                "level": len(m.group(1)),
                "title": m.group(2).strip(),
                "body_start": body_start,
                "body_end": body_end,
            }
        )
    return headings


def _assign_timestamps(headings: list[dict], segments: list[dict]) -> list[float | None]:
    """For each heading, search forward (from where the last heading matched)
    for the first transcript segment sharing a significant word with the
    heading title. This keeps timestamps monotonically increasing and re-anchors
    to the actual audio instead of just guessing from text position. Gaps
    where no match was found are filled in by interpolating between the
    nearest matched neighbours."""
    if not segments:
        return [None] * len(headings)

    timestamps: list[float | None] = [None] * len(headings)
    cursor = 0
    for i, heading in enumerate(headings):
        words = _significant_words(heading["title"])
        if not words:
            continue
        for j in range(cursor, len(segments)):
            if words & _significant_words(segments[j]["text"]):
                timestamps[i] = segments[j]["start"]
                cursor = j
                break

    last_known, last_idx = 0.0, -1
    for i, ts in enumerate(timestamps):
        if ts is None:
            continue
        if last_idx == -1:
            for k in range(i):
                timestamps[k] = 0.0
        else:
            gap = i - last_idx
            for k in range(last_idx + 1, i):
                frac = (k - last_idx) / gap
                timestamps[k] = last_known + frac * (ts - last_known)
        last_known, last_idx = ts, i

    if last_idx == -1:
        return [0.0] * len(headings)
    for k in range(last_idx + 1, len(headings)):
        timestamps[k] = last_known
    return timestamps


def _clean(text: str) -> str:
    return _INLINE_MARKUP_RE.sub("", text).strip()


def _extract_bullets(body_text: str, limit: int = 5) -> list[str]:
    bullets = [_clean(b) for b in _BULLET_RE.findall(body_text)]
    if bullets:
        return bullets[:limit]
    quotes = [_clean(q) for q in _QUOTE_RE.findall(body_text)]
    if quotes:
        return quotes[:limit]
    sentences = re.split(r"(?<=[.!?])\s+", body_text.strip())
    return [s.strip() for s in sentences[:3] if s.strip()]


def build_sections_and_slides(
    markdown_text: str, segments: list[dict]
) -> tuple[list[dict], list[dict]]:
    headings = _extract_headings(markdown_text)
    timestamps = _assign_timestamps(headings, segments)

    sections: list[dict] = []
    slides: list[dict] = []
    for idx, (heading, ts) in enumerate(zip(headings, timestamps)):
        section_id = f"sec-{idx + 1}"
        rounded_ts = round(ts, 1) if ts is not None else None
        sections.append(
            {
                "id": section_id,
                "level": heading["level"],
                "title": heading["title"],
                "timestamp": rounded_ts,
            }
        )
        if heading["level"] == 2:
            body = markdown_text[heading["body_start"]:heading["body_end"]]
            bullets = _extract_bullets(body)
            if bullets:
                slides.append(
                    {
                        "id": section_id,
                        "title": heading["title"],
                        "bullets": bullets,
                        "timestamp": rounded_ts,
                    }
                )

    return sections, slides
