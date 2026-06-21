import { motion } from 'framer-motion';

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
  illegal_gambling: 'from-red-500 to-rose-600',
  pyramid_scheme: 'from-amber-500 to-orange-600',
  investment_fraud: 'from-violet-500 to-purple-600',
  referral_scheme: 'from-blue-500 to-cyan-600',
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
              <span className="font-mono font-bold text-white">{score}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-800">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${score}%` }}
                transition={{ duration: 1, ease: 'easeOut' }}
                className={`h-full rounded-full bg-gradient-to-r ${barColors[key]}`}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
