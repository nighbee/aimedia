import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  History,
  Loader2,
  ExternalLink,
  FileDown,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
} from 'lucide-react';
import { listJobs, getEvidenceUrl, type Job } from '../services/api';
import StatusBadge from '../components/StatusBadge';

const STATUS_TABS = [
  { label: 'All', value: '' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' },
  { label: 'Processing', value: 'processing' },
];

function riskColor(score: number | null): string {
  if (score === null) return 'text-slate-500';
  if (score >= 70) return 'text-red-400';
  if (score >= 40) return 'text-amber-400';
  return 'text-emerald-400';
}

function riskBg(score: number | null): string {
  if (score === null) return '';
  if (score >= 70) return 'border-red-900/50 bg-red-950/30';
  if (score >= 40) return 'border-amber-900/50 bg-amber-950/30';
  return 'border-emerald-900/50 bg-emerald-950/30';
}

function truncateUrl(url: string, max = 50): string {
  return url.length > max ? url.slice(0, max) + '…' : url;
}

export default function HistoryPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const limit = 15;

  const fetchJobs = async () => {
    setLoading(true);
    setError(null);
    try {
      const filter = status || undefined;
      const data = await listJobs(filter, page, limit);
      setJobs(data.jobs);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch {
      setError('Failed to load job history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, [page, status]);

  const handleStatusChange = (newStatus: string) => {
    setStatus(newStatus);
    setPage(1);
  };

  const handleDownload = async (jobId: string) => {
    setDownloading(jobId);
    try {
      const url = await getEvidenceUrl(jobId);
      if (url) window.open(url, '_blank');
    } finally {
      setDownloading(null);
    }
  };

  // Processing includes any non-terminal status
  const isNonTerminal = (s: string) =>
    !['completed', 'failed'].includes(s);

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      {/* Header */}
      <div className="mb-8">
        <div className="mb-3 inline-flex items-center gap-2 rounded bg-violet-900/30 px-3 py-1 text-sm text-violet-300">
          <History className="h-4 w-4" />
          Analysis History
        </div>
        <h1 className="text-2xl font-bold text-white">All Runs</h1>
        <p className="mt-1 text-sm text-slate-400">
          {total} job{total !== 1 ? 's' : ''} analyzed
        </p>
      </div>

      {/* Status Tabs */}
      <div className="mb-6 flex flex-wrap gap-2">
        {STATUS_TABS.map(tab => (
          <button
            key={tab.value}
            onClick={() => handleStatusChange(tab.value)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
              status === tab.value
                ? 'bg-violet-600 text-white'
                : 'bg-slate-800/50 text-slate-400 hover:bg-slate-700/50 hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-violet-400" />
        </div>
      ) : error ? (
        <div className="flex items-center justify-center gap-2 py-20 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      ) : jobs.length === 0 ? (
        <div className="rounded border border-slate-800 bg-slate-900/50 py-16 text-center">
          <p className="text-sm text-slate-500">
            {status ? `No ${status} jobs found` : 'No jobs analyzed yet'}
          </p>
          <Link
            to="/"
            className="mt-3 inline-block text-sm text-violet-400 hover:text-violet-300"
          >
            Submit a video for analysis →
          </Link>
        </div>
      ) : (
        <>
          {/* Table */}
          <div className="overflow-x-auto rounded border border-slate-800">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/80 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3">URL / Platform</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Risk Score</th>
                  <th className="hidden px-4 py-3 md:table-cell">Categories</th>
                  <th className="hidden px-4 py-3 lg:table-cell">Submitted</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {jobs.map(job => (
                  <tr key={job.job_id} className="transition-colors hover:bg-slate-900/40">
                    {/* URL + Platform */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-bold uppercase text-slate-400">
                          {job.platform}
                        </span>
                      </div>
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-0.5 inline-flex items-center gap-1 text-xs text-slate-400 hover:text-violet-400"
                      >
                        {truncateUrl(job.url)}
                        <ExternalLink className="h-3 w-3 shrink-0" />
                      </a>
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3">
                      <StatusBadge status={job.status} />
                    </td>

                    {/* Risk Score */}
                    <td className="px-4 py-3">
                      {job.risk_score !== null ? (
                        <span
                          className={`inline-flex items-center rounded border px-2 py-0.5 text-sm font-bold ${riskBg(job.risk_score)} ${riskColor(job.risk_score)}`}
                        >
                          {job.risk_score}
                        </span>
                      ) : isNonTerminal(job.status) ? (
                        <span className="text-xs text-slate-500">—</span>
                      ) : (
                        <span className="text-xs text-slate-500">N/A</span>
                      )}
                    </td>

                    {/* Categories (desktop only) */}
                    <td className="hidden px-4 py-3 md:table-cell">
                      {job.categories ? (
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(job.categories)
                            .filter(([, score]) => (score ?? 0) > 0)
                            .sort(([, a], [, b]) => (b ?? 0) - (a ?? 0))
                            .slice(0, 3)
                            .map(([key, score]) => (
                              <span
                                key={key}
                                className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-medium text-slate-400"
                              >
                                {key.replace(/_/g, ' ')} {score}
                              </span>
                            ))}
                          {Object.values(job.categories).filter(s => (s ?? 0) > 0).length > 3 && (
                            <span className="text-[10px] text-slate-600">
                              +{Object.values(job.categories).filter(s => (s ?? 0) > 0).length - 3} more
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-slate-600">—</span>
                      )}
                    </td>

                    {/* Created At (desktop only) */}
                    <td className="hidden px-4 py-3 text-xs text-slate-500 lg:table-cell">
                      {new Date(job.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Link
                          to={`/report/${job.job_id}`}
                          className="inline-flex items-center gap-1 rounded bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-white"
                        >
                          Report
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                        {job.evidence_url && (
                          <button
                            onClick={() => handleDownload(job.job_id)}
                            disabled={downloading === job.job_id}
                            className="inline-flex items-center gap-1 rounded bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-white disabled:opacity-50"
                          >
                            {downloading === job.job_id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <FileDown className="h-3 w-3" />
                            )}
                            PDF
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="mt-4 flex items-center justify-between text-sm">
            <p className="text-slate-500">
              Page {page} of {totalPages} ({total} total)
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="inline-flex items-center gap-1 rounded bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-white disabled:opacity-40"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Prev
              </button>
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                const start = Math.max(1, Math.min(page - 2, totalPages - 4));
                const p = start + i;
                if (p > totalPages) return null;
                return (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`inline-flex h-7 w-7 items-center justify-center rounded text-xs font-medium transition-colors ${
                      p === page
                        ? 'bg-violet-600 text-white'
                        : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                    }`}
                  >
                    {p}
                  </button>
                );
              })}
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="inline-flex items-center gap-1 rounded bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-white disabled:opacity-40"
              >
                Next
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
