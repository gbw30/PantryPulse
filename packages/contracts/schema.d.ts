export interface paths {
    "/api/v1/allocation-methodology": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Methodology */
        get: operations["methodology_api_v1_allocation_methodology_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/capabilities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Capabilities */
        get: operations["capabilities_api_v1_capabilities_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/comparisons/{record_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Comparison Read */
        get: operations["comparison_read_api_v1_comparisons__record_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/demo/reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Demo Reset */
        post: operations["demo_reset_api_v1_demo_reset_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/demo/seed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Demo Seed */
        post: operations["demo_seed_api_v1_demo_seed_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health
         * @description Process liveness only; does not assert database or solver readiness.
         */
        get: operations["health_api_v1_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/jobs/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Job Read */
        get: operations["job_read_api_v1_jobs__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/jobs/{job_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Job Cancel */
        post: operations["job_cancel_api_v1_jobs__job_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/jobs/{job_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Job Retry */
        post: operations["job_retry_api_v1_jobs__job_id__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/or/input-packages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Package */
        post: operations["create_package_api_v1_or_input_packages_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/or/input-packages/from-sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Package From Sources */
        post: operations["package_from_sources_api_v1_or_input_packages_from_sources_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/or/input-packages/{record_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Package Read */
        get: operations["package_read_api_v1_or_input_packages__record_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/or/policies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Policy */
        post: operations["create_policy_api_v1_or_policies_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/or/policies/{record_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Policy Read */
        get: operations["policy_read_api_v1_or_policies__record_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/plans/{plan_id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Plan Review */
        post: operations["plan_review_api_v1_plans__plan_id__review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/plans/{record_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Plan Read */
        get: operations["plan_read_api_v1_plans__record_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/presenter/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Presenter Login */
        post: operations["presenter_login_api_v1_presenter_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/presenter/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Presenter Logout */
        post: operations["presenter_logout_api_v1_presenter_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/presenter/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Presenter Session */
        get: operations["presenter_session_api_v1_presenter_session_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/readiness": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Readiness */
        get: operations["readiness_api_v1_readiness_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/scenarios": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Scenario List */
        get: operations["scenario_list_api_v1_scenarios_get"];
        put?: never;
        /** Create Scenario */
        post: operations["create_scenario_api_v1_scenarios_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/scenarios/{record_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Scenario Read */
        get: operations["scenario_read_api_v1_scenarios__record_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/scenarios/{scenario_id}/compare-methods": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Pair */
        post: operations["submit_pair_api_v1_scenarios__scenario_id__compare_methods_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/scenarios/{scenario_id}/plans": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Plan */
        post: operations["submit_plan_api_v1_scenarios__scenario_id__plans_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * AllocationMethod
         * @enum {string}
         */
        AllocationMethod: "CLASSICAL_GP" | "EGP_PI_INSPIRED";
        /** AttemptSummary */
        AttemptSummary: {
            /**
             * Attempt Id
             * Format: uuid
             */
            attempt_id: string;
            /** Attempt Number */
            attempt_number: number;
            /** Completed At */
            completed_at: string | null;
            /**
             * Enqueued At
             * Format: date-time
             */
            enqueued_at: string;
            /** Reason Code */
            reason_code: string | null;
            /** Started At */
            started_at: string | null;
            /** State */
            state: string;
        };
        /** AttributeCoefficient */
        AttributeCoefficient: {
            /** Attribute Id */
            attribute_id: string;
            /** Percent */
            percent: number;
        };
        /** AttributeScore */
        AttributeScore: {
            /** Attribute Id */
            attribute_id: string;
            /**
             * Classification
             * @enum {string}
             */
            classification: "SIMULATED" | "OBSERVED";
            /** Raw Note */
            raw_note: string;
            /** Score Bp */
            score_bp: number;
            /** Transformation */
            transformation: string;
            /** Transformation Version */
            transformation_version: string;
        };
        /** Candidate */
        Candidate: {
            /** Assignments */
            assignments: components["schemas"]["TransferAssignment"][];
            claimed_metrics?: components["schemas"]["Metrics"] | null;
            /** Route Quantities */
            route_quantities: components["schemas"]["RouteQuantity"][];
        };
        /** Capacities */
        Capacities: {
            /** Cost Budget Minor */
            cost_budget_minor: number | null;
            global_handling: components["schemas"]["ResidualCapacity"];
            /** Sites */
            sites: components["schemas"]["SiteCapacity"][];
        };
        /** ComparisonResult */
        ComparisonResult: {
            baseline_metrics?: components["schemas"]["Metrics"] | null;
            /** Common Differences */
            common_differences: {
                [key: string]: unknown;
            };
            /** Historical */
            historical: boolean;
            /** Methods */
            methods: components["schemas"]["MethodOutcome"][];
            /** Operational Hash */
            operational_hash: string;
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "SUCCEEDED" | "PARTIAL" | "FAILED";
            /**
             * Schema Version
             * @default or-comparison-v1
             * @constant
             */
            schema_version: "or-comparison-v1";
            transfer_mode: components["schemas"]["TransferMode"];
            /** Warnings */
            warnings: string[];
        };
        /** ComparisonSummary */
        ComparisonSummary: {
            /** Historical */
            historical: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            result: components["schemas"]["ComparisonResult"];
            /**
             * Scenario Id
             * Format: uuid
             */
            scenario_id: string;
            /** Stale */
            stale: boolean;
        };
        /** ConfirmedArrival */
        ConfirmedArrival: {
            /** Already Posted */
            already_posted: boolean;
            /**
             * Available On
             * Format: date
             */
            available_on: string;
            /** Confirmed */
            confirmed: boolean;
            /**
             * Eligibility
             * @enum {string}
             */
            eligibility: "ELIGIBLE" | "HELD" | "UNKNOWN";
            /** Expires On */
            expires_on: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /**
             * Site Id
             * Format: uuid
             */
            site_id: string;
            /**
             * Source Line Id
             * Format: uuid
             */
            source_line_id: string;
            /** Source Revision */
            source_revision: string;
            /** Unit */
            unit: string;
            /** Units */
            units: number;
        };
        /** DemandModifier */
        DemandModifier: {
            /** Buffer Fraction */
            buffer_fraction: string | null;
            /**
             * Mode
             * @enum {string}
             */
            mode: "CENTRAL" | "CONSERVATIVE";
            /** Multiplier */
            multiplier: string;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /**
             * Site Id
             * Format: uuid
             */
            site_id: string;
        };
        /** ErrorDetail */
        ErrorDetail: {
            /** Code */
            code: string;
            /** Details */
            details: {
                [key: string]: unknown;
            };
            /** Message */
            message: string;
        };
        /** ErrorResponse */
        ErrorResponse: {
            error: components["schemas"]["ErrorDetail"];
            /** Request Id */
            request_id: string;
        };
        /** Exclusion */
        Exclusion: {
            /** Code */
            code: string;
            /** Resource Id */
            resource_id: string;
        };
        /** ForecastDay */
        ForecastDay: {
            /** Central Literal */
            central_literal: string;
            /**
             * Day
             * Format: date
             */
            day: string;
            /** P10 Literal */
            p10_literal: string | null;
            /** P50 Literal */
            p50_literal: string | null;
            /** P90 Literal */
            p90_literal: string | null;
        };
        /** ForecastSeries */
        ForecastSeries: {
            /** Actual Provider */
            actual_provider: string;
            /**
             * Basis
             * @enum {string}
             */
            basis: "REQUESTED" | "FULFILLED_PROXY";
            /** Committed */
            committed: boolean;
            /**
             * Cutoff
             * Format: date
             */
            cutoff: string;
            /** Days */
            days: components["schemas"]["ForecastDay"][];
            /**
             * Estimate Kind
             * @enum {string}
             */
            estimate_kind: "POINT" | "MEAN" | "MEDIAN";
            /**
             * Generated At
             * Format: date-time
             */
            generated_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Interval Method
             * @enum {string}
             */
            interval_method: "NONE" | "MODEL_QUANTILES";
            /**
             * Numeric Conversion
             * @enum {string}
             */
            numeric_conversion: "EXACT_LITERAL" | "LEGACY_FLOAT_LITERAL";
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Planning Ready */
            planning_ready: boolean;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            /**
             * Site Id
             * Format: uuid
             */
            site_id: string;
            /**
             * Source Classification
             * @enum {string}
             */
            source_classification: "SIMULATED" | "OBSERVED" | "MIXED";
            /**
             * Source Id
             * Format: uuid
             */
            source_id: string;
            /** Source Revision */
            source_revision: string;
            /** Timezone */
            timezone: string;
            /** Unit */
            unit: string;
            /** Upstream Metadata Json */
            upstream_metadata_json?: string | null;
        };
        /** GoalMetric */
        GoalMetric: {
            /** Ap */
            ap: boolean;
            deficit: components["schemas"]["Rational"];
            /** Exact Ap */
            exact_ap: boolean;
            /** Exact Rp */
            exact_rp: boolean;
            /** Fulfilled */
            fulfilled: number;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /** Q */
            q: number;
            /** Q0 */
            q0: number;
            /** Rp */
            rp: boolean;
            service_ratio: components["schemas"]["Rational"] | null;
            /**
             * Site Id
             * Format: uuid
             */
            site_id: string;
            /** Target */
            target: number;
            /** Unmet */
            unmet: number;
            vulnerability: components["schemas"]["Rational"];
            weighted_deficit: components["schemas"]["Rational"];
        };
        /** GroupMetric */
        GroupMetric: {
            /** Ap Count */
            ap_count: number;
            /** Ap Excess Numerator */
            ap_excess_numerator: number;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /** Rp Count */
            rp_count: number;
            /** Rp Excess Numerator */
            rp_excess_numerator: number;
            /** Size */
            size: number;
        };
        /** HealthResponse */
        HealthResponse: {
            /**
             * Scope
             * @constant
             */
            scope: "process";
            /**
             * Status
             * @constant
             */
            status: "ok";
        };
        /** InventoryLot */
        InventoryLot: {
            /**
             * Available On
             * Format: date
             */
            available_on: string;
            /** Commitment Overlaps Demand */
            commitment_overlaps_demand: boolean;
            /** Commitment Scope Refs */
            commitment_scope_refs: string[];
            /** Committed Units */
            committed_units: number;
            /** Dispatchable */
            dispatchable: boolean;
            /**
             * Eligibility
             * @enum {string}
             */
            eligibility: "ELIGIBLE" | "HELD" | "UNKNOWN";
            /** Expires On */
            expires_on: string | null;
            /** Free Units */
            free_units: number;
            /** Held Units */
            held_units: number;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Physical Units */
            physical_units: number;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /** Reserved Units */
            reserved_units: number;
            /**
             * Site Id
             * Format: uuid
             */
            site_id: string;
            /**
             * Source Line Id
             * Format: uuid
             */
            source_line_id: string;
            /** Source Revision */
            source_revision: string;
            /** Unit */
            unit: string;
        };
        /** JobAccepted */
        JobAccepted: {
            /**
             * Attempt Id
             * Format: uuid
             */
            attempt_id: string;
            /**
             * Job Id
             * Format: uuid
             */
            job_id: string;
            /** Replayed */
            replayed: boolean;
            /** State */
            state: string;
            /** Status Url */
            status_url: string;
        };
        /** JobSummary */
        JobSummary: {
            /** Attempts */
            attempts: components["schemas"]["AttemptSummary"][];
            /** Comparison Id */
            comparison_id: string | null;
            /** Error Code */
            error_code: string | null;
            /**
             * Job Id
             * Format: uuid
             */
            job_id: string;
            /** Plans */
            plans: components["schemas"]["PlanRef"][];
            /** Result Completeness */
            result_completeness: string;
            /** State */
            state: string;
            /** Status Url */
            status_url: string;
        };
        /** LoginRequest */
        LoginRequest: {
            /** Password */
            password: string;
            /** Username */
            username: string;
        };
        /** LoginResponse */
        LoginResponse: {
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /** Csrf Token */
            csrf_token: string;
            /** Expires In Seconds */
            expires_in_seconds: number;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
        };
        /** LotTrajectory */
        LotTrajectory: {
            /**
             * Arrival
             * Format: date
             */
            arrival: string;
            /** Consumed */
            consumed: number[];
            /** End Balances */
            end_balances: number[];
            /** Expired */
            expired: number[];
            /** Expires On */
            expires_on: string | null;
            /** Id */
            id: string;
            /** Initial Units */
            initial_units: number;
            /**
             * Original Lot Id
             * Format: uuid
             */
            original_lot_id: string;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /** Proposed */
            proposed: boolean;
            /**
             * Site Id
             * Format: uuid
             */
            site_id: string;
        };
        /** MethodOutcome */
        MethodOutcome: {
            candidate: components["schemas"]["Candidate"] | null;
            /** Decision Ids */
            decision_ids: string[];
            /** Error Code */
            error_code?: string | null;
            /** Gap */
            gap?: number | null;
            /**
             * Historical
             * @default false
             */
            historical: boolean;
            method: components["schemas"]["AllocationMethod"];
            /** Native Bound */
            native_bound?: number | null;
            /** Native Status */
            native_status: string | null;
            objective: components["schemas"]["Rational"] | null;
            /** Objective Integer */
            objective_integer?: number | null;
            objective_scale?: components["schemas"]["Rational"] | null;
            /** Operational Hash */
            operational_hash: string;
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "VERIFIED" | "FAILED" | "TIMED_OUT" | "CANCELLED" | "INTERRUPTED";
            /** Physical Fingerprint */
            physical_fingerprint?: string | null;
            /** Policy Hash */
            policy_hash: string;
            /**
             * Schema Version
             * @default or-method-result-v1
             * @constant
             */
            schema_version: "or-method-result-v1";
            /**
             * Search Seconds
             * @default 0
             */
            search_seconds: number;
            /** Settings Hash */
            settings_hash: string;
            /** Solver Version */
            solver_version?: string | null;
            /** Termination Reason */
            termination_reason?: string | null;
            /**
             * Total Seconds
             * @default 0
             */
            total_seconds: number;
            transfer_mode: components["schemas"]["TransferMode"];
            verification: components["schemas"]["VerificationReport"] | null;
            /**
             * Warnings
             * @default []
             */
            warnings: string[];
        };
        /** Metrics */
        Metrics: {
            W: components["schemas"]["Rational"];
            W0: components["schemas"]["Rational"];
            Z: components["schemas"]["Rational"];
            Z0: components["schemas"]["Rational"];
            ap_excess: components["schemas"]["Rational"];
            classical_objective: components["schemas"]["Rational"];
            /** Cost Minor */
            cost_minor: number;
            /** Goals */
            goals: components["schemas"]["GoalMetric"][];
            /** Groups */
            groups: components["schemas"]["GroupMetric"][];
            /** Q Cost */
            q_cost: number;
            /** Q Waste By Product */
            q_waste_by_product: [
                string,
                number
            ][];
            research_objective: components["schemas"]["Rational"];
            rp_excess: components["schemas"]["Rational"];
            /** Warnings */
            warnings: string[];
            /** Waste By Product */
            waste_by_product: [
                string,
                number
            ][];
        };
        /** ORInputPackage */
        ORInputPackage: {
            capacities: components["schemas"]["Capacities"];
            /** Confirmed Arrivals */
            confirmed_arrivals: components["schemas"]["ConfirmedArrival"][];
            /**
             * Dataset Id
             * Format: uuid
             */
            dataset_id: string;
            /** Decision Ids */
            decision_ids: string[];
            /**
             * First Planning Date
             * Format: date
             */
            first_planning_date: string;
            /** Forecasts */
            forecasts: components["schemas"]["ForecastSeries"][];
            /** Inventory */
            inventory: components["schemas"]["InventoryLot"][];
            /** Operational Timezone */
            operational_timezone: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Products */
            products: components["schemas"]["Product"][];
            /** Provenance Warnings */
            provenance_warnings: string[];
            /** Reserves */
            reserves: components["schemas"]["Reserve"][];
            /** Routes */
            routes: components["schemas"]["Route"][];
            /**
             * Schema Version
             * @default or-input-v1
             * @constant
             */
            schema_version: "or-input-v1";
            /** Sites */
            sites: components["schemas"]["Site"][];
            /**
             * Snapshot As Of
             * Format: date-time
             */
            snapshot_as_of: string;
            source_coverage: components["schemas"]["SourceCoverage"];
            /**
             * Source Kind
             * @enum {string}
             */
            source_kind: "SIMULATED" | "LIVE";
            /** Source Manifest Hash */
            source_manifest_hash: string;
            /** Source Refs */
            source_refs: components["schemas"]["SourceRef"][];
            /** Source Revision Token */
            source_revision_token: string;
            /** Vulnerability Attributes */
            vulnerability_attributes: components["schemas"]["VulnerabilityAttributes"][];
        };
        /** ORPolicy */
        ORPolicy: {
            /** Ap Cap Bp */
            ap_cap_bp: number;
            /** Ap Threshold */
            ap_threshold: number;
            /** Beta Percent */
            beta_percent: number;
            /** Coefficients */
            coefficients: components["schemas"]["AttributeCoefficient"][];
            /** Decision Ids */
            decision_ids: string[];
            /** Epsilon Cost Bp */
            epsilon_cost_bp: number;
            /** Epsilon Waste Bp */
            epsilon_waste_bp: number;
            /** Gamma Ap Percent */
            gamma_ap_percent: number;
            /** Gamma Rp Percent */
            gamma_rp_percent: number;
            /** Lambda Percent */
            lambda_percent: number;
            /**
             * Purpose
             * @enum {string}
             */
            purpose: "PRIMARY" | "ABLATION";
            /** Rp Cap Bp */
            rp_cap_bp: number;
            /** Rp Threshold */
            rp_threshold: number;
            /**
             * Schema Version
             * @default or-policy-v1
             * @constant
             */
            schema_version: "or-policy-v1";
            /** Version */
            version: string;
        };
        /** PackageSummary */
        PackageSummary: {
            /** Content Hash */
            content_hash: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Dataset Id
             * Format: uuid
             */
            dataset_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Payload */
            payload?: {
                [key: string]: unknown;
            } | null;
            /** Revision Token */
            revision_token: string;
            /** Schema Version */
            schema_version: string;
            /**
             * Source Kind
             * @enum {string}
             */
            source_kind: "SIMULATED" | "LIVE";
        };
        /** PairSubmit */
        PairSubmit: {
            /** Expected Scenario Hash */
            expected_scenario_hash: string;
            /**
             * Intent
             * @enum {string}
             */
            intent: "CURRENT" | "HISTORICAL_REPLAY";
        };
        /** PlanRef */
        PlanRef: {
            method: components["schemas"]["AllocationMethod"];
            /**
             * Plan Id
             * Format: uuid
             */
            plan_id: string;
            /** Result Hash */
            result_hash: string;
        };
        /** PlanSubmit */
        PlanSubmit: {
            /** Expected Scenario Hash */
            expected_scenario_hash: string;
            /**
             * Intent
             * @enum {string}
             */
            intent: "CURRENT" | "HISTORICAL_REPLAY";
            method: components["schemas"]["AllocationMethod"];
        };
        /** PlanSummary */
        PlanSummary: {
            /** Historical */
            historical: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            result: components["schemas"]["MethodOutcome"];
            /** Result Hash */
            result_hash: string;
            /**
             * Scenario Id
             * Format: uuid
             */
            scenario_id: string;
            /** Stale */
            stale: boolean;
        };
        /** Product */
        Product: {
            /** Handling Coefficient */
            handling_coefficient: number;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Source Revision */
            source_revision: string;
            /** Unit */
            unit: string;
        };
        /** ProductLabel */
        ProductLabel: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Unit */
            unit: string;
        };
        /** ProjectionDay */
        ProjectionDay: {
            /**
             * Day
             * Format: date
             */
            day: string;
            /** Demand */
            demand: number;
            /** Expired */
            expired: number;
            /** On Hand */
            on_hand: number;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /** Received */
            received: number;
            /** Served */
            served: number;
            /**
             * Site Id
             * Format: uuid
             */
            site_id: string;
            /** Unmet */
            unmet: number;
        };
        /** ProjectionReport */
        ProjectionReport: {
            /** Blocked Units */
            blocked_units: [
                string,
                number
            ][];
            /** Days */
            days: components["schemas"]["ProjectionDay"][];
            /** Exclusions */
            exclusions: components["schemas"]["Exclusion"][];
            /** Lots */
            lots: components["schemas"]["LotTrajectory"][];
            /**
             * Schema Version
             * @default or-projection-v1
             * @constant
             */
            schema_version: "or-projection-v1";
            /** Transit */
            transit: components["schemas"]["TransitDay"][];
        };
        /** Rational */
        Rational: {
            /** Denominator */
            denominator: number;
            /** Numerator */
            numerator: number;
        };
        /** Reserve */
        Reserve: {
            /** Floors */
            floors: number[];
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /**
             * Site Id
             * Format: uuid
             */
            site_id: string;
        };
        /** ResetRequest */
        ResetRequest: {
            /**
             * Dataset Id
             * Format: uuid
             */
            dataset_id: string;
        };
        /** ResidualCapacity */
        ResidualCapacity: {
            /** Fixed Used */
            fixed_used: number;
            /** Original */
            original: number;
            /** Residual */
            residual: number;
            /** Source Revision */
            source_revision: string;
        };
        /** ResourceCreated */
        ResourceCreated: {
            /** Content Hash */
            content_hash: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
        };
        /** ReviewRequest */
        ReviewRequest: {
            /**
             * Action
             * @enum {string}
             */
            action: "REVIEWED" | "REJECTED";
            /** Expected Result Hash */
            expected_result_hash: string;
            /** Note */
            note?: string | null;
        };
        /** ReviewResponse */
        ReviewResponse: {
            /** Action */
            action: string;
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Plan Id
             * Format: uuid
             */
            plan_id: string;
            /** Plan Result Hash */
            plan_result_hash: string;
        };
        /** Route */
        Route: {
            capacity: components["schemas"]["ResidualCapacity"];
            /** Cost Unit */
            cost_unit: string;
            /** Costs */
            costs: components["schemas"]["RouteCost"][];
            /**
             * Destination Id
             * Format: uuid
             */
            destination_id: string;
            /** Enabled */
            enabled: boolean;
            /** Eta Days */
            eta_days: number;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Source Id
             * Format: uuid
             */
            source_id: string;
        };
        /** RouteCost */
        RouteCost: {
            /** Cost Minor */
            cost_minor: number;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
        };
        /** RouteQuantity */
        RouteQuantity: {
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /**
             * Route Id
             * Format: uuid
             */
            route_id: string;
            /** Units */
            units: number;
        };
        /** ScenarioCreate */
        ScenarioCreate: {
            /** Expected Source Revision */
            expected_source_revision: string | null;
            /**
             * Input Package Id
             * Format: uuid
             */
            input_package_id: string;
            /**
             * Intent
             * @enum {string}
             */
            intent: "CURRENT" | "HISTORICAL_REPLAY";
            /** Modifiers */
            modifiers: components["schemas"]["DemandModifier"][];
            /** Planning Days */
            planning_days: number;
            /**
             * Policy Id
             * Format: uuid
             */
            policy_id: string;
            transfer_mode: components["schemas"]["TransferMode"];
        };
        /** ScenarioSummary */
        ScenarioSummary: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Decision Ids */
            decision_ids: string[];
            /** Historical */
            historical: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Input Package Id
             * Format: uuid
             */
            input_package_id: string;
            /** Intent */
            intent: string;
            /** Operational Hash */
            operational_hash: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Planning Days */
            planning_days: number;
            /** Policy Hash */
            policy_hash: string;
            /**
             * Policy Id
             * Format: uuid
             */
            policy_id: string;
            /** Products */
            products: components["schemas"]["ProductLabel"][];
            /** Revision Token */
            revision_token: string;
            /** Sites */
            sites: components["schemas"]["SiteLabel"][];
            /** Source Kind */
            source_kind: string;
            /** Stale */
            stale: boolean;
            transfer_mode: components["schemas"]["TransferMode"];
        };
        /** SeedRequest */
        SeedRequest: {
            /**
             * Fixture
             * @enum {string}
             */
            fixture: "six-beneficiary-v1" | "ap-ablation-v1" | "rp-ablation-v1";
        };
        /** SeedResponse */
        SeedResponse: {
            /**
             * Dataset Id
             * Format: uuid
             */
            dataset_id: string;
            /**
             * Input Package Id
             * Format: uuid
             */
            input_package_id: string;
            /** Modifiers */
            modifiers: components["schemas"]["DemandModifier"][];
            /**
             * Policy Id
             * Format: uuid
             */
            policy_id: string;
            /** Source Revision Token */
            source_revision_token: string;
        };
        /** Site */
        Site: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /**
             * Role
             * @enum {string}
             */
            role: "HUB" | "BENEFICIARY";
            /** Source Revision */
            source_revision: string;
            /** Timezone */
            timezone: string;
        };
        /** SiteCapacity */
        SiteCapacity: {
            /** Receiving */
            receiving: components["schemas"]["ResidualCapacity"][];
            /**
             * Site Id
             * Format: uuid
             */
            site_id: string;
            source: components["schemas"]["ResidualCapacity"];
            /** Storage */
            storage: components["schemas"]["ResidualCapacity"][];
        };
        /** SiteLabel */
        SiteLabel: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
        };
        /** SourceCoverage */
        SourceCoverage: {
            /** Excluded Series */
            excluded_series: string[];
            /** Forecast Handoff Hash */
            forecast_handoff_hash: string | null;
            /** Partial Scope */
            partial_scope: boolean;
            /** Required Complete */
            required_complete: boolean;
        };
        /** SourcePackageRequest */
        SourcePackageRequest: {
            /** Expected Source Revision */
            expected_source_revision: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Result Ids */
            result_ids: string[];
        };
        /** SourceRef */
        SourceRef: {
            /** Content Hash */
            content_hash: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Kind */
            kind: string;
            /** Revision */
            revision: string;
        };
        /** TransferAssignment */
        TransferAssignment: {
            /**
             * Arrival
             * Format: date
             */
            arrival: string;
            /** Cost Minor */
            cost_minor: number;
            /**
             * Departure
             * Format: date
             */
            departure: string;
            /**
             * Destination Id
             * Format: uuid
             */
            destination_id: string;
            /**
             * Expires On
             * Format: date
             */
            expires_on: string;
            /**
             * Original Lot Id
             * Format: uuid
             */
            original_lot_id: string;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /**
             * Route Id
             * Format: uuid
             */
            route_id: string;
            /**
             * Source Id
             * Format: uuid
             */
            source_id: string;
            /** Source Revision */
            source_revision: string;
            /** Unit */
            unit: string;
            /** Units */
            units: number;
        };
        /**
         * TransferMode
         * @enum {string}
         */
        TransferMode: "HUB_ONLY" | "HUB_AND_PANTRY";
        /** TransitDay */
        TransitDay: {
            /**
             * Day
             * Format: date
             */
            day: string;
            /**
             * Product Id
             * Format: uuid
             */
            product_id: string;
            /** Units */
            units: number;
        };
        /** VerificationReport */
        VerificationReport: {
            /** Candidate Hash */
            candidate_hash: string;
            metrics: components["schemas"]["Metrics"] | null;
            /** Operational Hash */
            operational_hash: string;
            /** Passed */
            passed: boolean;
            projection: components["schemas"]["ProjectionReport"] | null;
            /**
             * Schema Version
             * @default or-verification-v1
             * @constant
             */
            schema_version: "or-verification-v1";
            /**
             * Verifier Version
             * @default independent-replay-v1
             * @constant
             */
            verifier_version: "independent-replay-v1";
            /** Violations */
            violations: string[];
        };
        /** VulnerabilityAttributes */
        VulnerabilityAttributes: {
            /** Scores */
            scores: components["schemas"]["AttributeScore"][];
            /**
             * Site Id
             * Format: uuid
             */
            site_id: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    methodology_api_v1_allocation_methodology_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    capabilities_api_v1_capabilities_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    comparison_read_api_v1_comparisons__record_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ComparisonSummary"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    demo_reset_api_v1_demo_reset_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    demo_seed_api_v1_demo_seed_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SeedRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SeedResponse"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    health_api_v1_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    job_read_api_v1_jobs__job_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobSummary"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    job_cancel_api_v1_jobs__job_id__cancel_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    job_retry_api_v1_jobs__job_id__retry_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobAccepted"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_package_api_v1_or_input_packages_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-Expected-Revision"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ORInputPackage"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResourceCreated"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    package_from_sources_api_v1_or_input_packages_from_sources_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourcePackageRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResourceCreated"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    package_read_api_v1_or_input_packages__record_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PackageSummary"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_policy_api_v1_or_policies_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ORPolicy"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResourceCreated"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    policy_read_api_v1_or_policies__record_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ORPolicy"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    plan_review_api_v1_plans__plan_id__review_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReviewResponse"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    plan_read_api_v1_plans__record_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlanSummary"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    presenter_login_api_v1_presenter_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LoginResponse"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    presenter_logout_api_v1_presenter_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    presenter_session_api_v1_presenter_session_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    readiness_api_v1_readiness_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    scenario_list_api_v1_scenarios_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioSummary"][];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_scenario_api_v1_scenarios_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScenarioCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioSummary"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    scenario_read_api_v1_scenarios__record_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioSummary"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    submit_pair_api_v1_scenarios__scenario_id__compare_methods_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                scenario_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PairSubmit"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobAccepted"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    submit_plan_api_v1_scenarios__scenario_id__plans_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                scenario_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanSubmit"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobAccepted"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
}
