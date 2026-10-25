-- Frozen operational-v1 baseline, generated October 24, 2026.

CREATE TABLE organizations (
	name TEXT NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_organizations PRIMARY KEY (id)
);

CREATE TABLE categories (
	name TEXT NOT NULL, 
	active BOOLEAN NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_categories PRIMARY KEY (id), 
	CONSTRAINT fk_categories_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_categories_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE data_sources (
	name TEXT NOT NULL, 
	classification TEXT NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_data_sources PRIMARY KEY (id), 
	CONSTRAINT ck_data_sources_classification CHECK (classification IN ('OBSERVED', 'SIMULATED')), 
	CONSTRAINT fk_data_sources_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_data_sources_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE donors (
	name TEXT NOT NULL, 
	active BOOLEAN NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_donors PRIMARY KEY (id), 
	CONSTRAINT fk_donors_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_donors_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE sites (
	name TEXT NOT NULL, 
	role TEXT NOT NULL, 
	active BOOLEAN NOT NULL, 
	current_calendar_id UUID, 
	latitude NUMERIC(9, 6), 
	longitude NUMERIC(9, 6), 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_sites PRIMARY KEY (id), 
	CONSTRAINT ck_sites_role CHECK (role IN ('HUB', 'BENEFICIARY')), 
	CONSTRAINT ck_sites_latitude CHECK (latitude BETWEEN -90 AND 90), 
	CONSTRAINT ck_sites_longitude CHECK (longitude BETWEEN -180 AND 180), 
	CONSTRAINT fk_sites_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_sites_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE stock_commands (
	actor TEXT NOT NULL, 
	operation TEXT NOT NULL, 
	reason TEXT NOT NULL, 
	idempotency_key TEXT NOT NULL, 
	payload_hash VARCHAR(64) NOT NULL, 
	outcome JSONB NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_stock_commands PRIMARY KEY (id), 
	CONSTRAINT uq_stock_commands_organization_id_idempotency_key UNIQUE (organization_id, idempotency_key), 
	CONSTRAINT ck_stock_commands_payload_hash CHECK (payload_hash ~ '^[0-9a-f]{64}$'), 
	CONSTRAINT ck_stock_commands_attribution CHECK (length(trim(actor)) > 0 AND length(trim(reason)) > 0), 
	CONSTRAINT ck_stock_commands_idempotency_key CHECK (length(trim(idempotency_key)) > 0), 
	CONSTRAINT fk_stock_commands_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_stock_commands_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE audit_events (
	command_id UUID NOT NULL, 
	event TEXT NOT NULL, 
	details JSONB NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_audit_events PRIMARY KEY (id), 
	CONSTRAINT fk_audit_events_organization_id_command_id_stock_commands FOREIGN KEY(organization_id, command_id) REFERENCES stock_commands (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_audit_events_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_audit_events_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE products (
	category_id UUID NOT NULL, 
	name TEXT NOT NULL, 
	base_unit TEXT NOT NULL, 
	active BOOLEAN NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_products PRIMARY KEY (id), 
	CONSTRAINT fk_products_organization_id_category_id_categories FOREIGN KEY(organization_id, category_id) REFERENCES categories (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_products_base_unit CHECK (length(trim(base_unit)) > 0), 
	CONSTRAINT fk_products_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_products_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE receipts (
	source_id UUID NOT NULL, 
	source_record_key TEXT NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_receipts PRIMARY KEY (id), 
	CONSTRAINT fk_receipts_organization_id_source_id_data_sources FOREIGN KEY(organization_id, source_id) REFERENCES data_sources (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_receipts_organization_id_source_id_source_record_key UNIQUE (organization_id, source_id, source_record_key), 
	CONSTRAINT fk_receipts_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_receipts_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE site_calendars (
	site_id UUID NOT NULL, 
	timezone TEXT NOT NULL, 
	revision BIGINT NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_site_calendars PRIMARY KEY (id), 
	CONSTRAINT fk_site_calendars_organization_id_site_id_sites FOREIGN KEY(organization_id, site_id) REFERENCES sites (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_site_calendars_organization_id_site_id_revision UNIQUE (organization_id, site_id, revision), 
	CONSTRAINT uq_site_calendars_organization_id_id_site_id UNIQUE (organization_id, id, site_id), 
	CONSTRAINT ck_site_calendars_revision CHECK (revision > 0), 
	CONSTRAINT fk_site_calendars_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_site_calendars_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE demand_records (
	site_id UUID NOT NULL, 
	product_id UUID NOT NULL, 
	local_day DATE NOT NULL, 
	source_id UUID NOT NULL, 
	source_record_key TEXT NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_demand_records PRIMARY KEY (id), 
	CONSTRAINT fk_demand_records_organization_id_site_id_sites FOREIGN KEY(organization_id, site_id) REFERENCES sites (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_demand_records_organization_id_product_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_demand_records_organization_id_source_id_data_sources FOREIGN KEY(organization_id, source_id) REFERENCES data_sources (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_demand_records_organization_id_source_id_source_record_key UNIQUE (organization_id, source_id, source_record_key), 
	CONSTRAINT uq_demand_records_organization_id_source_id_site_id_pro_26a6 UNIQUE (organization_id, source_id, site_id, product_id, local_day), 
	CONSTRAINT uq_demand_records_organization_id_id_site_id UNIQUE (organization_id, id, site_id), 
	CONSTRAINT fk_demand_records_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_demand_records_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE donation_coverage_revisions (
	site_id UUID NOT NULL, 
	product_id UUID NOT NULL, 
	source_id UUID NOT NULL, 
	calendar_version_id UUID NOT NULL, 
	local_day DATE NOT NULL, 
	revision BIGINT NOT NULL, 
	complete BOOLEAN NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_donation_coverage_revisions PRIMARY KEY (id), 
	CONSTRAINT fk_donation_coverage_revisions_organization_id_product__6189 FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_donation_coverage_revisions_organization_id_source_i_e2c7 FOREIGN KEY(organization_id, source_id) REFERENCES data_sources (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_donation_coverage_revisions_organization_id_calendar_3bf5 FOREIGN KEY(organization_id, calendar_version_id, site_id) REFERENCES site_calendars (organization_id, id, site_id) ON DELETE RESTRICT, 
	CONSTRAINT uq_donation_coverage_revisions_organization_id_site_id__0ae4 UNIQUE (organization_id, site_id, product_id, source_id, local_day, revision), 
	CONSTRAINT ck_donation_coverage_revisions_revision CHECK (revision > 0), 
	CONSTRAINT fk_donation_coverage_revisions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_donation_coverage_revisions_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE expected_supplies (
	site_id UUID NOT NULL, 
	product_id UUID NOT NULL, 
	source_id UUID NOT NULL, 
	source_record_key TEXT NOT NULL, 
	quantity BIGINT NOT NULL, 
	received_quantity BIGINT NOT NULL, 
	outstanding_confirmed_quantity BIGINT NOT NULL, 
	expected_arrival_at TIMESTAMP WITH TIME ZONE, 
	state TEXT NOT NULL, 
	version BIGINT NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_expected_supplies PRIMARY KEY (id), 
	CONSTRAINT fk_expected_supplies_organization_id_site_id_sites FOREIGN KEY(organization_id, site_id) REFERENCES sites (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_expected_supplies_organization_id_product_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_expected_supplies_organization_id_source_id_data_sources FOREIGN KEY(organization_id, source_id) REFERENCES data_sources (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_expected_supplies_organization_id_source_id_source_r_22e2 UNIQUE (organization_id, source_id, source_record_key), 
	CONSTRAINT uq_expected_supplies_organization_id_id_site_id_product_id UNIQUE (organization_id, id, site_id, product_id), 
	CONSTRAINT ck_expected_supplies_counts CHECK (quantity > 0 AND received_quantity >= 0 AND outstanding_confirmed_quantity >= 0 AND version > 0), 
	CONSTRAINT ck_expected_supplies_balance CHECK (received_quantity::numeric + outstanding_confirmed_quantity::numeric <= quantity::numeric), 
	CONSTRAINT ck_expected_supplies_state CHECK (state IN ('UNCONFIRMED', 'CONFIRMED', 'CANCELLED', 'RECEIVED')), 
	CONSTRAINT ck_expected_supplies_confirmed_arrival CHECK (outstanding_confirmed_quantity = 0 OR (state = 'CONFIRMED' AND expected_arrival_at IS NOT NULL)), 
	CONSTRAINT ck_expected_supplies_received_state CHECK (state <> 'RECEIVED' OR received_quantity > 0), 
	CONSTRAINT fk_expected_supplies_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_expected_supplies_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE inventory_versions (
	site_id UUID NOT NULL, 
	product_id UUID NOT NULL, 
	version BIGINT NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_inventory_versions PRIMARY KEY (id), 
	CONSTRAINT fk_inventory_versions_organization_id_site_id_sites FOREIGN KEY(organization_id, site_id) REFERENCES sites (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_versions_organization_id_product_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_inventory_versions_organization_id_site_id_product_id UNIQUE (organization_id, site_id, product_id), 
	CONSTRAINT ck_inventory_versions_version CHECK (version > 0), 
	CONSTRAINT fk_inventory_versions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_inventory_versions_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE receipt_revisions (
	receipt_id UUID NOT NULL, 
	receiving_site_id UUID NOT NULL, 
	donor_id UUID NOT NULL, 
	calendar_version_id UUID NOT NULL, 
	revision BIGINT NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	local_day DATE NOT NULL, 
	is_void BOOLEAN NOT NULL, 
	ingest_transaction BIGINT DEFAULT txid_current() NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_receipt_revisions PRIMARY KEY (id), 
	CONSTRAINT fk_receipt_revisions_organization_id_receipt_id_receipts FOREIGN KEY(organization_id, receipt_id) REFERENCES receipts (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_receipt_revisions_organization_id_donor_id_donors FOREIGN KEY(organization_id, donor_id) REFERENCES donors (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_receipt_revisions_organization_id_calendar_version_i_94f9 FOREIGN KEY(organization_id, calendar_version_id, receiving_site_id) REFERENCES site_calendars (organization_id, id, site_id) ON DELETE RESTRICT, 
	CONSTRAINT uq_receipt_revisions_organization_id_receipt_id_revision UNIQUE (organization_id, receipt_id, revision), 
	CONSTRAINT uq_receipt_revisions_organization_id_id_receipt_id UNIQUE (organization_id, id, receipt_id), 
	CONSTRAINT uq_receipt_revisions_organization_id_id_receiving_site_id UNIQUE (organization_id, id, receiving_site_id), 
	CONSTRAINT ck_receipt_revisions_revision CHECK (revision > 0), 
	CONSTRAINT fk_receipt_revisions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_receipt_revisions_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE demand_revisions (
	record_id UUID NOT NULL, 
	site_id UUID NOT NULL, 
	calendar_version_id UUID NOT NULL, 
	revision BIGINT NOT NULL, 
	requested BIGINT, 
	fulfilled BIGINT, 
	unmet BIGINT, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_demand_revisions PRIMARY KEY (id), 
	CONSTRAINT fk_demand_revisions_organization_id_record_id_site_id_d_52c8 FOREIGN KEY(organization_id, record_id, site_id) REFERENCES demand_records (organization_id, id, site_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_demand_revisions_organization_id_calendar_version_id_7246 FOREIGN KEY(organization_id, calendar_version_id, site_id) REFERENCES site_calendars (organization_id, id, site_id) ON DELETE RESTRICT, 
	CONSTRAINT uq_demand_revisions_organization_id_record_id_revision UNIQUE (organization_id, record_id, revision), 
	CONSTRAINT ck_demand_revisions_revision CHECK (revision > 0), 
	CONSTRAINT ck_demand_revisions_observed CHECK (requested IS NOT NULL OR fulfilled IS NOT NULL OR unmet IS NOT NULL), 
	CONSTRAINT ck_demand_revisions_counts CHECK (requested >= 0 AND fulfilled >= 0 AND unmet >= 0), 
	CONSTRAINT ck_demand_revisions_component_bounds CHECK (requested >= fulfilled AND requested >= unmet), 
	CONSTRAINT ck_demand_revisions_arithmetic CHECK (requested::numeric = fulfilled::numeric + unmet::numeric), 
	CONSTRAINT fk_demand_revisions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_demand_revisions_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE receipt_lines (
	receipt_revision_id UUID NOT NULL, 
	line_key TEXT NOT NULL, 
	product_id UUID NOT NULL, 
	received_quantity BIGINT NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_receipt_lines PRIMARY KEY (id), 
	CONSTRAINT fk_receipt_lines_organization_id_receipt_revision_id_re_a9ec FOREIGN KEY(organization_id, receipt_revision_id) REFERENCES receipt_revisions (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_receipt_lines_organization_id_product_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_receipt_lines_organization_id_receipt_revision_id_line_key UNIQUE (organization_id, receipt_revision_id, line_key), 
	CONSTRAINT uq_receipt_lines_organization_id_id_product_id_receipt__61bd UNIQUE (organization_id, id, product_id, receipt_revision_id), 
	CONSTRAINT ck_receipt_lines_quantity CHECK (received_quantity > 0), 
	CONSTRAINT fk_receipt_lines_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_receipt_lines_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE receipt_postings (
	receipt_id UUID NOT NULL, 
	posted_revision_id UUID NOT NULL, 
	command_id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_receipt_postings PRIMARY KEY (id), 
	CONSTRAINT fk_receipt_postings_organization_id_posted_revision_id__0fdd FOREIGN KEY(organization_id, posted_revision_id, receipt_id) REFERENCES receipt_revisions (organization_id, id, receipt_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_receipt_postings_organization_id_command_id_stock_commands FOREIGN KEY(organization_id, command_id) REFERENCES stock_commands (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_receipt_postings_organization_id_receipt_id UNIQUE (organization_id, receipt_id), 
	CONSTRAINT uq_receipt_postings_organization_id_command_id UNIQUE (organization_id, command_id), 
	CONSTRAINT uq_receipt_postings_organization_id_id_receipt_id UNIQUE (organization_id, id, receipt_id), 
	CONSTRAINT fk_receipt_postings_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_receipt_postings_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE receipt_reconciliations (
	receipt_id UUID NOT NULL, 
	latest_revision_id UUID NOT NULL, 
	stock_revision_id UUID, 
	needs_reconciliation BOOLEAN NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_receipt_reconciliations PRIMARY KEY (id), 
	CONSTRAINT fk_receipt_reconciliations_organization_id_latest_revis_31a2 FOREIGN KEY(organization_id, latest_revision_id, receipt_id) REFERENCES receipt_revisions (organization_id, id, receipt_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_receipt_reconciliations_organization_id_stock_revisi_c6bf FOREIGN KEY(organization_id, stock_revision_id, receipt_id) REFERENCES receipt_revisions (organization_id, id, receipt_id) ON DELETE RESTRICT, 
	CONSTRAINT uq_receipt_reconciliations_organization_id_receipt_id UNIQUE (organization_id, receipt_id), 
	CONSTRAINT ck_receipt_reconciliations_consistent CHECK (needs_reconciliation OR (stock_revision_id IS NOT NULL AND stock_revision_id = latest_revision_id)), 
	CONSTRAINT fk_receipt_reconciliations_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_receipt_reconciliations_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE inventory_lots (
	site_id UUID NOT NULL, 
	product_id UUID NOT NULL, 
	receipt_id UUID, 
	receipt_line_id UUID, 
	receipt_revision_id UUID, 
	posting_id UUID, 
	batch_key TEXT NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	on_hand BIGINT NOT NULL, 
	eligibility TEXT NOT NULL, 
	expiry_kind TEXT NOT NULL, 
	expires_on DATE, 
	declaration_actor TEXT NOT NULL, 
	declaration_reason TEXT NOT NULL, 
	declared_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	metadata_version BIGINT NOT NULL, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_inventory_lots PRIMARY KEY (id), 
	CONSTRAINT fk_inventory_lots_organization_id_site_id_sites FOREIGN KEY(organization_id, site_id) REFERENCES sites (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_lots_organization_id_product_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_lots_organization_id_receipt_line_id_produ_68e8 FOREIGN KEY(organization_id, receipt_line_id, product_id, receipt_revision_id) REFERENCES receipt_lines (organization_id, id, product_id, receipt_revision_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_lots_organization_id_receipt_revision_id_s_832c FOREIGN KEY(organization_id, receipt_revision_id, site_id) REFERENCES receipt_revisions (organization_id, id, receiving_site_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_lots_organization_id_receipt_revision_id_r_f677 FOREIGN KEY(organization_id, receipt_revision_id, receipt_id) REFERENCES receipt_revisions (organization_id, id, receipt_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_lots_organization_id_posting_id_receipt_id_4a2c FOREIGN KEY(organization_id, posting_id, receipt_id) REFERENCES receipt_postings (organization_id, id, receipt_id) ON DELETE RESTRICT, 
	CONSTRAINT uq_inventory_lots_organization_id_site_id_product_id_batch_key UNIQUE (organization_id, site_id, product_id, batch_key), 
	CONSTRAINT uq_inventory_lots_organization_id_id_site_id_product_id UNIQUE (organization_id, id, site_id, product_id), 
	CONSTRAINT ck_inventory_lots_balance_version CHECK (on_hand >= 0 AND metadata_version > 0), 
	CONSTRAINT ck_inventory_lots_eligibility CHECK (eligibility IN ('ELIGIBLE', 'HELD', 'INELIGIBLE', 'UNKNOWN')), 
	CONSTRAINT ck_inventory_lots_expiry CHECK ((expiry_kind = 'DATED' AND expires_on IS NOT NULL) OR (expiry_kind IN ('NON_EXPIRING', 'UNKNOWN') AND expires_on IS NULL)), 
	CONSTRAINT ck_inventory_lots_receipt_linkage CHECK (num_nonnulls(receipt_id, receipt_line_id, receipt_revision_id, posting_id) IN (0, 4)), 
	CONSTRAINT ck_inventory_lots_declaration CHECK (length(trim(declaration_actor)) > 0 AND length(trim(declaration_reason)) > 0), 
	CONSTRAINT fk_inventory_lots_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_inventory_lots_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE supply_receipts (
	supply_id UUID NOT NULL, 
	site_id UUID NOT NULL, 
	product_id UUID NOT NULL, 
	receipt_line_id UUID NOT NULL, 
	receipt_revision_id UUID NOT NULL, 
	command_id UUID NOT NULL, 
	quantity_delta BIGINT NOT NULL, 
	reverses_allocation_id UUID, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_supply_receipts PRIMARY KEY (id), 
	CONSTRAINT fk_supply_receipts_organization_id_supply_id_site_id_pr_0aa8 FOREIGN KEY(organization_id, supply_id, site_id, product_id) REFERENCES expected_supplies (organization_id, id, site_id, product_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_supply_receipts_organization_id_receipt_line_id_prod_0815 FOREIGN KEY(organization_id, receipt_line_id, product_id, receipt_revision_id) REFERENCES receipt_lines (organization_id, id, product_id, receipt_revision_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_supply_receipts_organization_id_receipt_revision_id__6c03 FOREIGN KEY(organization_id, receipt_revision_id, site_id) REFERENCES receipt_revisions (organization_id, id, receiving_site_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_supply_receipts_organization_id_command_id_stock_commands FOREIGN KEY(organization_id, command_id) REFERENCES stock_commands (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_supply_receipts_organization_id_reverses_allocation__a981 FOREIGN KEY(organization_id, reverses_allocation_id, supply_id, receipt_line_id) REFERENCES supply_receipts (organization_id, id, supply_id, receipt_line_id) ON DELETE RESTRICT, 
	CONSTRAINT uq_supply_receipts_organization_id_id_supply_id_receipt_line_id UNIQUE (organization_id, id, supply_id, receipt_line_id), 
	CONSTRAINT uq_supply_receipts_organization_id_command_id_supply_id_e615 UNIQUE (organization_id, command_id, supply_id, receipt_line_id), 
	CONSTRAINT ck_supply_receipts_delta CHECK (quantity_delta <> 0), 
	CONSTRAINT ck_supply_receipts_reversal CHECK ((quantity_delta < 0) = (reverses_allocation_id IS NOT NULL)), 
	CONSTRAINT fk_supply_receipts_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_supply_receipts_organization_id_id UNIQUE (organization_id, id)
);

CREATE TABLE stock_ledger (
	site_id UUID NOT NULL, 
	product_id UUID NOT NULL, 
	lot_id UUID NOT NULL, 
	command_id UUID NOT NULL, 
	delta BIGINT NOT NULL, 
	effective_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	before_version BIGINT NOT NULL, 
	after_version BIGINT NOT NULL, 
	reverses_entry_id UUID, 
	organization_id UUID NOT NULL, 
	id UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_stock_ledger PRIMARY KEY (id), 
	CONSTRAINT fk_stock_ledger_organization_id_lot_id_site_id_product__da5c FOREIGN KEY(organization_id, lot_id, site_id, product_id) REFERENCES inventory_lots (organization_id, id, site_id, product_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_stock_ledger_organization_id_command_id_stock_commands FOREIGN KEY(organization_id, command_id) REFERENCES stock_commands (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_stock_ledger_organization_id_reverses_entry_id_lot_i_ccd3 FOREIGN KEY(organization_id, reverses_entry_id, lot_id) REFERENCES stock_ledger (organization_id, id, lot_id) ON DELETE RESTRICT, 
	CONSTRAINT uq_stock_ledger_organization_id_id_lot_id UNIQUE (organization_id, id, lot_id), 
	CONSTRAINT uq_stock_ledger_organization_id_command_id_lot_id UNIQUE (organization_id, command_id, lot_id), 
	CONSTRAINT ck_stock_ledger_delta CHECK (delta <> 0), 
	CONSTRAINT ck_stock_ledger_versions CHECK (before_version > 0 AND after_version::numeric = before_version::numeric + 1), 
	CONSTRAINT fk_stock_ledger_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_stock_ledger_organization_id_id UNIQUE (organization_id, id)
);

ALTER TABLE sites ADD CONSTRAINT fk_site_current_calendar FOREIGN KEY(organization_id, current_calendar_id, id) REFERENCES site_calendars (organization_id, id, site_id) DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX ix_demand_scope_day ON demand_records (organization_id, site_id, product_id, local_day);

CREATE INDEX ix_supply_arrival ON expected_supplies (organization_id, site_id, product_id, state, expected_arrival_at);

CREATE INDEX ix_receipt_day ON receipt_revisions (organization_id, receiving_site_id, local_day);

CREATE INDEX ix_lot_expiry ON inventory_lots (organization_id, site_id, product_id, expires_on);

CREATE INDEX ix_ledger_lot_time ON stock_ledger (organization_id, lot_id, recorded_at);
