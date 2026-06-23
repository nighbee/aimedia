import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import ProcessingPage from './pages/ProcessingPage';
import ReportPage from './pages/ReportPage';
import { getToken } from './services/api';

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen flex-col bg-slate-950 text-white">
        <Navbar />
        <main className="flex-1">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<RequireAuth><HomePage /></RequireAuth>} />
            <Route path="/processing/:jobId" element={<RequireAuth><ProcessingPage /></RequireAuth>} />
            <Route path="/report/:jobId" element={<RequireAuth><ReportPage /></RequireAuth>} />
          </Routes>
        </main>
        <Footer />
      </div>
    </BrowserRouter>
  );
}
