"""
AutoNote processing pipeline.

Given a video (uploaded file or a video URL), this module:
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
import re
import glob
import shutil
import subprocess
import tempfile
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
# ffmpeg / yt-dlp helpers
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


_YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def extract_youtube_id(url: str) -> str | None:
    """Best-effort YouTube video id extraction, for embedding the official
    player client-side. Returns None for non-YouTube URLs."""
    match = _YOUTUBE_ID_RE.search(url)
    return match.group(1) if match else None


# Optional: cookies from a real logged-in YouTube session, used to get past
# "Sign in to confirm you're not a bot" challenges that cloud/datacenter IPs
# (Render, AWS, etc.) increasingly trigger. Nothing breaks if these aren't
# set - YouTube downloads just stay best-effort without them.
#   YTDLP_COOKIES_FILE  - path to a Netscape-format cookies.txt file
#   YTDLP_COOKIES       - the raw contents of that file, e.g. pasted into a
#                          Render environment variable (written to a temp
#                          file on first use)
_YTDLP_COOKIES_FILE = os.getenv("YTDLP_COOKIES_FILE", "").strip()
_YTDLP_COOKIES_RAW = os.getenv("YTDLP_COOKIES", "").strip()
_resolved_cookies_path: str | None = None


def _cookies_file_path() -> str | None:
    global _resolved_cookies_path
    if _resolved_cookies_path:
        return _resolved_cookies_path

    if _YTDLP_COOKIES_FILE and os.path.exists(_YTDLP_COOKIES_FILE):
        _resolved_cookies_path = _YTDLP_COOKIES_FILE
        logger.info("Using YTDLP_COOKIES_FILE at %s", _YTDLP_COOKIES_FILE)
        return _resolved_cookies_path

    if _YTDLP_COOKIES_RAW:
        content = _YTDLP_COOKIES_RAW.replace("\r\n", "\n")
        # http.cookiejar's Netscape loader silently rejects files that don't
        # start with this exact header - a common gotcha when copy-pasting a
        # cookies.txt export into an env var, so we patch it in if missing.
        if not content.lstrip().startswith("# Netscape HTTP Cookie File") and not content.lstrip().startswith(
            "# HTTP Cookie File"
        ):
            content = "# Netscape HTTP Cookie File\n" + content
        cookie_lines = [
            ln for ln in content.splitlines() if ln.strip() and not ln.strip().startswith("#")
        ]
        path = os.path.join(tempfile.gettempdir(), "autonote_ytdlp_cookies.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        _resolved_cookies_path = path
        logger.info(
            "Loaded YTDLP_COOKIES from environment: %d cookie line(s) written to %s",
            len(cookie_lines),
            path,
        )
        if len(cookie_lines) == 0:
            logger.warning(
                "YTDLP_COOKIES was set but no cookie lines were parsed from it - check the "
                "value was pasted in as tab-separated Netscape cookies.txt format."
            )
        return _resolved_cookies_path

    return None


# Optional: a bgutil-ytdlp-pot-provider HTTP server, used to generate the
# "proof of origin" token YouTube increasingly requires alongside cookies to
# get past "Sign in to confirm you're not a bot". Deployed as a separate
# Render service (see render.yaml) so it doesn't share RAM/CPU with this
# app's Whisper transcription; BGUTIL_POT_HOST is auto-wired to that
# service's hostname by Render. BGUTIL_POT_BASE_URL can be set instead for a
# full URL override (e.g. when running the provider locally for testing).
_BGUTIL_POT_HOST = os.getenv("BGUTIL_POT_HOST", "").strip()
_BGUTIL_POT_BASE_URL = os.getenv("BGUTIL_POT_BASE_URL", "").strip() or (
    # Render's fromService/property:host gives the bare internal hostname for
    # its private network (e.g. "autonote-pot"), which is plain HTTP only -
    # not HTTPS - and isn't paired with a port. The pot-provider image always
    # listens on 4416 (it doesn't read $PORT), so that has to be added here.
    f"http://{_BGUTIL_POT_HOST}:4416" if _BGUTIL_POT_HOST else ""
)


class _YtdlpLogger:
    """Routes yt-dlp's own internal messages into our logger, so things like
    whether the PO token provider was actually reached show up in server
    logs even though we keep yt-dlp's own stdout ("quiet") suppressed."""

    def _emit(self, msg):
        logger.info("yt-dlp: %s", msg)

    debug = info = warning = error = _emit


