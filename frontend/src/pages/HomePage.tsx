import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Search, Upload, Shield, Cpu, Activity, FileText,
  ArrowRight, AlertTriangle, Loader2, Video, Link2
} from 'lucide-react';
import { submitJob } from '../services/api';

const STEPS = [
  { icon: Link2, label: 'Submit URL', desc: 'Paste a TikTok or Instagram video link' },
  { icon: Video, label: 'Extract Media', desc: 'Download video, audio & keyframes' },
  { icon: Cpu, label: 'AI Analysis', desc: 'Soniox STT + Gemini two-pass scoring' },
  { icon: FileText, label: 'Evidence Pack', desc: 'Auto-generated PDF report if risk ≥ 70' },
];

export default function HomePage() {
  const [url, setUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;

    setSubmitting(true);
    setError(null);
    try {
      const result = await submitJob(trimmed);
      navigate(`/processing/${result.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    // File upload is a v2 feature — for now just acknowledge
  };

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative overflow-hidden border-b border-slate-800/50 px-6 pt-32 pb-20">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-violet-900/20 via-transparent to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-violet-500/10 px-4 py-1.5 text-sm font-medium text-violet-300 ring-1 ring-violet-500/20">
              <Shield className="h-4 w-4" />
              AI-Powered Social Media Fraud Detection
            </div>
            <h1 className="text-5xl font-bold leading-tight tracking-tight text-white sm:text-6xl">
              Automated Watchdog for
              <span className="bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent"> Illegal Content</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-400">
              Hunts down illegal gambling, financial pyramid schemes, and investment fraud
              hidden in TikTok and Instagram videos. Replace thousands of hours of manual
              review with real-time AI analysis.
            </p>
          </motion.div>

          {/* URL Input Form */}
          <motion.form
            onSubmit={handleSubmit}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mx-auto mt-10 max-w-2xl"
          >
            <div className="flex gap-3">
              <div className="relative flex-1">
                <Link2 className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500" />
                <input
                  type="url"
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  placeholder="https://www.tiktok.com/@user/video/..."
                  className="w-full rounded-xl border border-slate-700/50 bg-slate-900/50 py-4 pl-12 pr-4 text-sm text-white placeholder-slate-500 outline-none transition-all focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20"
                />
              </div>
              <button
                type="submit"
                disabled={submitting || !url.trim()}
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6 py-4 text-sm font-semibold text-white transition-all hover:from-violet-500 hover:to-fuchsia-500 disabled:opacity-50"
              >
                {submitting ? <Loader2 className="h-5 w-5 animate-spin" /> : <Search className="h-5 w-5" />}
                Analyze
              </button>
            </div>
            {error && (
              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 text-sm text-red-400">
                {error}
              </motion.p>
            )}
          </motion.form>

          {/* File Upload */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="mx-auto mt-6 max-w-2xl"
          >
            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleFileDrop}
              className={`rounded-xl border-2 border-dashed p-6 text-center transition-all ${
                dragOver
                  ? 'border-violet-500/50 bg-violet-500/5'
                  : 'border-slate-700/50 bg-slate-900/30'
              }`}
            >
              <Upload className="mx-auto h-8 w-8 text-slate-500" />
              <p className="mt-2 text-sm text-slate-400">
                <span className="text-slate-300">Drag & drop a video file</span> or{' '}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="text-violet-400 underline underline-offset-2 hover:text-violet-300"
                >
                  browse
                </button>
              </p>
              <p className="mt-1 text-xs text-slate-600">MP4, max 100MB (v2 feature)</p>
              <input ref={fileInputRef} type="file" accept="video/mp4" className="hidden" />
            </div>
          </motion.div>
        </div>
      </section>

      {/* How It Works */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="text-center text-2xl font-bold text-white">How It Works</h2>
          <p className="mx-auto mt-2 max-w-xl text-center text-sm text-slate-400">
            A 6-stage event-driven pipeline — from URL submission to evidence PDF
          </p>
          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, i) => (
              <motion.div
                key={step.label}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="group rounded-xl border border-slate-800/50 bg-slate-900/30 p-6 transition-all hover:border-slate-700/50 hover:bg-slate-900/50"
              >
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br from-violet-600/20 to-fuchsia-600/20 ring-1 ring-violet-500/20">
                  <step.icon className="h-6 w-6 text-violet-400" />
                </div>
                <h3 className="font-semibold text-white">{step.label}</h3>
                <p className="mt-1 text-sm text-slate-400">{step.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Risk Tiers */}
      <section className="border-t border-slate-800/50 px-6 py-20">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-2xl font-bold text-white">Risk Scoring Tiers</h2>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {[
              { color: 'from-red-500/20 to-red-600/20 ring-red-500/30', text: 'text-red-400', score: '70–100', label: 'High Risk', badge: 'bg-red-500/10', desc: 'Auto-flagged, Evidence Pack PDF generated' },
              { color: 'from-amber-500/20 to-orange-600/20 ring-amber-500/30', text: 'text-amber-400', score: '40–69', label: 'Medium Risk', badge: 'bg-amber-500/10', desc: 'Manual review queue' },
              { color: 'from-emerald-500/20 to-green-600/20 ring-emerald-500/30', text: 'text-emerald-400', score: '0–39', label: 'Low Risk', badge: 'bg-emerald-500/10', desc: 'Archived, no action needed' },
            ].map(tier => (
              <div key={tier.label} className={`rounded-xl border border-slate-800/50 bg-gradient-to-b ${tier.color} p-6 ring-1 ${tier.badge}`}>
                <div className={`text-3xl font-black ${tier.text}`}>{tier.score}</div>
                <div className={`mt-1 text-lg font-bold ${tier.text}`}>{tier.label}</div>
                <p className="mt-2 text-xs text-slate-400">{tier.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
