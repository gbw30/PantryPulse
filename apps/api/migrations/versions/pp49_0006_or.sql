
CREATE TABLE or_audit_events (
	actor_id UUID, 
	action VARCHAR(128) NOT NULL, 
	resource_id UUID, 
	details JSONB NOT NULL, 
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	PRIMARY KEY (id)
)


;

CREATE TABLE or_dataset_state (
	organization_id UUID NOT NULL, 
	dataset_id UUID NOT NULL, 
	revision_token VARCHAR(256) NOT NULL, 
	org_epoch BIGINT NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	PRIMARY KEY (organization_id, dataset_id), 
	CONSTRAINT ck_dataset_epoch CHECK (org_epoch >= 0)
)


;

CREATE TABLE or_input_packages (
	dataset_id UUID NOT NULL, 
	schema_version VARCHAR(64) NOT NULL, 
	source_kind VARCHAR(16) NOT NULL, 
	revision_token VARCHAR(256) NOT NULL, 
	payload JSONB NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	source_manifest_hash VARCHAR(64) NOT NULL, 
	created_by UUID NOT NULL, 
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_or_package_org_id UNIQUE (organization_id, id), 
	CONSTRAINT uq_or_package_content UNIQUE (organization_id, dataset_id, content_hash), 
	CONSTRAINT ck_or_package_source CHECK (source_kind IN ('SIMULATED','LIVE')), 
	CONSTRAINT ck_or_package_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'), 
	CONSTRAINT ck_or_manifest_hash CHECK (source_manifest_hash ~ '^[0-9a-f]{64}$'), 
	CONSTRAINT ck_or_package_payload CHECK (jsonb_typeof(payload) = 'object')
)


;

CREATE TABLE or_policies (
	version VARCHAR(64) NOT NULL, 
	payload JSONB NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	decision_ids JSONB NOT NULL, 
	created_by UUID NOT NULL, 
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_or_policy_org_id UNIQUE (organization_id, id), 
	CONSTRAINT uq_or_policy_content UNIQUE (organization_id, content_hash), 
	CONSTRAINT ck_or_policy_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'), 
	CONSTRAINT ck_or_policy_payload CHECK (jsonb_typeof(payload) = 'object'), 
	CONSTRAINT ck_or_policy_decisions CHECK (jsonb_typeof(decision_ids) = 'array')
)


;

CREATE TABLE or_request_keys (
	actor_id UUID NOT NULL, 
	route_operation VARCHAR(128) NOT NULL, 
	key VARCHAR(256) NOT NULL, 
	request_hash VARCHAR(64) NOT NULL, 
	job_or_resource_id UUID NOT NULL, 
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_or_request_key UNIQUE (organization_id, actor_id, route_operation, key), 
	CONSTRAINT ck_or_request_key_length CHECK (length(key) BETWEEN 1 AND 256), 
	CONSTRAINT ck_or_request_hash CHECK (request_hash ~ '^[0-9a-f]{64}$')
)


;

CREATE TABLE or_scenarios (
	input_package_id UUID NOT NULL, 
	policy_id UUID NOT NULL, 
	schema_version VARCHAR(64) NOT NULL, 
	transfer_mode VARCHAR(32) NOT NULL, 
	planning_days INTEGER NOT NULL, 
	intent VARCHAR(32) NOT NULL, 
	revision_token VARCHAR(256) NOT NULL, 
	org_epoch BIGINT NOT NULL, 
	payload JSONB NOT NULL, 
	operational_hash VARCHAR(64) NOT NULL, 
	policy_hash VARCHAR(64) NOT NULL, 
	created_by UUID NOT NULL, 
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_or_scenario_org_id UNIQUE (organization_id, id), 
	CONSTRAINT uq_or_scenario_content UNIQUE (organization_id, operational_hash, policy_hash, org_epoch), 
	CONSTRAINT fk_or_scenario_package FOREIGN KEY(organization_id, input_package_id) REFERENCES or_input_packages (organization_id, id), 
	CONSTRAINT fk_or_scenario_policy FOREIGN KEY(organization_id, policy_id) REFERENCES or_policies (organization_id, id), 
	CONSTRAINT ck_or_mode CHECK (transfer_mode IN ('HUB_ONLY','HUB_AND_PANTRY')), 
	CONSTRAINT ck_or_window CHECK (planning_days BETWEEN 1 AND 3), 
	CONSTRAINT ck_or_intent CHECK (intent IN ('CURRENT','HISTORICAL_REPLAY')), 
	CONSTRAINT ck_or_scenario_epoch CHECK (org_epoch >= 0), 
	CONSTRAINT ck_or_operational_hash CHECK (operational_hash ~ '^[0-9a-f]{64}$'), 
	CONSTRAINT ck_or_scenario_policy_hash CHECK (policy_hash ~ '^[0-9a-f]{64}$')
)


;

