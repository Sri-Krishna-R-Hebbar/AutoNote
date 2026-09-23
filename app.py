import os
import re
import time
import uuid
import threading
import logging

from flask import Flask, request, send_file, send_from_directory, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

import pipeline
import notes_analysis
from pdf_builder import build_notes_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autonote.app")

# The React app is built into frontend/dist and served as static files by
# this same Flask process, so the whole thing deploys as one web service.
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")

app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path="")
CORS(app, resources={r"/api/*": {"origins": os.environ.get("FRONTEND_ORIGIN", "*")}})

app.config["UPLOAD_FOLDER"] = "uploads"
app.config["OUTPUT_FOLDER"] = "processed_notes"
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500MB max upload
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "mkv", "avi", "webm", "m4v", "wmv", "flv"}
ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "aac", "ogg", "flac", "wma", "opus"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)

# job_id -> {status, stage, progress, error, pdf_path, title, created,
#            video_kind ("video"|"audio"|"none"), video_path, audio_path,
#            sources ({audio: bool, visual: bool}), visual_notes,
#            markdown, sections, concept_slides}
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()

JOB_MAX_AGE_SECONDS = 2 * 60 * 60  # purge finished jobs' files after 2 hours


def _allowed_file(filename: str, extensions: set[str]) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in extensions


def _set_job(job_id: str, **fields):
    with JOBS_LOCK:
        JOBS[job_id].update(fields)


def _progress(job_id: str, stage: str, percent: int):
    logger.info("[%s] %s (%d%%)", job_id, stage, percent)
    _set_job(job_id, stage=stage, progress=percent)


def _purge_old_jobs():
    now = time.time()
    with JOBS_LOCK:
        stale = [
            jid
            for jid, job in JOBS.items()
            if job.get("status") in ("completed", "error")
            and now - job.get("created", now) > JOB_MAX_AGE_SECONDS
        ]
    for jid in stale:
        job = JOBS.pop(jid, None)
        if not job:
            continue
        for path_key in ("pdf_path", "video_path", "audio_path"):
            path = job.get(path_key)
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


def _run_pipeline(job_id: str, video_path: str | None, audio_path: str | None, display_name: str):
    work_dir = os.path.join(app.config["UPLOAD_FOLDER"], job_id)
    os.makedirs(work_dir, exist_ok=True)
    try:
        title = display_name

        # Path 1: audio -> transcript. Prefer a separately-uploaded audio
        # file (it's guaranteed to actually have sound); fall back to
        # extracting the audio track from the video file otherwise. Either
        # source might turn out to have no audio at all - that's not fatal
        # on its own, path 2 (below) can still carry the notes.
        transcript = None
        segments: list[dict] = []
        duration = 0.0
        audio_source = audio_path or video_path
        if audio_source:
            _progress(job_id, "Extracting audio", 10)
            try:
                extracted_audio = pipeline.extract_audio(audio_source, work_dir)
                _progress(job_id, "Transcribing audio locally... 0%", 18)
                transcript, segments, duration = pipeline.transcribe_audio(
                    extracted_audio,
                    progress=lambda msg: _progress(job_id, msg, 40),
                )
                if not transcript.strip():
                    transcript = None
            except pipeline.NoAudioTrackError as exc:
                logger.info("[%s] %s", job_id, exc)
                transcript = None

        # Path 2: video frames -> on-screen content (slides, whiteboard,
        # handwriting, code, diagrams - via a Qwen vision model on
        # OpenRouter). Only runs if a video file was actually uploaded.
        visual_notes: list[dict] = []
        if video_path:
            _progress(job_id, "Analyzing video frames for on-screen content", 45)
            visual_notes = pipeline.analyze_video_frames(
                video_path,
                progress=lambda msg: _progress(job_id, msg, 55),
            )
            if not duration:
                duration = pipeline.get_video_duration(video_path)

        if not transcript and not visual_notes:
            raise pipeline.PipelineError(
                "No speech could be transcribed and no readable on-screen content was found."
            )

        _progress(job_id, "Generating detailed notes with AI", 65)
        notes_markdown = pipeline.generate_notes(
            transcript, visual_notes, progress=lambda msg: _progress(job_id, msg, 78)
        )

        _progress(job_id, "Mapping notes to the timeline", 88)
        # Both audio segments and on-screen captures are {"start", "text"}
        # timed entries, so they can be merged into one timeline for
        # matching notes headings to a timestamp.
        timeline = sorted(segments + visual_notes, key=lambda s: s["start"])
        sections, concept_slides = notes_analysis.build_sections_and_slides(
            notes_markdown, timeline
        )

        _progress(job_id, "Designing your PDF", 92)
        source_label = f"Uploaded file: {display_name}"
        pdf_title = _extract_title(notes_markdown) or title
        pdf_path = os.path.join(app.config["OUTPUT_FOLDER"], f"{job_id}_notes.pdf")
        build_notes_pdf(notes_markdown, pdf_path, title=pdf_title, source_label=source_label)

        if video_path:
            video_kind = "video"
        elif audio_path:
            video_kind = "audio"
        else:
            video_kind = "none"

        _set_job(
            job_id,
            status="completed",
            stage="Done",
            progress=100,
            pdf_path=pdf_path,
            title=pdf_title,
            video_kind=video_kind,
            duration=duration,
            markdown=notes_markdown,
            sections=sections,
            concept_slides=concept_slides,
            visual_notes=visual_notes,
            sources={"audio": bool(transcript), "visual": bool(visual_notes)},
        )
    except pipeline.PipelineError as exc:
        logger.warning("[%s] pipeline error: %s", job_id, exc)
        _set_job(job_id, status="error", error=str(exc))
    except Exception:  # pragma: no cover - safety net
        logger.exception("[%s] unexpected error", job_id)
        _set_job(job_id, status="error", error="Something went wrong while processing your video.")
    finally:
        pipeline.cleanup_dir(work_dir)
        # The uploaded video/audio file itself is kept around so it can be
        # played back in the browser - it's cleaned up later by _purge_old_jobs.


