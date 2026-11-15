/**
 * Store global Zustand para Compulsa Multi-Negocio, Split Cart, Acopio y Snapshot (H-02, H-08, H-14, H-15).
 */

import { create } from 'zustand';
import {
  BudgetStrategy,
  ComparisonMatrixResponse,
  LockBudgetRequest,
  LockBudgetResponse,
  ManualVendorMatchOverride,
  PaymentModality,
  RequisitionDetailResponse,
  VendorResponse,
} from '../types/api';
import { apiClient } from '../services/apiClient';

/**
 * Determina si la matriz comparativa actual quedó desactualizada frente al pliego (H-39).
 */
export function getMatrixRequisitionStaleReason(
  matrix: ComparisonMatrixResponse | null,
  requisition: RequisitionDetailResponse | null
): string | null {
  if (
    !matrix ||
    !requisition ||
    matrix.is_locked ||
    matrix.status === 'LOCKED_BUDGET' ||
    matrix.requisition_id !== requisition.id
  ) {
    return null;
  }

  if (matrix.is_stale || matrix.status === 'STALE') {
    return (
      matrix.stale_reason ||
      'Se modificaron cantidades, unidades o especificaciones del pedido. Actualizá la comparativa antes de emitir.'
    );
  }

  if (
    matrix.requisition_version != null &&
    requisition.version != null &&
    matrix.requisition_version !== requisition.version
  ) {
    return 'El pedido cambió de versión respecto a la última comparativa. Ejecutá una nueva comparación.';
  }

  if (
    matrix.requisition_version_hash &&
    requisition.version_hash &&
    matrix.requisition_version_hash !== requisition.version_hash
  ) {
    return 'Las especificaciones, cantidades o unidades del pedido difieren de la comparativa actual.';
  }

  if (matrix.matrix_rows.length !== requisition.items.length) {
    return 'La cantidad de materiales del pedido cambió respecto a la comparativa actual.';
  }

  const sameNullableNum = (a?: number | null, b?: number | null) =>
    (a == null && b == null) || (a != null && b != null && Math.abs(a - b) <= 1e-4);

  const reqById = new Map(requisition.items.map((it) => [it.id, it]));
  for (const row of matrix.matrix_rows) {
    const reqItem = reqById.get(row.requisition_item_id);
    if (!reqItem) {
      return 'Los renglones del pedido cambiaron respecto a la comparativa actual.';
    }
    if (
      Math.abs(row.quantity - reqItem.quantity) > 1e-4 ||
      row.requested_unit.trim().toUpperCase() !== reqItem.requested_unit.trim().toUpperCase() ||
      (row.material_type ?? null) !== (reqItem.material_type ?? null) ||
      !sameNullableNum(row.diameter_mm, reqItem.diameter_mm) ||
      !sameNullableNum(row.length_m, reqItem.length_m) ||
      !sameNullableNum(row.weight_kg, reqItem.weight_kg)
    ) {
      return `Cambiaron especificaciones, cantidad o unidad de "${reqItem.requested_term}". Ejecutá una nueva comparativa para recalcular.`;
    }
  }

  return null;
}

let debounceTimer: ReturnType<typeof setTimeout> | null = null;
let latestRunSeq = 0;

interface ComparisonState {
  vendors: VendorResponse[];
  selectedVendorIds: string[];
  paymentModality: PaymentModality;
  markupPct: number;
  includeDeliveryFees: boolean;
  budgetStrategy: BudgetStrategy;
  selectedSingleVendorId: string | null;
  currentMatrix: ComparisonMatrixResponse | null;
  lockedBudget: LockBudgetResponse | null;
  isLoading: boolean;
  error: string | null;

  loadVendors: () => Promise<void>;
  toggleVendorSelection: (vendorId: string) => void;
  setPaymentModality: (modality: PaymentModality) => void;
  setMarkupPct: (markup: number) => void;
  setIncludeDeliveryFees: (include: boolean) => void;
  setBudgetStrategy: (strategy: BudgetStrategy) => void;
  setSelectedSingleVendorId: (vendorId: string | null) => void;
  runComparison: (reqId: string) => Promise<void>;
  applyMatrixOverride: (
    runId: string,
    matchId: string,
    payload: ManualVendorMatchOverride
  ) => Promise<void>;
  lockBudget: (payload?: LockBudgetRequest) => Promise<void>;
  markMatrixStale: (reason?: string) => void;
  resetComparison: () => void;
}

const scheduleDebouncedRerun = (get: () => ComparisonState) => {
  const matrix = get().currentMatrix;
  if (!matrix || get().lockedBudget) return;
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }
  debounceTimer = setTimeout(() => {
    void get().runComparison(matrix.requisition_id).catch(() => {
      // El estado de error ya fue persistido en el store
    });
  }, 250);
};

