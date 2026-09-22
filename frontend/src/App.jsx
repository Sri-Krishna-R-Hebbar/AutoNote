import { useEffect, useRef, useState } from 'react';
import UploadForm from './components/UploadForm';
import ProcessingView from './components/ProcessingView';
import ResultView from './components/ResultView';
import ErrorView from './components/ErrorView';
import StudioView from './components/StudioView';
import SeoContent from './components/SeoContent';
import { fetchConfig, startJob, fetchStatus, fetchNotes } from './api';

const POLL_INTERVAL_MS = 3000;

export default function App() {
  const [view, setView] = useState('upload'); // upload | processing | studio | done | error
  const [stage, setStage] = useState('');
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null); // fallback simple result { downloadUrl, title }
  const [notes, setNotes] = useState(null); // rich studio payload
  const [errorMessage, setErrorMessage] = useState('');
  const [groqConfigured, setGroqConfigured] = useState(true);
  const pollTimer = useRef(null);

  useEffect(() => {
    fetchConfig().then((cfg) => setGroqConfigured(cfg.groq_configured));
    return () => clearTimeout(pollTimer.current);
  }, []);

  function reset() {
    clearTimeout(pollTimer.current);
    setStage('');
    setProgress(0);
    setResult(null);
    setNotes(null);
    setErrorMessage('');
    setView('upload');
  }

  function showError(message) {
    clearTimeout(pollTimer.current);
    setErrorMessage(message);
    setView('error');
  }

  async function handleCompleted(jobId, data) {
    setProgress(100);
    try {
      const notesData = await fetchNotes(jobId);
      setNotes(notesData);
      setView('studio');
    } catch {
      setResult({ downloadUrl: data.download_url, title: data.title });
      setView('done');
    }
  }

  function poll(jobId) {
    fetchStatus(jobId)
      .then((data) => {
        if (data.error) {
          showError(data.error);
          return;
        }
        if (data.status === 'processing') {
          setStage(data.stage || 'Processing…');
          setProgress(Math.max(2, data.progress || 0));
          pollTimer.current = setTimeout(() => poll(jobId), POLL_INTERVAL_MS);
        } else if (data.status === 'completed') {
          handleCompleted(jobId, data);
        } else if (data.status === 'error') {
          showError(data.error || 'Processing failed.');
        } else {
          pollTimer.current = setTimeout(() => poll(jobId), POLL_INTERVAL_MS);
        }
      })
      .catch(() => {
        pollTimer.current = setTimeout(() => poll(jobId), 4000);
      });
  }

  async function handleSubmit(formData) {
    setView('processing');
    setStage('Uploading…');
    setProgress(2);
    try {
      const jobId = await startJob(formData);
      poll(jobId);
    } catch (err) {
      showError(err.message);
    }
  }

  const isStudio = view === 'studio';

  return (
    <div className={isStudio ? 'wrap wrap-wide' : 'wrap'}>
      <header>
        <span className="logo">🪶 AutoNote</span>
        {!isStudio && (
          <>
            <h1>
              Turn any video into <span>detailed notes</span>
            </h1>
            <p className="subtitle">
              Upload a video or paste a link. AutoNote transcribes it, writes thorough AI-generated notes, and
              hands you back a beautifully designed PDF you can study from.
            </p>
          </>
        )}
      </header>

      {isStudio ? (
        <StudioView notes={notes} onReset={reset} />
      ) : (
        <div className="card">
          {view === 'upload' && <UploadForm onSubmit={handleSubmit} />}
          {view === 'processing' && <ProcessingView stage={stage} progress={progress} />}
          {view === 'done' && result && (
            <ResultView downloadUrl={result.downloadUrl} title={result.title} onReset={reset} />
          )}
          {view === 'error' && <ErrorView message={errorMessage} onRetry={reset} />}
        </div>
      )}

      {view === 'upload' && <SeoContent />}

      {!isStudio && (
        <footer>
          <span>Powered by a local open-source speech model and fast AI note-writing.</span>{' '}
          <span className="badge">Whisper (local)</span>
          <span className="badge">Groq</span>
          {!groqConfigured && <span className="badge">⚠ No API key configured</span>}
        </footer>
      )}
    </div>
  );
}
