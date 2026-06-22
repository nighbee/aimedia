import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Shield, Loader2, Link2 } from 'lucide-react';
import { submitJob } from '../services/api';

export default function HomePage() {
  const [url, setUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;

    setSubmitting(true);
    setError(null);
    try {
      const result = await submitJob(trimmed);
      navigate(`/processing/${result.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-6 pt-16 pb-12">
      {/* Header */}
      <div className="mb-8 text-center">
        <div className="mb-3 inline-flex items-center gap-2 rounded bg-violet-900/30 px-3 py-1 text-sm text-violet-300">
          <Shield className="h-4 w-4" />
          AI-Powered Fraud Detection
        </div>
        <h1 className="text-3xl font-bold text-white">
          AI Media Watch
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Automated analysis of TikTok and Instagram videos for illegal gambling,
          pyramid schemes, and investment fraud.
        </p>
      </div>

      {/* URL Form */}
      <form onSubmit={handleSubmit} className="mb-6">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Link2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              type="url"
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://www.tiktok.com/@user/video/..."
              className="w-full rounded border border-slate-700 bg-slate-900 py-3 pl-10 pr-3 text-sm text-white placeholder-slate-500 outline-none focus:border-violet-500"
            />
          </div>
          <button
            type="submit"
            disabled={submitting || !url.trim()}
            className="inline-flex items-center gap-2 rounded bg-violet-600 px-5 py-3 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Analyze
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      </form>

      {/* Risk Tiers */}
      <div className="rounded border border-slate-800 bg-slate-900/50 p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-400 uppercase tracking-wide">Risk Tiers</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded border border-red-900/50 bg-red-950/30 p-3 text-center">
            <div className="text-2xl font-black text-red-400">70–100</div>
            <div className="text-sm font-bold text-red-400">High Risk</div>
            <div className="mt-1 text-xs text-slate-400">Auto-flagged, Evidence PDF generated</div>
          </div>
          <div className="rounded border border-amber-900/50 bg-amber-950/30 p-3 text-center">
            <div className="text-2xl font-black text-amber-400">40–69</div>
            <div className="text-sm font-bold text-amber-400">Medium Risk</div>
            <div className="mt-1 text-xs text-slate-400">Manual review queue</div>
          </div>
          <div className="rounded border border-emerald-900/50 bg-emerald-950/30 p-3 text-center">
            <div className="text-2xl font-black text-emerald-400">0–39</div>
            <div className="text-sm font-bold text-emerald-400">Low Risk</div>
            <div className="mt-1 text-xs text-slate-400">Archived, no action needed</div>
          </div>
        </div>
      </div>
    </div>
  );
}
