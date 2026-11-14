/**
 * Store global Zustand para Requisiciones, Ingesta Multimodal y Desambiguación HITL (H-15).
 */

import { create } from 'zustand';
import {
  RequisitionDetailResponse,
  ItemClarificationResolveRequest,
} from '../types/api';
import { apiClient } from '../services/apiClient';
import { useComparisonStore } from './useComparisonStore';

interface RequisitionState {
  currentRequisition: RequisitionDetailResponse | null;
  isLoading: boolean;
  error: string | null;

  ingestPreset: (presetId: string) => Promise<void>;
  ingestText: (title: string, rawText: string, clientName?: string) => Promise<void>;
  ingestFile: (title: string, file: File, clientName?: string) => Promise<void>;
  resolveItem: (itemId: string, payload: ItemClarificationResolveRequest) => Promise<void>;
  resetRequisition: () => void;
}

const runRequisitionRequest = async (
  set: (partial: Partial<RequisitionState>) => void,
  action: () => Promise<RequisitionDetailResponse>,
  fallbackError: string
) => {
  try {
    set({ isLoading: true, error: null });
    const req = await action();
    set({ currentRequisition: req, isLoading: false });
  } catch (err: unknown) {
    set({
      isLoading: false,
      error: err instanceof Error ? err.message : fallbackError,
    });
    throw err;
  }
};

export const useRequisitionStore = create<RequisitionState>((set, get) => ({
  currentRequisition: null,
  isLoading: false,
  error: null,

  ingestPreset: async (presetId: string) =>
    runRequisitionRequest(
      set,
      () =>
        apiClient.ingestRequisitionJson({
          title: `Pedido desde Preset: ${presetId}`,
          preset_id: presetId,
        }),
      'Error al cargar preset'
    ),

  ingestText: async (title: string, rawText: string, clientName?: string) =>
    runRequisitionRequest(
      set,
      () =>
        apiClient.ingestRequisitionJson({
          title: title || 'Pedido de Materiales',
          client_name: clientName?.trim() || null,
          raw_text: rawText,
        }),
      'Error al procesar texto'
    ),

  ingestFile: async (title: string, file: File, clientName?: string) => {
    const formData = new FormData();
    formData.append('title', title || 'Pedido desde Imagen');
    if (clientName?.trim()) {
      formData.append('client_name', clientName.trim());
    }
    formData.append('image_file', file);
    return runRequisitionRequest(
      set,
      () => apiClient.ingestRequisitionForm(formData),
      'Error al procesar imagen'
    );
  },

  resolveItem: async (itemId: string, payload: ItemClarificationResolveRequest) => {
    const current = get().currentRequisition;
    if (!current) return;
    await runRequisitionRequest(
      set,
      () => apiClient.resolveItem(current.id, itemId, payload),
      'Error al resolver ítem'
    );
    const updated = get().currentRequisition;
    if (updated && updated.id === current.id) {
      useComparisonStore
        .getState()
        .markMatrixStale(
          'Se modificaron cantidades, unidades o especificaciones del pedido. Actualizá la comparativa antes de emitir el presupuesto.'
        );
    }
  },

  resetRequisition: () => {
    set({ currentRequisition: null, error: null });
  },
}));
