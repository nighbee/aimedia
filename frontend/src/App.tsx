import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Shield, 
  AlertTriangle, 
  CheckCircle2, 
  Download, 
  Search, 
  Plus, 
  FileText, 
  Layers, 
  Cpu, 
  ExternalLink,
  Info,
  Clock,
  Check,
  RefreshCw
} from 'lucide-react'

interface Job {
  id: string
  url: string
  platform: 'tiktok' | 'instagram'
  status: string
  risk_score: number
  confidence: 'low' | 'medium' | 'high'
  reasoning: string
  categories: {
    illegal_gambling: number
    pyramid_scheme: number
    investment_fraud: number
    referral_scheme: number
  }
  evidence_url: string | null
  completed_at: string
}

const mockJobs: Job[] = [
  {
    id: "550e8400-e29b-41d4-a716-446655440000",
    url: "https://www.tiktok.com/@example/video/7123456789",
    platform: "tiktok",
    status: "completed",
    risk_score: 88,
    confidence: "high",
    reasoning: "High risk (88/100). Soniox detected guaranteed income promise at 0:12. Gemini identified 1xBet logo overlay at frame 7 and aggressive referral call-to-action at frame 14.",
    categories: { illegal_gambling: 91, pyramid_scheme: 42, investment_fraud: 65, referral_scheme: 78 },
    evidence_url: "https://storage.googleapis.com/evidence-packs/550e8400.pdf",
    completed_at: "2026-06-20T09:16:05Z"
  },
  {
    id: "3bc84992-129b-41d4-b716-446655440111",
    url: "https://www.instagram.com/reel/C8xYz10A9bC",
    platform: "instagram",
    status: "completed",
    risk_score: 54,
    confidence: "medium",
    reasoning: "Medium risk (54/100). Video shows luxury lifestyle representations with caption promoting private VIP messaging channels. No direct logo detections, but audio implies quick returns.",
    categories: { illegal_gambling: 20, pyramid_scheme: 68, investment_fraud: 55, referral_scheme: 60 },
    evidence_url: null,
    completed_at: "2026-06-20T10:02:11Z"
  },
  {
    id: "9f0a8291-729b-41d4-c716-446655440222",
    url: "https://www.tiktok.com/@finance_guru/video/7123999123",
    platform: "tiktok",
    status: "completed",
    risk_score: 18,
    confidence: "high",
    reasoning: "Low risk (18/100). Standard educational content detailing historic performance of stock market indexes. No suspicious indicators detected.",
    categories: { illegal_gambling: 0, pyramid_scheme: 5, investment_fraud: 15, referral_scheme: 22 },
    evidence_url: null,
    completed_at: "2026-06-20T10:14:45Z"
  }
]

