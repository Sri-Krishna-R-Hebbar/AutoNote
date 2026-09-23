"""
AutoNote processing pipeline.

Given an uploaded video and/or audio file, this module runs two independent
content-extraction paths and merges what they find:

  Path 1 - audio:  extract the audio track (ffmpeg) -> transcribe it LOCALLY
                    with faster-whisper (open-source, from Hugging Face) ->
                    a plain transcript of everything that was SAID.
  Path 2 - video:  sample frames from the video (OpenCV) -> for frames that
                    changed meaningfully since the last one, ask a vision
                    language model (Qwen2.5-VL, via OpenRouter) to transcribe
                    any text/handwriting/diagrams visibly WRITTEN on screen
                    (slides, whiteboards, code editors, annotations) - things
                    that may never be spoken aloud.

Either path is optional - whichever input(s) are available determines which
path(s) run; if only one produces content, the other is simply left out.
Both paths' output then feed into note generation using one of Groq's chat
models (smallest model tried first, falling back to progressively larger
ones), and finally into a nicely designed PDF (see pdf_builder.py).

Groq is used only for note-writing (text in, text out) - transcription runs
locally, and frame analysis uses a vision model on OpenRouter, so no single
provider is a dependency for everything.
"""
from __future__ import annotations

import base64
import os
import shutil
import subprocess
import logging

import cv2
import numpy as np
import requests
import imageio_ffmpeg

logger = logging.getLogger("autonote.pipeline")

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Groq text-generation models to try, smallest/cheapest first, falling back to
# progressively larger ones if a model is unavailable or a request fails.
_DEFAULT_GROQ_LLM_CHAIN = [
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
]
_groq_llm_override = os.getenv("GROQ_LLM_MODEL", "").strip()
GROQ_LLM_MODELS = [_groq_llm_override] + _DEFAULT_GROQ_LLM_CHAIN if _groq_llm_override else _DEFAULT_GROQ_LLM_CHAIN

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

# faster-whisper (local, open-source, from Hugging Face). "base" is a good
# balance of speed/accuracy on a CPU-only free-tier host; bump to "small" or
# "medium" if you have more RAM/CPU available.
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

# Transcript characters above which we switch to a map-reduce note pass.
NOTES_SINGLE_PASS_CHAR_LIMIT = int(os.getenv("NOTES_SINGLE_PASS_CHAR_LIMIT", "60000"))

# OpenRouter (https://openrouter.ai) gives access to Qwen's vision-language
# models for reading on-screen text/handwriting out of video frames. This is
# entirely optional - if OPENROUTER_API_KEY isn't set, path 2 (visual
# content) is simply skipped and notes are generated from audio alone, same
# as before. Free-tier ":free" model slugs on OpenRouter rotate over time, so
# this is a fallback chain (first one that works wins) and can be overridden
# with OPENROUTER_VISION_MODEL if these stop being available - check
# https://openrouter.ai/models?modality=text%2Bimage-%3Etext for current ones.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_OPENROUTER_VISION_CHAIN = [
    "qwen/qwen2.5-vl-72b-instruct:free",
    "qwen/qwen2.5-vl-32b-instruct:free",
    "meta-llama/llama-3.2-11b-vision-instruct:free",
]
_openrouter_vision_override = os.getenv("OPENROUTER_VISION_MODEL", "").strip()
OPENROUTER_VISION_MODELS = (
    [_openrouter_vision_override] + _DEFAULT_OPENROUTER_VISION_CHAIN
    if _openrouter_vision_override
    else _DEFAULT_OPENROUTER_VISION_CHAIN
)

# How the video is sampled for path 2 (on-screen content). A candidate frame
# is grabbed every FRAME_SAMPLE_INTERVAL_SECONDS; it's only sent to the
# vision model if it differs enough from the last kept frame (skips long
# static stretches), and at most FRAME_MAX_CALLS frames are ever sent per
# video (evenly thinned if more candidates than that turn up), to keep
# free-tier API usage and processing time bounded on long videos.
FRAME_SAMPLE_INTERVAL_SECONDS = float(os.getenv("FRAME_SAMPLE_INTERVAL_SECONDS", "5"))
FRAME_DIFF_THRESHOLD = float(os.getenv("FRAME_DIFF_THRESHOLD", "12"))
FRAME_MAX_CALLS = int(os.getenv("FRAME_MAX_CALLS", "30"))


