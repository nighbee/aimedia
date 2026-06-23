import { Shield, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getToken, clearToken } from '../services/api';

export default function Navbar() {
  const navigate = useNavigate();
  const isLoggedIn = !!getToken();

  const handleLogout = () => {
    clearToken();
    navigate('/login');
  };

  return (
    <nav className="border-b border-slate-800 bg-slate-950 px-6 py-4">
      <div className="mx-auto flex max-w-5xl items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded bg-violet-600">
          <Shield className="h-4 w-4 text-white" />
        </div>
        <span className="font-bold text-white">AI Media Watch</span>
        <span className="rounded bg-emerald-900/50 px-2 py-0.5 text-xs text-emerald-400">
          MVP
        </span>
        {isLoggedIn && (
          <button
            onClick={handleLogout}
            className="ml-auto inline-flex items-center gap-1.5 rounded px-2 py-1 text-xs text-slate-400 hover:text-white"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign Out
          </button>
        )}
      </div>
    </nav>
  );
}