export default function App() {
  const [jobs, setJobs] = useState<Job[]>(mockJobs)
  const [selectedJob, setSelectedJob] = useState<Job>(mockJobs[0])
  const [searchUrl, setSearchUrl] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchUrl) return

    setIsSubmitting(true)
    setTimeout(() => {
      const isInstagram = searchUrl.includes('instagram.com')
      const newJob: Job = {
        id: crypto.randomUUID(),
        url: searchUrl,
        platform: isInstagram ? 'instagram' : 'tiktok',
        status: 'pending',
        risk_score: 0,
        confidence: 'low',
        reasoning: 'Job has been submitted to the Kafka broker. Analysis is starting...',
        categories: { illegal_gambling: 0, pyramid_scheme: 0, investment_fraud: 0, referral_scheme: 0 },
        evidence_url: null,
        completed_at: new Date().toISOString()
      }
      setJobs([newJob, ...jobs])
      setSearchUrl('')
      setIsSubmitting(false)
    }, 1200)
  }

  const getRiskColor = (score: number) => {
    if (score >= 70) return 'text-accent-red bg-accent-red/10 border-accent-red/30'
    if (score >= 40) return 'text-accent-amber bg-accent-amber/10 border-accent-amber/30'
    return 'text-accent-green bg-accent-green/10 border-accent-green/30'
  }

  const getRiskBadge = (score: number) => {
    if (score >= 70) return 'High Risk'
    if (score >= 40) return 'Medium Risk'
    return 'Low Risk'
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-primary/30 selection:text-white">
      {/* Top Navbar */}
      <nav className="border-b border-slate-900 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-primary/20 p-2 rounded-xl border border-primary/30 text-primary">
              <Shield className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-purple-400 to-indigo-400 bg-clip-text text-transparent">
                AI Media Watch
              </span>
              <span className="ml-2 text-xs bg-indigo-950 text-indigo-300 border border-indigo-900 px-2 py-0.5 rounded-full font-mono">
                Hackathon MVP
              </span>
            </div>
          </div>
          <div className="flex items-center gap-6 text-sm text-slate-400">
            <div className="flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-primary" />
              <span>Clean Architecture</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-emerald-400" />
              <span>Pipeline Active</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        
        {/* Header / Intro */}
        <div className="bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 rounded-2xl border border-slate-900 p-6 md:p-8 flex flex-col md:flex-row gap-6 justify-between items-start md:items-center">
          <div className="space-y-2">
            <h1 className="text-3xl font-extrabold tracking-tight text-white">
              Automated Fraud Watchdog
            </h1>
            <p className="text-slate-400 max-w-2xl text-sm leading-relaxed">
              Real-time multi-modal analysis pipeline monitoring TikTok and Instagram URLs. 
              Hunts down illegal gambling, financial pyramid schemes, and fraud to generate legal evidence packs.
            </p>
          </div>
          <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800 text-xs font-mono space-y-1.5 w-full md:w-auto">
            <div className="text-slate-400">Broker: Kafka KRaft Mode</div>
            <div className="text-slate-400">API Gateway: Go + Fiber</div>
            <div className="text-slate-400">Worker: Python 3.11</div>
          </div>
        </div>

        {/* Input Form */}
        <div className="bg-slate-900/40 border border-slate-900 rounded-xl p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
            <Plus className="w-4 h-4 text-primary" />
            Analyze New Media URL
          </h2>
          <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-grow">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
              <input
                type="url"
                required
                placeholder="Paste TikTok or Instagram video URL (e.g. https://www.tiktok.com/@example/video/7123456789)"
                value={searchUrl}
                onChange={(e) => setSearchUrl(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-slate-950 border border-slate-800 rounded-xl focus:outline-none focus:border-primary text-sm text-slate-200 placeholder:text-slate-600 transition-colors"
              />
            </div>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-6 py-3 bg-primary hover:bg-primary-hover active:scale-95 text-white font-medium text-sm rounded-xl transition-all disabled:opacity-50 flex items-center justify-center gap-2 shadow-lg shadow-purple-900/25"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Enqueuing...</span>
                </>
              ) : (
                <>
                  <Cpu className="w-4 h-4" />
                  <span>Submit to Pipeline</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Grid Dashboard */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Queue List (2 cols on desktop/tablets or left col) */}
          <div className="lg:col-span-1 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-primary" />
                Pipeline Queue
              </h2>
              <span className="text-xs bg-slate-900 border border-slate-800 px-2 py-0.5 rounded text-slate-400 font-mono">
                {jobs.length} Jobs
              </span>
            </div>

            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
              <AnimatePresence initial={false}>
                {jobs.map((job) => {
                  const isSelected = selectedJob.id === job.id
                  return (
                    <motion.div
                      key={job.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      onClick={() => setSelectedJob(job)}
                      className={`p-4 rounded-xl border cursor-pointer transition-all ${
                        isSelected 
                          ? 'bg-slate-900 border-primary shadow-md shadow-purple-950/20' 
                          : 'bg-slate-900/30 border-slate-900 hover:border-slate-800 hover:bg-slate-900/50'
                      }`}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 font-mono">
                          {job.platform}
                        </span>
                        {job.status === 'completed' ? (
                          <div className={`text-xs px-2.5 py-0.5 rounded-full border font-medium ${getRiskColor(job.risk_score)}`}>
                            {job.risk_score} pts · {getRiskBadge(job.risk_score)}
                          </div>
                        ) : (
                          <div className="text-xs px-2.5 py-0.5 rounded-full border border-indigo-500/20 bg-indigo-950/20 text-indigo-300 animate-pulse font-medium">
                            Processing
                          </div>
                        )}
                      </div>
                      <p className="text-slate-300 text-xs font-mono truncate mb-2">
                        {job.url}
                      </p>
                      <div className="flex items-center justify-between text-[11px] text-slate-500">
                        <span className="font-mono">{job.id.substring(0, 8)}...</span>
                        <span>{new Date(job.completed_at).toLocaleTimeString()}</span>
                      </div>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            </div>
          </div>

          {/* Details & Reasoning Panel */}
          <div className="lg:col-span-2 space-y-6">
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <Info className="w-4 h-4 text-primary" />
              Analysis Detail Panel
            </h2>

            <div className="bg-slate-900/30 border border-slate-900 rounded-2xl p-6 space-y-6">
              
              {/* Header inside Panel */}
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-6 border-b border-slate-900">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs uppercase font-semibold text-slate-500 font-mono">ID: {selectedJob.id}</span>
                    <a href={selectedJob.url} target="_blank" rel="noreferrer" className="text-xs text-primary hover:underline flex items-center gap-0.5">
                      Open Source <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                  <h3 className="text-lg font-bold text-white truncate max-w-md">
                    {selectedJob.url}
                  </h3>
                </div>

                {selectedJob.status === 'completed' && (
                  <div className={`px-4 py-2 rounded-xl border flex flex-col items-center sm:items-end ${getRiskColor(selectedJob.risk_score)}`}>
                    <span className="text-[10px] uppercase font-bold tracking-wider opacity-70">Risk Score</span>
                    <span className="text-2xl font-black">{selectedJob.risk_score}</span>
                  </div>
                )}
              </div>

              {/* Main Analysis Results */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                
                {/* Reasoning Description */}
                <div className="space-y-4">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    AI Watchdog Evaluation
                  </h4>
                  <div className="p-4 bg-slate-950/50 border border-slate-900 rounded-xl text-sm text-slate-300 leading-relaxed min-h-[120px]">
                    {selectedJob.reasoning}
                  </div>
                  {selectedJob.evidence_url && (
                    <a
                      href={selectedJob.evidence_url}
                      className="inline-flex items-center gap-2 px-4 py-2.5 bg-accent-red/10 border border-accent-red/30 hover:bg-accent-red/20 active:scale-95 text-accent-red text-xs font-semibold rounded-lg transition-all"
                    >
                      <Download className="w-4 h-4" />
                      <span>Download Evidence Pack PDF</span>
                    </a>
                  )}
                </div>

                {/* Score Breakdown Table */}
                <div className="space-y-4">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Category Breakdown
                  </h4>
                  <div className="space-y-3">
                    {[
                      { name: 'Illegal Gambling', score: selectedJob.categories.illegal_gambling, color: 'bg-purple-500' },
                      { name: 'Pyramid Scheme', score: selectedJob.categories.pyramid_scheme, color: 'bg-indigo-500' },
                      { name: 'Investment Fraud', score: selectedJob.categories.investment_fraud, color: 'bg-blue-500' },
                      { name: 'Referral Scheme', score: selectedJob.categories.referral_scheme, color: 'bg-pink-500' }
                    ].map((cat) => (
                      <div key={cat.name} className="space-y-1">
                        <div className="flex justify-between text-xs font-medium">
                          <span className="text-slate-400">{cat.name}</span>
                          <span className="text-slate-200">{cat.score}%</span>
                        </div>
                        <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden border border-slate-900">
                          <motion.div 
                            initial={{ width: 0 }}
                            animate={{ width: `${cat.score}%` }}
                            transition={{ duration: 0.8, ease: 'easeOut' }}
                            className={`h-full ${cat.color}`}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

              </div>

              {/* Technical / Pipeline Metadata */}
              <div className="pt-6 border-t border-slate-900 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
                <div className="space-y-1">
                  <div className="text-slate-500">Pipeline Status</div>
                  <div className="flex items-center gap-1.5 text-slate-300">
                    {selectedJob.status === 'completed' ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Completed</span>
                      </>
                    ) : (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
                        <span>Queued</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-slate-500">Model Confidence</div>
                  <div className="text-slate-300 capitalize">{selectedJob.confidence}</div>
                </div>
                <div className="space-y-1">
                  <div className="text-slate-500">Completed At</div>
                  <div className="text-slate-300 truncate">
                    {selectedJob.status === 'completed' 
                      ? new Date(selectedJob.completed_at).toLocaleTimeString() 
                      : 'Pending'}
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-slate-500">Evidence Pack</div>
                  <div className="text-slate-300">
                    {selectedJob.evidence_url ? 'Generated (PDF)' : 'Not Generated'}
                  </div>
                </div>
              </div>

            </div>
          </div>

        </div>

      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 mt-16 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row justify-between items-center gap-4 text-slate-500 text-xs">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-primary" />
            <span>© 2026 AI Media Watch. Hackathon Project.</span>
          </div>
          <div className="flex gap-4">
            <span className="hover:text-slate-400 transition-colors">Documentation</span>
            <span>·</span>
            <span className="hover:text-slate-400 transition-colors">Legal Custody Log</span>
            <span>·</span>
            <span className="hover:text-slate-400 transition-colors">API Reference</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
