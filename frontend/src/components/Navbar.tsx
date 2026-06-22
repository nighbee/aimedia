import { Shield } from 'lucide-react';

export default function Navbar() {
  return (
    <nav className="border-b border-slate-800 bg-slate-950 px-6 py-4">
      <div className="mx-auto flex max-w-5xl items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded bg-violet-600">
          <Shield className="h-4 w-4 text-white" />
        </div>
        <span className="font-bold text-white">AI Media Watch</span>
        <span className="ml-auto rounded bg-emerald-900/50 px-2 py-0.5 text-xs text-emerald-400">
          MVP
        </span>
      </div>
    </nav>
  );
}