class PipelineError(Exception):
    """Raised for any expected/user-facing pipeline failure."""


class NoAudioTrackError(PipelineError):
    """Raised when a video/audio file has no audio track to transcribe.

    Not always fatal - the caller may still have on-screen video content
    (path 2) to fall back on."""


def notes_provider() -> str:
    if GROQ_API_KEY:
        return "groq"
    raise PipelineError("No LLM API key configured. Set GROQ_API_KEY in your environment.")


# --------------------------------------------------------------------------
# ffmpeg helpers
# --------------------------------------------------------------------------
def _ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(cmd: list[str]) -> str:
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    if result.returncode != 0:
        raise PipelineError(
            f"Command failed ({cmd[0]}): {result.stdout[-2000:] if result.stdout else 'unknown error'}"
        )
    return result.stdout or ""


def extract_audio(video_path: str, out_dir: str) -> str:
    """Extract a mono, 16kHz, low-bitrate mp3 track from an uploaded video or
    audio file."""
    os.makedirs(out_dir, exist_ok=True)
    audio_path = os.path.join(out_dir, "source_audio.mp3")
    try:
        _run(
            [
                _ffmpeg_exe(),
                "-y",
                "-i",
                video_path,
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-b:a",
                "48k",
                audio_path,
            ]
        )
    except PipelineError as exc:
        # "-vn" drops the video track, so if the file has no audio track at
        # all (common for video-only downloads from some YouTube downloader
        # sites) ffmpeg ends up with nothing to encode and fails with this
        # exact message.
        if "does not contain any stream" in str(exc):
            raise NoAudioTrackError(
                "This file doesn't have an audio track, so there's nothing to transcribe "
                "from it."
            ) from exc
        raise
    if not os.path.exists(audio_path):
        raise PipelineError("Audio extraction failed: no output produced.")
    return audio_path


