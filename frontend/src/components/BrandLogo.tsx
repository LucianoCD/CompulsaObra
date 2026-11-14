import React from 'react';

export type BrandLogoVariant = 'full' | 'compact' | 'seal';

export interface BrandLogoProps {
  /** Variante visual según jerarquía del contexto */
  variant?: BrandLogoVariant;
  /** Muestra la píldora geográfica en cabeceras principales */
  showRegionBadge?: boolean;
  /** Clases adicionales para el contenedor raíz */
  className?: string;
}

/**
 * Imagotipo "Escuadra y Cotejo" de CompulsaObra.
 * El SVG permanece oculto a lectores de pantalla (aria-hidden) para que
 * el wordmark continuo o el aria-label del enlace gobiernen la accesibilidad.
 */
export const BrandLogo: React.FC<BrandLogoProps> = ({
  variant = 'full',
  showRegionBadge = false,
  className = '',
}) => {
  if (variant === 'seal') {
    return (
      <svg
        viewBox="0 0 32 32"
        className={`h-6 w-6 shrink-0 ${className}`.trim()}
        role="img"
        aria-hidden="true"
        focusable="false"
      >
        <path
          d="M 24.2 7.5 H 7.5 V 24.5 H 24.2"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <line
          x1="12.2"
          y1="13"
          x2="24.2"
          y2="13"
          stroke="currentColor"
          strokeWidth="2.6"
          strokeLinecap="round"
        />
        <line
          x1="12.2"
          y1="19"
          x2="17"
          y2="19"
          stroke="currentColor"
          strokeWidth="2.6"
          strokeLinecap="round"
        />
        <circle cx="23.3" cy="19" r="2.2" fill="currentColor" />
      </svg>
    );
  }

  const isFull = variant === 'full';
  const markSizeClass = isFull ? 'h-9 w-9' : 'h-8 w-8';
  const wordmarkSizeClass = isFull ? 'text-base sm:text-[18px]' : 'text-base';

  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`.trim()}>
      <span
        className={`${markSizeClass} inline-flex shrink-0 items-center justify-center rounded-control shadow-card transition-transform duration-150 group-active:scale-[0.98] motion-reduce:transition-none motion-reduce:group-active:scale-100`}
      >
        <svg
          viewBox="0 0 32 32"
          className="h-full w-full"
          role="img"
          aria-hidden="true"
          focusable="false"
        >
          <rect
            x="0"
            y="0"
            width="32"
            height="32"
            rx="7"
            className="fill-brand-markBg group-hover:fill-action-hover transition-colors duration-150 motion-reduce:transition-none"
          />
          <path
            d="M 24.2 7.5 H 7.5 V 24.5 H 24.2"
            fill="none"
            stroke="var(--brand-mark-fg)"
            strokeWidth="2.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <line
            x1="12.2"
            y1="13"
            x2="24.2"
            y2="13"
            stroke="var(--brand-mark-fg)"
            strokeWidth="2.6"
            strokeLinecap="round"
          />
          <line
            x1="12.2"
            y1="19"
            x2="17"
            y2="19"
            stroke="var(--brand-mark-accent)"
            strokeWidth="2.6"
            strokeLinecap="round"
            className="transition-transform duration-150 group-hover:translate-x-[2px] motion-reduce:transition-none motion-reduce:group-hover:translate-x-0"
          />
          <circle cx="23.3" cy="19" r="2.2" fill="var(--brand-mark-accent)" />
        </svg>
      </span>

      <span className="inline-flex items-center gap-2">
        <span
          className={`font-display ${wordmarkSizeClass} tracking-[-0.025em] leading-[1.1]`}
        >
          <span className="font-extrabold text-content-primary">Compulsa</span>
          <span className="font-semibold text-content-secondary">Obra</span>
        </span>
        {isFull && showRegionBadge && (
          <span className="hidden sm:inline-block text-xs font-medium px-2 py-0.5 rounded-pill bg-surface-subtle text-content-secondary border border-surface-hairline">
            NOA · Jujuy
          </span>
        )}
      </span>
    </span>
  );
};

const CORNER_POSITIONS = [
  'top-2 left-2 border-t-2 border-l-2',
  'top-2 right-2 border-t-2 border-r-2',
  'bottom-2 left-2 border-b-2 border-l-2',
  'bottom-2 right-2 border-b-2 border-r-2',
] as const;

/**
 * Retículas de cota arquitectónica (10×10 px) para esquinas de zonas de carga.
 */
export const DraftingCornerTicks: React.FC = () => (
  <>
    {CORNER_POSITIONS.map((posClass) => (
      <span
        key={posClass}
        aria-hidden="true"
        className={`pointer-events-none absolute w-2.5 h-2.5 ${posClass} border-action-primary/45 group-hover:border-action-primary group-focus-within:border-action-primary transition-colors motion-reduce:transition-none`}
      />
    ))}
  </>
);
