/**
 * Store global Zustand para Workspace, Sesión basada exclusivamente en cookies HttpOnly y Rol activo (H-21, H-28, H-33).
 */

import { create } from 'zustand';
import { SessionResponse, UserRole } from '../types/api';
import { apiClient } from '../services/apiClient';
import { useRequisitionStore } from './useRequisitionStore';
import { useComparisonStore } from './useComparisonStore';

interface WorkspaceState {
  workspaceId: string | null;
  workspaceName: string;
  isDemo: boolean;
  role: UserRole;
  email: string | null;
  emailVerified: boolean;
  pendingVerificationEmail: string | null;
  isLoading: boolean;
  error: string | null;

  initSession: () => Promise<void>;
  switchMode: (isDemo: boolean) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    fullName: string,
    workspaceName?: string,
    role?: UserRole
  ) => Promise<SessionResponse>;
  verifyEmail: (email: string, token: string) => Promise<SessionResponse>;
  resendVerification: (email: string) => Promise<string>;
  clearPendingVerification: () => void;
  logout: () => Promise<void>;
  setRole: (role: UserRole) => Promise<void>;
}

const applySessionToClient = (
  session: SessionResponse,
  set: (partial: Partial<WorkspaceState>) => void,
  prevWorkspaceId?: string | null
) => {
  if (prevWorkspaceId && prevWorkspaceId !== session.workspace_id) {
    useRequisitionStore.getState().resetRequisition();
    useComparisonStore.getState().resetComparison();
  }
  apiClient.setWorkspaceId(session.workspace_id);
  set({
    workspaceId: session.workspace_id,
    workspaceName: session.workspace_name,
    isDemo: session.is_demo,
    role: session.role,
    email: session.email,
    emailVerified: session.email_verified,
    pendingVerificationEmail: null,
    isLoading: false,
  });
};

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  workspaceId: null,
  workspaceName: 'Workspace Demo Jujuy',
  isDemo: true,
  role: 'ESTIMATOR',
  email: null,
  emailVerified: true,
  pendingVerificationEmail: null,
  isLoading: false,
  error: null,

  initSession: async () => {
    const prevWsId = get().workspaceId;
    try {
      set({ isLoading: true, error: null });

      try {
        const info = await apiClient.getSessionInfo();
        applySessionToClient(info, set, prevWsId);
        return;
      } catch {
        // Sin cookie HttpOnly activa: iniciar sesión Demo automáticamente
      }

      const session = await apiClient.getDemoSession();
      applySessionToClient(session, set, prevWsId);
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al inicializar sesión',
      });
    }
  },

  switchMode: async (targetIsDemo: boolean) => {
    const prevWsId = get().workspaceId;
    try {
      set({ isLoading: true, error: null });
      const currentRole = get().role;
      const session = await apiClient.switchMode(targetIsDemo, currentRole);
      applySessionToClient(session, set, prevWsId);
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al cambiar de modo',
      });
      throw err;
    }
  },

  login: async (email: string, password: string) => {
    const prevWsId = get().workspaceId;
    try {
      set({ isLoading: true, error: null });
      const session = await apiClient.login({ email, password });
      applySessionToClient(session, set, prevWsId);
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al iniciar sesión',
      });
      throw err;
    }
  },

  register: async (
    email: string,
    password: string,
    fullName: string,
    workspaceName?: string,
    role?: UserRole
  ) => {
    const prevWsId = get().workspaceId;
    try {
      set({ isLoading: true, error: null });
      const res = await apiClient.register({
        email,
        password,
        full_name: fullName,
        workspace_name: workspaceName,
        role,
      });
      if (res.authenticated && !res.verification_required) {
        applySessionToClient(res, set, prevWsId);
        return res;
      }
      set({
        pendingVerificationEmail: res.email,
        isLoading: false,
      });
      return res;
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al registrar cuenta',
      });
      throw err;
    }
  },

  verifyEmail: async (email: string, token: string) => {
    const prevWsId = get().workspaceId;
    try {
      set({ isLoading: true, error: null });
      const session = await apiClient.verifyEmail({ email, token });
      applySessionToClient(session, set, prevWsId);
      return session;
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al verificar correo',
      });
      throw err;
    }
  },

  resendVerification: async (email: string) => {
    try {
      set({ isLoading: true, error: null });
      const res = await apiClient.resendVerification(email);
      set({ isLoading: false });
      return res.message;
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al reenviar verificación',
      });
      throw err;
    }
  },

  clearPendingVerification: () => {
    set({ pendingVerificationEmail: null, error: null });
  },

  logout: async () => {
    try {
      set({ isLoading: true, error: null });
      await apiClient.logout();
    } finally {
      apiClient.setWorkspaceId(null);
      useRequisitionStore.getState().resetRequisition();
      useComparisonStore.getState().resetComparison();
      set({ isLoading: false, email: null, pendingVerificationEmail: null });
      await get().initSession();
    }
  },

  setRole: async (role: UserRole) => {
    try {
      set({ error: null });
      const res = await apiClient.updateRole(role);
      set({ role: res.role });
    } catch (err: unknown) {
      set({
        error: err instanceof Error ? err.message : 'Error al actualizar rol',
      });
    }
  },
}));
