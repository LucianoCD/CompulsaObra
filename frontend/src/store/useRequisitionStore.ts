/**
 * Store global Zustand para Requisiciones, Ingesta Multimodal y Desambiguación HITL.
 */

import { create } from 'zustand';
import {
  RequisitionDetailResponse,
  ItemClarificationResolveRequest,
} from '../types/api';
import { apiClient } from '../services/apiClient';

interface RequisitionState {
  currentRequisition: RequisitionDetailResponse | null;
  isLoading: boolean;
  error: string | null;

  ingestPreset: (presetId: string) => Promise<void>;
  ingestText: (title: string, rawText: string) => Promise<void>;
  ingestFile: (title: string, file: File) => Promise<void>;
  resolveItem: (itemId: string, payload: ItemClarificationResolveRequest) => Promise<void>;
  resetRequisition: () => void;
}

export const useRequisitionStore = create<RequisitionState>((set, get) => ({
  currentRequisition: null,
  isLoading: false,
  error: null,

  ingestPreset: async (presetId: string) => {
    try {
      set({ isLoading: true, error: null });
      const req = await apiClient.ingestRequisitionJson({
        title: `Pedido desde Preset: ${presetId}`,
        preset_id: presetId,
      });
      set({ currentRequisition: req, isLoading: false });
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al cargar preset',
      });
    }
  },

  ingestText: async (title: string, rawText: string) => {
    try {
      set({ isLoading: true, error: null });
      const req = await apiClient.ingestRequisitionJson({
        title: title || 'Pedido de Materiales',
        raw_text: rawText,
      });
      set({ currentRequisition: req, isLoading: false });
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al procesar texto',
      });
    }
  },

  ingestFile: async (title: string, file: File) => {
    try {
      set({ isLoading: true, error: null });
      const formData = new FormData();
      formData.append('title', title || 'Pedido desde Imagen');
      formData.append('image_file', file);

      const req = await apiClient.ingestRequisitionForm(formData);
      set({ currentRequisition: req, isLoading: false });
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al procesar imagen',
      });
    }
  },

  resolveItem: async (itemId: string, payload: ItemClarificationResolveRequest) => {
    const current = get().currentRequisition;
    if (!current) return;

    try {
      set({ isLoading: true, error: null });
      const updated = await apiClient.resolveItem(current.id, itemId, payload);
      set({ currentRequisition: updated, isLoading: false });
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al resolver ítem',
      });
    }
  },

  resetRequisition: () => {
    set({ currentRequisition: null, error: null });
  },
}));
