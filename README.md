# AutoNote 📝🎥

Turn an uploaded video (and/or audio) into detailed, well-organized study notes, with the video
and notes synced side by side in the browser, plus a swipeable PDF and slide deck.

AutoNote runs **two independent content-extraction paths** and merges what they find, because a
presenter often *writes* things down (on a slide, whiteboard, or in code) that they never actually
*say out loud*:

- **Path 1 — audio → transcript.** The audio track is extracted (ffmpeg) and transcribed
  **locally** with `faster-whisper` (open-source, from Hugging Face) — no transcription API/key
  required.
- **Path 2 — video frames → on-screen content.** Frames are sampled from the video (OpenCV), and
  for frames that changed meaningfully since the last one, a **Qwen2.5-VL vision-language model**
  (via [OpenRouter](https://openrouter.ai), free tier) reads any text/handwriting/diagrams
  actually visible on screen — slides, whiteboards, code editors, annotations.

Upload just a video, just an audio file, or both (handy if you downloaded them separately) —
whichever path(s) have input run; if only one produces content, the notes are built from that
alone. Both paths' output then flows into:

1. Detailed, structured markdown notes written by a **Groq chat model** (tries a small model
   first, falling back to progressively larger ones if needed), explicitly merging what was said
   with what was shown on screen.
2. Notes lined up against a combined audio+on-screen timeline, so the notes panel can
   auto-highlight and scroll in sync as the video plays.
3. A **Studio view**: the video/audio played in-browser next to the synced notes panel, a
   swipeable **Concept Slides** deck, and (when on-screen content was found) an **On-Screen** tab
   listing everything read off the video frames, each jumping the player to that moment.
4. A polished **PDF** (cover page, clickable table of contents, styled headings, callout boxes,
   code blocks and tables) using **ReportLab**.

Groq is used only for the final note-writing step; transcription runs locally and frame analysis
uses a separate vision model on OpenRouter, so no single provider is a dependency for everything.

---

## 🔧 Local setup

You need **Python 3.10+** and **Node.js 18+**.

1. **Clone the repository**
   ```bash
   git clone https://github.com/Sri-Krishna-R-Hebbar/AutoNote.git
   cd AutoNote
   ```

2. **Install the Python backend**
   ```bash
   pip install -r requirements.txt
   ```
   The first transcription request downloads the local Whisper model (~140MB for the default
   `base` size) from Hugging Face and caches it — expect a one-time delay there.

3. **Install the React frontend**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. **Configure your API key(s)**
   ```bash
   cp .env.example .env
   ```
   Fill in `GROQ_API_KEY` (used for note-writing). Free key: https://console.groq.com/keys

   Optionally also fill in `OPENROUTER_API_KEY` to enable path 2 (on-screen content from video
   frames). Free key: https://openrouter.ai/keys — without it, notes are generated from the audio
   transcript alone.

5. **Run it**

   Two options:

   - **Quick (single process):** build the frontend once, then run Flask, which serves both
     the API and the built React app:
     ```bash
     cd frontend && npm run build && cd ..
     python app.py
     ```
     Open http://localhost:5000

   - **Dev mode (hot reload while editing the UI):** run both servers side by side. Vite proxies
     `/api/*` calls to Flask automatically (see `frontend/vite.config.js`).
     ```bash
     # terminal 1
     python app.py
     # terminal 2
     cd frontend && npm run dev
     ```
     Open http://localhost:5173

---

## 🗂️ Project layout

- `app.py` — Flask API: upload handling, background job processing (orchestrating both paths),
  status polling, download, media streaming, and serving the built React app.
- `pipeline.py` — audio extraction (ffmpeg) + local transcription (faster-whisper) for path 1;
  video frame sampling (OpenCV) + vision-model calls (Qwen2.5-VL via OpenRouter) for path 2; and
  notes generation (Groq chat models) merging both.
- `notes_analysis.py` — turns generated markdown + a combined audio/on-screen timeline into the
  `sections` (heading → timestamp) and `concept_slides` used by the Studio view, with no extra
  AI calls.
- `pdf_builder.py` — turns the generated markdown notes into a designed PDF with ReportLab.
- `frontend/` — the React (Vite) single-page UI, including `StudioView` (video/audio + synced
  notes + concept slides + on-screen content tab) and the dual video/audio `UploadForm`.
- `Dockerfile` — multi-stage build (Node to build the frontend, Python to run the app, with the
  Whisper model pre-downloaded at build time) used for deployment.
- `legacy_scripts/` — the original local-model pipeline (Whisper-large-v2/Wav2Vec2/Qwen2-VL via
  `transformers`+`torch`) and the original Jinja/vanilla-JS UI, kept for reference; not used by
  the app anymore.

---

## ⚙️ Useful environment variables

See `.env.example` for the full list. The main ones:

- `GROQ_API_KEY` — required, used for note generation.
- `WHISPER_MODEL_SIZE` — local transcription model size: `tiny`, `base` (default), `small`,
  `medium`, `large-v3`. Bigger = more accurate but slower/heavier; `base` is a good default for a
  free-tier CPU host.
- `GROQ_LLM_MODEL` — override the notes model instead of using the built-in fallback chain.
- `OPENROUTER_API_KEY` — optional, enables path 2 (on-screen content). Without it, that path is
  silently skipped and notes come from audio alone.
- `OPENROUTER_VISION_MODEL` — override the vision model instead of the built-in Qwen2.5-VL
  fallback chain. OpenRouter's free-tier model slugs rotate over time, so check
  https://openrouter.ai/models?modality=text%2Bimage-%3Etext if the defaults stop working.
- `FRAME_SAMPLE_INTERVAL_SECONDS` / `FRAME_DIFF_THRESHOLD` / `FRAME_MAX_CALLS` — tune how
  aggressively video frames are sampled and how many are ever sent to the vision model per video.

---

## ☁️ Free hosting

Push to GitHub, then create a Render **Web Service** from this repo — it will pick up the
`Dockerfile` automatically (or set `render.yaml` as your blueprint). Set `GROQ_API_KEY` (required)
and `OPENROUTER_API_KEY` (optional, for on-screen content) as environment variables in the Render
dashboard, and deploy.

Note: running transcription locally (instead of via an API) means the app now needs more CPU/RAM
than a pure-API version — the `base` Whisper model is a reasonable fit for Render's free tier, but
transcription will be slower than the previous Groq-API approach, especially for longer videos.

## 📌 Notes

- Video frame analysis (path 2) sends downscaled JPEG frames to a third-party API
  (OpenRouter/Qwen) - only enable it (`OPENROUTER_API_KEY`) for content you're comfortable
  sending off-server. It's skipped entirely if the key isn't set.
- On a long video, path 2 is capped at `FRAME_MAX_CALLS` (default 30) vision-model calls, evenly
  covering the video's most visually different moments - it's a sample, not a frame-by-frame scan,
  to keep free-tier API usage and processing time bounded. Candidate frames are downscaled to
  `FRAME_MAX_WIDTH` (default 960px) and JPEG-encoded immediately rather than held as raw frames,
  to keep memory use bounded on Render's free-tier 512MB limit for longer videos.
- Job status is kept in memory, not a database - if the server process restarts while a job is
  still processing (e.g. an out-of-memory crash), that job is lost and polling it returns "job was
  lost" - just re-upload.
- File upload only — YouTube (and other) URL downloading was removed. YouTube blanket-blocks
  video downloads from cloud/datacenter IP ranges (Render, AWS, GCP, etc.) at the network level,
  independent of cookies or PO tokens, so it never worked reliably once deployed. The UI now
  points users to download the video themselves first (e.g. via
  [YTUltra](https://www.ytultra.com/en/youtube-video-downloader/), picking a version with audio
  included) and upload the file instead.
- Works best with lectures, talks, and other clearly-spoken content.
- Very long videos are automatically chunked, if needed, for note generation, so there's no hard
  duration limit — just longer processing time.
- Section timestamps (used for video/notes sync and Concept Slides) are a best-effort match
  between each heading and the transcript — usually accurate, but not guaranteed frame-perfect.
