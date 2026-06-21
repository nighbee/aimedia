import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Loader2, AlertCircle, CheckCircle2, Video, AudioLines, Brain, FileText, Activity } from 'lucide-react';
import { pollJob, type Job } from '../services/api';
import StatusBadge from '../components/StatusBadge';

const STAGE_ORDER = [
  'pending', 'downloading', 'extracting', 'analyzing',
  'aggregating', 'generating_evidence', 'completed',
];

const STAGE_META: Record<string, { icon: typeof Video; label: string }> = {
  pending:             { icon: Activity,  label: 'Queued' },
  downloading:         { icon: Video,    label: 'Downloading' },
  extracting:          { icon: AudioLines, label: 'Extracting Media' },
  analyzing:           { icon: Brain,    label: 'AI Analysis' },
  aggregating:         { icon: Activity, label: 'Aggregating Results' },
  generating_evidence: { icon: FileText, label: 'Generating Evidence' },
  completed:           { icon: CheckCircle2, label: 'Complete' },
  failed:              { icon: AlertCircle, label: 'Failed' },
};

export default function ProcessingPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!jobId) return;

    const cancel = pollJob(
      jobId,
      (updated) => setJob(updated),
      (final) => {
        setJob(final);
        setDone(true);
        setTimeout(() => {
          navigate(`/report/${final.job_id}`, { replace: true });
        }, 1500);
      }
    );

    // Timeout after 60s
    const timeout = setTimeout(() => {
      setError('Analysis timed out. The job may still be processing.');
      cancel();
    }, 62000);

    return () => {
      cancel();
      clearTimeout(timeout);
    };
  }, [jobId, navigate]);

  if (!jobId) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-slate-400">No job ID provided</p>
      </div>
    );
  }

  const currentIdx = job ? STAGE_ORDER.indexOf(job.status) : 0;
  const isFailed = job?.status === 'failed';

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 pt-24">
      <div className="w-full max-w-lg">
        {/* Job ID */}
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-white">Analyzing Content</h1>
          <p className="mt-1 text-sm text-slate-500 font-mono">Job {jobId.slice(0, 8)}...</p>
          {job && (
            <div className="mt-2">
              <StatusBadge status={job.status} />
            </div>
          )}
        </div>

        {/* Pipeline Stages */}
        <div className="space-y-3">
          {STAGE_ORDER.filter(s => s !== 'completed').map((stage, i) => {
            const meta = STAGE_META[stage];
            const isActive = stage === job?.status;
            const isDone = currentIdx > i;
            const isPending = currentIdx < i;

            return (
              <motion.div
                key={stage}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: i * 0.1 }}
                className={`flex items-center gap-4 rounded-xl border p-4 transition-all ${
                  isActive
                    ? 'border-violet-500/50 bg-violet-500/5'
                    : isDone
                    ? 'border-emerald-500/20 bg-emerald-500/5'
                    : 'border-slate-800/50 bg-slate-900/30'
                }`}
              >
                <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                  isActive
                    ? 'bg-violet-500/20 text-violet-400'
                    : isDone
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'bg-slate-800/50 text-slate-600'
                }`}>
                  {isActive ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : isDone ? (
                    <CheckCircle2 className="h-5 w-5" />
                  ) : (
                    <meta.icon className="h-5 w-5" />
                  )}
                </div>
                <div className="flex-1">
                  <p className={`text-sm font-medium ${
                    isActive ? 'text-white' : isDone ? 'text-emerald-300' : 'text-slate-500'
                  }`}>
                    {meta.label}
                  </p>
                  <p className={`text-xs ${
                    isActive ? 'text-violet-400' : 'text-slate-600'
                  }`}>
                    {isActive ? 'Processing...' : isDone ? 'Complete' : 'Waiting'}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Error */}
        {error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-6 rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-center"
          >
            <AlertCircle className="mx-auto h-8 w-8 text-red-400" />
            <p className="mt-2 text-sm text-red-400">{error}</p>
          </motion.div>
        )}

        {/* Redirecting */}
        {done && !isFailed && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-6 text-center text-sm text-emerald-400"
          >
            Analysis complete! Redirecting to report...
          </motion.p>
        )}
      </div>
    </div>
  );
}
