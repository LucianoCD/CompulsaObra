import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useWorkspaceStore } from './store/useWorkspaceStore';
import { useRequisitionStore } from './store/useRequisitionStore';
import { useComparisonStore } from './store/useComparisonStore';
import { DemoBanner } from './components/DemoBanner';
import { BuilderDashboardPage } from './pages/BuilderDashboardPage';
import { PublicBudgetViewPage } from './pages/PublicBudgetViewPage';
import { TractionEvidencePage } from './pages/TractionEvidencePage';
import { VendorCatalogModal } from './components/VendorCatalogModal';
import { BrandLogo } from './components/BrandLogo';
import { CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

const THEME_STORAGE_KEY = 'compulsa_theme';

function getInitialTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light';
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  return stored === 'dark' ? 'dark' : 'light';
}

interface EmailVerificationPageProps {
  onNavigate: (path: string) => void;
}

const EmailVerificationPage: React.FC<EmailVerificationPageProps> = ({ onNavigate }) => {
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
      <div className="max-w-md w-full bg-surface-elevated border border-surface-hairline rounded-container p-6 text-center space-y-4 shadow-card">
        <div className="flex justify-center pb-1">
          <BrandLogo variant="compact" />
        </div>
        <div className="flex justify-center">
          {status === 'verifying' && <Loader2 className="w-8 h-8 animate-spin text-action-primary" />}
          {status === 'success' && <CheckCircle2 className="w-8 h-8 text-semantic-winnerText" />}
          {status === 'error' && <AlertCircle className="w-8 h-8 text-action-danger" />}
        </div>
        <h1 className="text-lg font-display font-bold text-content-primary">
          Verificación de Cuenta CompulsaObra
        </h1>
        <p className="text-sm text-content-secondary leading-relaxed">{message}</p>
        <a
          href="/"
          onClick={(e) => {
            e.preventDefault();
            onNavigate('/');
          }}
          className="inline-flex items-center justify-center px-4 py-2.5 rounded-control bg-action-primary hover:bg-action-hover text-white font-bold text-[13px] transition min-h-[42px]"
        >
          Ir a CompulsaObra
        </a>
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  const { initSession } = useWorkspaceStore();
  const currentRequisition = useRequisitionStore((state) => state.currentRequisition);
  const currentMatrix = useComparisonStore((state) => state.currentMatrix);

  const [theme, setTheme] = useState<'light' | 'dark'>(getInitialTheme);
  const [currentPath, setCurrentPath] = useState<string>(() =>
    typeof window !== 'undefined' ? window.location.pathname : '/'
  );
  const [isCatalogModalOpen, setIsCatalogModalOpen] = useState(false);
  const sessionInitializedRef = useRef(false);

  // Sincronización de tema persistente con localStorage y data-theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  // Escucha de historial del navegador (History API SPA)
  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Inicialización de sesión al entrar a rutas de trabajo o impacto
  useEffect(() => {
    if (
      !sessionInitializedRef.current &&
      currentPath !== '/verificar-correo' &&
      !currentPath.startsWith('/p/')
    ) {
      sessionInitializedRef.current = true;
      void initSession();
    }
  }, [currentPath, initSession]);

  // Guardia antes de abandonar pestaña si hay un pedido o comparativa abierta sin confirmar
  useEffect(() => {
    const hasUnsavedWork =
      currentRequisition !== null &&
      currentMatrix?.status !== 'LOCKED_BUDGET' &&
      !currentMatrix?.is_locked;

    if (!hasUnsavedWork) return;

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [currentRequisition, currentMatrix]);

  const navigate = useCallback((to: string) => {
    const targetPath = to.split('?')[0] || '/';
    if (window.location.pathname !== to) {
      window.history.pushState({}, '', to);
    }
    setCurrentPath(targetPath);
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  }, []);

  if (currentPath === '/verificar-correo') {
    return <EmailVerificationPage onNavigate={navigate} />;
  }

  if (currentPath.startsWith('/p/')) {
    const token = currentPath.replace('/p/', '');
    return (
      <div className="min-h-screen bg-surface-canvas text-content-primary flex flex-col font-sans transition-colors duration-150">
        <PublicBudgetViewPage
          shareToken={token}
          currentTheme={theme}
          onToggleTheme={toggleTheme}
          onNavigate={navigate}
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface-canvas text-content-primary flex flex-col font-sans transition-colors duration-150">
      <DemoBanner
        currentPath={currentPath}
        onNavigate={navigate}
        currentTheme={theme}
        onToggleTheme={toggleTheme}
        onOpenCatalogs={() => setIsCatalogModalOpen(true)}
      />

      <main id="main-workspace" tabIndex={-1} className="flex-1 focus:outline-none">
        {currentPath === '/traccion' ? (
          <TractionEvidencePage onNavigate={navigate} />
        ) : (
          <BuilderDashboardPage onOpenCatalogs={() => setIsCatalogModalOpen(true)} />
        )}
      </main>

      <footer
        role="contentinfo"
        className="border-t border-surface-hairline bg-surface-elevated py-4 text-center text-xs text-content-muted"
      >
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>
            CompulsaObra · Presupuestos de Materiales y Comparativa de Corralones en el NOA (Jujuy, Palpalá, Perico y El Carmen)
          </span>
          <span>Comparación exacta de medidas y materiales · Sin reemplazos imprevistos en obra</span>
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
