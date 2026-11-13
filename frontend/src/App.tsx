import React, { useEffect, useState } from 'react';
import { useWorkspaceStore } from './store/useWorkspaceStore';
import { DemoBanner } from './components/DemoBanner';
import { BuilderDashboardPage } from './pages/BuilderDashboardPage';
import { PublicBudgetViewPage } from './pages/PublicBudgetViewPage';
import { TractionEvidencePage } from './pages/TractionEvidencePage';
import { VendorCatalogModal } from './components/VendorCatalogModal';
import { CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

const EmailVerificationPage: React.FC = () => {
  const { verifyEmail } = useWorkspaceStore();
  const [status, setStatus] = useState<'verifying' | 'success' | 'error'>('verifying');
  const [message, setMessage] = useState<string>('Verificando tu dirección de correo...');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const email = params.get('email') || '';
    const token = params.get('token') || '';
    if (!email || !token) {
      setStatus('error');
      setMessage('El enlace de verificación es incompleto.');
      return;
    }

    let cancelled = false;
    verifyEmail(email, token)
      .then(() => {
        if (!cancelled) {
          setStatus('success');
          setMessage('¡Correo verificado correctamente! Ya podés operar en tu espacio privado.');
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setStatus('error');
          setMessage(err instanceof Error ? err.message : 'No se pudo verificar el enlace.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [verifyEmail]);

  return (
    <div className="min-h-screen bg-surface-canvas text-content-primary flex items-center justify-center p-4 font-sans">
      <div className="max-w-md w-full bg-surface-elevated border border-surface-hairline rounded-container p-6 text-center space-y-4 shadow-sm">
        <div className="flex justify-center">
          {status === 'verifying' && <Loader2 className="w-8 h-8 animate-spin text-action-primary" />}
          {status === 'success' && <CheckCircle2 className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />}
          {status === 'error' && <AlertCircle className="w-8 h-8 text-action-danger" />}
        </div>
        <h1 className="text-lg font-display font-bold text-content-primary">
          Verificación de Cuenta CompulsaObra
        </h1>
        <p className="text-xs text-content-secondary leading-relaxed">{message}</p>
        <a
          href="/"
          className="inline-flex items-center justify-center px-4 py-2 rounded-control bg-action-primary hover:bg-action-hover text-white font-bold text-xs transition"
        >
          Ir a CompulsaObra
        </a>
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  const { initSession } = useWorkspaceStore();
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [isCatalogModalOpen, setIsCatalogModalOpen] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'light');
    if (window.location.pathname !== '/verificar-correo') {
      void initSession();
    }
  }, [initSession]);

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);
    document.documentElement.setAttribute('data-theme', nextTheme);
  };

  const pathname = window.location.pathname;

  if (pathname === '/verificar-correo') {
    return <EmailVerificationPage />;
  }

  // Ruta pública compartible: /p/:token
  if (pathname.startsWith('/p/')) {
    const token = pathname.replace('/p/', '');
    return <PublicBudgetViewPage shareToken={token} />;
  }

  // Ruta tablero de tracción: /traccion
  if (pathname === '/traccion') {
    return <TractionEvidencePage />;
  }

  // Ruta principal: Dashboard Operativo de Compulsa
  return (
    <div className="min-h-screen bg-surface-canvas text-content-primary flex flex-col font-sans transition-colors duration-150">
      <DemoBanner
        currentTheme={theme}
        onToggleTheme={toggleTheme}
        onOpenCatalogs={() => setIsCatalogModalOpen(true)}
      />

      <main id="main-workspace" tabIndex={-1} className="flex-1 focus:outline-none">
        <BuilderDashboardPage onOpenCatalogs={() => setIsCatalogModalOpen(true)} />
      </main>

      <footer className="border-t border-surface-hairline bg-surface-elevated py-4 text-center text-xs text-content-muted font-mono">
        <div className="max-w-[1600px] mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>CompulsaObra — Jujuy / NOA — Cómputo Métrico y Compulsa Multi-Corralón</span>
          <span className="tabular-nums">Estándar ISO/IEC 25010:2023 · WCAG 2.2 AA · Cero Sustitución Ciega</span>
        </div>
      </footer>

      <VendorCatalogModal
        isOpen={isCatalogModalOpen}
        onClose={() => setIsCatalogModalOpen(false)}
      />
    </div>
  );
};

export default App;
