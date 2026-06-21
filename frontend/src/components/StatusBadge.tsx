interface Props {
  status: string;
}

const styles: Record<string, { label: string; color: string }> = {
  pending:            { label: 'Pending',          color: 'text-slate-400 bg-slate-800/50 ring-slate-700/50' },
  downloading:        { label: 'Downloading',      color: 'text-blue-400 bg-blue-500/10 ring-blue-500/20' },
  extracting:         { label: 'Extracting',       color: 'text-cyan-400 bg-cyan-500/10 ring-cyan-500/20' },
  analyzing:          { label: 'Analyzing',        color: 'text-violet-400 bg-violet-500/10 ring-violet-500/20' },
  aggregating:        { label: 'Aggregating',      color: 'text-fuchsia-400 bg-fuchsia-500/10 ring-fuchsia-500/20' },
  generating_evidence:{ label: 'Generating PDF',   color: 'text-amber-400 bg-amber-500/10 ring-amber-500/20' },
  completed:          { label: 'Completed',        color: 'text-emerald-400 bg-emerald-500/10 ring-emerald-500/20' },
  failed:             { label: 'Failed',           color: 'text-red-400 bg-red-500/10 ring-red-500/20' },
};

export default function StatusBadge({ status }: Props) {
  const s = styles[status] ?? { label: status, color: 'text-slate-400 bg-slate-800/50 ring-slate-700/50' };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${s.color}`}>
      {status === 'pending' || status === 'downloading' || status === 'extracting' ||
       status === 'analyzing' || status === 'aggregating' || status === 'generating_evidence' ? (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      ) : null}
      {s.label}
    </span>
  );
}
