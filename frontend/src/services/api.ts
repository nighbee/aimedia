const API_BASE = '/api/v1';

export interface Job {
  job_id: string;
  url: string;
  platform: 'tiktok' | 'instagram';
  status: string;
  risk_score: number | null;
  confidence: 'low' | 'medium' | 'high' | null;
  reasoning: string | null;
  categories: Record<string, number> | null;
  top_flags: { signal: string; weight: string }[] | null;
  evidence_url: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface SubmitResponse {
  job_id: string;
  status: string;
  created_at: string;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export async function submitJob(url: string): Promise<SubmitResponse> {
  const res = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || 'Failed to submit job');
  }
  return res.json();
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || 'Failed to fetch job');
  }
  return res.json();
}

export async function listJobs(status?: string, page = 1, limit = 20): Promise<JobListResponse> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (status) params.set('status', status);
  const res = await fetch(`${API_BASE}/jobs?${params}`);
  if (!res.ok) throw new Error('Failed to list jobs');
  return res.json();
}

export async function getEvidenceUrl(jobId: string): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/evidence`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.evidence_url || null;
  } catch {
    return null;
  }
}

export function pollJob(jobId: string, onUpdate: (job: Job) => void, onDone: (job: Job) => void): () => void {
  let cancelled = false;
  let retries = 0;
  const maxRetries = 30; // 30 * 2s = 60s timeout

  const poll = async () => {
    while (!cancelled && retries < maxRetries) {
      try {
        const job = await getJob(jobId);
        if (!cancelled) onUpdate(job);

        if (job.status === 'completed' || job.status === 'failed') {
          if (!cancelled) onDone(job);
          return;
        }
      } catch {
        retries++;
      }
      await new Promise(r => setTimeout(r, 2000));
    }
  };

  poll();
  return () => { cancelled = true; };
}