def get_video_duration(video_path: str) -> float:
    """Best-effort video duration in seconds, via OpenCV - used as a fallback
    when there's no audio track to derive duration from instead."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0.0
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        return frame_count / fps if fps else 0.0
    finally:
        cap.release()


# --------------------------------------------------------------------------
# On-screen content (video frames -> Qwen vision-language model)
# --------------------------------------------------------------------------
FRAME_VISION_PROMPT = """You are analyzing a single frame from an educational/instructional \
video. Extract ONLY text that is visibly WRITTEN, TYPED, DRAWN, or ANNOTATED on screen - for \
example on a slide, whiteboard, code editor, handwritten note, diagram label, or on-screen \
caption. Preserve structure (equations, bullet points, code, labels) as plain text. Do NOT \
describe people, backgrounds, or the general scene, and do NOT guess at anything not clearly \
legible. If there is no readable on-screen text/writing in this frame, respond with EXACTLY: \
NONE"""


def _encode_frame_jpeg_b64(frame) -> str:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:
        raise PipelineError("Could not encode a video frame for analysis.")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _call_openrouter_vision(image_b64: str, model: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": FRAME_VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            }
        ],
        "temperature": 0.1,
        "max_tokens": 600,
    }
    resp = requests.post(OPENROUTER_CHAT_URL, headers=headers, json=payload, timeout=90)
    if resp.status_code != 200:
        raise PipelineError(
            f"OpenRouter vision error ({resp.status_code}, model={model}): {resp.text[:300]}"
        )
    result = resp.json()
    choices = result.get("choices") or []
    if not choices:
        raise PipelineError(f"OpenRouter vision returned no choices (model={model}).")
    return (choices[0].get("message", {}).get("content") or "").strip()


def _describe_frame(frame) -> str | None:
    """Ask the vision model what's written on this frame. Returns None if
    nothing readable was found (or every fallback model failed)."""
    image_b64 = _encode_frame_jpeg_b64(frame)
    for model in OPENROUTER_VISION_MODELS:
        try:
            text = _call_openrouter_vision(image_b64, model)
        except PipelineError as exc:
            logger.warning("OpenRouter vision model %s failed: %s", model, exc)
            continue
        if not text or text.strip().upper() == "NONE":
            return None
        return text.strip()
    return None


def analyze_video_frames(video_path: str, progress=None) -> list[dict]:
    """Sample frames from the video and extract any on-screen text/handwriting
    via a vision-language model. Returns a list of {"start": seconds, "text":
    str}, sorted by time - empty if OPENROUTER_API_KEY isn't configured, the
    video can't be read, or nothing readable was ever found on screen."""
    if not OPENROUTER_API_KEY:
        logger.info("OPENROUTER_API_KEY not set - skipping on-screen video content analysis.")
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning("Could not open video for frame analysis: %s", video_path)
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(fps * FRAME_SAMPLE_INTERVAL_SECONDS))

    candidates: list[tuple[float, "np.ndarray", float]] = []
    prev_small = None
    idx = 0
    try:
        while True:
            ok = cap.grab()
            if not ok:
                break
            if idx % step == 0:
                ok, frame = cap.retrieve()
                if ok:
                    small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (64, 36))
                    score = 999.0
                    if prev_small is not None:
                        score = float(np.mean(cv2.absdiff(small, prev_small)))
                    if prev_small is None or score > FRAME_DIFF_THRESHOLD:
                        candidates.append((idx / fps, frame, score))
                    prev_small = small
            idx += 1
    finally:
        cap.release()

    if not candidates:
        return []

    if len(candidates) > FRAME_MAX_CALLS:
        # Keep the most visually different frames (most likely to be new
        # content, e.g. a fresh slide), then put them back in time order.
        candidates.sort(key=lambda c: c[2], reverse=True)
        candidates = candidates[:FRAME_MAX_CALLS]
        candidates.sort(key=lambda c: c[0])

    logger.info("Analyzing %d candidate video frame(s) for on-screen content", len(candidates))

    results: list[dict] = []
    for i, (timestamp, frame, _score) in enumerate(candidates):
        if progress:
            progress(f"Analyzing video frames ({i + 1}/{len(candidates)})")
        text = _describe_frame(frame)
        if text:
            results.append({"start": timestamp, "text": text})
    return results


# --------------------------------------------------------------------------
# Transcription (local faster-whisper)
# --------------------------------------------------------------------------
_WHISPER_MODEL = None


def _get_whisper_model():
    """Lazily load (and cache) the local Whisper model - it's only downloaded/
    loaded once per process, not once per request."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel

        logger.info(
            "Loading local Whisper model '%s' (compute_type=%s)...",
            WHISPER_MODEL_SIZE,
            WHISPER_COMPUTE_TYPE,
        )
        _WHISPER_MODEL = WhisperModel(
            WHISPER_MODEL_SIZE, device="cpu", compute_type=WHISPER_COMPUTE_TYPE
        )
    return _WHISPER_MODEL


def transcribe_audio(audio_path: str, progress=None) -> tuple[str, list[dict], float]:
    """Transcribe audio locally. Returns (full_text, segments, duration_seconds),
    where each segment is {"start": float, "end": float, "text": str} - used
    later to line up notes sections with the moment they were discussed."""
    try:
        model = _get_whisper_model()
    except Exception as exc:
        raise PipelineError(f"Could not load the local transcription model: {exc}") from exc

    try:
        segments_iter, info = model.transcribe(audio_path, beam_size=1, vad_filter=True)
    except Exception as exc:
        raise PipelineError(f"Transcription failed: {exc}") from exc

    duration = float(info.duration or 0.0)
    segments: list[dict] = []
    text_parts: list[str] = []
    for seg in segments_iter:
        text = seg.text.strip()
        if not text:
            continue
        segments.append({"start": float(seg.start), "end": float(seg.end), "text": text})
        text_parts.append(text)
        if progress and duration:
            pct = min(99, int((seg.end / duration) * 100))
            progress(f"Transcribing audio... {pct}%")

    full_text = " ".join(text_parts).strip()
    return full_text, segments, duration


# --------------------------------------------------------------------------
# Notes generation (Groq chat models)
# --------------------------------------------------------------------------
NOTES_INSTRUCTIONS = """You are an expert note-taker who turns raw video/lecture material into
excellent, detailed study notes. The source material below has up to two parts: SPOKEN CONTENT
(an audio transcript of everything said) and ON-SCREEN CONTENT (text/handwriting/diagrams read
directly off video frames - slides, whiteboards, code editors, annotations - each with an
approximate timestamp). ON-SCREEN CONTENT often includes material that was NEVER spoken aloud, so
treat it as equally important, not just supporting color - a presenter often writes things down
without ever reading them out. Produce thorough, well-organized markdown notes following these
rules:

