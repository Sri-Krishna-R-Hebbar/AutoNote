# AutoNote 📝🎥

Turn an uploaded video into detailed, well-organized study notes, with the video and notes synced
side by side in the browser, plus a swipeable PDF and slide deck.

Upload a video in the browser, and AutoNote will:

1. Extract the audio track (fast, no GPU needed).
2. Transcribe it **locally** with `faster-whisper` (open-source, from Hugging Face) — no
   transcription API/key required.
3. Write detailed, structured markdown notes with a **Groq chat model** (tries a small model
   first, falling back to progressively larger ones if needed).
4. Line the notes up against the transcript's timestamps, so the notes panel can auto-highlight
   and scroll in sync as the video plays.
5. Render everything into:
   - A **Studio view**: the video played in-browser next to a synced notes panel and a swipeable
     **Concept Slides** deck (tap a slide to jump the video to that moment).
   - A polished **PDF** (cover page, clickable table of contents, styled headings, callout boxes,
     code blocks and tables) using **ReportLab**.

Groq is used exactly once in the pipeline (note-writing) — transcription runs locally, so the app
isn't dependent on a single provider for everything.

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

4. **Configure your API key**
   ```bash
   cp .env.example .env
   ```
   Fill in `GROQ_API_KEY` (used for note-writing only). Free key: https://console.groq.com/keys

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

- `app.py` — Flask API: upload handling, background job processing, status polling, download,
  video streaming, and serving the built React app.
- `pipeline.py` — audio extraction (ffmpeg), local transcription (faster-whisper), and notes
  generation (Groq chat models).
- `notes_analysis.py` — turns generated markdown + timed transcript segments into the
  `sections` (heading → timestamp) and `concept_slides` used by the Studio view, with no extra
  AI calls.
- `pdf_builder.py` — turns the generated markdown notes into a designed PDF with ReportLab.
- `frontend/` — the React (Vite) single-page UI, including `StudioView` (video + synced notes +
  concept slides).
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

---

## ☁️ Free hosting

Push to GitHub, then create a Render **Web Service** from this repo — it will pick up the
`Dockerfile` automatically (or set `render.yaml` as your blueprint). Set `GROQ_API_KEY` as an
environment variable in the Render dashboard, and deploy.

Note: running transcription locally (instead of via an API) means the app now needs more CPU/RAM
than a pure-API version — the `base` Whisper model is a reasonable fit for Render's free tier, but
transcription will be slower than the previous Groq-API approach, especially for longer videos.

## 📌 Notes

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
