/**
 * Cliente HTTP tipado centralizado con gestión de token y workspace_id.
 */

import {
  SessionResponse,
  RegisterRequest,
  LoginRequest,
  RoleUpdateResponse,
  VendorResponse,
  VendorCreateRequest,
  CatalogImportSummary,
  VendorProductResponse,
  RequisitionDetailResponse,
  RequisitionIngestRequest,
  ItemClarificationResolveRequest,
  ComparisonMatrixResponse,
  RunComparisonRequest,
  ManualVendorMatchOverride,
  LockBudgetRequest,
  LockBudgetResponse,
  PublicClientBudgetResponse,
  BudgetStrategy,
  TractionMetricsResponse,
  UserRole,
} from '../types/api';

const BASE_URL = '/api/v1';

class ApiClient {
  private token: string | null = null;
  private workspaceId: string | null = null;

  public setToken(token: string | null) {
    this.token = token;
  }

  public setWorkspaceId(workspaceId: string | null) {
    this.workspaceId = workspaceId;
  }

  private getHeaders(customHeaders: Record<string, string> = {}): Record<string, string> {
    const headers: Record<string, string> = {
      ...customHeaders,
    };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    if (this.workspaceId) {
      headers['X-Workspace-Id'] = this.workspaceId;
    }
    return headers;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers = this.getHeaders(
      (options.headers as Record<string, string>) || {}
    );

    const response = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      credentials: 'include',
      headers,
    });

    if (!response.ok) {
      let errorMessage = `Error HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorJson = await response.json();
        if (errorJson?.error?.message) {
          errorMessage = errorJson.error.message;
        } else if (errorJson?.detail) {
          errorMessage = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fallback a statusText
      }
      throw new Error(errorMessage);
    }

    return response.json() as Promise<T>;
  }

  // --- Auth & Sesión ---
  public async getDemoSession(): Promise<SessionResponse> {
    return this.request<SessionResponse>('/auth/demo-session', {
      method: 'POST',
    });
  }

  public async register(payload: RegisterRequest): Promise<SessionResponse> {
    return this.request<SessionResponse>('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  public async login(payload: LoginRequest): Promise<SessionResponse> {
    return this.request<SessionResponse>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  public async getSessionInfo(): Promise<{ workspace_id: string; workspace_name: string; is_demo: boolean; role: UserRole }> {
    return this.request('/auth/me', {
      method: 'GET',
    });
  }

  public async logout(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/auth/logout', {
      method: 'POST',
    });
  }

  public async switchMode(isDemo: boolean, role: UserRole = 'ESTIMATOR'): Promise<SessionResponse> {
    return this.request<SessionResponse>('/auth/switch-mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_demo: isDemo, role }),
    });
  }

  public async updateRole(role: UserRole): Promise<RoleUpdateResponse> {
    return this.request<RoleUpdateResponse>('/auth/role', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    });
  }

  // --- Vendors & Catálogos ---
  public async listVendors(): Promise<VendorResponse[]> {
    return this.request<VendorResponse[]>('/vendors');
  }

  public async createVendor(payload: VendorCreateRequest): Promise<VendorResponse> {
    return this.request<VendorResponse>('/vendors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  public async getVendorProducts(vendorId: string): Promise<VendorProductResponse[]> {
    return this.request<VendorProductResponse[]>(`/vendors/${vendorId}/products`);
  }

  public async importCatalog(
    vendorId: string,
    file: File,
    mappingJson: string
  ): Promise<CatalogImportSummary> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('mapping_json', mappingJson);

    const headers = this.getHeaders();
    delete headers['Content-Type']; // Permite que el navegador establezca multipart/form-data con boundary

    const response = await fetch(`${BASE_URL}/vendors/${vendorId}/catalogs/import`, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err?.error?.message || err?.detail || 'Error al importar catálogo');
    }

    return response.json();
  }

  public getSampleTemplateUrl(): string {
    return `${BASE_URL}/vendors/sample-template/download`;
  }

  // --- Requisiciones & HITL ---
  public async ingestRequisitionForm(formData: FormData): Promise<RequisitionDetailResponse> {
    const headers = this.getHeaders();
    delete headers['Content-Type'];

    const response = await fetch(`${BASE_URL}/requisitions/ingest`, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err?.error?.message || err?.detail || 'Error al procesar el pedido');
    }

    return response.json();
  }

  public async ingestRequisitionJson(payload: RequisitionIngestRequest): Promise<RequisitionDetailResponse> {
    return this.request<RequisitionDetailResponse>('/requisitions/ingest-json', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  public async getRequisition(reqId: string): Promise<RequisitionDetailResponse> {
    return this.request<RequisitionDetailResponse>(`/requisitions/${reqId}`);
  }

  public async resolveItem(
    reqId: string,
    itemId: string,
    payload: ItemClarificationResolveRequest
  ): Promise<RequisitionDetailResponse> {
    return this.request<RequisitionDetailResponse>(
      `/requisitions/${reqId}/items/${itemId}/resolve`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    );
  }

  // --- Compulsa & Snapshot ---
  public async runComparison(
    reqId: string,
    payload: RunComparisonRequest
  ): Promise<ComparisonMatrixResponse> {
    return this.request<ComparisonMatrixResponse>(`/requisitions/${reqId}/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  public async getComparison(runId: string): Promise<ComparisonMatrixResponse> {
    return this.request<ComparisonMatrixResponse>(`/comparisons/${runId}`);
  }

  public async overrideMatch(
    runId: string,
    matchId: string,
    payload: ManualVendorMatchOverride
  ): Promise<ComparisonMatrixResponse> {
    return this.request<ComparisonMatrixResponse>(`/comparisons/${runId}/matches/${matchId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  public async lockBudget(runId: string, payload: LockBudgetRequest = {}): Promise<LockBudgetResponse> {
    return this.request<LockBudgetResponse>(`/comparisons/${runId}/lock-budget`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  public getPdfUrl(
    runId: string,
    mode: 'comparison' | 'client_budget' = 'comparison',
    strategy: BudgetStrategy = 'SPLIT_CART',
    singleVendorId?: string | null
  ): string {
    const params = new URLSearchParams({ mode, strategy });
    if (singleVendorId) {
      params.set('single_vendor_id', singleVendorId);
    }
    return `${BASE_URL}/comparisons/${runId}/pdf?${params.toString()}`;
  }

  public async downloadPdfBlob(
    runId: string,
    mode: 'comparison' | 'client_budget' = 'comparison',
    strategy: BudgetStrategy = 'SPLIT_CART',
    singleVendorId?: string | null
  ): Promise<Blob> {
    const url = this.getPdfUrl(runId, mode, strategy, singleVendorId);
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      let detail = `Error HTTP ${response.status} al descargar PDF`;
      try {
        const errJson = await response.json();
        detail = errJson?.detail || errJson?.error?.message || detail;
      } catch {
        // Sin cuerpo JSON
      }
      throw new Error(detail);
    }
    return response.blob();
  }

  public async triggerPdfDownload(
    runId: string,
    mode: 'comparison' | 'client_budget' = 'comparison',
    strategy: BudgetStrategy = 'SPLIT_CART',
    singleVendorId?: string | null
  ): Promise<void> {
    const blob = await this.downloadPdfBlob(runId, mode, strategy, singleVendorId);
    const objectUrl = URL.createObjectURL(blob);
    try {
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = `compulsa_${mode}_${runId.slice(0, 8)}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } finally {
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    }
  }

  // --- Público y Tracción ---
  public async getPublicComparison(shareToken: string): Promise<PublicClientBudgetResponse> {
    return this.request<PublicClientBudgetResponse>(`/public/comparisons/${shareToken}?mode=client_budget`);
  }

  public async getTractionMetrics(): Promise<TractionMetricsResponse> {
    return this.request<TractionMetricsResponse>('/public/traction');
  }
}

export const apiClient = new ApiClient();
