import { useState } from 'react';
import { FileDown, Loader2 } from 'lucide-react';
import { getEvidenceUrl } from '../services/api';

interface Props {
  jobId: string;
}

export default function EvidenceButton({ jobId }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async () => {
    setLoading(true);
    setError(null);
    try {
      const url = await getEvidenceUrl(jobId);
      if (url) {
        window.open(url, '_blank');
      } else {
        setError('Evidence not available');
      }
    } catch {
      setError('Failed to get download link');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button
        onClick={handleDownload}
        disabled={loading}
        className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-fuchsia-600 px-4 py-2 text-sm font-medium text-white transition-all hover:from-violet-500 hover:to-fuchsia-500 disabled:opacity-50"
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <FileDown className="h-4 w-4" />
        )}
        Download Evidence Pack
      </button>
      {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
    </div>
  );
}
