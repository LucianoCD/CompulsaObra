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
  VendorResponse,
} from '../types/api';
import { apiClient } from '../services/apiClient';

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
      const vendors = await apiClient.listVendors();
      const defaultSelected = vendors.map((v) => v.id);
      set({
        vendors,
        selectedVendorIds: defaultSelected,
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
    try {
      set({ isLoading: true, error: null });
      const updatedMatrix = await apiClient.overrideMatch(runId, matchId, payload);
      set({ currentMatrix: updatedMatrix, isLoading: false });
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al aplicar sustitución de producto',
      });
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
        currentMatrix: { ...matrix, status: 'LOCKED_BUDGET' },
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
