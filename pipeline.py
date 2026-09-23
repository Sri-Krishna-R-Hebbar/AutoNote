"""
AutoNote processing pipeline.

Given an uploaded video file, this module:
  1. Extracts the audio track (fast, via a bundled static ffmpeg binary).
  2. Transcribes the audio LOCALLY using faster-whisper (an open-source,
     CTranslate2-optimized reimplementation of OpenAI's Whisper, pulled from
     Hugging Face) - no external transcription API/key needed.
  3. Turns the timed transcript into detailed, well-structured markdown notes
     using one of Groq's chat models (smallest model tried first, falling
     back to progressively larger ones).
  4. Renders those notes into a nicely designed PDF (see pdf_builder.py).

Groq is used exactly once in this pipeline now (note-writing) - transcription
runs locally on CPU, so there's no double dependency on a single provider.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import logging

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


class PipelineError(Exception):
    """Raised for any expected/user-facing pipeline failure."""


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
    """Extract a mono, 16kHz, low-bitrate mp3 track from an uploaded video."""
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
        # exact message - give a clear explanation instead of a raw ffmpeg dump.
        if "does not contain any stream" in str(exc):
            raise PipelineError(
                "This video file doesn't have an audio track, so there's nothing to "
                "transcribe. If you downloaded it from a YouTube downloader site, make "
                "sure you pick the option that includes audio (not a video-only stream) "
                "and try uploading it again."
            ) from exc
        raise
    if not os.path.exists(audio_path):
        raise PipelineError("Audio extraction failed: no output produced.")
    return audio_path


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
NOTES_INSTRUCTIONS = """You are an expert note-taker who turns raw video/lecture transcripts into
excellent, detailed study notes. Given the transcript below, produce thorough, well-organized
markdown notes following these rules:

1. Start with a single `# Title` line summarizing the video's subject (no "Notes on" prefix).
2. Write a short 2-4 sentence "Overview" section right after the title.
3. Organize the rest of the content into logical `## Section` headings (and `### Subsection`
   headings where useful) that follow the natural structure of the talk - do not just say
   "Part 1, Part 2".
4. Use bullet points (`- `) for lists of facts, steps, or examples. Use numbered lists (`1. `)
   only for sequential/ordered steps.
5. Bold (`**term**`) key terms, names, and important numbers the first time they appear.
6. Put important definitions, formulas, or key takeaways inside blockquotes (`> `) so they stand
   out visually.
7. Include concrete examples, analogies, and any numbers/formulas/code mentioned - do not drop
   detail, this should be a DETAILED and COMPREHENSIVE set of notes, not a short summary.
8. If the transcript covers a sequence of topics, keep them in the order they were discussed.
9. End with a `## Key Takeaways` section (5-10 bullet points) and, if it makes sense for the
   content, a `## Glossary` section defining important terms.
10. Ignore filler speech, false starts, "um"s, and unrelated small talk.
11. Output ONLY the markdown notes - no commentary about what you are doing, no code fences
    wrapping the whole output.

Transcript:
{transcript}
"""

MAP_INSTRUCTIONS = """You are an expert note-taker. Below is one part ({part} of {total}) of a
longer video transcript. Write detailed markdown notes for ONLY this part, using `## ` headings
for each topic covered, bullet points for details, **bold** for key terms, and blockquotes (`> `)
for important definitions or takeaways. Do not add an overall title or introduction - just the
notes for this part, picking up wherever the topic starts. Do not mention "this part" or "this
transcript" in the output.

Transcript part:
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


def generate_notes(transcript: str, progress=None) -> str:
    transcript = transcript.strip()
    if not transcript:
        raise PipelineError("The transcript came back empty - nothing to summarize.")

    if len(transcript) <= NOTES_SINGLE_PASS_CHAR_LIMIT:
        if progress:
            progress("Generating detailed notes")
        return _generate(NOTES_INSTRUCTIONS.format(transcript=transcript))

    # Long transcript: map-reduce so we stay within model context/output limits.
    parts = _chunk_transcript(transcript, NOTES_SINGLE_PASS_CHAR_LIMIT)
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