def download_youtube_audio(url: str, out_dir: str) -> tuple[str, str]:
    """Download only the audio track of a YouTube (or other yt-dlp supported) URL.

    We only ever need the audio server-side - if it's a YouTube link the
    browser plays the original video directly via the YouTube embed, so we
    never have to download (or store) the full video file for that case.

    Returns (mp3_path, video_title).
    """
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover
        raise PipelineError("yt-dlp is not installed on the server.") from exc

    os.makedirs(out_dir, exist_ok=True)
    out_template = os.path.join(out_dir, "source_audio.%(ext)s")
    cookies_path = _cookies_file_path()

    def base_opts() -> dict:
        opts = {
            "format": "bestaudio/best",
            "outtmpl": out_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "verbose": True,
            "logger": _YtdlpLogger(),
            "ffmpeg_location": _ffmpeg_exe(),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "64",
                }
            ],
        }
        if cookies_path:
            opts["cookiefile"] = cookies_path
        if _BGUTIL_POT_BASE_URL:
            opts["extractor_args"] = {
                "youtubepot-bgutilhttp": {"base_url": [_BGUTIL_POT_BASE_URL]}
            }
        return opts

    # Cloud/datacenter IPs (Render, AWS, etc.) frequently get blocked by
    # YouTube's default "web" extraction path, or hit a "confirm you're not a
    # bot" wall - cookies (if configured) and a PO token provider (if
    # configured, see BGUTIL_POT_BASE_URL above) get past that.
    #
    # Separately, YouTube has been rolling out "SABR-only" streaming that
    # strips direct download URLs from most formats. As of testing this
    # against the live site, the "web"/"ios"/"mweb" clients currently return
    # NO downloadable formats at all under SABR, while "android" still
    # exposes one legacy progressive (video+audio combined) format that
    # survives it - so android goes first regardless of cookies/POT, with the
    # rest kept only as a fallback in case that changes again later.
    player_client_attempts = [
        ["android"],
        ["android", "web"],
        ["ios"],
        ["mweb"],
        ["tv"],
        ["web"],
        None,  # yt-dlp's default behaviour, as a last resort
    ]

    logger.info(
        "YouTube download starting for %s (cookies=%s, pot_provider=%s, %d client attempt(s) queued)",
        url,
        "yes" if cookies_path else "no",
        "yes" if _BGUTIL_POT_BASE_URL else "no",
        len(player_client_attempts),
    )

    info = None
    errors = []
    for clients in player_client_attempts:
        label = "+".join(clients) if clients else "default"
        opts = base_opts()
        if clients:
            # merge, don't overwrite - base_opts() may already have set
            # youtubepot-bgutilhttp's base_url here, and clobbering the whole
            # dict would silently drop the PO token provider config.
            opts.setdefault("extractor_args", {})["youtube"] = {"player_client": clients}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            logger.info("YouTube download succeeded using client(s): %s", label)
            break
        except Exception as exc:
            logger.warning("YouTube client attempt '%s' failed: %s", label, exc)
            errors.append(f"[{label}] {exc}")
            continue

    if info is None:
        hint = ""
        if not cookies_path and any("sign in" in e.lower() or "bot" in e.lower() for e in errors):
            hint = (
                " (YouTube is asking for a logged-in session on this server - set the "
                "YTDLP_COOKIES environment variable with exported browser cookies to fix this "
                "reliably.)"
            )
        logger.warning("All YouTube client attempts failed for %s:\n%s", url, "\n".join(errors))
        raise PipelineError(
            "Could not download that video after trying "
            f"{len(player_client_attempts)} methods: "
            + (errors[-1] if errors else "unknown error")
            + hint
        )

    title = (info or {}).get("title") or "Video"
    mp3_path = os.path.join(out_dir, "source_audio.mp3")
    if not os.path.exists(mp3_path):
        # yt-dlp may have picked a slightly different final filename
        candidates = glob.glob(os.path.join(out_dir, "source_audio.*"))
        if not candidates:
            raise PipelineError("Audio download finished but no output file was found.")
        mp3_path = candidates[0]

    return mp3_path, title


def extract_audio(video_path: str, out_dir: str) -> str:
    """Extract a mono, 16kHz, low-bitrate mp3 track from an uploaded video."""
    os.makedirs(out_dir, exist_ok=True)
    audio_path = os.path.join(out_dir, "source_audio.mp3")
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