def _extract_title(markdown_text: str) -> str | None:
    match = re.search(r"^#\s+(.+)$", markdown_text.strip(), re.MULTILINE)
    if match:
        return match.group(1).strip()[:120]
    return None


@app.route("/api/config")
def config():
    return jsonify({"groq_configured": bool(pipeline.GROQ_API_KEY)})


@app.route("/api/process", methods=["POST"])
def process():
    _purge_old_jobs()

    video_file = request.files.get("video")
    audio_file = request.files.get("audio")
    has_video = video_file and video_file.filename != ""
    has_audio = audio_file and audio_file.filename != ""

    if not has_video and not has_audio:
        return jsonify({"error": "Please upload a video file, an audio file, or both."}), 400

    try:
        pipeline.notes_provider()
    except pipeline.PipelineError as exc:
        return jsonify({"error": str(exc)}), 500

    if has_video and not _allowed_file(video_file.filename, ALLOWED_VIDEO_EXTENSIONS):
        return (
            jsonify(
                {
                    "error": "Unsupported video file type. Allowed: "
                    + ", ".join(sorted(ALLOWED_VIDEO_EXTENSIONS))
                }
            ),
            400,
        )
    if has_audio and not _allowed_file(audio_file.filename, ALLOWED_AUDIO_EXTENSIONS):
        return (
            jsonify(
                {
                    "error": "Unsupported audio file type. Allowed: "
                    + ", ".join(sorted(ALLOWED_AUDIO_EXTENSIONS))
                }
            ),
            400,
        )

    job_id = uuid.uuid4().hex
    video_path = None
    audio_path = None
    display_name = "Video"

    if has_video:
        filename = secure_filename(video_file.filename)
        display_name = filename
        video_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{job_id}_video_{filename}")
        video_file.save(video_path)
    if has_audio:
        filename = secure_filename(audio_file.filename)
        if not has_video:
            display_name = filename
        audio_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{job_id}_audio_{filename}")
        audio_file.save(audio_path)

    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "processing",
            "stage": "Queued",
            "progress": 0,
            "error": None,
            "pdf_path": None,
            "video_path": video_path,
            "audio_path": audio_path,
            "video_kind": None,
            "title": display_name,
            "created": time.time(),
        }

    thread = threading.Thread(
        target=_run_pipeline,
        args=(job_id, video_path, audio_path, display_name),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def status(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return (
            jsonify(
                {
                    "error": "This job was lost (likely a server restart while it was still "
                    "processing). Please try uploading again."
                }
            ),
            404,
        )

    response = {
        "status": job["status"],
        "stage": job["stage"],
        "progress": job["progress"],
    }
    if job["status"] == "error":
        response["error"] = job["error"]
    if job["status"] == "completed":
        response["download_url"] = f"/api/download/{job_id}"
        response["notes_url"] = f"/api/notes/{job_id}"
        response["title"] = job["title"]
    return jsonify(response)


@app.route("/api/notes/<job_id>")
def notes(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job.get("status") != "completed":
        return jsonify({"error": "Notes not ready"}), 404

    video_kind = job.get("video_kind") or "none"
    video = {"kind": video_kind}
    if video_kind in ("video", "audio"):
        video["src"] = f"/api/media/{job_id}"

    return jsonify(
        {
            "title": job.get("title"),
            "markdown": job.get("markdown", ""),
            "sections": job.get("sections", []),
            "concept_slides": job.get("concept_slides", []),
            "duration": job.get("duration"),
            "video": video,
            "sources": job.get("sources", {"audio": False, "visual": False}),
            "visual_notes": job.get("visual_notes", []),
            "download_url": f"/api/download/{job_id}",
        }
    )


@app.route("/api/media/<job_id>")
def media(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job.get("video_kind") not in ("video", "audio"):
        return jsonify({"error": "Media not available"}), 404
    media_path = job.get("video_path") or job.get("audio_path")
    if not media_path or not os.path.exists(media_path):
        return jsonify({"error": "Media not available"}), 404
    return send_file(media_path, conditional=True)


@app.route("/api/download/<job_id>")
def download(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job.get("status") != "completed" or not job.get("pdf_path"):
        return jsonify({"error": "File not found"}), 404
    if not os.path.exists(job["pdf_path"]):
        return jsonify({"error": "File not found"}), 404

    safe_title = re.sub(r"[^\w\- ]", "", job.get("title") or "notes").strip() or "notes"
    download_name = f"{safe_title[:60]}.pdf"
    return send_file(job["pdf_path"], as_attachment=True, download_name=download_name)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# --- Serve the built React frontend (production) -------------------------
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path and os.path.exists(os.path.join(FRONTEND_DIST, path)):
        return send_from_directory(FRONTEND_DIST, path)
    index_path = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index_path):
        return send_from_directory(FRONTEND_DIST, "index.html")
    return jsonify(
        {
            "error": "Frontend build not found. Run `npm install && npm run build` inside "
            "the frontend/ folder, or run the React dev server separately."
        }
    ), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
