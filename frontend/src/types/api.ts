/**
 * Tipos TypeScript de CompulsaObra espejados 1:1 con backend/app/schemas/
 * Estricto: cero uso de any.
 */

export type CompletenessStatus = 'complete' | 'missing_critical_attribute' | 'user_resolved';
export type PaymentModality = 'CASH' | 'LIST' | 'ACOPIO';
export type MatchStatus = 'EXACT_MATCH' | 'AMBIGUOUS_CANDIDATES' | 'OUT_OF_STOCK' | 'NOT_CARRIED';
export type UserRole = 'BUYER' | 'ESTIMATOR' | 'ADMIN';

export interface PhysicalDimensions {
  diameter_inch?: string | null;
  diameter_mm?: number | null;
  length_m?: number | null;
  weight_kg?: number | null;
  material_type?: string | null;
  completeness: CompletenessStatus;
}

export interface NormalizedItemDraft {
  line_order: number;
  raw_line: string;
  requested_term: string;
  quantity: number;
  requested_unit: string;
  diameter_inch?: string | null;
  diameter_mm?: number | null;
  length_m?: number | null;
  weight_kg?: number | null;
  material_type?: string | null;
  completeness: CompletenessStatus;
  clarification_prompt?: string | null;
  is_confirmed: boolean;
}

export interface AcopioConfig {
  enabled: boolean;
  min_down_payment_pct: number;
  freeze_days: number;
  max_withdrawal_days: number;
  min_notice_hours: number;
}

export interface AcopioSummary {
  enabled: boolean;
  min_down_payment_pct: number;
  down_payment_ars: number;
  remaining_balance_ars: number;
  freeze_days: number;
  freeze_until_date: string;
  max_withdrawal_days: number;
  max_withdrawal_date: string;
  min_notice_hours: number;
}

export interface VendorCreateRequest {
  name: string;
  locality: string;
  whatsapp_phone?: string | null;
  cash_discount_pct: number;
  estimate_delivery_fee_ars: number;
  acopio_config?: AcopioConfig | null;
}

export interface VendorResponse {
  id: string;
  workspace_id?: string | null;
  name: string;
  locality: string;
  whatsapp_phone?: string | null;
  is_public_directory: boolean;
  cash_discount_pct: number;
  estimate_delivery_fee_ars: number;
  acopio_config_json: AcopioConfig | Record<string, unknown>;
  created_at: string;
}

export interface ColumnMapping {
  sku_col: string;
  desc_col: string;
  price_cash_col: string;
  price_list_col?: string | null;
  unit_col?: string | null;
  brand_col?: string | null;
  category_col?: string | null;
}

export interface CatalogImportSummary {
  price_list_id: string;
  vendor_id: string;
  version_number: number;
  total_rows: number;
  new_or_updated_rows: number;
  unchanged_skipped_rows: number;
  skipped_invalid_rows?: number;
  source_filename: string;
}

export interface VendorProductResponse {
  id: string;
  sku: string;
  raw_description: string;
  normalized_description: string;
  brand?: string | null;
  brand_tier: string;
  category?: string | null;
  sale_unit: string;
  price_cash_ars: number;
  price_list_ars: number;
  stock_available: boolean;
  diameter_mm?: number | null;
  length_m?: number | null;
  weight_kg?: number | null;
  material_type?: string | null;
  row_sha256: string;
}

export interface RequisitionIngestRequest {
  title: string;
  client_name?: string | null;
  raw_text?: string | null;
  preset_id?: string | null;
}

export interface ItemClarificationResolveRequest {
  diameter_mm?: number | null;
  length_m?: number | null;
  weight_kg?: number | null;
  material_type?: string | null;
  confirmed_term?: string | null;
  save_as_alias: boolean;
  vendor_id?: string | null;
}

export interface RequisitionItemResponse {
  id: string;
  requisition_id: string;
  line_order: number;
  raw_line: string;
  requested_term: string;
  quantity: number;
  requested_unit: string;
  diameter_inch?: string | null;
  diameter_mm?: number | null;
  length_m?: number | null;
  weight_kg?: number | null;
  material_type?: string | null;
  completeness: CompletenessStatus;
  clarification_prompt?: string | null;
  is_confirmed: boolean;
}

export interface RequisitionDetailResponse {
  id: string;
  workspace_id: string;
  title: string;
  client_name?: string | null;
  source_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  items: RequisitionItemResponse[];
  pending_clarifications_count: number;
}

export interface RunComparisonRequest {
  vendor_ids: string[];
  payment_modality: PaymentModality;
  markup_pct: number;
  include_delivery_fees: boolean;
}

export interface ManualVendorMatchOverride {
  vendor_product_id: string;
  save_vendor_alias: boolean;
  force_dimension_override: boolean;
}

export interface ComparisonVendorSummary {
  vendor_id: string;
  vendor_name: string;
  locality: string;
  coverage_pct: number;
  matched_items_count: number;
  missing_items_count: number;
  materials_subtotal_ars: number;
  delivery_fee_ars: number;
  total_with_delivery_ars: number;
  acopio_summary?: AcopioSummary | null;
}

export interface ComparisonItemCell {
  match_id?: string | null;
  vendor_id: string;
  vendor_name: string;
  match_status: MatchStatus;
  vendor_product_id?: string | null;
  product_sku?: string | null;
  product_description?: string | null;
  unit_price_ars?: number | null;
  line_subtotal_ars?: number | null;
  similarity_score?: number | null;
  is_best_price: boolean;
  is_selected_split: boolean;
}

export interface ComparisonItemRow {
  requisition_item_id: string;
  line_order: number;
  requested_term: string;
  quantity: number;
  requested_unit: string;
  diameter_mm?: number | null;
  material_type?: string | null;
  vendor_cells: ComparisonItemCell[];
  lowest_price_ars?: number | null;
  winning_vendor_id?: string | null;
}

export interface SplitCartSummary {
  total_materials_ars: number;
  total_delivery_fees_ars: number;
  total_cart_ars: number;
  participating_vendors_count: number;
  participating_vendor_names: string[];
  savings_vs_single_vendor_ars: number;
  is_split_recommended: boolean;
}

export interface ComparisonMatrixResponse {
  run_id: string;
  requisition_id: string;
  payment_modality: PaymentModality;
  markup_pct: number;
  include_delivery_fees: boolean;
  best_single_vendor_id?: string | null;
  best_single_vendor_name?: string | null;
  best_single_total_ars?: number | null;
  split_cart: SplitCartSummary;
  vendors: ComparisonVendorSummary[];
  matrix_rows: ComparisonItemRow[];
  public_share_token: string;
  created_at: string;
}

export interface TractionMetricsResponse {
  active_real_workspaces: number;
  real_vendors_compared: number;
  real_budgets_generated: number;
  total_lines_processed: number;
  median_elaboration_seconds: number;
}

export interface LockBudgetResponse {
  run_id: string;
  public_share_token: string;
  share_url: string;
  pdf_url: string;
  status: string;
}

export interface SessionResponse {
  access_token: string;
  token_type: string;
  workspace_id: string;
  workspace_name: string;
  is_demo: boolean;
  role: UserRole;
  email: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  workspace_name?: string;
  role?: UserRole;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RoleUpdateResponse {
  status: string;
  role: UserRole;
  access_token: string;
}
