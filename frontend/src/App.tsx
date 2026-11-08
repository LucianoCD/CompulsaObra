import React, { useEffect, useState } from 'react';
import { useWorkspaceStore } from './store/useWorkspaceStore';
import { DemoBanner } from './components/DemoBanner';
import { BuilderDashboardPage } from './pages/BuilderDashboardPage';
import { PublicBudgetViewPage } from './pages/PublicBudgetViewPage';
import { TractionEvidencePage } from './pages/TractionEvidencePage';
import { VendorCatalogModal } from './components/VendorCatalogModal';

export const App: React.FC = () => {
  const { initSession } = useWorkspaceStore();
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [isCatalogModalOpen, setIsCatalogModalOpen] = useState(false);

  useEffect(() => {
    initSession();
    // Iniciar siempre en Tema Claro por defecto ('Papel Técnico de Cómputo' #FAF8F5)
    document.documentElement.setAttribute('data-theme', 'light');
  }, [initSession]);

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);
    document.documentElement.setAttribute('data-theme', nextTheme);
  };

  const pathname = window.location.pathname;

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
