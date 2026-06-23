import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Loader2, Mail, Lock } from 'lucide-react';
import { login } from '../services/api';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-sm px-6 pt-24">
      <div className="mb-8 text-center">
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded bg-violet-600">
          <Shield className="h-5 w-5 text-white" />
        </div>
        <h1 className="text-xl font-bold text-white">Inspector Login</h1>
        <p className="mt-1 text-sm text-slate-400">Sign in to submit and review jobs.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="relative">
          <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="admin@mediawatch.ai"
            required
            className="w-full rounded border border-slate-700 bg-slate-900 py-3 pl-10 pr-3 text-sm text-white placeholder-slate-500 outline-none focus:border-violet-500"
          />
        </div>
        <div className="relative">
          <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Password"
            required
            className="w-full rounded border border-slate-700 bg-slate-900 py-3 pl-10 pr-3 text-sm text-white placeholder-slate-500 outline-none focus:border-violet-500"
          />
        </div>
        <button
          type="submit"
          disabled={submitting || !email.trim() || !password}
          className="flex w-full items-center justify-center gap-2 rounded bg-violet-600 px-5 py-3 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
        >
          {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
          Sign In
        </button>
        {error && <p className="text-sm text-red-400">{error}</p>}
      </form>
    </div>
  );
}
