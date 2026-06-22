interface Props {
  categories: Record<string, number> | null;
}

const labels: Record<string, string> = {
  illegal_gambling: 'Illegal Gambling',
  pyramid_scheme: 'Pyramid Scheme',
  investment_fraud: 'Investment Fraud',
  referral_scheme: 'Referral Scheme',
};

const barColors: Record<string, string> = {
  illegal_gambling: 'bg-red-600',
  pyramid_scheme: 'bg-amber-600',
  investment_fraud: 'bg-violet-600',
  referral_scheme: 'bg-blue-600',
};

export default function CategoryBreakdown({ categories }: Props) {
  if (!categories) return null;

  return (
    <div className="space-y-3">
      {Object.entries(labels).map(([key, label]) => {
        const score = categories[key] ?? 0;
        return (
          <div key={key}>
            <div className="mb-1 flex justify-between text-sm">
              <span className="text-slate-300">{label}</span>
              <span className="font-mono text-white">{score}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-800">
              <div
                className={`h-full rounded-full ${barColors[key]}`}
                style={{ width: `${score}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