export const useComparisonStore = create<ComparisonState>((set, get) => ({
  vendors: [],
  selectedVendorIds: [],
  paymentModality: 'CASH',
  markupPct: 0.0,
  includeDeliveryFees: true,
  budgetStrategy: 'SPLIT_CART',
  selectedSingleVendorId: null,
  currentMatrix: null,
  lockedBudget: null,
  isLoading: false,
  error: null,

  loadVendors: async () => {
    try {
      set({ isLoading: true, error: null });
      const prevKnownIds = new Set(get().vendors.map((v) => v.id));
      const vendors = await apiClient.listVendors();
      const validIds = new Set(vendors.map((v) => v.id));
      const prevSelected = get().selectedVendorIds.filter((id) => validIds.has(id));
      const newlyAddedIds = vendors
        .filter((v) => !prevKnownIds.has(v.id))
        .map((v) => v.id);
      const nextSelected =
        prevSelected.length > 0
          ? Array.from(new Set([...prevSelected, ...newlyAddedIds]))
          : vendors.map((v) => v.id);
      set({
        vendors,
        selectedVendorIds: nextSelected,
        isLoading: false,
      });
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al cargar comercios',
      });
      throw err;
    }
  },

  toggleVendorSelection: (vendorId: string) => {
    const current = get().selectedVendorIds;
    let next: string[];
    if (current.includes(vendorId)) {
      if (current.length > 1) {
        next = current.filter((id) => id !== vendorId);
      } else {
        next = current;
      }
    } else {
      next = [...current, vendorId];
    }
    set({ selectedVendorIds: next });
    scheduleDebouncedRerun(get);
  },

  setPaymentModality: (paymentModality: PaymentModality) => {
    set({ paymentModality });
    scheduleDebouncedRerun(get);
  },

  setMarkupPct: (markupPct: number) => {
    set({ markupPct });
    scheduleDebouncedRerun(get);
  },

  setIncludeDeliveryFees: (includeDeliveryFees: boolean) => {
    set({ includeDeliveryFees });
    scheduleDebouncedRerun(get);
  },

  setBudgetStrategy: (budgetStrategy: BudgetStrategy) => {
    set({ budgetStrategy });
    scheduleDebouncedRerun(get);
  },

  setSelectedSingleVendorId: (selectedSingleVendorId: string | null) => {
    set({ selectedSingleVendorId });
    scheduleDebouncedRerun(get);
  },

  runComparison: async (reqId: string) => {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    const {
      selectedVendorIds,
      paymentModality,
      markupPct,
      includeDeliveryFees,
      budgetStrategy,
      selectedSingleVendorId,
      currentMatrix,
    } = get();
    if (selectedVendorIds.length === 0) {
      const msg = 'Debe seleccionar al menos un comercio para comparar';
      set({ error: msg });
      throw new Error(msg);
    }

    const requestSeq = ++latestRunSeq;
    const reuseRunId =
      currentMatrix && currentMatrix.requisition_id === reqId && currentMatrix.status !== 'LOCKED_BUDGET'
        ? currentMatrix.run_id
        : undefined;

    try {
      set({ isLoading: true, error: null });
      const matrix = await apiClient.runComparison(reqId, {
        vendor_ids: selectedVendorIds,
        payment_modality: paymentModality,
        markup_pct: markupPct,
        include_delivery_fees: includeDeliveryFees,
        budget_strategy: budgetStrategy,
        selected_single_vendor_id:
          budgetStrategy === 'SINGLE_VENDOR' ? selectedSingleVendorId : null,
        existing_run_id: reuseRunId ?? null,
        persist: true,
      });
      if (requestSeq !== latestRunSeq) {
        return;
      }
      set({ currentMatrix: matrix, isLoading: false });
    } catch (err: unknown) {
      if (requestSeq === latestRunSeq) {
        set({
          isLoading: false,
          error: err instanceof Error ? err.message : 'Error al ejecutar compulsa',
        });
      }
      throw err;
    }
  },

  applyMatrixOverride: async (runId, matchId, payload) => {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    const requestSeq = ++latestRunSeq;
    try {
      set({ isLoading: true, error: null });
      const updatedMatrix = await apiClient.overrideMatch(runId, matchId, payload);
      if (requestSeq !== latestRunSeq) {
        return;
      }
      set({ currentMatrix: updatedMatrix, isLoading: false });
    } catch (err: unknown) {
      if (requestSeq === latestRunSeq) {
        set({
          isLoading: false,
          error: err instanceof Error ? err.message : 'Error al aplicar sustitución de producto',
        });
      }
      throw err;
    }
  },

  lockBudget: async (payload?: LockBudgetRequest) => {
    const matrix = get().currentMatrix;
    if (!matrix) {
      const msg = 'No hay una compulsa activa para congelar';
      set({ error: msg });
      throw new Error(msg);
    }

    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    ++latestRunSeq;

    try {
      set({ isLoading: true, error: null });
      const effectivePayload: LockBudgetRequest = {
        accept_partial: payload?.accept_partial ?? false,
        strategy: payload?.strategy ?? get().budgetStrategy,
        selected_single_vendor_id:
          payload?.selected_single_vendor_id ??
          (get().budgetStrategy === 'SINGLE_VENDOR'
            ? get().selectedSingleVendorId ?? matrix.best_single_vendor_id ?? null
            : null),
      };
      const lockRes = await apiClient.lockBudget(matrix.run_id, effectivePayload);
      set({
        lockedBudget: lockRes,
        currentMatrix: {
          ...matrix,
          status: 'LOCKED_BUDGET',
          is_locked: true,
          budget_strategy: lockRes.budget_strategy,
          public_share_token: lockRes.public_share_token,
          snapshot_content_hash: lockRes.snapshot_content_hash,
        },
        isLoading: false,
      });
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al congelar presupuesto',
      });
      throw err;
    }
  },

  markMatrixStale: (reason?: string) => {
    const matrix = get().currentMatrix;
    if (!matrix || get().lockedBudget || matrix.is_locked || matrix.status === 'LOCKED_BUDGET') {
      return;
    }
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    set({
      currentMatrix: {
        ...matrix,
        status: 'STALE',
        is_stale: true,
        stale_reason:
          reason ||
          'El requerimiento fue modificado. Ejecutá una nueva comparación antes de congelar el presupuesto.',
      },
    });
  },

  resetComparison: () => {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    latestRunSeq++;
    set({
      currentMatrix: null,
      lockedBudget: null,
      budgetStrategy: 'SPLIT_CART',
      selectedSingleVendorId: null,
      error: null,
    });
  },
}));
