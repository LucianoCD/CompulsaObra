import React, { useEffect, useRef, useState } from 'react';
import { useComparisonStore } from '../store/useComparisonStore';
import { apiClient } from '../services/apiClient';
import { DraftingCornerTicks } from './BrandLogo';
import { CatalogImportSummary, ColumnMapping } from '../types/api';
import {
  Store,
  Upload,
  Download,
  CheckCircle2,
  X,
  Plus,
  Clock,
  AlertTriangle,
  Loader2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

interface VendorCatalogModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const MAX_CATALOG_BYTES = 12 * 1024 * 1024;

export const VendorCatalogModal: React.FC<VendorCatalogModalProps> = ({ isOpen, onClose }) => {
  const { vendors, loadVendors } = useComparisonStore();

  const [activeTab, setActiveTab] = useState<'import' | 'new_vendor'>(() =>
    vendors.length === 0 ? 'new_vendor' : 'import'
  );
  const [selectedVendorId, setSelectedVendorId] = useState<string>(vendors[0]?.id || '');
  const [file, setFile] = useState<File | null>(null);
  const [showOptionalCols, setShowOptionalCols] = useState(false);
  const [mapping, setMapping] = useState<ColumnMapping>({
    sku_col: 'sku',
    desc_col: 'descripcion',
    price_cash_col: 'precio_contado',
    price_list_col: 'precio_lista',
    unit_col: 'unidad',
    brand_col: 'marca',
    category_col: 'categoria',
  });

  const [importSummary, setImportSummary] = useState<CatalogImportSummary | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Formulario nuevo corralón
  const [newName, setNewName] = useState('');
  const [newLocality, setNewLocality] = useState('San Salvador de Jujuy');
  const [newPhone, setNewPhone] = useState('');
  const [newDiscount, setNewDiscount] = useState('5');
  const [newDelivery, setNewDelivery] = useState('15000');
  const [acopioEnabled, setAcopioEnabled] = useState(true);
  const [acopioDownPayment, setAcopioDownPayment] = useState('80');
  const [acopioFreezeDays, setAcopioFreezeDays] = useState('45');
  const [acopioMaxWithdrawalDays, setAcopioMaxWithdrawalDays] = useState('90');
  const [acopioMinNoticeHours, setAcopioMinNoticeHours] = useState('24');

  const dialogRef = useRef<HTMLDialogElement | null>(null);

  useEffect(() => {
    if (isOpen && dialogRef.current) {
      if (!dialogRef.current.open) dialogRef.current.showModal();
      if (vendors.length === 0) {
        setActiveTab('new_vendor');
      }
    } else if (!isOpen && dialogRef.current?.open) {
      dialogRef.current.close();
    }
  }, [isOpen, vendors.length]);

  useEffect(() => {
    if (vendors.length > 0 && !selectedVendorId) {
      setSelectedVendorId(vendors[0].id);
    }
  }, [vendors, selectedVendorId]);

  if (!isOpen) return null;

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] || null;
    if (!selected) {
      setFile(null);
      return;
    }
    if (selected.size > MAX_CATALOG_BYTES) {
      setErrorMessage('El archivo supera el tamaño máximo permitido de 12 MB.');
      setFile(null);
      e.target.value = '';
      return;
    }
    setErrorMessage(null);
    setFile(selected);
  };

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !selectedVendorId) return;

    try {
      setIsUploading(true);
      setErrorMessage(null);
      const summary = await apiClient.importCatalog(selectedVendorId, file, JSON.stringify(mapping));
      setImportSummary(summary);
      await loadVendors();
      setIsUploading(false);
    } catch (err: unknown) {
      setIsUploading(false);
      setErrorMessage(err instanceof Error ? err.message : 'Error al importar lista de precios');
    }
  };

  const handleCreateVendor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;

    try {
      setIsUploading(true);
      setErrorMessage(null);
      const created = await apiClient.createVendor({
        name: newName,
        locality: newLocality,
        whatsapp_phone: newPhone || null,
        cash_discount_pct: parseFloat(newDiscount) || 0,
        estimate_delivery_fee_ars: parseFloat(newDelivery) || 0,
        acopio_config: {
          enabled: acopioEnabled,
          min_down_payment_pct: parseFloat(acopioDownPayment) || 100,
          freeze_days: parseInt(acopioFreezeDays, 10) || 30,
          max_withdrawal_days: parseInt(acopioMaxWithdrawalDays, 10) || 90,
          min_notice_hours: parseInt(acopioMinNoticeHours, 10) || 24,
        },
      });
      await loadVendors();
      setSelectedVendorId(created.id);
      setActiveTab('import');
      setIsUploading(false);
    } catch (err: unknown) {
      setIsUploading(false);
      setErrorMessage(err instanceof Error ? err.message : 'Error al registrar corralón');
    }
  };

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="catalog-modal-title"
      onClose={onClose}
      className="fixed inset-0 m-auto w-full max-w-2xl bg-surface-elevated border border-surface-hairline rounded-container shadow-modal p-0 text-content-primary backdrop:bg-black/50 backdrop:backdrop-blur-sm focus:outline-none"
    >
      <div className="flex flex-col max-h-[90vh]">
        {/* Cabecera */}
        <div className="p-4 sm:p-5 border-b border-surface-hairline flex items-center justify-between bg-surface-subtle">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-control bg-action-primary/10 text-action-primary">
              <Store className="w-5 h-5" />
            </div>
            <div>
              <h2 id="catalog-modal-title" className="text-base font-display font-bold text-content-primary">
                Corralones y Listas de Precios
              </h2>
              <p className="text-xs text-content-secondary mt-0.5">
                Registrá comercios de tu zona y cargá sus listas de precios desde Excel o CSV.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            type="button"
            className="p-2 rounded-control hover:bg-surface-elevated text-content-secondary hover:text-content-primary transition min-h-[38px] min-w-[38px] flex items-center justify-center"
            aria-label="Cerrar ventana"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Pestañas */}
        <div role="tablist" className="flex border-b border-surface-hairline bg-surface-canvas px-4">
          <button
            id="tab-catalog-import"
            role="tab"
            aria-selected={activeTab === 'import'}
            onClick={() => setActiveTab('import')}
            type="button"
            className={`py-3 px-4 text-[13px] font-bold border-b-2 transition ${
              activeTab === 'import'
                ? 'border-action-primary text-action-primary'
                : 'border-transparent text-content-secondary hover:text-content-primary'
            }`}
          >
            Importar Lista de Precios (.xlsx / .csv)
          </button>
          <button
            id="tab-catalog-new-vendor"
            role="tab"
            aria-selected={activeTab === 'new_vendor'}
            onClick={() => setActiveTab('new_vendor')}
            type="button"
            className={`py-3 px-4 text-[13px] font-bold border-b-2 transition ${
              activeTab === 'new_vendor'
                ? 'border-action-primary text-action-primary'
                : 'border-transparent text-content-secondary hover:text-content-primary'
            }`}
          >
            + Registrar Nuevo Corralón
          </button>
        </div>

        {/* Cuerpo */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {errorMessage && (
            <div
              role="alert"
              className="p-3 bg-semantic-dangerBg border border-semantic-dangerBorder rounded-control text-[13px] text-semantic-dangerText font-medium flex items-center gap-2"
            >
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {activeTab === 'import' && (
            <form onSubmit={handleImport} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor="vendor-select"
                    className="block text-[13px] font-semibold text-content-secondary mb-1.5"
                  >
                    Corralón a actualizar:
                  </label>
                  <select
                    id="vendor-select"
                    value={selectedVendorId}
                    onChange={(e) => setSelectedVendorId(e.target.value)}
                    className="w-full h-10 bg-surface-subtle border border-surface-hairline rounded-control px-3 text-[13px] text-content-primary focus:outline-none"
                  >
                    {vendors.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} ({v.locality})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <span className="block text-[13px] font-semibold text-content-secondary mb-1.5">
                    Archivo modelo de ejemplo:
                  </span>
                  <a
                    href={apiClient.getSampleTemplateUrl()}
                    download="plantilla_materiales_ejemplo.csv"
                    className="flex items-center justify-center gap-1.5 w-full h-10 bg-surface-subtle hover:bg-surface-canvas border border-surface-hairline text-content-primary rounded-control px-3 text-[13px] font-semibold transition"
                  >
                    <Download className="w-4 h-4 text-action-primary" />
                    <span>Descargar Plantilla CSV</span>
                  </a>
                </div>
              </div>

              {/* Selector de archivo accesible (44px) */}
              <div className="space-y-1.5">
                <span className="block text-[13px] font-semibold text-content-secondary">
                  Planilla de precios (.xlsx, .xls o .csv, máximo 12 MB):
                </span>
                <input
                  id="catalog-file-input"
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleFileSelect}
                  className="sr-only"
                />
                <div className="relative group flex flex-wrap items-center gap-3 p-4 rounded-control bg-surface-subtle border border-dashed border-surface-strong/70">
                  <DraftingCornerTicks />
                  <label
                    htmlFor="catalog-file-input"
                    className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-control bg-surface-elevated hover:bg-surface-canvas border border-surface-strong text-content-primary text-[13px] font-bold transition shadow-card cursor-pointer min-h-[44px]"
                  >
                    <Upload className="w-4 h-4 text-action-primary" />
                    <span>{file ? 'Cambiar archivo' : 'Seleccionar planilla'}</span>
                  </label>
                  <span className="text-[13px] text-content-secondary font-mono truncate max-w-full">
                    {file
                      ? `${file.name} (${Math.max(1, Math.round(file.size / 1024))} KB)`
                      : 'Ningún archivo seleccionado'}
                  </span>
                </div>
              </div>

              {/* Nombres de columnas */}
              <div className="bg-surface-subtle p-3.5 rounded-control border border-surface-hairline space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold text-content-primary uppercase tracking-wide">
                    Nombres de columnas en tu planilla
                  </span>
                  <button
                    type="button"
                    aria-expanded={showOptionalCols}
                    onClick={() => setShowOptionalCols((prev) => !prev)}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-action-primary hover:underline"
                  >
                    <span>
                      {showOptionalCols
                        ? 'Ocultar columnas opcionales'
                        : 'Mostrar columnas opcionales (unidad, marca, categoría)'}
                    </span>
                    {showOptionalCols ? (
                      <ChevronUp className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-[13px]">
                  <div>
                    <label htmlFor="map-sku-col" className="block text-xs text-content-muted font-semibold mb-1">
                      Columna Código / SKU
                    </label>
                    <input
                      id="map-sku-col"
                      type="text"
                      value={mapping.sku_col}
                      onChange={(e) => setMapping({ ...mapping, sku_col: e.target.value })}
                      className="w-full h-9 bg-surface-elevated border border-surface-hairline rounded-control px-2.5 text-content-primary text-[13px]"
                    />
                  </div>
                  <div>
                    <label htmlFor="map-desc-col" className="block text-xs text-content-muted font-semibold mb-1">
                      Columna Descripción
                    </label>
                    <input
                      id="map-desc-col"
                      type="text"
                      value={mapping.desc_col}
                      onChange={(e) => setMapping({ ...mapping, desc_col: e.target.value })}
                      className="w-full h-9 bg-surface-elevated border border-surface-hairline rounded-control px-2.5 text-content-primary text-[13px]"
                    />
                  </div>
                  <div>
                    <label htmlFor="map-cash-col" className="block text-xs text-content-muted font-semibold mb-1">
                      Columna Contado
                    </label>
                    <input
                      id="map-cash-col"
                      type="text"
                      value={mapping.price_cash_col}
                      onChange={(e) => setMapping({ ...mapping, price_cash_col: e.target.value })}
                      className="w-full h-9 bg-surface-elevated border border-surface-hairline rounded-control px-2.5 text-content-primary text-[13px]"
                    />
                  </div>
                  <div>
                    <label htmlFor="map-list-col" className="block text-xs text-content-muted font-semibold mb-1">
                      Columna Lista
                    </label>
                    <input
                      id="map-list-col"
                      type="text"
                      value={mapping.price_list_col || ''}
                      onChange={(e) => setMapping({ ...mapping, price_list_col: e.target.value })}
                      className="w-full h-9 bg-surface-elevated border border-surface-hairline rounded-control px-2.5 text-content-primary text-[13px]"
                    />
                  </div>
                </div>

                {showOptionalCols && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-2 border-t border-surface-hairline text-[13px]">
                    <div>
                      <label htmlFor="map-unit-col" className="block text-xs text-content-muted font-semibold mb-1">
                        Columna Unidad
                      </label>
                      <input
                        id="map-unit-col"
                        type="text"
                        value={mapping.unit_col || ''}
                        onChange={(e) => setMapping({ ...mapping, unit_col: e.target.value })}
                        className="w-full h-9 bg-surface-elevated border border-surface-hairline rounded-control px-2.5 text-content-primary text-[13px]"
                      />
                    </div>
                    <div>
                      <label htmlFor="map-brand-col" className="block text-xs text-content-muted font-semibold mb-1">
                        Columna Marca
                      </label>
                      <input
                        id="map-brand-col"
                        type="text"
                        value={mapping.brand_col || ''}
                        onChange={(e) => setMapping({ ...mapping, brand_col: e.target.value })}
                        className="w-full h-9 bg-surface-elevated border border-surface-hairline rounded-control px-2.5 text-content-primary text-[13px]"
                      />
                    </div>
                    <div>
                      <label htmlFor="map-category-col" className="block text-xs text-content-muted font-semibold mb-1">
                        Columna Rubro / Categoría
                      </label>
                      <input
                        id="map-category-col"
                        type="text"
                        value={mapping.category_col || ''}
                        onChange={(e) => setMapping({ ...mapping, category_col: e.target.value })}
                        className="w-full h-9 bg-surface-elevated border border-surface-hairline rounded-control px-2.5 text-content-primary text-[13px]"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Resumen de carga */}
              {importSummary && (
                <div className="p-3.5 bg-semantic-winnerBg text-semantic-winnerText border border-emerald-600/25 rounded-control text-[13px] space-y-2">
                  <div className="flex items-center gap-1.5 font-bold">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span>¡Catálogo Versión {importSummary.version_number} Importado con Éxito!</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 pt-1 text-xs font-mono">
                    <div>
                      Total filas: <strong className="tabular-nums">{importSummary.total_rows}</strong>
                    </div>
                    <div>
                      Nuevas o editadas:{' '}
                      <strong className="tabular-nums">{importSummary.new_or_updated_rows}</strong>
                    </div>
                    <div>
                      Sin cambios:{' '}
                      <strong className="tabular-nums">{importSummary.unchanged_skipped_rows}</strong>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-surface-hairline">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-control border border-surface-hairline bg-surface-subtle text-content-secondary hover:text-content-primary text-[13px] font-semibold min-h-[40px]"
                >
                  Cerrar
                </button>
                <button
                  type="submit"
                  disabled={isUploading || !file || !selectedVendorId}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-control bg-action-primary hover:bg-action-hover text-white font-bold text-[13px] shadow-card transition disabled:opacity-55 min-h-[40px]"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Cargando lista de precios...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4" />
                      <span>Importar Lista</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}

          {activeTab === 'new_vendor' && (
            <form onSubmit={handleCreateVendor} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div>
                  <label
                    htmlFor="vendor-name-input"
                    className="block text-[13px] font-semibold text-content-secondary mb-1"
                  >
                    Nombre del Corralón:
                  </label>
                  <input
                    id="vendor-name-input"
                    type="text"
                    required
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="Ej. Corralón Norte Jujuy"
                    className="w-full h-10 bg-surface-subtle border border-surface-hairline rounded-control px-3 text-[13px] text-content-primary"
                  />
                </div>
                <div>
                  <label
                    htmlFor="vendor-locality-input"
                    className="block text-[13px] font-semibold text-content-secondary mb-1"
                  >
                    Localidad:
                  </label>
                  <input
                    id="vendor-locality-input"
                    type="text"
                    required
                    value={newLocality}
                    onChange={(e) => setNewLocality(e.target.value)}
                    placeholder="San Salvador de Jujuy / Palpalá / Perico"
                    className="w-full h-10 bg-surface-subtle border border-surface-hairline rounded-control px-3 text-[13px] text-content-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
                <div>
                  <label
                    htmlFor="vendor-phone-input"
                    className="block text-[13px] font-semibold text-content-secondary mb-1"
                  >
                    Teléfono WhatsApp:
                  </label>
                  <input
                    id="vendor-phone-input"
                    type="text"
                    value={newPhone}
                    onChange={(e) => setNewPhone(e.target.value)}
                    placeholder="+543884..."
                    className="w-full h-10 bg-surface-subtle border border-surface-hairline rounded-control px-3 text-[13px] text-content-primary"
                  />
                </div>
                <div>
                  <label
                    htmlFor="vendor-discount-input"
                    className="block text-[13px] font-semibold text-content-secondary mb-1"
                  >
                    Descuento Contado (%):
                  </label>
                  <input
                    id="vendor-discount-input"
                    type="number"
                    min="0"
                    max="100"
                    step="0.5"
                    value={newDiscount}
                    onChange={(e) => setNewDiscount(e.target.value)}
                    className="w-full h-10 bg-surface-subtle border border-surface-hairline rounded-control px-3 text-[13px] text-content-primary font-mono tabular-nums"
                  />
                </div>
                <div>
                  <label
                    htmlFor="vendor-delivery-input"
                    className="block text-[13px] font-semibold text-content-secondary mb-1"
                  >
                    Flete Estimado ($):
                  </label>
                  <input
                    id="vendor-delivery-input"
                    type="number"
                    min="0"
                    step="100"
                    value={newDelivery}
                    onChange={(e) => setNewDelivery(e.target.value)}
                    className="w-full h-10 bg-surface-subtle border border-surface-hairline rounded-control px-3 text-[13px] text-content-primary font-mono tabular-nums"
                  />
                </div>
              </div>

              {/* Condiciones de Acopio */}
              <div className="p-3.5 bg-surface-subtle rounded-control border border-surface-hairline space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-content-primary flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-action-primary" />
                    Condiciones de Acopio de Materiales
                  </span>
                  <label
                    htmlFor="vendor-acopio-enabled"
                    className="flex items-center gap-2 text-[13px] text-content-secondary font-semibold cursor-pointer select-none"
                  >
                    <input
                      id="vendor-acopio-enabled"
                      type="checkbox"
                      checked={acopioEnabled}
                      onChange={(e) => setAcopioEnabled(e.target.checked)}
                      className="rounded border-surface-strong text-action-primary focus:ring-action-focus w-4 h-4"
                    />
                    <span>Habilitar Acopio</span>
                  </label>
                </div>

                {acopioEnabled && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs pt-1">
                    <div>
                      <label
                        htmlFor="vendor-acopio-downpayment"
                        className="block text-xs text-content-muted font-semibold mb-1"
                      >
                        Anticipo requerido (%)
                      </label>
                      <input
                        id="vendor-acopio-downpayment"
                        type="number"
                        min="0"
                        max="100"
                        value={acopioDownPayment}
                        onChange={(e) => setAcopioDownPayment(e.target.value)}
                        className="w-full h-9 bg-surface-elevated border border-surface-hairline rounded-control px-2.5 text-[13px] text-content-primary font-mono tabular-nums"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="vendor-acopio-freezedays"
                        className="block text-xs text-content-muted font-semibold mb-1"
                      >
                        Días precio fijo
                      </label>
                      <input
                        id="vendor-acopio-freezedays"
                        type="number"
                        min="1"
                        value={acopioFreezeDays}
                        onChange={(e) => setAcopioFreezeDays(e.target.value)}
                        className="w-full h-9 bg-surface-elevated border border-surface-hairline rounded-control px-2.5 text-[13px] text-content-primary font-mono tabular-nums"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="vendor-acopio-withdrawaldays"
                        className="block text-xs text-content-muted font-semibold mb-1"
                      >
                        Plazo máx. retiro (días)
                      </label>
                      <input
                        id="vendor-acopio-withdrawaldays"
                        type="number"
                        min="1"
                        value={acopioMaxWithdrawalDays}
                        onChange={(e) => setAcopioMaxWithdrawalDays(e.target.value)}
                        className="w-full h-9 bg-surface-elevated border border-surface-hairline rounded-control px-2.5 text-[13px] text-content-primary font-mono tabular-nums"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="vendor-acopio-noticehours"
                        className="block text-xs text-content-muted font-semibold mb-1"
                      >
                        Aviso previo (horas)
                      </label>
                      <input
                        id="vendor-acopio-noticehours"
                        type="number"
                        min="0"
                        value={acopioMinNoticeHours}
                        onChange={(e) => setAcopioMinNoticeHours(e.target.value)}
                        className="w-full h-9 bg-surface-elevated border border-surface-hairline rounded-control px-2.5 text-[13px] text-content-primary font-mono tabular-nums"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-surface-hairline">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-control border border-surface-hairline bg-surface-subtle text-content-secondary hover:text-content-primary text-[13px] font-semibold min-h-[40px]"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={isUploading}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-control bg-action-primary hover:bg-action-hover text-white font-bold text-[13px] shadow-card transition min-h-[40px]"
                >
                  <Plus className="w-4 h-4" />
                  <span>Guardar Corralón</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </dialog>
  );
};
