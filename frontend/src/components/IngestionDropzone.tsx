import React, { useEffect, useState } from 'react';
import { useRequisitionStore } from '../store/useRequisitionStore';
import { DraftingCornerTicks } from './BrandLogo';
import {
  FileText,
  Upload,
  MessageSquare,
  ArrowRight,
  Loader2,
  ClipboardList,
  FileCheck2,
  Image as ImageIcon,
  CheckCircle2,
  Edit3,
  ChevronUp,
} from 'lucide-react';

export const IngestionDropzone: React.FC = () => {
  const { currentRequisition, ingestPreset, ingestText, ingestFile, isLoading, error } =
    useRequisitionStore();

  const [isExpanded, setIsExpanded] = useState(true);
  const [activeTab, setActiveTab] = useState<'presets' | 'text' | 'image'>('presets');
  const [title, setTitle] = useState('Pedido de Materiales - Obra');
  const [clientName, setClientName] = useState('');
  const [rawText, setRawText] = useState(
    '50 bolsas de cemento avellaneda\n40 barras del 8\n20 hierro del 10\n4 caño de 3/4\n5 caño PVC 40 mm'
  );
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  useEffect(() => {
    if (!currentRequisition) {
      setIsExpanded(true);
    } else {
      setIsExpanded(false);
    }
  }, [currentRequisition?.id]);

  const handlePresetClick = async (presetId: string) => {
    try {
      await ingestPreset(presetId);
      setIsExpanded(false);
    } catch {
      // Error manejado en store
    }
  };

  const handleTextSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawText.trim()) return;
    try {
      await ingestText(title, rawText, clientName);
      setIsExpanded(false);
    } catch {
      // Error manejado en store
    }
  };

  const handleFileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    try {
      await ingestFile(title, selectedFile, clientName);
      setIsExpanded(false);
    } catch {
      // Error manejado en store
    }
  };

  const handleKeyDownTextarea = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (rawText.trim()) {
        void ingestText(title, rawText, clientName)
          .then(() => setIsExpanded(false))
          .catch(() => {});
      }
    }
  };

  // Vista Colapsada tras cargar un pedido (Acordeón de 60px)
  if (currentRequisition && !isExpanded) {
    return (
      <section
        aria-label="Resumen de lista de materiales cargada"
        className="bg-surface-elevated border border-surface-hairline rounded-container px-4 sm:px-5 py-3 min-h-[60px] flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-card transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-8 w-8 rounded-control bg-semantic-winnerBg text-semantic-winnerText border border-emerald-600/25 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-[13px]">
              <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-content-secondary border border-surface-hairline">
                PASO 1 · LISTO
              </span>
              <h2 className="font-display font-bold text-content-primary truncate">
                {currentRequisition.title}
              </h2>
              {currentRequisition.client_name && (
                <span className="text-xs font-semibold text-content-secondary bg-surface-subtle px-2 py-0.5 rounded-pill border border-surface-hairline">
                  Comitente: {currentRequisition.client_name}
                </span>
              )}
            </div>
            <p className="text-xs text-content-muted mt-0.5">
              {currentRequisition.items.length} materiales detectados
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsExpanded(true)}
          className="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-control bg-surface-subtle hover:bg-surface-canvas border border-surface-hairline text-[13px] font-semibold text-content-primary transition min-h-[38px] shrink-0"
        >
          <Edit3 className="w-3.5 h-3.5 text-action-primary" />
          <span>Editar lista</span>
        </button>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="ingestion-heading"
      className="bg-surface-elevated border border-surface-hairline rounded-container p-4 sm:p-5 shadow-card transition-colors"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3.5 border-b border-surface-hairline gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-action-primary border border-surface-hairline">
              PASO 1
            </span>
            <h2
              id="ingestion-heading"
              className="text-base font-display font-bold text-content-primary"
            >
              1. Cargar lista de materiales
            </h2>
          </div>
          <p className="text-[13px] text-content-secondary mt-1">
            Elegí un ejemplo rápido, pegá tu pedido de WhatsApp o subí una foto de tu nota de obra.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
          <div
            role="tablist"
            aria-label="Formas de cargar tu pedido"
            className="flex bg-surface-subtle p-1 rounded-control border border-surface-hairline"
          >
            <button
              id="tab-presets"
              role="tab"
              type="button"
              aria-selected={activeTab === 'presets'}
              aria-controls="panel-presets"
              onClick={() => setActiveTab('presets')}
              className={`px-3 py-1.5 rounded-control text-[13px] font-medium transition ${
                activeTab === 'presets'
                  ? 'bg-surface-elevated text-content-primary font-bold shadow-card'
                  : 'text-content-secondary hover:text-content-primary'
              }`}
            >
              Ejemplos Rápidos
            </button>
            <button
              id="tab-text"
              role="tab"
              type="button"
              aria-selected={activeTab === 'text'}
              aria-controls="panel-text"
              onClick={() => setActiveTab('text')}
              className={`px-3 py-1.5 rounded-control text-[13px] font-medium transition ${
                activeTab === 'text'
                  ? 'bg-surface-elevated text-content-primary font-bold shadow-card'
                  : 'text-content-secondary hover:text-content-primary'
              }`}
            >
              Texto / WhatsApp
            </button>
            <button
              id="tab-image"
              role="tab"
              type="button"
              aria-selected={activeTab === 'image'}
              aria-controls="panel-image"
              onClick={() => setActiveTab('image')}
              className={`px-3 py-1.5 rounded-control text-[13px] font-medium transition ${
                activeTab === 'image'
                  ? 'bg-surface-elevated text-content-primary font-bold shadow-card'
                  : 'text-content-secondary hover:text-content-primary'
              }`}
            >
              Foto de Pedido
            </button>
          </div>

          {currentRequisition && (
            <button
              type="button"
              onClick={() => setIsExpanded(false)}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-control border border-surface-hairline bg-surface-subtle text-xs font-semibold text-content-secondary hover:text-content-primary min-h-[34px]"
              aria-label="Contraer panel de carga"
            >
              <ChevronUp className="w-3.5 h-3.5" />
              <span>Contraer</span>
            </button>
          )}
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="mt-3.5 p-3 bg-semantic-dangerBg border border-semantic-dangerBorder rounded-control text-[13px] text-semantic-dangerText font-medium flex items-center gap-2"
        >
          <span>{error}</span>
        </div>
      )}

      <div className="mt-4">
        {/* Panel Ejemplos Rápidos */}
        {activeTab === 'presets' && (
          <div
            id="panel-presets"
            role="tabpanel"
            aria-labelledby="tab-presets"
            className="grid grid-cols-1 md:grid-cols-3 gap-3"
          >
            <button
              onClick={() => void handlePresetClick('whatsapp_jerga_noa')}
              disabled={isLoading}
              type="button"
              className="text-left p-4 rounded-control bg-surface-subtle hover:bg-surface-canvas border border-surface-hairline hover:border-surface-strong transition group flex flex-col justify-between min-h-[144px]"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="p-1.5 rounded-control bg-action-primary/10 text-action-primary">
                    <MessageSquare className="w-4 h-4" />
                  </div>
                  <span className="text-[11px] font-semibold uppercase px-2 py-0.5 rounded-pill bg-surface-elevated text-content-muted border border-surface-hairline">
                    Ejemplo 1
                  </span>
                </div>
                <h3 className="text-[13px] font-bold text-content-primary group-hover:text-action-primary transition">
                  Pedido por WhatsApp (Jerga NOA)
                </h3>
                <p className="text-xs text-content-secondary mt-1 leading-snug">
                  &quot;50 bolsas cemento, 40 barras del 8, 20 hierro del 10 y caños&quot;.
                </p>
              </div>
              <div className="mt-3 flex items-center text-[13px] text-action-primary font-bold gap-1">
                <span>Cargar en 1 clic</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
              </div>
            </button>

            <button
              onClick={() => void handlePresetClick('manuscrito_obra')}
              disabled={isLoading}
              type="button"
              className="text-left p-4 rounded-control bg-semantic-hitlBg/50 hover:bg-semantic-hitlBg/80 border border-semantic-hitlBorder/60 hover:border-semantic-hitlBorder transition group flex flex-col justify-between min-h-[144px]"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="p-1.5 rounded-control bg-amber-500/20 text-semantic-hitlText">
                    <FileText className="w-4 h-4" />
                  </div>
                  <span className="text-[11px] font-semibold uppercase px-2 py-0.5 rounded-pill bg-surface-elevated text-semantic-hitlText border border-semantic-hitlBorder/40">
                    Ejemplo 2
                  </span>
                </div>
                <h3 className="text-[13px] font-bold text-content-primary group-hover:text-semantic-hitlText transition">
                  Manuscrito de Obra (Guardia HITL)
                </h3>
                <p className="text-xs text-content-secondary mt-1 leading-snug">
                  &quot;20 barra del 8 y 4 caño de 3/4&quot; (pide definir material antes de cotizar).
                </p>
              </div>
              <div className="mt-3 flex items-center text-[13px] text-semantic-hitlText font-bold gap-1">
                <span>Cargar y revisar medidas</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
              </div>
            </button>

            <button
              onClick={() => void handlePresetClick('computo_tecnico')}
              disabled={isLoading}
              type="button"
              className="text-left p-4 rounded-control bg-surface-subtle hover:bg-surface-canvas border border-surface-hairline hover:border-surface-strong transition group flex flex-col justify-between min-h-[144px]"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="p-1.5 rounded-control bg-semantic-infoBg text-semantic-infoText">
                    <ClipboardList className="w-4 h-4" />
                  </div>
                  <span className="text-[11px] font-semibold uppercase px-2 py-0.5 rounded-pill bg-surface-elevated text-content-muted border border-surface-hairline">
                    Ejemplo 3
                  </span>
                </div>
                <h3 className="text-[13px] font-bold text-content-primary group-hover:text-semantic-infoText transition">
                  Cómputo de Obra Completo
                </h3>
                <p className="text-xs text-content-secondary mt-1 leading-snug">
                  Lista con caños cloacales de 110 mm, 40 mm y hierros aletados.
                </p>
              </div>
              <div className="mt-3 flex items-center text-[13px] text-semantic-infoText font-bold gap-1">
                <span>Cargar lista completa</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
              </div>
            </button>
          </div>
        )}

        {/* Panel Texto / WhatsApp */}
        {activeTab === 'text' && (
          <form
            id="panel-text"
            role="tabpanel"
            aria-labelledby="tab-text"
            onSubmit={handleTextSubmit}
            className="space-y-3.5"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor="req-title"
                  className="block text-[13px] font-semibold text-content-secondary mb-1"
                >
                  Título del Pedido u Obra:
                </label>
                <input
                  id="req-title"
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full h-10 bg-surface-subtle border border-surface-hairline focus:border-surface-strong rounded-control px-3 text-[13px] text-content-primary focus:outline-none"
                  placeholder="Ej. Casa Barrio Los Perales - Lote 4"
                />
              </div>
              <div>
                <label
                  htmlFor="req-client"
                  className="block text-[13px] font-semibold text-content-secondary mb-1"
                >
                  Cliente o Comitente (Opcional):
                </label>
                <input
                  id="req-client"
                  type="text"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  className="w-full h-10 bg-surface-subtle border border-surface-hairline focus:border-surface-strong rounded-control px-3 text-[13px] text-content-primary focus:outline-none"
                  placeholder="Ej. Ing. Juan Pérez / Constructora Jujuy"
                />
              </div>
            </div>

            <div>
              <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                <label
                  htmlFor="req-raw-text"
                  className="block text-[13px] font-semibold text-content-secondary"
                >
                  Lista de materiales o mensaje de WhatsApp:
                </label>
                <span className="text-xs text-content-muted">
                  Atajo:{' '}
                  <kbd className="px-1.5 py-0.5 rounded bg-surface-subtle border border-surface-hairline font-mono text-[11px]">
                    Ctrl
                  </kbd>{' '}
                  +{' '}
                  <kbd className="px-1.5 py-0.5 rounded bg-surface-subtle border border-surface-hairline font-mono text-[11px]">
                    Enter
                  </kbd>
                </span>
              </div>
              <textarea
                id="req-raw-text"
                rows={5}
                required
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                onKeyDown={handleKeyDownTextarea}
                className="w-full bg-surface-subtle border border-surface-hairline focus:border-surface-strong rounded-control p-3 text-[13px] font-mono text-content-primary focus:outline-none leading-relaxed"
                placeholder="Pegá aquí tu lista con cantidades y medidas (ej. 20 barra del 8 y 4 caño de 3/4)..."
              />
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={isLoading || !rawText.trim()}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-control bg-action-primary hover:bg-action-hover text-white font-bold text-[13px] shadow-card transition disabled:opacity-55 disabled:cursor-not-allowed min-h-[44px]"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Leyendo materiales y medidas...</span>
                  </>
                ) : (
                  <>
                    <FileCheck2 className="w-4 h-4" />
                    <span>Cargar y Revisar Lista</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}

        {/* Panel Foto de Pedido */}
        {activeTab === 'image' && (
          <form
            id="panel-image"
            role="tabpanel"
            aria-labelledby="tab-image"
            onSubmit={handleFileSubmit}
            className="space-y-3.5"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor="req-img-title"
                  className="block text-[13px] font-semibold text-content-secondary mb-1"
                >
                  Título del Pedido u Obra:
                </label>
                <input
                  id="req-img-title"
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full h-10 bg-surface-subtle border border-surface-hairline focus:border-surface-strong rounded-control px-3 text-[13px] text-content-primary focus:outline-none"
                  placeholder="Ej. Casa Barrio Los Perales - Lote 4"
                />
              </div>
              <div>
                <label
                  htmlFor="req-img-client"
                  className="block text-[13px] font-semibold text-content-secondary mb-1"
                >
                  Cliente o Comitente (Opcional):
                </label>
                <input
                  id="req-img-client"
                  type="text"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  className="w-full h-10 bg-surface-subtle border border-surface-hairline focus:border-surface-strong rounded-control px-3 text-[13px] text-content-primary focus:outline-none"
                  placeholder="Ej. Ing. Juan Pérez / Constructora Jujuy"
                />
              </div>
            </div>

            <div className="relative group border border-dashed border-surface-strong/70 rounded-control p-6 text-center bg-surface-subtle/50 transition">
              <DraftingCornerTicks />
              <div className="w-10 h-10 rounded-full bg-surface-elevated border border-surface-hairline flex items-center justify-center mx-auto mb-2 text-action-primary">
                <ImageIcon className="w-5 h-5" />
              </div>
              <p className="text-[13px] font-semibold text-content-primary mb-1">
                Subí una foto de tu libreta de obra, remito o planilla escrita a mano
              </p>
              <p className="text-xs text-content-muted mb-3">
                Formatos admitidos: JPEG, PNG o WebP (máximo 10 MB)
              </p>

              <input
                id="file-upload-input"
                type="file"
                accept="image/*"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                className="sr-only"
              />
              <label
                htmlFor="file-upload-input"
                className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-control bg-surface-elevated hover:bg-surface-subtle border border-surface-strong text-content-primary text-[13px] font-bold transition shadow-card cursor-pointer min-h-[44px]"
              >
                <Upload className="w-4 h-4 text-action-primary" />
                <span>{selectedFile ? 'Cambiar imagen seleccionada' : 'Seleccionar Imagen'}</span>
              </label>

              {selectedFile && (
                <div className="mt-3 inline-block px-3 py-1 bg-surface-elevated border border-surface-hairline rounded-control text-xs font-mono text-content-secondary">
                  Imagen lista: <strong>{selectedFile.name}</strong> (
                  {Math.round(selectedFile.size / 1024)} KB)
                </div>
              )}
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={isLoading || !selectedFile}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-control bg-action-primary hover:bg-action-hover text-white font-bold text-[13px] shadow-card transition disabled:opacity-55 disabled:cursor-not-allowed min-h-[44px]"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Leyendo materiales de la imagen...</span>
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    <span>Procesar Fotografía</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
};
