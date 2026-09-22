const STEPS = [
  { label: 'Audio', min: 10 },
  { label: 'Transcript', min: 30 },
  { label: 'AI Notes', min: 65 },
  { label: 'PDF', min: 90 },
];

export default function ProcessingView({ stage, progress }) {
  const pct = Math.max(2, progress || 0);
  return (
    <div className="status-block">
      <div className="spinner"></div>
      <div className="stage-text">{stage || 'Getting started…'}</div>
      <div className="stage-sub">This usually takes a couple of minutes, depending on video length.</div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }}></div>
      </div>
      <div className="progress-pct">{pct}%</div>
      <div className="steps">
        {STEPS.map((step) => (
          <div key={step.label} className={`step ${pct >= step.min ? 'done' : ''}`}>
            <div className="dot"></div>
            {step.label}
          </div>
        ))}
      </div>
    </div>
  );
}
