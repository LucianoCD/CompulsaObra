/**
 * Store global Zustand para Compulsa Multi-Negocio, Split Cart y Snapshot.
 */

import { create } from 'zustand';
import {
  VendorResponse,
  PaymentModality,
  ComparisonMatrixResponse,
  LockBudgetResponse,
} from '../types/api';
import { apiClient } from '../services/apiClient';

interface ComparisonState {
  vendors: VendorResponse[];
  selectedVendorIds: string[];
  paymentModality: PaymentModality;
  markupPct: number;
  includeDeliveryFees: boolean;
  currentMatrix: ComparisonMatrixResponse | null;
  lockedBudget: LockBudgetResponse | null;
  isLoading: boolean;
  error: string | null;

  loadVendors: () => Promise<void>;
  toggleVendorSelection: (vendorId: string) => void;
  setPaymentModality: (modality: PaymentModality) => void;
  setMarkupPct: (markup: number) => void;
  setIncludeDeliveryFees: (include: boolean) => void;
  runComparison: (reqId: string) => Promise<void>;
  lockBudget: () => Promise<void>;
  resetComparison: () => void;
}

export const useComparisonStore = create<ComparisonState>((set, get) => ({
  vendors: [],
  selectedVendorIds: [],
  paymentModality: 'CASH',
  markupPct: 0.0,
  includeDeliveryFees: true,
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

    const matrix = get().currentMatrix;
    if (matrix && !get().lockedBudget) {
      get().runComparison(matrix.requisition_id);
    }
  },

  setPaymentModality: (paymentModality: PaymentModality) => {
    set({ paymentModality });
    const matrix = get().currentMatrix;
    if (matrix && !get().lockedBudget) {
      get().runComparison(matrix.requisition_id);
    }
  },

  setMarkupPct: (markupPct: number) => {
    set({ markupPct });
    const matrix = get().currentMatrix;
    if (matrix && !get().lockedBudget) {
      get().runComparison(matrix.requisition_id);
    }
  },

  setIncludeDeliveryFees: (includeDeliveryFees: boolean) => {
    set({ includeDeliveryFees });
    const matrix = get().currentMatrix;
    if (matrix && !get().lockedBudget) {
      get().runComparison(matrix.requisition_id);
    }
  },

  runComparison: async (reqId: string) => {
    const { selectedVendorIds, paymentModality, markupPct, includeDeliveryFees } = get();
    if (selectedVendorIds.length === 0) {
      set({ error: 'Debe seleccionar al menos un comercio para comparar' });
      return;
    }

    try {
      set({ isLoading: true, error: null });
      const matrix = await apiClient.runComparison(reqId, {
        vendor_ids: selectedVendorIds,
        payment_modality: paymentModality,
        markup_pct: markupPct,
        include_delivery_fees: includeDeliveryFees,
      });
      set({ currentMatrix: matrix, isLoading: false });
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al ejecutar compulsa',
      });
    }
  },

  lockBudget: async () => {
    const matrix = get().currentMatrix;
    if (!matrix) return;

    try {
      set({ isLoading: true, error: null });
      const lockRes = await apiClient.lockBudget(matrix.run_id);
      set({ lockedBudget: lockRes, isLoading: false });
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al congelar presupuesto',
      });
    }
  },

  resetComparison: () => {
    set({ currentMatrix: null, lockedBudget: null, error: null });
  },
}));
