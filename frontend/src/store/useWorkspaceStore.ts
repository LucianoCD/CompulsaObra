/**
 * Store global Zustand para Workspace, Sesión Demo y Rol activo.
 */

import { create } from 'zustand';
import { UserRole } from '../types/api';
import { apiClient } from '../services/apiClient';

const STORAGE_TOKEN_KEY = 'compulsa_access_token';
const STORAGE_WS_KEY = 'compulsa_workspace_id';

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
  setRole: (role: UserRole) => Promise<void>;
}

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
      const savedToken = localStorage.getItem(STORAGE_TOKEN_KEY);
      const savedWsId = localStorage.getItem(STORAGE_WS_KEY);

      if (savedToken) {
        apiClient.setToken(savedToken);
        if (savedWsId) apiClient.setWorkspaceId(savedWsId);
        try {
          const info = await apiClient.getSessionInfo();
          set({
            workspaceId: info.workspace_id,
            workspaceName: info.workspace_name,
            isDemo: info.is_demo,
            role: info.role,
            token: savedToken,
            isLoading: false,
          });
          return;
        } catch {
          // Token expirado o revocado: limpiar y fallback a sesión demo
          localStorage.removeItem(STORAGE_TOKEN_KEY);
          localStorage.removeItem(STORAGE_WS_KEY);
        }
      }

      const session = await apiClient.getDemoSession();
      apiClient.setToken(session.access_token);
      apiClient.setWorkspaceId(session.workspace_id);
      localStorage.setItem(STORAGE_TOKEN_KEY, session.access_token);
      localStorage.setItem(STORAGE_WS_KEY, session.workspace_id);

      set({
        workspaceId: session.workspace_id,
        workspaceName: session.workspace_name,
        isDemo: session.is_demo,
        role: session.role,
        token: session.access_token,
        isLoading: false,
      });
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
      apiClient.setToken(session.access_token);
      apiClient.setWorkspaceId(session.workspace_id);
      localStorage.setItem(STORAGE_TOKEN_KEY, session.access_token);
      localStorage.setItem(STORAGE_WS_KEY, session.workspace_id);

      set({
        workspaceId: session.workspace_id,
        workspaceName: session.workspace_name,
        isDemo: session.is_demo,
        role: session.role,
        token: session.access_token,
        isLoading: false,
      });
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al cambiar de modo',
      });
    }
  },

  login: async (email: string, password: string) => {
    try {
      set({ isLoading: true, error: null });
      const session = await apiClient.login({ email, password });
      apiClient.setToken(session.access_token);
      apiClient.setWorkspaceId(session.workspace_id);
      localStorage.setItem(STORAGE_TOKEN_KEY, session.access_token);
      localStorage.setItem(STORAGE_WS_KEY, session.workspace_id);

      set({
        workspaceId: session.workspace_id,
        workspaceName: session.workspace_name,
        isDemo: session.is_demo,
        role: session.role,
        token: session.access_token,
        isLoading: false,
      });
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
      apiClient.setToken(session.access_token);
      apiClient.setWorkspaceId(session.workspace_id);
      localStorage.setItem(STORAGE_TOKEN_KEY, session.access_token);
      localStorage.setItem(STORAGE_WS_KEY, session.workspace_id);

      set({
        workspaceId: session.workspace_id,
        workspaceName: session.workspace_name,
        isDemo: session.is_demo,
        role: session.role,
        token: session.access_token,
        isLoading: false,
      });
    } catch (err: unknown) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Error al registrar cuenta',
      });
      throw err;
    }
  },

  setRole: async (role: UserRole) => {
    try {
      const res = await apiClient.updateRole(role);
      if (res.access_token) {
        apiClient.setToken(res.access_token);
        localStorage.setItem(STORAGE_TOKEN_KEY, res.access_token);
      }
      set({ role, token: res.access_token || get().token });
    } catch (err: unknown) {
      set({
        error: err instanceof Error ? err.message : 'Error al actualizar rol',
      });
    }
  },
}));

