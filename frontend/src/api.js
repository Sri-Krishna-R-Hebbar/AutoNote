export async function fetchConfig() {
  const res = await fetch('/api/config');
  if (!res.ok) return { groq_configured: false };
  return res.json();
}

export async function startJob(formData) {
  const res = await fetch('/api/process', { method: 'POST', body: formData });
  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error || 'Upload failed.');
  }
  return data.job_id;
}

export async function fetchStatus(jobId) {
  const res = await fetch(`/api/status/${jobId}`);
  return res.json();
}

export async function fetchNotes(jobId) {
  const res = await fetch(`/api/notes/${jobId}`);
  if (!res.ok) throw new Error('Could not load notes.');
  return res.json();
}
