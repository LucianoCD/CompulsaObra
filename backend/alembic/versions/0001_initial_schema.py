"""Initial schema with pg_trgm, unaccent and 10 core tables

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-06 22:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == 'postgresql'

    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")

    # 1. workspaces
    op.create_table(
        'workspaces',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('owner_role', sa.String(30), nullable=False, server_default='ESTIMATOR'),
        sa.Column('is_demo', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_workspaces_is_demo', 'workspaces', ['is_demo'])

    # 2. users
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', sa.Uuid(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(180), nullable=False),
        sa.Column('full_name', sa.String(120), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(30), nullable=False, server_default='ESTIMATOR'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('BUYER', 'ESTIMATOR', 'ADMIN')", name='chk_user_role'),
        sa.UniqueConstraint('email', name='uq_users_email')
    )
    op.create_index('ix_users_workspace_id', 'users', ['workspace_id'])
    op.create_index('ix_users_email', 'users', ['email'])

    # 3. vendors
    json_type = postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON()
    op.create_table(
        'vendors',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', sa.Uuid(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(140), nullable=False),
        sa.Column('locality', sa.String(80), nullable=False),
        sa.Column('whatsapp_phone', sa.String(30), nullable=True),
        sa.Column('is_public_directory', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('cash_discount_pct', sa.Numeric(5, 2), nullable=False, server_default='0.00'),
        sa.Column('estimate_delivery_fee_ars', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('acopio_config_json', json_type, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_vendors_workspace_id', 'vendors', ['workspace_id'])
    op.create_index('ix_vendors_is_public_directory', 'vendors', ['is_public_directory'])

    # 4. price_lists
    op.create_table(
        'price_lists',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('vendor_id', sa.Uuid(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('source_filename', sa.String(255), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.CheckConstraint('version_number >= 1', name='chk_price_list_version_positive'),
        sa.UniqueConstraint('vendor_id', 'version_number', name='uq_vendor_price_list_version')
    )
    op.create_index('ix_price_lists_vendor_id', 'price_lists', ['vendor_id'])
    op.create_index('ix_price_lists_is_active', 'price_lists', ['is_active'])

    # 5. vendor_products
    tsvector_type = postgresql.TSVECTOR() if is_postgres else sa.Text()
    op.create_table(
        'vendor_products',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('price_list_id', sa.Uuid(as_uuid=True), sa.ForeignKey('price_lists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vendor_id', sa.Uuid(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sku', sa.String(80), nullable=False),
        sa.Column('raw_description', sa.Text(), nullable=False),
        sa.Column('normalized_description', sa.Text(), nullable=False),
        sa.Column('brand', sa.String(80), nullable=True),
        sa.Column('brand_tier', sa.String(20), nullable=False, server_default='STANDARD'),
        sa.Column('category', sa.String(80), nullable=True),
        sa.Column('sale_unit', sa.String(30), nullable=False, server_default='UN'),
        sa.Column('price_cash_ars', sa.Numeric(14, 2), nullable=False),
        sa.Column('price_list_ars', sa.Numeric(14, 2), nullable=False),
        sa.Column('stock_available', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('diameter_mm', sa.Numeric(8, 2), nullable=True),
        sa.Column('length_m', sa.Numeric(8, 2), nullable=True),
        sa.Column('weight_kg', sa.Numeric(8, 2), nullable=True),
        sa.Column('material_type', sa.String(60), nullable=True),
        sa.Column('row_sha256', sa.String(64), nullable=False),
        sa.Column('search_vector', tsvector_type, nullable=True),
        sa.CheckConstraint('price_cash_ars > 0 AND price_list_ars > 0', name='chk_vendor_product_positive_prices')
    )
    op.create_index('ix_vendor_products_sku', 'vendor_products', ['sku'])
    op.create_index('ix_vendor_products_row_sha256', 'vendor_products', ['row_sha256'])
    op.create_index('ix_vendor_products_norm_desc', 'vendor_products', ['normalized_description'])
    op.create_index('ix_vendor_products_price_list_id', 'vendor_products', ['price_list_id'])
    op.create_index('ix_vendor_products_vendor_id', 'vendor_products', ['vendor_id'])
    op.create_index('idx_vendor_products_dim', 'vendor_products', ['vendor_id', 'diameter_mm', 'length_m', 'weight_kg'])
    if is_postgres:
        op.create_index('idx_vendor_products_trgm', 'vendor_products', ['normalized_description'], postgresql_using='gin', postgresql_ops={'normalized_description': 'gin_trgm_ops'})
        op.create_index('idx_vendor_products_fts', 'vendor_products', ['search_vector'], postgresql_using='gin')

    # 6. product_aliases
    op.create_table(
        'product_aliases',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', sa.Uuid(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vendor_id', sa.Uuid(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=True),
        sa.Column('alias_term', sa.String(180), nullable=False),
        sa.Column('canonical_term', sa.String(180), nullable=False),
        sa.Column('target_vendor_product_id', sa.Uuid(as_uuid=True), sa.ForeignKey('vendor_products.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('workspace_id', 'vendor_id', 'alias_term', name='uq_workspace_vendor_alias')
    )
    op.create_index('ix_product_aliases_workspace_id', 'product_aliases', ['workspace_id'])
    op.create_index('ix_product_aliases_vendor_id', 'product_aliases', ['vendor_id'])
    op.create_index('ix_product_aliases_alias_term', 'product_aliases', ['alias_term'])

    # 7. requisitions
    op.create_table(
        'requisitions',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', sa.Uuid(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('client_name', sa.String(140), nullable=True),
        sa.Column('source_type', sa.String(20), nullable=False, server_default='TEXT'),
        sa.Column('raw_input_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='DRAFT_EXTRACTED'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT_EXTRACTED', 'NEEDS_CLARIFICATION', 'READY_TO_COMPARE', 'COMPARED', 'LOCKED_BUDGET')", name='chk_requisition_status')
    )
    op.create_index('ix_requisitions_workspace_id', 'requisitions', ['workspace_id'])
    op.create_index('ix_requisitions_status', 'requisitions', ['status'])

    # 8. requisition_items
    op.create_table(
        'requisition_items',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('requisition_id', sa.Uuid(as_uuid=True), sa.ForeignKey('requisitions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('line_order', sa.Integer(), nullable=False),
        sa.Column('raw_line', sa.Text(), nullable=False),
        sa.Column('requested_term', sa.String(200), nullable=False),
        sa.Column('quantity', sa.Numeric(12, 2), nullable=False),
        sa.Column('requested_unit', sa.String(40), nullable=False, server_default='UN'),
        sa.Column('diameter_inch', sa.String(20), nullable=True),
        sa.Column('diameter_mm', sa.Numeric(8, 2), nullable=True),
        sa.Column('length_m', sa.Numeric(8, 2), nullable=True),
        sa.Column('weight_kg', sa.Numeric(8, 2), nullable=True),
        sa.Column('material_type', sa.String(60), nullable=True),
        sa.Column('completeness', sa.String(40), nullable=False, server_default='complete'),
        sa.Column('clarification_prompt', sa.Text(), nullable=True),
        sa.Column('is_confirmed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.CheckConstraint('quantity > 0', name='chk_requisition_item_quantity_positive'),
        sa.CheckConstraint("completeness IN ('complete', 'missing_critical_attribute', 'user_resolved')", name='chk_requisition_item_completeness'),
        sa.UniqueConstraint('requisition_id', 'line_order', name='uq_requisition_line_order')
    )
    op.create_index('ix_requisition_items_requisition_id', 'requisition_items', ['requisition_id'])
    op.create_index('ix_requisition_items_requested_term', 'requisition_items', ['requested_term'])
    op.create_index('ix_requisition_items_completeness', 'requisition_items', ['completeness'])

    # 9. comparison_runs
    op.create_table(
        'comparison_runs',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('requisition_id', sa.Uuid(as_uuid=True), sa.ForeignKey('requisitions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workspace_id', sa.Uuid(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('payment_modality', sa.String(20), nullable=False, server_default='CASH'),
        sa.Column('markup_pct', sa.Numeric(5, 2), nullable=False, server_default='0.00'),
        sa.Column('best_single_vendor_id', sa.Uuid(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='SET NULL'), nullable=True),
        sa.Column('best_single_total_ars', sa.Numeric(14, 2), nullable=True),
        sa.Column('split_cart_total_ars', sa.Numeric(14, 2), nullable=True),
        sa.Column('split_cart_savings_ars', sa.Numeric(14, 2), nullable=True),
        sa.Column('comparison_matrix_json', json_type, nullable=False),
        sa.Column('public_share_token', sa.String(128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("payment_modality IN ('CASH', 'LIST', 'ACOPIO')", name='chk_comparison_payment_modality'),
        sa.UniqueConstraint('public_share_token', name='uq_comparison_runs_share_token')
    )
    op.create_index('ix_comparison_runs_requisition_id', 'comparison_runs', ['requisition_id'])
    op.create_index('ix_comparison_runs_workspace_id', 'comparison_runs', ['workspace_id'])

    # 10. comparison_item_matches
    op.create_table(
        'comparison_item_matches',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('comparison_run_id', sa.Uuid(as_uuid=True), sa.ForeignKey('comparison_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requisition_item_id', sa.Uuid(as_uuid=True), sa.ForeignKey('requisition_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vendor_id', sa.Uuid(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vendor_product_id', sa.Uuid(as_uuid=True), sa.ForeignKey('vendor_products.id', ondelete='SET NULL'), nullable=True),
        sa.Column('match_status', sa.String(30), nullable=False, server_default='NOT_CARRIED'),
        sa.Column('unit_price_applied_ars', sa.Numeric(14, 2), nullable=True),
        sa.Column('line_subtotal_ars', sa.Numeric(14, 2), nullable=True),
        sa.Column('similarity_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('is_selected_for_split_cart', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.CheckConstraint("match_status IN ('EXACT_MATCH', 'AMBIGUOUS_CANDIDATES', 'OUT_OF_STOCK', 'NOT_CARRIED')", name='chk_item_match_status')
    )
    op.create_index('ix_comparison_item_matches_run_id', 'comparison_item_matches', ['comparison_run_id'])
    op.create_index('ix_comparison_item_matches_req_item_id', 'comparison_item_matches', ['requisition_item_id'])
    op.create_index('ix_comparison_item_matches_vendor_id', 'comparison_item_matches', ['vendor_id'])
    op.create_index('ix_comparison_item_matches_vendor_product_id', 'comparison_item_matches', ['vendor_product_id'])


def downgrade() -> None:
    op.drop_table('comparison_item_matches')
    op.drop_table('comparison_runs')
    op.drop_table('requisition_items')
    op.drop_table('requisitions')
    op.drop_table('product_aliases')
    op.drop_table('vendor_products')
    op.drop_table('price_lists')
    op.drop_table('vendors')
    op.drop_table('users')
    op.drop_table('workspaces')
