import React, { useState } from 'react';
import { useRequisitionStore } from '../store/useRequisitionStore';
import {
  FileText,
  Upload,
  MessageSquare,
  ArrowRight,
  Loader2,
  Cpu,
  FileCheck2,
  Image as ImageIcon,
} from 'lucide-react';

export const IngestionDropzone: React.FC = () => {
  const { ingestPreset, ingestText, ingestFile, isLoading, error } = useRequisitionStore();
  const [activeTab, setActiveTab] = useState<'presets' | 'text' | 'image'>('presets');
  const [title, setTitle] = useState('Pedido de Materiales - Obra');
  const [clientName, setClientName] = useState('');
  const [rawText, setRawText] = useState(
    '50 bolsas de cemento avellaneda\n40 barras del 8\n20 hierro del 10\n4 caño de 3/4\n5 caño PVC 40 mm'
  );
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawText.trim()) return;
    void ingestText(title, rawText).catch(() => {});
  };

  const handleFileSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    void ingestFile(title, selectedFile).catch(() => {});
  };

  const handleKeyDownTextarea = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (rawText.trim()) {
        void ingestText(title, rawText).catch(() => {});
      }
    }
  };

  return (
    <section
      aria-labelledby="ingestion-heading"
      className="bg-surface-elevated border border-surface-hairline rounded-container p-4 sm:p-5 transition-colors"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3.5 border-b border-surface-hairline gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-action-primary border border-surface-hairline">
              PASO 01
            </span>
            <h2 id="ingestion-heading" className="text-sm sm:text-base font-display font-bold text-content-primary">
              Ingesta Multimodal y Normalización Dimensional
            </h2>
          </div>
          <p className="text-xs text-content-secondary mt-1">
            Procesa pliegos manuscritos, mensajes de WhatsApp o carga presets instantáneos calibrados para el NOA.
          </p>
        </div>

        {/* Selector de Pestañas con Roles Accesibles */}
        <div
          role="tablist"
          aria-label="Modalidades de carga de pliego"
          className="flex bg-surface-subtle p-1 rounded-control border border-surface-hairline self-start sm:self-auto"
        >
          <button
            role="tab"
            aria-selected={activeTab === 'presets'}
            onClick={() => setActiveTab('presets')}
            className={`px-3 py-1.5 rounded-control text-xs font-medium transition ${
              activeTab === 'presets'
                ? 'bg-surface-elevated text-content-primary font-bold shadow-sm'
                : 'text-content-secondary hover:text-content-primary'
            }`}
          >
            Presets Rápidos
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'text'}
            onClick={() => setActiveTab('text')}
            className={`px-3 py-1.5 rounded-control text-xs font-medium transition ${
              activeTab === 'text'
                ? 'bg-surface-elevated text-content-primary font-bold shadow-sm'
                : 'text-content-secondary hover:text-content-primary'
            }`}
          >
            Texto / WhatsApp
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'image'}
            onClick={() => setActiveTab('image')}
            className={`px-3 py-1.5 rounded-control text-xs font-medium transition ${
              activeTab === 'image'
                ? 'bg-surface-elevated text-content-primary font-bold shadow-sm'
                : 'text-content-secondary hover:text-content-primary'
            }`}
          >
            Foto Manuscrita
          </button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="mt-3.5 p-3 bg-action-danger/10 border border-action-danger/30 rounded-control text-xs text-action-danger font-medium flex items-center gap-2"
        >
          <span>{error}</span>
        </div>
      )}

      {/* Contenido de Ingesta */}
      <div className="mt-4">
        {/* Pestaña Presets */}
        {activeTab === 'presets' && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <button
              onClick={() => { void ingestPreset('whatsapp_jerga_noa').catch(() => {}); }}
              disabled={isLoading}
              type="button"
              className="text-left p-3.5 rounded-control bg-surface-subtle hover:bg-surface-elevated border border-surface-hairline hover:border-surface-strong transition group flex flex-col justify-between min-h-[140px]"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="p-1.5 rounded-control bg-action-primary/10 text-action-primary">
                    <MessageSquare className="w-4 h-4" />
                  </div>
                  <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded-control bg-surface-elevated text-content-muted border border-surface-hairline">
                    Preset 1
                  </span>
                </div>
                <h3 className="text-xs font-bold text-content-primary group-hover:text-action-primary transition">
                  WhatsApp con Jerga NOA
                </h3>
                <p className="text-[11px] text-content-secondary mt-1 leading-snug">
                  "50 bolsas cemento, 40 barras del 8, 20 hierro del 10 y caños".
                </p>
              </div>
              <div className="mt-3 flex items-center text-xs text-action-primary font-semibold gap-1">
                <span>Cargar en 1 clic</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
              </div>
            </button>

            <button
              onClick={() => { void ingestPreset('manuscrito_obra').catch(() => {}); }}
              disabled={isLoading}
              type="button"
              className="text-left p-3.5 rounded-control bg-semantic-hitlBg/40 hover:bg-semantic-hitlBg/70 border border-semantic-hitlBorder/60 hover:border-semantic-hitlBorder transition group flex flex-col justify-between min-h-[140px]"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="p-1.5 rounded-control bg-amber-500/20 text-amber-700 dark:text-amber-400">
                    <FileText className="w-4 h-4" />
                  </div>
                  <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded-control bg-surface-elevated text-content-muted border border-surface-hairline">
                    Preset 2 (E2E-01)
                  </span>
                </div>
                <h3 className="text-xs font-bold text-content-primary group-hover:text-amber-700 dark:group-hover:text-amber-400 transition">
                  Manuscrito de Obra (Guardia HITL)
                </h3>
                <p className="text-[11px] text-content-secondary mt-1 leading-snug">
                  "20 barra del 8 y 4 caño de 3/4" (detecta atributo faltante).
                </p>
              </div>
              <div className="mt-3 flex items-center text-xs text-amber-700 dark:text-amber-400 font-bold gap-1">
                <span>Probar Desambiguación</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
              </div>
            </button>

            <button
              onClick={() => { void ingestPreset('computo_tecnico').catch(() => {}); }}
              disabled={isLoading}
              type="button"
              className="text-left p-3.5 rounded-control bg-surface-subtle hover:bg-surface-elevated border border-surface-hairline hover:border-surface-strong transition group flex flex-col justify-between min-h-[140px]"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="p-1.5 rounded-control bg-blue-500/10 text-blue-600 dark:text-blue-400">
                    <Cpu className="w-4 h-4" />
                  </div>
                  <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded-control bg-surface-elevated text-content-muted border border-surface-hairline">
                    Preset 3
                  </span>
                </div>
                <h3 className="text-xs font-bold text-content-primary group-hover:text-blue-600 dark:group-hover:text-blue-400 transition">
                  Cómputo Técnico Completo
                </h3>
                <p className="text-[11px] text-content-secondary mt-1 leading-snug">
                  Pliego con caños cloacales 110mm, 40mm y hierros aletados.
                </p>
              </div>
              <div className="mt-3 flex items-center text-xs text-blue-600 dark:text-blue-400 font-semibold gap-1">
                <span>Cargar Pliego Técnico</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
              </div>
            </button>
          </div>
        )}

        {/* Pestaña Texto Libre / WhatsApp */}
        {activeTab === 'text' && (
          <form onSubmit={handleTextSubmit} className="space-y-3.5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label htmlFor="req-title" className="block text-xs font-semibold text-content-secondary mb-1">
                  Título del Pedido u Obra:
                </label>
                <input
                  id="req-title"
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-surface-subtle border border-surface-hairline focus:border-surface-strong rounded-control px-3 py-1.5 text-xs text-content-primary focus:outline-none"
                  placeholder="Ej. Casa Barrio Los Perales - Lote 4"
                />
              </div>
              <div>
                <label htmlFor="req-client" className="block text-xs font-semibold text-content-secondary mb-1">
                  Cliente o Comitente (Opcional):
                </label>
                <input
                  id="req-client"
                  type="text"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  className="w-full bg-surface-subtle border border-surface-hairline focus:border-surface-strong rounded-control px-3 py-1.5 text-xs text-content-primary focus:outline-none"
                  placeholder="Ej. Ing. Juan Pérez / Constructora Jujuy"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label htmlFor="req-raw-text" className="block text-xs font-semibold text-content-secondary">
                  Texto del Pedido o Mensaje de WhatsApp:
                </label>
                <span className="text-[10px] text-content-muted font-mono">
                  Presiona <kbd className="px-1 py-0.5 rounded bg-surface-subtle border border-surface-hairline">Ctrl</kbd> + <kbd className="px-1 py-0.5 rounded bg-surface-subtle border border-surface-hairline">Enter</kbd> para procesar
                </span>
              </div>
              <textarea
                id="req-raw-text"
                rows={5}
                required
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                onKeyDown={handleKeyDownTextarea}
                className="w-full bg-surface-subtle border border-surface-hairline focus:border-surface-strong rounded-control p-3 text-xs font-mono text-content-primary focus:outline-none leading-relaxed"
                placeholder="Pegar aquí la lista con cantidades y medidas (ej. 20 barra del 8 y 4 caño de 3/4)..."
              />
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={isLoading || !rawText.trim()}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-control bg-action-primary hover:bg-action-hover text-white font-semibold text-xs shadow-sm transition disabled:opacity-50 min-h-[40px]"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Normalizando unidades y jerga NOA...</span>
                  </>
                ) : (
                  <>
                    <FileCheck2 className="w-4 h-4" />
                    <span>Extraer y Normalizar Materiales</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}

        {/* Pestaña Foto Manuscrita con Alternativa Accesible a Drag-and-Drop (WCAG 2.5.7 & 2.5.8) */}
        {activeTab === 'image' && (
          <form onSubmit={handleFileSubmit} className="space-y-3.5">
            <div className="border border-dashed border-surface-strong/70 rounded-control p-6 text-center bg-surface-subtle/50 transition">
              <div className="w-10 h-10 rounded-full bg-surface-elevated border border-surface-hairline flex items-center justify-center mx-auto mb-2 text-action-primary">
                <ImageIcon className="w-5 h-5" />
              </div>
              <p className="text-xs font-semibold text-content-primary mb-1">
                Sube una fotografía de remito, libreta de obra o plano de cómputo
              </p>
              <p className="text-[11px] text-content-muted mb-3">
                Formatos compatibles: JPEG, PNG o WebP (límite máximo 10 MB)
              </p>

              {/* Input de archivo nativo oculto pero disparado por botón de 44px (WCAG 2.5.7 y 2.5.8) */}
              <input
                id="file-upload-input"
                type="file"
                accept="image/*"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                className="sr-only"
              />
              <label
                htmlFor="file-upload-input"
                className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-control bg-surface-elevated hover:bg-surface-subtle border border-surface-strong text-content-primary text-xs font-bold transition shadow-sm cursor-pointer min-h-[44px]"
              >
                <Upload className="w-4 h-4 text-action-primary" />
                <span>{selectedFile ? 'Cambiar archivo seleccionado' : 'Explorar y Seleccionar Imagen'}</span>
              </label>

              {selectedFile && (
                <div className="mt-3 inline-block px-3 py-1 bg-surface-elevated border border-surface-hairline rounded-control text-xs font-mono text-content-secondary">
                  Archivo cargado: <strong>{selectedFile.name}</strong> ({Math.round(selectedFile.size / 1024)} KB)
                </div>
              )}
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={isLoading || !selectedFile}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-control bg-action-primary hover:bg-action-hover text-white font-semibold text-xs shadow-sm transition disabled:opacity-50 min-h-[40px]"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Extrayendo con IA Multimodal...</span>
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
