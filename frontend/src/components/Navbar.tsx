import { Link } from 'react-router-dom';
import { Shield, History } from 'lucide-react';

export default function Navbar() {
  return (
    <nav className="border-b border-slate-800 bg-slate-950 px-6 py-4">
      <div className="mx-auto flex max-w-6xl items-center gap-3">
        <Link to="/" className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-violet-600">
            <Shield className="h-4 w-4 text-white" />
          </div>
          <span className="font-bold text-white">AI Media Watch</span>
        </Link>
        <Link
          to="/history"
          className="ml-auto inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-sm text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
        >
          <History className="h-4 w-4" />
          History
        </Link>
        <span className="rounded bg-emerald-900/50 px-2 py-0.5 text-xs text-emerald-400">
          MVP
        </span>
      </div>
    </nav>
  );
}
