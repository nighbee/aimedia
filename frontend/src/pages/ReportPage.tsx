import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  AlertCircle, CheckCircle2, ExternalLink, Clock,
  Hash, Target, MessageSquare, FileText
} from 'lucide-react';
import { getJob, type Job } from '../services/api';
import RiskScoreBadge from '../components/RiskScoreBadge';
import CategoryBreakdown from '../components/CategoryBreakdown';
import StatusBadge from '../components/StatusBadge';
import EvidenceButton from '../components/EvidenceButton';

export default function ReportPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;

    const fetchJob = async () => {
      try {
        const j = await getJob(jobId);
        if (!cancelled) setJob(j);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load report');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchJob();
    return () => { cancelled = true; };
  }, [jobId]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6 pt-20">
        <div className="text-center">
          <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
          <p className="mt-3 text-sm text-slate-400">Loading report...</p>
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 pt-20">
        <AlertCircle className="h-8 w-8 text-red-400" />
        <p className="text-sm text-slate-400">{error || 'Report not found'}</p>
        <Link to="/" className="text-sm text-violet-400 underline underline-offset-2">Back to home</Link>
      </div>
    );
  }

  const isCompleted = job.status === 'completed';
  const isFailed = job.status === 'failed';
  const isProcessing = !isCompleted && !isFailed;
  const score = job.risk_score;

  return (
    <div className="mx-auto max-w-4xl px-6 pt-16 pb-12">
      {/* Breadcrumb */}
      <div className="mb-4 flex items-center gap-2 text-sm text-slate-500">
        <Link to="/" className="hover:text-slate-300">Home</Link>
        <span>/</span>
        <span className="text-slate-400">Report</span>
        <span className="font-mono text-slate-600">#{jobId?.slice(0, 8)}</span>
      </div>

      {/* Header */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Analysis Report</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <StatusBadge status={job.status} />
            <span className="max-w-md truncate text-sm text-slate-500 font-mono">{job.url}</span>
            <a href={job.url} target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-slate-300">
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
        {score !== null && <RiskScoreBadge score={score} size="lg" />}
      </div>

      {/* Processing banner */}
      {isProcessing && (
        <div className="mb-6 rounded border border-amber-800 bg-amber-950/30 p-3">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-amber-400" />
            <p className="text-sm text-amber-300">
              Still processing.{' '}
              <Link to={`/processing/${jobId}`} className="underline underline-offset-2">View progress</Link>
            </p>
          </div>
        </div>
      )}

      {/* Failed banner */}
      {isFailed && (
        <div className="mb-6 rounded border border-red-800 bg-red-950/30 p-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-red-400" />
            <p className="text-sm text-red-300">Analysis failed during processing.</p>
          </div>
        </div>
      )}

      {/* Main grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {/* AI Reasoning */}
          {job.reasoning && (
            <div className="rounded border border-slate-800 bg-slate-900/30 p-4">
              <h2 className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                <MessageSquare className="h-3 w-3" />
                AI Reasoning
              </h2>
              <p className="text-sm leading-relaxed text-slate-300">{job.reasoning}</p>
            </div>
          )}

          {/* Category Breakdown */}
          {job.categories && (
            <div className="rounded border border-slate-800 bg-slate-900/30 p-4">
              <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                <Target className="h-3 w-3" />
                Risk by Category
              </h2>
              <CategoryBreakdown categories={job.categories} />
            </div>
          )}

          {/* Top Flags */}
          {job.top_flags && job.top_flags.length > 0 && (
            <div className="rounded border border-slate-800 bg-slate-900/30 p-4">
              <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                <Hash className="h-3 w-3" />
                Top Flags
              </h2>
              <div className="space-y-1">
                {job.top_flags.map((flag, i) => (
                  <div key={i} className="flex items-center gap-2 rounded bg-slate-800/50 px-3 py-2">
                    <div className={`h-2 w-2 rounded-full ${
                      flag.weight === 'high' ? 'bg-red-500' :
                      flag.weight === 'medium' ? 'bg-amber-500' : 'bg-slate-500'
                    }`} />
                    <span className="flex-1 text-sm text-slate-300">{flag.signal}</span>
                    <span className={`text-xs uppercase ${
                      flag.weight === 'high' ? 'text-red-400' :
                      flag.weight === 'medium' ? 'text-amber-400' : 'text-slate-500'
                    }`}>{flag.weight}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evidence Download */}
          {isCompleted && (
            <div className="rounded border border-slate-800 bg-slate-900/30 p-4">
              <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                <FileText className="h-3 w-3" />
                Evidence Pack
              </h2>
              <p className="mb-3 text-sm text-slate-400">
                {score !== null && score >= 70
                  ? 'High risk content detected. Download the evidence pack PDF.'
                  : 'Risk score below threshold. No evidence pack generated.'}
              </p>
              {score !== null && score >= 70 && <EvidenceButton jobId={job.job_id} />}
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <div className="rounded border border-slate-800 bg-slate-900/30 p-4">
            <h3 className="mb-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Metadata</h3>
            <dl className="space-y-2 text-sm">
              <div><dt className="text-xs text-slate-500">Job ID</dt><dd className="font-mono text-slate-300">{job.job_id}</dd></div>
              <div><dt className="text-xs text-slate-500">Platform</dt><dd className="capitalize text-slate-300">{job.platform}</dd></div>
              <div><dt className="text-xs text-slate-500">Created</dt><dd className="text-slate-300">{new Date(job.created_at).toLocaleString()}</dd></div>
              {job.completed_at && (
                <div><dt className="text-xs text-slate-500">Completed</dt><dd className="text-slate-300">{new Date(job.completed_at).toLocaleString()}</dd></div>
              )}
              <div>
                <dt className="text-xs text-slate-500">Confidence</dt>
                <dd className={`font-medium capitalize ${
                  job.confidence === 'high' ? 'text-emerald-400' :
                  job.confidence === 'medium' ? 'text-amber-400' : 'text-slate-400'
                }`}>{job.confidence ?? '—'}</dd>
              </div>
            </dl>
          </div>

          <Link
            to="/"
            className="flex items-center gap-2 rounded border border-slate-800 bg-slate-900/50 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            <CheckCircle2 className="h-4 w-4" />
            Submit Another URL
          </Link>
        </div>
      </div>
    </div>
  );
}
