import React, { useState } from 'react';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import {
  AlertTriangle,
  Briefcase,
  ShoppingCart,
  Sparkles,
  Building2,
  LogIn,
  Sun,
  Moon,
  Store,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { AuthModal } from './AuthModal';
import { UserRole } from '../types/api';

interface DemoBannerProps {
  currentTheme: 'light' | 'dark';
  onToggleTheme: () => void;
  onOpenCatalogs: () => void;
}

export const DemoBanner: React.FC<DemoBannerProps> = ({
  currentTheme,
  onToggleTheme,
  onOpenCatalogs,
}) => {
  const { isDemo, role, workspaceName, switchMode, setRole } = useWorkspaceStore();
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  const handleRoleKeyDown = (e: React.KeyboardEvent, currentActiveRole: UserRole) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault();
      const nextRole: UserRole = currentActiveRole === 'ESTIMATOR' ? 'BUYER' : 'ESTIMATOR';
      setRole(nextRole);
    }
  };

  return (
    <>
      {/* 1. BARRA GLOBAL DE SISTEMA (h: 56px, border-bottom: 1px solid hairline) */}
      <header
        role="banner"
        className="h-14 border-b border-surface-hairline bg-surface-elevated sticky top-0 z-40 transition-colors"
      >
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 h-full flex items-center justify-between gap-4">
          {/* Identidad y Región */}
          <div className="flex items-center gap-3">
            <a
              href="/"
              className="flex items-center gap-2.5 group focus:outline-none focus-visible:ring-2 focus-visible:ring-action-focus rounded"
              aria-label="Ir al inicio de CompulsaObra"
            >
              <div className="h-8 w-8 rounded-control bg-action-primary text-white flex items-center justify-center font-display font-extrabold text-sm tracking-tight shadow-sm">
                CO
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="font-display font-bold text-content-primary tracking-tight text-base sm:text-lg">
                    CompulsaObra
                  </span>
                  <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded-control bg-surface-subtle text-content-secondary border border-surface-hairline">
                    NOA v0.1
                  </span>
                </div>
              </div>
            </a>
          </div>

          {/* Navegación Principal y Herramientas */}
          <nav aria-label="Navegación principal de la plataforma" className="flex items-center gap-2 sm:gap-3">
            <a
              href="/"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control text-xs font-semibold bg-surface-subtle border border-surface-hairline text-content-primary hover:border-surface-strong transition"
            >
              <Layers className="w-3.5 h-3.5 text-action-primary" />
              <span className="hidden sm:inline">Consola de</span> Compulsa
            </a>

            <button
              onClick={onOpenCatalogs}
              type="button"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control text-xs font-medium bg-surface-elevated hover:bg-surface-subtle border border-surface-hairline text-content-secondary hover:text-content-primary transition"
            >
              <Store className="w-3.5 h-3.5" />
              <span>Catálogos</span>
            </button>

            <a
              href="/traccion"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control text-xs font-medium bg-surface-elevated hover:bg-surface-subtle border border-surface-hairline text-content-secondary hover:text-content-primary transition"
            >
              <Building2 className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Métricas</span>
              <span className="font-mono text-[11px]">/traccion</span>
            </a>

            {/* Conmutador de Tema Sol / Luna */}
            <button
              onClick={onToggleTheme}
              type="button"
              className="p-2 rounded-control border border-surface-hairline bg-surface-elevated hover:bg-surface-subtle text-content-secondary hover:text-content-primary transition focus-visible:ring-2 focus-visible:ring-action-focus"
              aria-label={currentTheme === 'light' ? 'Cambiar a Tema Pizarra Oscura' : 'Cambiar a Tema Papel Técnico'}
              title={currentTheme === 'light' ? 'Modo Pizarra Oscura' : 'Modo Papel Técnico'}
            >
              {currentTheme === 'light' ? (
                <Moon className="w-4 h-4 text-content-secondary" />
              ) : (
                <Sun className="w-4 h-4 text-amber-400" />
              )}
            </button>

            {/* Acceso a Cuenta */}
            {isDemo ? (
              <button
                onClick={() => setIsAuthOpen(true)}
                type="button"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control bg-surface-subtle hover:bg-surface-strong/20 border border-surface-hairline text-xs font-semibold text-content-primary transition"
              >
                <LogIn className="w-3.5 h-3.5 text-action-primary" />
                <span>Acceder</span>
              </button>
            ) : (
              <button
                onClick={() => switchMode(true)}
                type="button"
                className="text-xs px-2.5 py-1 rounded-control bg-surface-subtle hover:bg-surface-strong/20 text-content-secondary transition border border-surface-hairline"
              >
                Volver a Demo
              </button>
            )}
          </nav>
        </div>
      </header>

      {/* 2. CINTA DE COMANDO CONTEXTUAL: ESTADO DE WORKSPACE Y ROL (h: 40px) */}
      <aside
        aria-label="Estado de espacio de trabajo y rol activo"
        className={`border-b transition-colors ${
          isDemo
            ? 'bg-semantic-hitlBg border-semantic-hitlBorder text-semantic-hitlText'
            : 'bg-semantic-winnerBg border-surface-hairline text-semantic-winnerText'
        }`}
      >
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-1.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
          {/* Insignia de Estado */}
          <div className="flex items-center gap-2 font-medium">
            {isDemo ? (
              <>
                <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600 dark:text-amber-400" />
                <span className="font-bold uppercase tracking-wide">
                  [MODO DEMO DATOS COMERCIALES ILUSTRATIVOS]
                </span>
                <span className="hidden md:inline text-[11px] opacity-90">
                  — 3 corralones semilla cargados (El Pórtico, Cuyaya, Sanitarios Palpalá).
                </span>
              </>
            ) : (
              <>
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="font-bold uppercase tracking-wide">
                  [ESPACIO REAL AUDITADO]
                </span>
                <span className="text-[11px] font-mono">({workspaceName})</span>
              </>
            )}
          </div>

          {/* Selector de Rol ESTIMATOR vs BUYER y CTA Espacio Real */}
          <div className="flex items-center gap-3">
            <div
              role="radiogroup"
              aria-label="Seleccionar perfil de trabajo"
              className="flex items-center bg-surface-elevated p-0.5 rounded-control border border-surface-hairline shadow-sm"
            >
              <button
                role="radio"
                aria-checked={role === 'ESTIMATOR'}
                tabIndex={role === 'ESTIMATOR' ? 0 : -1}
                onClick={() => setRole('ESTIMATOR')}
                onKeyDown={(e) => handleRoleKeyDown(e, 'ESTIMATOR')}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-control text-xs font-semibold transition ${
                  role === 'ESTIMATOR'
                    ? 'bg-action-primary text-white shadow-sm'
                    : 'text-content-secondary hover:text-content-primary'
                }`}
              >
                <Briefcase className="w-3.5 h-3.5" />
                <span>Presupuestador</span>
              </button>

              <button
                role="radio"
                aria-checked={role === 'BUYER'}
                tabIndex={role === 'BUYER' ? 0 : -1}
                onClick={() => setRole('BUYER')}
                onKeyDown={(e) => handleRoleKeyDown(e, 'BUYER')}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-control text-xs font-semibold transition ${
                  role === 'BUYER'
                    ? 'bg-action-primary text-white shadow-sm'
                    : 'text-content-secondary hover:text-content-primary'
                }`}
              >
                <ShoppingCart className="w-3.5 h-3.5" />
                <span>Comprador</span>
              </button>
            </div>

            {isDemo && (
              <button
                onClick={() => setIsAuthOpen(true)}
                type="button"
                className="inline-flex items-center gap-1 px-3 py-1 rounded-control bg-surface-elevated hover:bg-surface-subtle text-action-primary border border-surface-hairline text-xs font-bold transition shadow-sm"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Pasar a Espacio Real</span>
                <ArrowRight className="w-3 h-3 ml-0.5" />
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* Modal de Autenticación / Registro */}
      <AuthModal isOpen={isAuthOpen} onClose={() => setIsAuthOpen(false)} />
    </>
  );
};