1. Start with a single `# Title` line summarizing the subject (no "Notes on" prefix).
2. Write a short 2-4 sentence "Overview" section right after the title.
3. Organize the rest of the content into logical `## Section` headings (and `### Subsection`
   headings where useful) that follow the natural structure of the material - do not just say
   "Part 1, Part 2".
4. Merge SPOKEN CONTENT and ON-SCREEN CONTENT into one cohesive narrative wherever they cover the
   same topic; where ON-SCREEN CONTENT introduces something not mentioned in speech (e.g. a
   formula written but not read aloud, code shown but not explained line-by-line), include it in
   the notes anyway, in the section where it appears chronologically.
5. Use bullet points (`- `) for lists of facts, steps, or examples. Use numbered lists (`1. `)
   only for sequential/ordered steps.
6. Bold (`**term**`) key terms, names, and important numbers the first time they appear.
7. Put important definitions, formulas, or key takeaways inside blockquotes (`> `) so they stand
   out visually.
8. Include concrete examples, analogies, and any numbers/formulas/code mentioned - do not drop
   detail, this should be a DETAILED and COMPREHENSIVE set of notes, not a short summary.
9. Keep topics in the order they were discussed/shown.
10. End with a `## Key Takeaways` section (5-10 bullet points) and, if it makes sense for the
    content, a `## Glossary` section defining important terms.
11. Ignore filler speech, false starts, "um"s, and unrelated small talk.
12. Output ONLY the markdown notes - no commentary about what you are doing, no code fences
    wrapping the whole output.

Source material:
{transcript}
"""

MAP_INSTRUCTIONS = """You are an expert note-taker. Below is one part ({part} of {total}) of
longer video source material (it may include a SPOKEN CONTENT transcript, ON-SCREEN CONTENT read
off video frames with timestamps, or both - on-screen material can include things never spoken
aloud, so treat it as equally important). Write detailed markdown notes for ONLY this part, using
`## ` headings for each topic covered, bullet points for details, **bold** for key terms, and
blockquotes (`> `) for important definitions or takeaways. Do not add an overall title or
introduction - just the notes for this part, picking up wherever the topic starts. Do not mention
"this part" or "this transcript" in the output.

Source material part:
{transcript}
"""

REDUCE_INSTRUCTIONS = """You are an expert editor. Below are draft notes written separately for
consecutive parts of the same video transcript. Merge and polish them into one cohesive, detailed
markdown document:

1. Start with a single `# Title` line for the whole video, followed by a short "Overview" section.
2. Merge/reorganize the section headings (`## `, `### `) so the flow makes sense and there is no
   redundant repetition between parts.
3. Preserve ALL of the factual detail, examples, definitions, and blockquotes from the drafts -
   do not shorten or summarize them away.
4. End with a `## Key Takeaways` section and a `## Glossary` section if useful.
5. Output ONLY the final markdown notes, nothing else.

