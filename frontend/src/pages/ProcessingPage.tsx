import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Loader2, AlertCircle, CheckCircle2, Video, AudioLines, Brain, FileText, Activity } from 'lucide-react';
import { pollJob, type Job } from '../services/api';
import StatusBadge from '../components/StatusBadge';

const STAGES: { key: string; icon: typeof Video; label: string }[] = [
  { key: 'pending',              icon: Activity,   label: 'Queued' },
  { key: 'downloading',         icon: Video,      label: 'Downloading' },
  { key: 'extracting',          icon: AudioLines,  label: 'Extracting Media' },
  { key: 'analyzing',           icon: Brain,       label: 'AI Analysis' },
  { key: 'aggregating',         icon: Activity,    label: 'Aggregating Results' },
  { key: 'generating_evidence', icon: FileText,    label: 'Generating Evidence' },
];

const STAGE_KEYS = STAGES.map(s => s.key);

export default function ProcessingPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const cancel = pollJob(
      jobId,
      (updated) => setJob(updated),
      (final) => {
        setTimeout(() => {
          navigate(`/report/${final.job_id}`, { replace: true });
        }, 1000);
      }
    );

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
      <div className="flex min-h-screen items-center justify-center p-6 pt-20">
        <p className="text-slate-400">No job ID provided</p>
      </div>
    );
  }

  const currentIdx = job ? STAGE_KEYS.indexOf(job.status) : 0;

  return (
    <div className="mx-auto max-w-lg px-6 pt-16 pb-12">
      <div className="mb-6 text-center">
        <h1 className="text-xl font-bold text-white">Analyzing Content</h1>
        <p className="mt-1 text-sm text-slate-500 font-mono">Job {jobId.slice(0, 8)}...</p>
        {job && <div className="mt-2"><StatusBadge status={job.status} /></div>}
      </div>

      <div className="space-y-2">
        {STAGES.map((stage, i) => {
          const isActive = stage.key === job?.status;
          const isDone = currentIdx > i;

          return (
            <div
              key={stage.key}
              className={`flex items-center gap-3 rounded border p-3 ${
                isActive
                  ? 'border-violet-700 bg-violet-950/30'
                  : isDone
                  ? 'border-emerald-800 bg-emerald-950/20'
                  : 'border-slate-800 bg-slate-900/30'
              }`}
            >
              <div className={`flex h-8 w-8 items-center justify-center rounded ${
                isActive ? 'bg-violet-900/50 text-violet-300' :
                isDone ? 'bg-emerald-900/50 text-emerald-400' :
                'bg-slate-800 text-slate-600'
              }`}>
                {isActive ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : isDone ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <stage.icon className="h-4 w-4" />
                )}
              </div>
              <div className="flex-1">
                <p className={`text-sm font-medium ${
                  isActive ? 'text-white' : isDone ? 'text-emerald-300' : 'text-slate-500'
                }`}>
                  {stage.label}
                </p>
                <p className={`text-xs ${isActive ? 'text-violet-400' : 'text-slate-600'}`}>
                  {isActive ? 'Processing...' : isDone ? 'Complete' : 'Waiting'}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {error && (
        <div className="mt-6 rounded border border-red-800 bg-red-950/30 p-4 text-center">
          <AlertCircle className="mx-auto mb-2 h-6 w-6 text-red-400" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}
    </div>
  );
}
