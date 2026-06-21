interface Props {
  score: number | null;
  size?: 'sm' | 'lg';
}

function tier(score: number): { label: string; color: string; bg: string } {
  if (score >= 70) return { label: 'High Risk', color: 'text-red-400', bg: 'bg-red-500/10 ring-red-500/20' };
  if (score >= 40) return { label: 'Medium Risk', color: 'text-amber-400', bg: 'bg-amber-500/10 ring-amber-500/20' };
  return { label: 'Low Risk', color: 'text-emerald-400', bg: 'bg-emerald-500/10 ring-emerald-500/20' };
}

export default function RiskScoreBadge({ score, size = 'sm' }: Props) {
  if (score === null) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-800/50 px-3 py-1 text-xs font-medium text-slate-400 ring-1 ring-slate-700/50">
        Pending
      </span>
    );
  }

  const t = tier(score);
  const textSize = size === 'lg' ? 'text-5xl' : 'text-sm';

  return (
    <div className={`inline-flex items-center gap-2 rounded-full ${t.bg} px-3 py-1 ring-1`}>
      {size === 'lg' && <span className={`font-black ${textSize} ${t.color}`}>{score}</span>}
      <span className={`font-semibold ${t.color} ${size === 'lg' ? 'text-lg' : 'text-xs'}`}>
        {size === 'lg' && '/'}100
      </span>
      {size === 'sm' && <span className={`text-xs font-medium ${t.color}`}>{t.label}</span>}
    </div>
  );
}