Draft notes:
{drafts}
"""


def _call_groq_chat(prompt: str, model: str) -> str:
    if not GROQ_API_KEY:
        raise PipelineError("Groq API key not configured.")
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "max_tokens": 8192,
    }
    resp = requests.post(GROQ_CHAT_URL, headers=headers, json=payload, timeout=180)
    if resp.status_code != 200:
        raise PipelineError(f"Groq error ({resp.status_code}, model={model}): {resp.text[:500]}")
    result = resp.json()
    choices = result.get("choices") or []
    if not choices:
        raise PipelineError(f"Groq returned no choices (model={model}).")
    text = choices[0].get("message", {}).get("content", "").strip()
    if not text:
        raise PipelineError(f"Groq returned an empty response (model={model}).")
    return text


def _generate(prompt: str) -> str:
    """Call Groq's chat models, smallest/cheapest model first, falling back to
    progressively larger ones if a model is unavailable or a request fails."""
    if not GROQ_API_KEY:
        raise PipelineError("Note generation failed. GROQ_API_KEY is not configured.")

    errors = []
    for model in GROQ_LLM_MODELS:
        try:
            return _call_groq_chat(prompt, model)
        except PipelineError as exc:
            logger.warning("Groq model %s failed: %s", model, exc)
            errors.append(str(exc))
    raise PipelineError("Note generation failed. " + " | ".join(errors))


def _chunk_transcript(transcript: str, max_chars: int) -> list[str]:
    words = transcript.split()
    chunks, current, current_len = [], [], 0
    for word in words:
        current.append(word)
        current_len += len(word) + 1
        if current_len >= max_chars:
            chunks.append(" ".join(current))
            current, current_len = [], 0
    if current:
        chunks.append(" ".join(current))
    return chunks


def _format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def _format_source_text(transcript: str | None, visual_notes: list[dict] | None) -> str:
    """Combine path 1 (audio transcript) and path 2 (on-screen content) into
    one labeled block of text for the notes prompt."""
    transcript = (transcript or "").strip()
    sections = [
        "=== SPOKEN CONTENT (audio transcript) ===\n"
        + (transcript if transcript else "[No audio track / speech detected in this upload.]")
    ]

    if visual_notes:
        lines = [f"[{_format_timestamp(n['start'])}] {n['text']}" for n in visual_notes]
        sections.append(
            "=== ON-SCREEN CONTENT (read from video frames - slides, whiteboard, handwriting, "
            "code, diagrams; may include material that was NOT spoken aloud) ===\n"
            + "\n\n".join(lines)
        )
    else:
        sections.append(
            "=== ON-SCREEN CONTENT ===\n[No readable on-screen text/writing was detected.]"
        )

    return "\n\n".join(sections)


def generate_notes(
    transcript: str | None, visual_notes: list[dict] | None = None, progress=None
) -> str:
    if not (transcript and transcript.strip()) and not visual_notes:
        raise PipelineError(
            "Nothing to summarize - no speech was transcribed and no on-screen content was found."
        )

    source_text = _format_source_text(transcript, visual_notes)

    if len(source_text) <= NOTES_SINGLE_PASS_CHAR_LIMIT:
        if progress:
            progress("Generating detailed notes")
        return _generate(NOTES_INSTRUCTIONS.format(transcript=source_text))

    # Long source material: map-reduce so we stay within model context/output limits.
    parts = _chunk_transcript(source_text, NOTES_SINGLE_PASS_CHAR_LIMIT)
    drafts = []
    for idx, part in enumerate(parts, start=1):
        if progress:
            progress(f"Generating notes (part {idx}/{len(parts)})")
        drafts.append(
            _generate(
                MAP_INSTRUCTIONS.format(part=idx, total=len(parts), transcript=part)
            )
        )

    if progress:
        progress("Merging notes into final document")
    combined = "\n\n---\n\n".join(drafts)
    return _generate(REDUCE_INSTRUCTIONS.format(drafts=combined))


def cleanup_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)
