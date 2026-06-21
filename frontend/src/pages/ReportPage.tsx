import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
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
      <div className="flex min-h-screen items-center justify-center pt-24">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent mx-auto" />
          <p className="mt-4 text-slate-400">Loading report...</p>
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 pt-24">
        <AlertCircle className="h-12 w-12 text-red-400" />
        <p className="text-slate-400">{error || 'Report not found'}</p>
        <Link to="/" className="text-sm text-violet-400 underline underline-offset-2 hover:text-violet-300">
          Back to home
        </Link>
      </div>
    );
  }

  const isCompleted = job.status === 'completed';
  const isFailed = job.status === 'failed';
  const isProcessing = !isCompleted && !isFailed;
  const score = job.risk_score;

  return (
    <div className="min-h-screen px-6 pt-24 pb-16">
      <div className="mx-auto max-w-4xl">
        {/* Breadcrumb */}
        <div className="mb-6 flex items-center gap-2 text-sm text-slate-500">
          <Link to="/" className="hover:text-slate-300">Home</Link>
          <span>/</span>
          <span className="text-slate-400">Report</span>
          <span className="font-mono text-slate-600">#{jobId?.slice(0, 8)}</span>
        </div>

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-white">Analysis Report</h1>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <StatusBadge status={job.status} />
                <span className="text-sm text-slate-500 font-mono">{job.url}</span>
                <a href={job.url} target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-slate-300">
                  <ExternalLink className="h-4 w-4" />
                </a>
              </div>
            </div>
            {score !== null && <RiskScoreBadge score={score} size="lg" />}
          </div>
        </motion.div>

        {/* Still processing banner */}
        {isProcessing && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mb-8 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4"
          >
            <div className="flex items-center gap-3">
              <Clock className="h-5 w-5 animate-pulse text-amber-400" />
              <p className="text-sm text-amber-300">
                This job is still being processed.{' '}
                <Link to={`/processing/${jobId}`} className="underline underline-offset-2 hover:text-amber-200">
                  View live progress
                </Link>
              </p>
            </div>
          </motion.div>
        )}

        {/* Failed banner */}
        {isFailed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mb-8 rounded-xl border border-red-500/20 bg-red-500/5 p-4"
          >
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-red-400" />
              <p className="text-sm text-red-300">
                Analysis failed. The job encountered an error during processing.
              </p>
            </div>
          </motion.div>
        )}

        {/* Main grid */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left column — risk details */}
          <div className="space-y-6 lg:col-span-2">
            {/* AI Reasoning */}
            {job.reasoning && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="rounded-xl border border-slate-800/50 bg-slate-900/30 p-6"
              >
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300 uppercase tracking-wider">
                  <MessageSquare className="h-4 w-4" />
                  AI Reasoning
                </h2>
                <p className="text-sm leading-relaxed text-slate-300">{job.reasoning}</p>
              </motion.div>
            )}

            {/* Category Breakdown */}
            {job.categories && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="rounded-xl border border-slate-800/50 bg-slate-900/30 p-6"
              >
                <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-300 uppercase tracking-wider">
                  <Target className="h-4 w-4" />
                  Risk Breakdown by Category
                </h2>
                <CategoryBreakdown categories={job.categories} />
              </motion.div>
            )}

            {/* Top Flags */}
            {job.top_flags && job.top_flags.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="rounded-xl border border-slate-800/50 bg-slate-900/30 p-6"
              >
                <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-300 uppercase tracking-wider">
                  <Hash className="h-4 w-4" />
                  Top Flags
                </h2>
                <div className="space-y-2">
                  {job.top_flags.map((flag, i) => (
                    <div key={i} className="flex items-center gap-3 rounded-lg bg-slate-800/30 px-4 py-3">
                      <div className={`h-2 w-2 rounded-full ${
                        flag.weight === 'high' ? 'bg-red-400' :
                        flag.weight === 'medium' ? 'bg-amber-400' : 'bg-slate-500'
                      }`} />
                      <span className="flex-1 text-sm text-slate-300">{flag.signal}</span>
                      <span className={`text-xs font-medium uppercase ${
                        flag.weight === 'high' ? 'text-red-400' :
                        flag.weight === 'medium' ? 'text-amber-400' : 'text-slate-500'
                      }`}>
                        {flag.weight}
                      </span>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Evidence Download */}
            {isCompleted && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="rounded-xl border border-slate-800/50 bg-slate-900/30 p-6"
              >
                <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-300 uppercase tracking-wider">
                  <FileText className="h-4 w-4" />
                  Evidence Pack
                </h2>
                <p className="mb-4 text-sm text-slate-400">
                  {score !== null && score >= 70
                    ? 'This content was flagged as high risk. Download the auto-generated evidence pack for prosecution.'
                    : 'Risk score is below the evidence threshold. No evidence pack was generated.'}
                </p>
                {score !== null && score >= 70 && <EvidenceButton jobId={job.job_id} />}
              </motion.div>
            )}
          </div>

          {/* Right column — metadata */}
          <div className="space-y-4">
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
              className="rounded-xl border border-slate-800/50 bg-slate-900/30 p-5"
            >
              <h3 className="mb-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Metadata</h3>
              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-xs text-slate-500">Job ID</dt>
                  <dd className="font-mono text-slate-300">{job.job_id}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Platform</dt>
                  <dd className="font-medium capitalize text-slate-300">{job.platform}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Created</dt>
                  <dd className="text-slate-300">{new Date(job.created_at).toLocaleString()}</dd>
                </div>
                {job.completed_at && (
                  <div>
                    <dt className="text-xs text-slate-500">Completed</dt>
                    <dd className="text-slate-300">{new Date(job.completed_at).toLocaleString()}</dd>
                  </div>
                )}
                <div>
                  <dt className="text-xs text-slate-500">Confidence</dt>
                  <dd className={`font-medium capitalize ${
                    job.confidence === 'high' ? 'text-emerald-400' :
                    job.confidence === 'medium' ? 'text-amber-400' : 'text-slate-400'
                  }`}>
                    {job.confidence ?? '—'}
                  </dd>
                </div>
              </dl>
            </motion.div>

            {/* Quick Actions */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
              className="rounded-xl border border-slate-800/50 bg-slate-900/30 p-5"
            >
              <h3 className="mb-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Actions</h3>
              <div className="space-y-2">
                <Link
                  to="/"
                  className="flex w-full items-center gap-2 rounded-lg bg-slate-800/50 px-4 py-2.5 text-sm text-slate-300 transition-all hover:bg-slate-700/50"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Submit Another URL
                </Link>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  );
}