CREATE TABLE or_plans (
	scenario_id UUID NOT NULL, 
	job_id UUID NOT NULL, 
	attempt_id UUID NOT NULL, 
	method VARCHAR(32) NOT NULL, 
	native_status VARCHAR(24) NOT NULL, 
	outcome VARCHAR(32) NOT NULL, 
	settings_hash VARCHAR(64) NOT NULL, 
	result JSONB NOT NULL, 
	result_hash VARCHAR(64) NOT NULL, 
	verified_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_or_plan_org_id UNIQUE (organization_id, id), 
	CONSTRAINT uq_or_plan_attempt_method UNIQUE (attempt_id, method), 
	CONSTRAINT fk_or_plan_scenario FOREIGN KEY(organization_id, scenario_id) REFERENCES or_scenarios (organization_id, id), 
	CONSTRAINT fk_or_plan_job FOREIGN KEY(organization_id, job_id) REFERENCES compute_jobs (organization_id, job_id), 
	CONSTRAINT fk_or_plan_attempt FOREIGN KEY(organization_id, attempt_id) REFERENCES compute_attempts (organization_id, attempt_id), 
	CONSTRAINT fk_or_plan_job_attempt FOREIGN KEY(job_id, attempt_id) REFERENCES compute_attempts (job_id, attempt_id), 
	CONSTRAINT ck_or_plan_method CHECK (method IN ('CLASSICAL_GP','EGP_PI_INSPIRED')), 
	CONSTRAINT ck_or_plan_native CHECK (native_status IN ('OPTIMAL','FEASIBLE')), 
	CONSTRAINT ck_or_plan_verified CHECK (outcome = 'VERIFIED'), 
	CONSTRAINT ck_or_result_hash CHECK (result_hash ~ '^[0-9a-f]{64}$')
)


;

CREATE TABLE or_comparisons (
	job_id UUID NOT NULL, 
	attempt_id UUID NOT NULL, 
	scenario_id UUID NOT NULL, 
	first_plan_id UUID, 
	second_plan_id UUID, 
	outcome VARCHAR(24) NOT NULL, 
	payload JSONB NOT NULL, 
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_or_comparison_org_id UNIQUE (organization_id, id), 
	CONSTRAINT fk_or_comparison_scenario FOREIGN KEY(organization_id, scenario_id) REFERENCES or_scenarios (organization_id, id), 
	CONSTRAINT fk_or_comparison_job FOREIGN KEY(organization_id, job_id) REFERENCES compute_jobs (organization_id, job_id), 
	CONSTRAINT fk_or_comparison_attempt FOREIGN KEY(organization_id, attempt_id) REFERENCES compute_attempts (organization_id, attempt_id), 
	CONSTRAINT fk_or_comparison_first FOREIGN KEY(organization_id, first_plan_id) REFERENCES or_plans (organization_id, id), 
	CONSTRAINT fk_or_comparison_second FOREIGN KEY(organization_id, second_plan_id) REFERENCES or_plans (organization_id, id), 
	CONSTRAINT ck_or_comparison_outcome CHECK (outcome IN ('SUCCEEDED','PARTIAL','FAILED')), 
	CONSTRAINT ck_or_comparison_completeness CHECK ((outcome = 'SUCCEEDED' AND first_plan_id IS NOT NULL AND second_plan_id IS NOT NULL) OR (outcome = 'PARTIAL' AND ((first_plan_id IS NULL) <> (second_plan_id IS NULL))) OR (outcome = 'FAILED' AND first_plan_id IS NULL AND second_plan_id IS NULL)), 
	UNIQUE (attempt_id)
)


;

CREATE TABLE or_reviews (
	plan_id UUID NOT NULL, 
	actor_id UUID NOT NULL, 
	action VARCHAR(16) NOT NULL, 
	note TEXT, 
	plan_result_hash VARCHAR(64) NOT NULL, 
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_or_review_plan FOREIGN KEY(organization_id, plan_id) REFERENCES or_plans (organization_id, id), 
	CONSTRAINT ck_or_review_action CHECK (action IN ('REVIEWED','REJECTED')), 
	CONSTRAINT ck_or_review_note CHECK (note IS NULL OR length(note) <= 2000)
)


;

CREATE TABLE or_transfers (
	plan_id UUID NOT NULL, 
	original_lot_id UUID NOT NULL, 
	source_id UUID NOT NULL, 
	destination_id UUID NOT NULL, 
	product_id UUID NOT NULL, 
	unit VARCHAR(64) NOT NULL, 
	quantity BIGINT NOT NULL, 
	departure_date DATE NOT NULL, 
	arrival_date DATE NOT NULL, 
	expiry_date DATE, 
	source_revision VARCHAR(256) NOT NULL, 
	cost_minor BIGINT NOT NULL, 
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_or_transfer_plan FOREIGN KEY(organization_id, plan_id) REFERENCES or_plans (organization_id, id), 
	CONSTRAINT uq_or_transfer_lineage UNIQUE (plan_id, original_lot_id, source_id, destination_id, product_id), 
	CONSTRAINT ck_or_transfer_amounts CHECK (quantity > 0 AND cost_minor >= 0), 
	CONSTRAINT ck_or_transfer_no_self CHECK (source_id <> destination_id), 
	CONSTRAINT ck_or_transfer_dates CHECK (arrival_date >= departure_date AND (expiry_date IS NULL OR expiry_date >= arrival_date))
)


;

CREATE TABLE or_verifications (
	plan_id UUID NOT NULL, 
	verifier_version VARCHAR(64) NOT NULL, 
	passed BOOLEAN NOT NULL, 
	checks JSONB NOT NULL, 
	objective JSONB NOT NULL, 
	report_hash VARCHAR(64) NOT NULL, 
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_or_check_plan FOREIGN KEY(organization_id, plan_id) REFERENCES or_plans (organization_id, id), 
	CONSTRAINT ck_or_check_passed CHECK (passed), 
	CONSTRAINT ck_or_check_hash CHECK (report_hash ~ '^[0-9a-f]{64}$'), 
	UNIQUE (plan_id)
)


;
CREATE INDEX ix_or_scenario_page ON or_scenarios (organization_id, created_at, id)
;
