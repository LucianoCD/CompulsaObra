import React, { useState } from 'react';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { useComparisonStore } from '../store/useComparisonStore';
import {
  Info,
  Briefcase,
  ShoppingCart,
  Sparkles,
  BarChart3,
  LogIn,
  LogOut,
  Sun,
  Moon,
  Store,
  Layers,
  ArrowRight,
  Building2,
} from 'lucide-react';
import { AuthModal } from './AuthModal';
import { BrandLogo } from './BrandLogo';
import { UserRole } from '../types/api';

interface DemoBannerProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  currentTheme: 'light' | 'dark';
  onToggleTheme: () => void;
  onOpenCatalogs: () => void;
}

export const DemoBanner: React.FC<DemoBannerProps> = ({
  currentPath,
  onNavigate,
  currentTheme,
  onToggleTheme,
  onOpenCatalogs,
}) => {
  const { isDemo, role, workspaceName, switchMode, logout, setRole } = useWorkspaceStore();
  const vendorsCount = useComparisonStore((state) => state.vendors.length);
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  const handleRoleKeyDown = (e: React.KeyboardEvent, currentActiveRole: UserRole) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault();
      const nextRole: UserRole = currentActiveRole === 'ESTIMATOR' ? 'BUYER' : 'ESTIMATOR';
      setRole(nextRole);
    }
  };

  const handleSpaNav = (e: React.MouseEvent<HTMLAnchorElement>, path: string) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
      return;
    }
    e.preventDefault();
    onNavigate(path);
  };

  const isDashboardActive = currentPath === '/';
  const isTractionActive = currentPath.startsWith('/traccion');

  return (
    <>
      {/* 1. CABECERA GLOBAL (h: 60px, sticky top-0, z-40) */}
      <header
        role="banner"
        className="min-h-[60px] border-b border-surface-hairline bg-surface-elevated sticky top-0 z-40 transition-colors"
      >
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 min-h-[60px] flex flex-wrap items-center justify-between gap-3 py-1.5">
          {/* Marca */}
          <a
            href="/"
            onClick={(e) => handleSpaNav(e, '/')}
            className="inline-flex items-center group focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-action-focus focus-visible:outline-offset-2 rounded-control"
            aria-label="Ir al inicio de CompulsaObra"
          >
            <BrandLogo variant="full" showRegionBadge />
          </a>

          {/* Navegación Principal y Controles */}
          <nav aria-label="Navegación principal" className="flex flex-wrap items-center gap-2">
            <a
              href="/"
              onClick={(e) => handleSpaNav(e, '/')}
              aria-current={isDashboardActive ? 'page' : undefined}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control text-[13px] font-semibold border transition min-h-[38px] ${
                isDashboardActive
                  ? 'bg-action-primary/10 border-action-primary/40 text-action-primary'
                  : 'bg-surface-elevated hover:bg-surface-subtle border-surface-hairline text-content-secondary hover:text-content-primary'
              }`}
            >
              <Layers className="w-4 h-4 shrink-0" />
              <span>Presupuestar</span>
            </a>

            <button
              onClick={onOpenCatalogs}
              type="button"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control text-[13px] font-semibold bg-surface-elevated hover:bg-surface-subtle border border-surface-hairline text-content-secondary hover:text-content-primary transition min-h-[38px]"
            >
              <Store className="w-4 h-4 shrink-0 text-action-primary" />
              <span>Corralones</span>
              {vendorsCount > 0 && (
                <span className="font-mono text-xs px-1.5 py-0.2 rounded-pill bg-surface-subtle text-content-primary tabular-nums">
                  {vendorsCount}
                </span>
              )}
            </button>

            <a
              href="/traccion"
              onClick={(e) => handleSpaNav(e, '/traccion')}
              aria-current={isTractionActive ? 'page' : undefined}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control text-[13px] font-semibold border transition min-h-[38px] ${
                isTractionActive
                  ? 'bg-action-primary/10 border-action-primary/40 text-action-primary'
                  : 'bg-surface-elevated hover:bg-surface-subtle border-surface-hairline text-content-secondary hover:text-content-primary'
              }`}
            >
              <BarChart3 className="w-4 h-4 shrink-0" />
              <span>Impacto</span>
            </a>

            {/* Selector de Tema */}
            <button
              onClick={onToggleTheme}
              type="button"
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-control border border-surface-hairline bg-surface-elevated hover:bg-surface-subtle text-content-secondary hover:text-content-primary transition min-h-[38px] text-[13px] font-medium"
              aria-label="Cambiar entre modo claro y oscuro"
              title={currentTheme === 'light' ? 'Activar modo oscuro' : 'Activar modo claro'}
            >
              {currentTheme === 'light' ? (
                <>
                  <Moon className="w-4 h-4 text-content-secondary" />
                  <span className="hidden lg:inline">Oscuro</span>
                </>
              ) : (
                <>
                  <Sun className="w-4 h-4 text-amber-400" />
                  <span className="hidden lg:inline">Claro</span>
                </>
              )}
            </button>

            {/* Cuenta */}
            {isDemo ? (
              <button
                onClick={() => setIsAuthOpen(true)}
                type="button"
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-control bg-action-primary hover:bg-action-hover text-white text-[13px] font-bold transition shadow-card min-h-[38px]"
              >
                <LogIn className="w-4 h-4" />
                <span>Acceder</span>
              </button>
            ) : (
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => switchMode(true)}
                  type="button"
                  className="text-[13px] font-medium px-2.5 py-1.5 rounded-control bg-surface-subtle hover:bg-surface-canvas text-content-secondary hover:text-content-primary transition border border-surface-hairline min-h-[38px]"
                >
                  Ver ejemplos
                </button>
                <button
                  onClick={() => logout()}
                  type="button"
                  className="inline-flex items-center gap-1 text-[13px] font-semibold px-3 py-1.5 rounded-control bg-surface-elevated hover:bg-surface-subtle text-content-secondary hover:text-content-primary transition border border-surface-hairline min-h-[38px]"
                  title="Cerrar sesión"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Salir</span>
                </button>
              </div>
            )}
          </nav>
        </div>
      </header>

      {/* 2. CINTA CONTEXTUAL DE MODO DE TRABAJO (h: 44px, sticky top-[60px], z-40) */}
      {isDashboardActive && (
        <aside
          aria-label="Modo de trabajo"
          className={`border-b sticky top-[60px] z-40 transition-colors ${
            isDemo
              ? 'bg-semantic-hitlBg border-semantic-hitlBorder/50 text-semantic-hitlText'
              : 'bg-semantic-winnerBg border-surface-hairline text-semantic-winnerText'
          }`}
        >
          <div className="max-w-[1440px] mx-auto px-4 sm:px-6 min-h-[44px] py-1.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[13px]">
            {/* Estado de Sesión */}
            <div className="flex flex-wrap items-center gap-2 font-medium">
              {isDemo ? (
                <>
                  <Info className="w-4 h-4 shrink-0 text-semantic-hitlText" />
                  <span className="font-bold">
                    Modo Exploración · 3 corralones de Jujuy
                  </span>
                  <span className="text-xs opacity-90">
                    (Datos comerciales ilustrativos)
                  </span>
                </>
              ) : (
                <>
                  <Building2 className="w-4 h-4 shrink-0 text-semantic-winnerText" />
                  <span className="font-bold">Espacio de Trabajo Privado ·</span>
                  <span className="font-bold underline decoration-dotted underline-offset-4">
                    {workspaceName}
                  </span>
                </>
              )}
            </div>

            {/* Selector de Vista Presupuestador / Comprador */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold hidden md:inline">Vista:</span>
                <div
                  role="radiogroup"
                  aria-label="Vista de trabajo"
                  className="flex items-center bg-surface-elevated p-0.5 rounded-control border border-surface-hairline shadow-card"
                >
                  <button
                    role="radio"
                    type="button"
                    aria-checked={role === 'ESTIMATOR'}
                    tabIndex={role === 'ESTIMATOR' ? 0 : -1}
                    onClick={() => setRole('ESTIMATOR')}
                    onKeyDown={(e) => handleRoleKeyDown(e, 'ESTIMATOR')}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-control text-xs font-semibold transition min-h-[30px] ${
                      role === 'ESTIMATOR'
                        ? 'bg-action-primary text-white shadow-card'
                        : 'text-content-secondary hover:text-content-primary'
                    }`}
                  >
                    <Briefcase className="w-3.5 h-3.5" />
                    <span>Presupuestador</span>
                  </button>

                  <button
                    role="radio"
                    type="button"
                    aria-checked={role === 'BUYER'}
                    tabIndex={role === 'BUYER' ? 0 : -1}
                    onClick={() => setRole('BUYER')}
                    onKeyDown={(e) => handleRoleKeyDown(e, 'BUYER')}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-control text-xs font-semibold transition min-h-[30px] ${
                      role === 'BUYER'
                        ? 'bg-action-primary text-white shadow-card'
                        : 'text-content-secondary hover:text-content-primary'
                    }`}
                  >
                    <ShoppingCart className="w-3.5 h-3.5" />
                    <span>Comprador</span>
                  </button>
                </div>
              </div>

              {isDemo && (
                <button
                  onClick={() => setIsAuthOpen(true)}
                  type="button"
                  className="inline-flex items-center gap-1 px-3 py-1 rounded-control bg-surface-elevated hover:bg-surface-subtle text-action-primary border border-surface-hairline text-xs font-bold transition shadow-card min-h-[32px]"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Pasar a mi cuenta</span>
                  <ArrowRight className="w-3 h-3 ml-0.5" />
                </button>
              )}
            </div>
          </div>
        </aside>
      )}

      {/* Modal de Autenticación / Registro */}
      <AuthModal isOpen={isAuthOpen} onClose={() => setIsAuthOpen(false)} />
    </>
  );
};
