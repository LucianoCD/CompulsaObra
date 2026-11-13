/**
 * Store global Zustand para Workspace, Sesión HttpOnly/Demo y Rol activo (H-21).
 */

import { create } from 'zustand';
import { SessionResponse, UserRole } from '../types/api';
import { apiClient } from '../services/apiClient';

interface WorkspaceState {
  workspaceId: string | null;
  workspaceName: string;
  isDemo: boolean;
  role: UserRole;
  token: string | null;
  isLoading: boolean;
  error: string | null;

  initSession: () => Promise<void>;
  switchMode: (isDemo: boolean) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string, workspaceName?: string, role?: UserRole) => Promise<void>;
  logout: () => Promise<void>;
  setRole: (role: UserRole) => Promise<void>;
}

const applySessionToClient = (
  session: SessionResponse,
  set: (partial: Partial<WorkspaceState>) => void
) => {
  apiClient.setToken(session.access_token);
  apiClient.setWorkspaceId(session.workspace_id);
  set({
    workspaceId: session.workspace_id,
    workspaceName: session.workspace_name,
    isDemo: session.is_demo,
    role: session.role,
    token: session.access_token,
    isLoading: false,
  });
};

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  workspaceId: null,
  workspaceName: 'Workspace Demo Jujuy',
  isDemo: true,
  role: 'ESTIMATOR',
  token: null,
  isLoading: false,
  error: null,

  initSession: async () => {
    try {
      set({ isLoading: true, error: null });

      try {
        const info = await apiClient.getSessionInfo();
        apiClient.setWorkspaceId(info.workspace_id);
        set({
          workspaceId: info.workspace_id,
          workspaceName: info.workspace_name,
          isDemo: info.is_demo,
          role: info.role,
          token: get().token,
          isLoading: false,
        });
        return;
      } catch {
        // Sin cookie HttpOnly activa: iniciar sesión Demo automáticamente
      }

      const session = await apiClient.getDemoSession();
      applySessionToClient(session, set);
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al inicializar sesión',
      });
    }
  },

  switchMode: async (targetIsDemo: boolean) => {
    try {
      set({ isLoading: true, error: null });
      const currentRole = get().role;
      const session = await apiClient.switchMode(targetIsDemo, currentRole);
      applySessionToClient(session, set);
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al cambiar de modo',
      });
      throw err;
    }
  },

  login: async (email: string, password: string) => {
    try {
      set({ isLoading: true, error: null });
      const session = await apiClient.login({ email, password });
      applySessionToClient(session, set);
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al iniciar sesión',
      });
      throw err;
    }
  },

  register: async (email: string, password: string, fullName: string, workspaceName?: string, role?: UserRole) => {
    try {
      set({ isLoading: true, error: null });
      const session = await apiClient.register({
        email,
        password,
        full_name: fullName,
        workspace_name: workspaceName,
        role,
      });
      applySessionToClient(session, set);
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al registrar cuenta',
      });
      throw err;
    }
  },

  logout: async () => {
    try {
      set({ isLoading: true, error: null });
      await apiClient.logout();
    } finally {
      apiClient.setToken(null);
      apiClient.setWorkspaceId(null);
      set({ token: null, isLoading: false });
      await get().initSession();
    }
  },

  setRole: async (role: UserRole) => {
    try {
      const res = await apiClient.updateRole(role);
      if (res.access_token) {
        apiClient.setToken(res.access_token);
      }
      set({ role, token: res.access_token || get().token });
    } catch (err: unknown) {
      set({
        error: err instanceof Error ? err.message : 'Error al actualizar rol',
      });
    }
  },
}));
