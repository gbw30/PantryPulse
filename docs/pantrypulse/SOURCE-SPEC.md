# PantryPulse source spec extraction

Recovered from the attached Hackathon spec document.docx. Paragraph text is retained; source tables are linearized and formatting is not reproduced. Source version 1.0, dated October 23, 2026.

V1
PantryPulse
Product Requirements Document & Technical Specification
Version: 1.0 — Hackathon MVPDate: October 23, 2026Status: Proposed / Ready for ImplementationTarget: Gator Hack V, 48-hour development windowApplication type: Predictive analytics and decision-support web platform

1. Product Overview
1.1 Problem Statement
Organizations that distribute essential resources frequently operate with incomplete information about future demand and available inventory.
Food banks, community fridges, and emergency relief centers may experience shortages despite sufficient inventory existing elsewhere in their networks.
Conventional inventory systems primarily report current stock. Forecasting tools estimate future demand but often stop before recommending operational decisions.
PantryPulse addresses both problems by predicting potential shortages and recommending feasible actions to reduce them.
The system combines time-series forecasting, inventory projection, uncertainty analysis, and constrained resource allocation into one interactive platform.
1.2 Product Vision
Enable resource-distribution organizations to anticipate shortages and coordinate inventory before essential goods become unavailable.
The product should answer four questions:
What resources do we currently have, and where?
How much of each resource will we need over the next seven days?
Which locations are at risk of running out?
What feasible actions can reduce those shortages?
1.3 Value Proposition
PantryPulse is not simply a forecasting dashboard.
Its unique value comes from combining:
Predictive intelligence: A specialized time-series model forecasts demand.
Uncertainty awareness: Predictions expose possible variation rather than falsely implying certainty.
Operational optimization: Mathematical solvers identify transfers that respect real constraints.
Explainable decisions: Users can understand why an action is proposed and what it is expected to improve.
Continuous replanning: Inventory and demand changes can trigger updated shortage assessments.
1.4 Target Users
Persona
Responsibilities
Primary needs
Network Coordinator
Oversees multiple locations
Identify shortages, allocate inventory, compare scenarios
Site Manager
Manages a single location
Record stock, inspect demand, request transfers
Volunteer Coordinator
Coordinates transportation
Review proposed deliveries and available capacity
Analyst
Evaluates planning quality
Compare forecasts, baseline accuracy, and shortage outcomes
For the MVP, one demo administrator can perform all roles. Production-grade permissions are deferred.
1.5 Success Metrics
Technical metrics
Forecast error compared with a seasonal-naive baseline.
Prediction-interval coverage, if calibration is implemented.
Number of inventory or capacity constraints violated by a proposed plan.
Solver feasibility and optimization status.
Time needed to regenerate a transfer plan.
Product metrics
Number of projected shortages identified.
Forecasted unmet demand before and after optimization.
Quantity transferred and estimated transportation cost.
Percentage reduction in forecasted unmet demand within the modeled scenario.
Time required for a user to understand and approve a recommendation.
These metrics must distinguish simulated projections from observed real-world outcomes.

2. Scope and Priorities
Priorities:
P0: Required for the hackathon MVP.
P1: Valuable enhancement after the core workflow works.
P2: Future product capability.
2.1 MVP Scope — P0
The demonstration supports:
Dimension
MVP definition
Organization
One simulated distribution network
Locations
Three distribution sites
Resource categories
Two categories, e.g. shelf-stable meals and bottled water
Historical data
Ideally 60–120 daily observations per site/category
Forecast horizon
Seven days
Allocation window
Next 24–72 hours
Data sources
Seeded dataset, CSV upload, and manual adjustments
Forecasting
Chronos-2 with a simple baseline fallback
Shortage detection
Projected inventory versus forecast demand
Optimization
OR-Tools allocation between sites
Planning
Create, review, and approve a simulated transfer plan
Visualization
Dashboard, forecast charts, site inventory, transfer recommendations
Scenario simulation
Modify demand, supply, or site constraints and recalculate
2.2 Secondary Features — P1
Forecast backtesting and coverage calibration.
Multi-day transfer scheduling.
Lot-level expiration-aware optimization.
Volunteer or vehicle routing with travel times.
Natural-language scenario creation using Gemini.
Email or notification alerts.
Role-based access.
Scheduled daily forecasting.
Real data integrations.
2.3 Out of Scope — P2
Real-world autonomous dispatch.
Payment processing.
Actual donation pickup coordination.
Verified food-safety compliance.
Unsupervised emergency-response decisions.
Clinical, nutritional, or medical recommendations.
Training a large forecasting model from scratch.
Production integrations with external food-bank systems.
Critical scope rule: The application recommends simulated operational actions. It does not execute real transfers or claim to ensure that food is safe to distribute.

3. Functional Requirements
ID
Priority
Requirement
Acceptance condition
FR-01
P0
Display all network locations
Each site shows name, inventory, and shortage status
FR-02
P0
Track inventory by site and category
Stock quantities are nonnegative integers
FR-03
P0
Import historical demand
Valid CSV rows are accepted and invalid rows receive specific errors
FR-04
P0
Generate seven-day demand forecasts
Each eligible site/category receives dated forecast values
FR-05
P0
Provide forecasting fallback
Application remains functional when Chronos inference fails
FR-06
P0
Calculate projected inventory
Demand, expected inbound stock, and scheduled outgoing stock are accounted for
FR-07
P0
Detect projected shortages
Deficits are shown by site, category, and date
FR-08
P0
Display uncertainty information
Forecast bands are labeled with their method and interpretation
FR-09
P0
Create planning scenarios
Users can change demand or supply assumptions without altering observed history
FR-10
P0
Optimize resource transfers
Plans respect modeled inventory, capacity, and site constraints
FR-11
P0
Explain recommendations
Each transfer shows origin, destination, category, quantity, and expected benefit
FR-12
P0
Compare before and after
Dashboard displays estimated shortages with and without the proposed plan
FR-13
P0
Handle infeasible scenarios
UI explains that no feasible plan exists under specified constraints
FR-14
P0
Support repeatable demo
A demo reset restores seeded data and a known scenario
FR-15
P0
Record plan changes
A scenario or plan can be reconstructed from stored inputs and outputs
FR-16
P1
Approve plans with reservations
Approval revalidates stock and prevents double allocation
FR-17
P1
Simulate completion of transfers
Completed movements update inventory transactionally
FR-18
P1
View forecast evaluation
Display model error against baselines over held-out periods
FR-19
P1
Support roles
Coordinators and site operators have appropriate permissions
FR-20
P2
Connect live systems
Inventory and demand events can arrive through documented integrations

4. User Stories
Epic A — Inventory Visibility
US-01: Network Overview
As a network coordinator, I want to see every location's inventory and projected shortage status so that I can identify which locations may need help.
Acceptance criteria:
Three locations are visible on the dashboard.
Each location displays available inventory by category.
A shortage indicator is shown when projected demand exceeds available supply.
Selecting a location opens its detailed view.
US-02: Inventory Adjustment
As a site manager, I want to update inventory quantities so that predictions and plans reflect the latest reported stock.
Acceptance criteria:
The user can add or subtract a quantity with a reason.
Negative resulting inventory is rejected.
The adjustment is recorded with a timestamp.
Existing plans are marked stale when an adjustment invalidates their inventory assumptions.
US-03: Historical Demand Import
As an analyst, I want to upload historical demand data so that the system can forecast future resource needs.
Acceptance criteria:
CSV rows are validated.
Duplicate date/site/category observations follow a documented replacement or rejection policy.
Errors identify the affected rows.
Imported data is distinguishable from generated demo data.
Missing demand is not silently treated as zero.
Epic B — Predictive Intelligence
US-04: Demand Forecast
As a network coordinator, I want to view expected demand over the next seven days so that I can prepare inventory before shortages occur.
Acceptance criteria:
Forecasts are timestamped and associated with a model version.
Each forecast contains the site, category, date, and point estimate.
Available uncertainty quantiles are displayed clearly.
Unsupported or insufficient data uses a labeled baseline.
US-05: Shortage Alerts
As a site manager, I want to know when my site may run out of a resource so that I can request additional supply.
Acceptance criteria:
Projected inventory is calculated for each day.
First projected shortage date is displayed when applicable.
Estimated deficit is displayed in resource units.
Forecast-driven warnings are not presented as confirmed shortages.
US-06: Uncertainty Visibility
As a coordinator, I want to see a range of possible outcomes so that I can understand the risk of relying on one forecast.
Acceptance criteria:
Forecast bands identify whether they are model quantiles or calibrated intervals.
The dashboard can compare a central forecast with a conservative planning scenario.
Numerical stockout probabilities are displayed only when a sufficiently validated probabilistic method is implemented.
Epic C — Optimization
US-07: Generate Transfer Plan
As a network coordinator, I want the system to suggest inventory transfers between locations so that I can reduce overall shortages.
Acceptance criteria:
The optimizer uses available inventory and predicted need.
Proposed transfers do not exceed transferable inventory.
Capacity constraints are respected.
A plan includes expected unmet demand and estimated movement cost.
The solver status is visible.
US-08: Inspect Recommendations
As a coordinator, I want to understand why each transfer is recommended so that I can evaluate it before approval.
Acceptance criteria:
Each recommendation includes its source and destination.
It identifies the shortage being addressed.
It shows the expected effect on both locations.
The application states which operational assumptions were used.
US-09: Compare Scenarios
As a coordinator, I want to modify inventory or demand assumptions and see an updated plan so that I can prepare for disruptions.
Acceptance criteria:
A scenario can be created without modifying historical observations.
Optimization can be rerun against the modified assumptions.
Before/after differences are visible.
A plan's inputs are retained for reproducibility.
US-10: Handle Impossible Plans
As a coordinator, I want to know when available resources cannot cover projected need so that I can prioritize unresolved shortages.
Acceptance criteria:
Infeasibility is not silently replaced with an invalid schedule.
The interface shows unmet demand and relevant limiting constraints.
Feasible partial allocations are supported when shortages are unavoidable.
No additional inventory is invented.
Epic D — Demonstration and Trust
US-11: Reproducible Demo
As a judge or evaluator, I want to reset the system to a prepared scenario so that I can repeatedly observe its capabilities.
Acceptance criteria:
Demo reset restores a known scenario.
Sample data is explicitly labeled simulated or proxy-based.
A complete shortage detection and planning workflow can be demonstrated.
US-12: Model Transparency
As an analyst, I want to know which models and datasets produced a recommendation so that I can assess reliability.
Acceptance criteria:
Forecast run metadata is available.
Model version and fallback status are shown.
Data origin is recorded.
Numerical evaluation metrics are not invented.

5. User Experience and Screens
5.1 Overview Dashboard
The first screen should answer:
Which locations are at risk, when, and what can we do about it?
Components:
Summary cards for total available inventory, projected demand, potential shortfall, and projected unmet demand after optimization.
Seven-day shortage timeline.
Site status table or location cards.
Category filters.
Button to generate or inspect an allocation plan.
Data provenance indicator.
5.2 Location Detail
Displays:
Inventory by category.
Recent historical demand.
Forecast demand for seven days.
Projected inventory balance.
Scheduled inbound and outbound movements.
Recommended transfers involving the location.
5.3 Forecast and Risk Explorer
Displays:
Historical and forecast demand.
Quantile or uncertainty bands.
First projected shortage date.
Historical backtest results, when available.
Central versus conservative demand scenarios.
5.4 Resource Allocation Planner
Displays:
Proposed transfer rows.
Origins and destinations.
Resource quantities.
Capacity utilization.
Forecasted shortages before and after.
Solver result status.
Approval or simulation controls.
For the MVP, a transfer matrix or site-to-site flow diagram is sufficient. A geographic map is optional.
5.5 Scenario Simulator
Allows changes to:
Demand multipliers.
Incoming supply.
Donor minimum inventory.
Available transfer capacity.
Site priority weights.
Simulated closures or disruptions.
The user can generate a new plan without overwriting the baseline.

6. System Architecture
6.1 Architectural Style
Use a modular full-stack architecture:
Next.js handles the user interface.
FastAPI exposes versioned application endpoints.
PostgreSQL stores operational records, forecasts, scenarios, and plans.
A forecasting adapter wraps Chronos-2 or a fallback model.
An optimization service wraps OR-Tools.
An inventory projection service performs deterministic calculations.
The services can initially live in one FastAPI codebase. Microservices are unnecessary for the MVP.
6.2 Logical Components
Frontend
Dashboard pages.
Charts and scenario controls.
API client.
Loading/error states.
Demo/reset interface.
API layer
Input validation with Pydantic.
Structured error handling.
CRUD operations.
Forecast and optimization orchestration.
Request logging.
Forecasting module
Historical-data preparation.
Missing-data handling.
Chronos-2 inference.
Seasonal-naive fallback.
Forecast persistence.
Optional backtesting.
Inventory projection module
Available stock calculation.
Scheduled supply calculation.
Projected consumption.
Shortage detection.
Expiration eligibility checks where data is available.
Optimization module
Decision-variable construction.
Hard-constraint enforcement.
Objective evaluation.
Solver execution.
Plan generation.
Feasibility and result metadata.
Persistence layer
PostgreSQL tables.
Migrations.
Query helpers.
Transactional inventory updates.
Audit logging.
6.3 Data Flow
Demand history and inventory data are imported or seeded.
The data layer validates and stores observations.
The forecasting service generates or retrieves demand forecasts.
The inventory service projects future balances for each site/category.
The shortage engine identifies possible deficits.
The optimizer receives transferable inventory, shortages, and constraints.
OR-Tools produces a feasible allocation or reports failure.
The resulting plan is stored and returned.
The frontend displays the recommendation and relevant evidence.
Scenario changes repeat the necessary downstream calculations.
6.4 Architectural Rules
The LLM, if added, must never directly modify inventory or approve transfers.
All quantitative inputs must be validated on the backend.
Forecast runs must be versioned.
Optimization must be reproducible from saved inputs.
Existing forecasts must not be silently modified by new scenarios.
Approved plans must be revalidated against current inventory.
User-facing quantities must always have an explicit category and unit.
Model failure must not prevent users from inspecting existing data.

7. Data Model and Database Schema
Database: PostgreSQLPrimary identifiers: UUIDTimestamps: UTC timestampsOperational planning dates: Site-local calendar dates
7.1 organizations
Column
Type
Description
id
UUID, PK
Organization identifier
name
TEXT
Organization name
is_demo
BOOLEAN
Whether data is simulated
created_at
TIMESTAMPTZ
Creation time
7.2 sites
Column
Type
Description
id
UUID, PK
Site identifier
organization_id
UUID, FK
Owning organization
name
TEXT
Display name
latitude
NUMERIC, nullable
Geographic latitude
longitude
NUMERIC, nullable
Geographic longitude
timezone
TEXT
Site time zone
priority_weight
NUMERIC
Policy-defined shortage priority
max_inbound_units
INTEGER, nullable
Receiving capacity
active
BOOLEAN
Whether site participates
Constraints: Priority weight must be positive; capacities cannot be negative.
7.3 resource_categories
Column
Type
Description
id
UUID, PK
Resource category
name
TEXT
Example: shelf-stable meals
unit
TEXT
Example: meal, bottle, package
active
BOOLEAN
Category enabled
Important: The MVP assumes identical units within each category. It must not add unrelated categories together as though they were interchangeable.
7.4 inventory_lots
Column
Type
Description
id
UUID, PK
Inventory lot
site_id
UUID, FK
Owning site
category_id
UUID, FK
Resource category
quantity_on_hand
INTEGER
Current stock
expires_on
DATE, nullable
Expiration date
received_at
TIMESTAMPTZ
Receipt time
data_source
TEXT
Demo, imported, manual
Constraints: Stock must be nonnegative. Expired lots are excluded from transferable inventory.
The MVP can aggregate eligible lots for planning. Precise lot assignment is required before production dispatch.
7.5 demand_observations
Column
Type
Description
id
UUID, PK
Observation identifier
site_id
UUID, FK
Site
category_id
UUID, FK
Category
demand_date
DATE
Observation date
requested_units
INTEGER, nullable
Total recorded requests
fulfilled_units
INTEGER
Served units
unmet_units
INTEGER, nullable
Unserved requests
source_type
TEXT
Observed, proxy, simulated
created_at
TIMESTAMPTZ
Ingestion time
Constraints:
Quantities cannot be negative.
Unique site/category/date observations in the active dataset.
If all counts are supplied, requested units should equal fulfilled plus unmet units.
Data-quality rule: Fulfilled demand is not necessarily true demand. If unmet requests were not tracked, the UI must warn that the forecasting target may underestimate actual need.
7.6 scheduled_supplies
Column
Type
Description
id
UUID, PK
Supply identifier
site_id
UUID, FK
Receiving site
category_id
UUID, FK
Category
expected_date
DATE
Planned arrival
quantity
INTEGER
Incoming stock
status
TEXT
Expected, confirmed, received, cancelled
Only appropriate statuses should contribute to projected incoming inventory, with assumptions shown in the UI.
7.7 forecast_runs
Column
Type
Description
id
UUID, PK
Forecast run
organization_id
UUID, FK
Organization
model_name
TEXT
Chronos-2, seasonal-naive, etc.
model_version
TEXT
Model identifier/checkpoint
generated_at
TIMESTAMPTZ
Creation time
horizon_days
INTEGER
Prediction horizon
data_cutoff_date
DATE
Last historical date
data_source_label
TEXT
Observed, proxy, simulated
status
TEXT
Queued, running, succeeded, failed
evaluation_json
JSONB
Optional backtesting results
error_message
TEXT, nullable
Failure reason
7.8 forecast_points
Column
Type
Description
id
UUID, PK
Forecast point
run_id
UUID, FK
Forecast run
site_id
UUID, FK
Site
category_id
UUID, FK
Category
forecast_date
DATE
Prediction date
p10
NUMERIC, nullable
Lower model quantile
p50
NUMERIC
Central demand estimate
p90
NUMERIC, nullable
Upper model quantile
interval_method
TEXT
Model quantiles, calibrated, or none
Use a unique constraint over (run_id, site_id, category_id, forecast_date).
7.9 scenarios
Column
Type
Description
id
UUID, PK
Scenario
organization_id
UUID, FK
Organization
forecast_run_id
UUID, FK
Baseline forecast
name
TEXT
Scenario name
overrides_json
JSONB
Demand and supply modifications
created_at
TIMESTAMPTZ
Creation time
Overrides must be schema-validated before use.
7.10 allocation_plans
Column
Type
Description
id
UUID, PK
Allocation plan
scenario_id
UUID, FK
Scenario
inventory_version
BIGINT
Inventory snapshot version
solver_status
TEXT
Optimal, feasible, infeasible, unknown
plan_status
TEXT
Draft, approved, stale, cancelled
objective_value
NUMERIC, nullable
Solver objective
unmet_before
NUMERIC
Projected unmet units before
unmet_after
NUMERIC
Projected unmet units after
movement_cost
NUMERIC
Estimated transfer cost
assumptions_json
JSONB
Solver parameters
generated_at
TIMESTAMPTZ
Plan creation time
7.11 plan_transfers
Column
Type
Description
id
UUID, PK
Transfer identifier
plan_id
UUID, FK
Owning plan
from_site_id
UUID, FK
Source
to_site_id
UUID, FK
Destination
category_id
UUID, FK
Resource category
quantity
INTEGER
Transfer quantity
planned_date
DATE
Planned movement date
estimated_cost
NUMERIC
Scenario-specific cost
status
TEXT
Proposed, reserved, completed, cancelled
Constraints: Quantity must be positive; source and destination must differ.
7.12 inventory_movements
Column
Type
Description
id
UUID, PK
Movement identifier
site_id
UUID, FK
Affected site
lot_id
UUID, FK, nullable
Affected lot
category_id
UUID, FK
Category
signed_quantity
INTEGER
Increase or decrease
reason
TEXT
Adjustment, transfer, receipt
transfer_id
UUID, nullable
Associated transfer
created_at
TIMESTAMPTZ
Movement time
idempotency_key
TEXT, nullable
Duplicate-operation protection
For P1 transfer approval, add explicit inventory reservations per lot. A transfer should not consume physical inventory until a simulated or verified completion event.
7.13 Database Integrity
Required indexes:
demand_observations(site_id, category_id, demand_date)
inventory_lots(site_id, category_id, expires_on)
forecast_points(run_id, site_id, category_id, forecast_date)
plan_transfers(plan_id)
scheduled_supplies(site_id, category_id, expected_date)
Use database transactions for inventory adjustments, reservations, and transfer completion.
Store plan input snapshots or references to immutable versions so calculations remain reproducible.

8. API Specification
Base path:/api/v1Protocol: HTTPSContent type:application/jsonSchema: Pydantic models exported as OpenAPI through FastAPI.
8.1 API Conventions
Standard error response
{ "error": { "code": "INVALID_QUANTITY", "message": "Quantity must be positive", "details": {} }, "request_id": "..." }
Status codes
Code
Meaning
200
Successful read or action
201
Resource created
202
Background forecast accepted
400
Malformed request
401
Authentication required, if enabled
403
Action not permitted
404
Resource not found
409
Version or inventory conflict
422
Schema or business-rule validation failed
500
Unexpected internal error
503
Forecast provider unavailable without usable fallback
Every mutating request should be traceable. Approval and completion endpoints must support idempotency keys.
8.2 Dashboard
GET /dashboard/summary
Returns network-wide operational summaries.
Response fields:
site_count
category_count
inventory_by_category
projected_shortage_count
at_risk_sites
latest_forecast_run_id
data_source_label
Behavior: Return the latest committed data; do not run model inference during dashboard reads.
8.3 Site and Inventory APIs
GET /sites
Returns all sites within the active organization.
GET /sites/{site_id}/inventory
Returns inventory by category, current stock, eligible transferable stock, and scheduled inbound supply.
POST /inventory/adjustments
Example request:
{ "site_id": "SITE_UUID", "category_id": "CATEGORY_UUID", "quantity_delta": 25, "reason": "New donation", "expected_inventory_version": 4 }
Behavior:
Validate category, site, quantity, and inventory version.
Reject changes that would produce negative stock.
Record a movement.
Increment the inventory version.
Mark incompatible draft plans stale.
Return the updated inventory.
Response:201 Created with adjustment ID and new inventory version.
8.4 Demand API
GET /demand/history
Query parameters:
site_id
category_id
start_date
end_date
Returns chronologically ordered demand observations and provenance labels.
POST /demand/import
Accepts a CSV upload containing:
site_id, category_id, demand_date, requested_units, fulfilled_units, unmet_units, source_type
Behavior:
Validate headers and rows.
Detect duplicates.
Report accepted and rejected counts.
Never silently convert missing values to zero.
Store provenance.
MVP policy: Reject duplicate observation keys rather than automatically overwriting existing records.
8.5 Forecast API
POST /forecast-runs
Starts a forecasting job.
Example request:
{ "organization_id": "ORG_UUID", "horizon_days": 7, "model": "chronos-2", "allow_fallback": true }
Behavior:
Validate the available historical time series.
Normalize the daily frequency.
Select the requested model when operational.
Use a documented fallback when permitted and necessary.
Store model metadata.
Persist results after successful inference.
Response:202 Accepted
{ "run_id": "RUN_UUID", "status": "queued" }
For very small synchronous inference, returning 201 Created with a completed run is also permitted, but the frontend must use the returned status rather than assume completion.
GET /forecast-runs/{run_id}
Returns status, model metadata, errors, and evaluation metrics.
GET /forecast-runs/{run_id}/points
Returns dated forecast values by site and category.
Example forecast point:
{ "site_id": "SITE_UUID", "category_id": "CATEGORY_UUID", "date": "2026-10-24", "p10": 82, "p50": 104, "p90": 139, "interval_method": "model_quantiles" }
Model quantiles must not be mislabeled as empirically calibrated intervals.
8.6 Shortage API
GET /shortages
Query parameters:
forecast_run_id
scenario_id (optional)
planning_mode (central or conservative)
Returns:
Site.
Category.
First projected deficit date.
Forecasted shortage quantity.
Current inventory.
Expected inbound supply.
Planning assumptions.
Risk classification.
Behavior: Recompute or retrieve deterministic projections against the selected forecast and inventory snapshot.
8.7 Scenario API
POST /scenarios
Example request:
{ "name": "Demand surge", "forecast_run_id": "RUN_UUID", "overrides": { "demand_multiplier": 1.25, "disabled_site_ids": [] } }
Behavior:
Validate allowed override fields and ranges.
Preserve the baseline.
Store the scenario.
Return its identifier.
GET /scenarios/{scenario_id}
Returns the scenario configuration and linked plans.
8.8 Optimization API
POST /scenarios/{scenario_id}/plans
Example request:
{ "planning_days": 2, "priority_mode": "minimize_weighted_shortage", "max_total_transfer_units": 300, "solver_time_limit_seconds": 5 }
Behavior:
Retrieve the scenario and immutable forecast snapshot.
Calculate eligible stock.
Construct solver variables and hard constraints.
Optimize the defined objective.
Store the result, including solver status.
Return plan and transfer identifiers.
Response:201 Created
Example response:
{ "plan_id": "PLAN_UUID", "solver_status": "OPTIMAL", "plan_status": "draft", "unmet_before": 190, "unmet_after": 65, "transfers": [{ "from_site_id": "SITE_A", "to_site_id": "SITE_B", "category_id": "MEALS", "quantity": 125 }] }
These quantities are illustrative. The API must return OPTIMAL only when the solver proves optimality.
GET /plans/{plan_id}
Returns plan details, proposed transfers, assumptions, and objective metrics.
POST /plans/{plan_id}/approve — P1
Behavior:
Confirm the expected inventory version matches.
Revalidate transfer feasibility.
Reserve eligible inventory atomically.
Reject conflicting approvals with 409 Conflict.
Mark the plan approved.
POST /transfers/{transfer_id}/complete — P1
Records a simulated completed movement transactionally, updates stock and reservations, and rejects duplicate completion.
8.9 Demo API
POST /demo/reset
Recreates a documented demo dataset and baseline scenario.
This endpoint must operate only on a dedicated demo organization. It must never reset production operational data.

9. Forecasting Specification
9.1 Prediction Target
The model predicts daily requested resource units for each site/category pair.
Each pair is treated as a time series identified by:
series_id = site_id + category_id
9.2 Input Features
Required:
Historical daily demand.
Site identifier.
Category identifier.
Calendar date.
Optional:
Day of week.
Holiday/event indicators.
Planned closures.
Forecast weather.
Other future-known covariates.
Covariates must be known or forecast for the future horizon. Actual future outcomes must never leak into the forecasting inputs.
9.3 Model Selection
Primary: Chronos-2.
Baseline: Seasonal naive, using values from the previous comparable weekday.
Fallback: Seasonal naive, or a simpler moving-average model when data is insufficient.
Chronos-2's public interface supports long-format DataFrames, quantile levels, and optional future covariates.
The application should isolate model-specific code behind a common forecasting interface so the model can be replaced without changing the API contract.
9.4 Data Preparation
Enforce one daily record per site/category/date.
Sort observations chronologically.
Reject duplicate keys.
Flag missing dates rather than treating them automatically as zero demand.
Separate real observations from synthetic and proxy data.
Clip invalid negative values only after recording a validation error; do not silently repair source data.
Evaluate performance on future periods not included in the model's historical context.
9.5 Forecast Output
For each day:
Central demand estimate.
Optional lower and upper quantiles.
Model identifier.
Forecast generation timestamp.
Data cutoff date.
Fallback flag.
Resource counts may be integer-valued in the UI, but preserve underlying numerical forecast values for evaluation.
9.6 Uncertainty and Calibration
The MVP may initially use model-generated quantiles.
A P1 enhancement may calibrate intervals using chronological residuals or appropriate time-series conformal techniques.
The system must distinguish:
Raw model quantiles.
Empirically calibrated prediction intervals.
User-specified conservative planning buffers.
Do not claim that an interval represents a calibrated probability until evaluation supports that interpretation.
9.7 Forecast Evaluation
Evaluate using chronological holdout windows.
Metrics:
Mean absolute error.
Weighted absolute percentage error, with appropriate handling of zero-demand groups.
Bias.
Prediction-interval empirical coverage, when intervals are evaluated.
Compare Chronos-2 against at least one simple baseline.
If Chronos does not outperform the baseline on the selected data, the application should report that result and use the more suitable model.

10. Shortage Detection Specification
10.1 Projected Inventory
For a site, category, and target date:
Projected inventory = starting eligible inventory + confirmed incoming supply − projected demand − committed outgoing supply + committed incoming transfers
All terms must refer to the same unit and calendar period.
10.2 Shortage Classification
A projected shortage exists when the computed balance falls below zero.
The backend should expose:
First projected shortage date.
Magnitude of projected deficit.
Forecast method.
Whether the estimate used central or conservative assumptions.
Suggested UI categories:
No projected deficit: Central and conservative projections remain nonnegative.
Potential deficit: Central forecast remains nonnegative but conservative assumptions create a deficit.
Projected deficit: Central forecast creates a negative projected balance.
Insufficient data: Reliable projection could not be constructed.
These categories are operational indicators, not independently calibrated probabilities.
10.3 Important Accounting Rules
Do not double-count a transfer as both scheduled inbound supply and inventory already on hand.
Exclude expired or already reserved inventory where applicable.
Approved but incomplete transfers are commitments, not completed physical movements.
Treat future inbound supplies according to their recorded certainty/status.
Recalculate projections when relevant inventory or supply information changes.
Do not add daily quantile bounds together and claim the result is a calibrated aggregate interval.

11. Resource Optimization Specification
11.1 Optimization Objective
Minimize a weighted combination of:
Forecasted unmet demand.
Transportation or movement costs.
Unnecessary transfers.
Shortage reduction should take priority over minor transportation savings when that matches the organization's selected policy.
A lexicographic optimization strategy can first minimize weighted unmet demand and then minimize cost among solutions with the best shortage objective.
11.2 Decision Variables
Let:
x(i,j,c) = quantity of resource category c transferred from site i to site j.
Each decision variable is a nonnegative integer.
Optional variables represent remaining shortages after allocation.
11.3 Hard Constraints
The optimizer must enforce:
No negative inventory.
No transferring more stock than is eligible and available.
Donor minimum-reserve requirements.
Destination receiving capacity.
Maximum total transfer quantity.
Category compatibility.
No self-transfer.
Any explicitly modeled delivery-time restrictions.
Optional vehicle capacity constraints.
11.4 Soft Objectives
Subject to those hard constraints, the optimizer attempts to:
Reduce weighted unmet demand.
Reduce the number of unnecessary movements.
Reduce estimated transportation costs.
Respect policy-defined priorities.
11.5 Solver Outcomes
Possible statuses:
OPTIMAL: A mathematically optimal solution was proven for the defined model.
FEASIBLE: A valid solution was found, but optimality was not established.
INFEASIBLE: No solution satisfies all hard constraints.
UNKNOWN: Solver did not produce a conclusive result.
For unavoidable shortages, unmet demand should be represented as an explicit slack variable where appropriate, so the solver can return a best-effort allocation rather than declaring an otherwise useful scenario infeasible.
11.6 Baseline Comparison
Include a simple comparison such as:
No redistribution.
Equal-share allocation.
Greedy allocation to the largest shortage.
Optimized allocation.
Measure:
Unmet units.
Weighted unmet demand.
Transfers required.
Estimated movement cost.
Constraint violations.
All baseline methods must use the same input data and feasible-resource assumptions.

12. Technology Stack
Layer
Selection
Reason
Frontend
Next.js App Router + React + TypeScript
Rapid full-stack UI development
CSS
Tailwind CSS
Fast responsive styling
UI components
shadcn/ui + Radix primitives
Accessible, customizable components
Animation
Motion for React
Explain state changes and transfer movement
Charts
Recharts
Straightforward inventory and forecast visualizations
Maps, optional
MapLibre
Visualize site locations and inventory flows
API backend
FastAPI + Pydantic
Python-native ML/optimization integration
Forecasting
Chronos-2
Pretrained time-series foundation model
Baseline
Seasonal naive
Simple, interpretable evaluation reference
Uncertainty
Model quantiles; optional conformal calibration
Quantify forecasting uncertainty
Optimization
Google OR-Tools
Constraint programming and allocation
Database
Neon PostgreSQL
Managed relational persistence
ORM / migrations
SQLAlchemy + Alembic
Conventional Python database tooling
Frontend hosting
Vercel
Fast deployments and preview URLs
Backend hosting
Railway or comparable Python service
Run FastAPI separately from frontend
Code hosting
GitHub
Collaboration and delivery
Testing
pytest + Vitest/Playwright
Backend correctness and frontend regression
AI coding workflow
Codex / Claude Code
Accelerate implementation and testing
12.1 Repository Organization
Recommended monorepo:
pantrypulse/
apps/web/ — Next.js frontend
apps/api/ — FastAPI backend
apps/api/routers/ — Versioned HTTP routes
apps/api/services/forecasting/ — Forecast provider adapters
apps/api/services/inventory/ — Inventory projections
apps/api/services/optimization/ — OR-Tools model
apps/api/models/ — Database ORM models
apps/api/schemas/ — Pydantic contracts
apps/api/migrations/ — Alembic migrations
packages/contracts/ — Shared OpenAPI-generated TypeScript types
data/demo/ — Seeded datasets
tests/ — API, optimization, and end-to-end tests
docs/ — Product specification, architecture, API, demo plan
Use generated API types to prevent frontend/backend contract drift.
12.2 Environment Variables
Frontend:
NEXT_PUBLIC_API_BASE_URL
Backend:
DATABASE_URL
CORS_ALLOWED_ORIGINS
APP_ENV
DEMO_MODE
FORECAST_MODEL_ID
FORECAST_DEVICE
SOLVER_TIME_LIMIT_SECONDS
Optional:
GEMINI_API_KEY
Monitoring credentials.
All secrets must remain server-side. Never place secrets in NEXT_PUBLIC_ environment variables.

13. Nonfunctional Requirements
13.1 Performance
For the small MVP dataset, target:
Cached dashboard reads under 1 second in normal conditions.
Solver completion under 5 seconds for the seeded three-site scenario.
Forecast generation through a background job or explicitly bounded request.
Visible loading states for all operations.
These are acceptance targets, not hosting guarantees.
13.2 Reliability
Existing dashboards remain accessible when forecasting fails.
Forecasting falls back to a baseline where appropriate.
Invalid optimization inputs return structured errors.
Plans are never labeled optimal without proof.
Demo data can be reset to a reproducible state.
13.3 Security
Validate all incoming API data.
Restrict CORS to known application origins.
Use parameterized SQL/ORM queries.
Keep database credentials server-side.
Rate-limit publicly exposed mutating endpoints where feasible.
Restrict the demo reset endpoint to demo-only data.
Log approval and inventory movement actions.
Avoid storing personal information not required for the demonstration.
13.4 Accessibility
Responsive design.
Keyboard-accessible controls.
Clear text labels for risk statuses.
Sufficient visual contrast.
Accessible descriptions for charts.
Never communicate shortages using color alone.
13.5 Observability
Log:
Forecast run ID and duration.
Forecast provider and fallback reason.
Model error metadata.
Optimization run ID and status.
Solver duration.
API request ID.
Inventory version conflicts.
Do not log sensitive operational data unnecessarily.

14. Demo Scenario
14.1 Seeded Environment
Three fictional food distribution sites:
North Community Pantry.
Central Community Pantry.
South Community Pantry.
Two categories:
Shelf-stable meals.
Bottled water.
The seeded data must create:
One site with a projected shortage.
One site with transferable surplus.
One site near its minimum reserve.
A constrained transfer capacity.
14.2 Demonstration Sequence
Scene 1 — Current state
Open the dashboard and show inventory across the three locations.
Scene 2 — Future shortage
Open forecasts and identify a location expected to run short within the seven-day window.
Scene 3 — Preventive action
Generate an allocation plan. Show proposed transfers, remaining unmet demand, and solver status.
Scene 4 — Unexpected disruption
Simulate a supply reduction or demand surge.
Scene 5 — Reoptimization
Recompute the plan. Demonstrate that allocations change while hard constraints remain satisfied.
Scene 6 — Technical proof
Reveal the baseline-versus-optimized comparison and explain the specialized roles of forecasting, uncertainty, and mathematical optimization.
14.3 Judging Message
“Most inventory tools show what organizations have. PantryPulse predicts what they will need, identifies shortages before they occur, and recommends feasible redistribution plans under resource constraints.”

15. Testing and Acceptance
15.1 Inventory Tests
Adjustment increases stock correctly.
Adjustment cannot create negative stock.
Stock is not double-counted after a transfer.
Expired inventory is excluded from eligible supply.
Stale inventory versions are rejected.
15.2 Forecast Tests
Valid historical series produces seven dated outputs.
Missing observations are detected.
Invalid numerical values are rejected.
Chronos failure invokes the documented fallback.
Forecast metadata identifies the actual model used.
Historical test data does not leak future observations.
15.3 Optimization Tests
No transfer exceeds eligible source stock.
No source falls below its required reserve.
Destination receiving capacity is respected.
Impossible constraints produce correct solver status.
Unavoidable demand shortages remain explicitly visible.
Plans do not create stock.
Results can be reconstructed from stored inputs.
15.4 API Tests
Valid requests return documented responses.
Missing identifiers return 404.
Invalid quantities return 422.
Inventory version conflicts return 409.
Failed background jobs expose an error state.
Duplicate transfer completion does not modify stock twice.
15.5 End-to-End Tests
Dashboard loads seeded network.
User inspects a shortage.
User generates a feasible transfer plan.
User changes a scenario.
UI displays the new projected result.
Demo reset restores the initial scenario.
15.6 Definition of Done
The MVP is complete when:
A deployed dashboard displays three locations and two resource categories.
Historical demand and inventory data are available.
Seven-day demand predictions can be generated or retrieved.
A documented baseline fallback works.
Projected shortages are calculated correctly.
OR-Tools produces a feasible allocation plan.
Hard constraints are checked by automated tests.
The user can modify a scenario and rerun optimization.
Before-and-after unmet demand is displayed.
The system distinguishes simulated data from real observations.
An automated end-to-end test exercises the main workflow.
The project is deployed and a reproducible demo can be performed.
README, architecture overview, model limitations, and demo instructions are committed.

16. Implementation Roadmap
Phase 1 — Hours 0–8: Foundation
Initialize monorepo.
Set up frontend/backend.
Define schema and seed data.
Implement site and inventory APIs.
Build simple network dashboard.
Define solver requirements.
Deliverable: Working application showing inventory across three locations.
Phase 2 — Hours 8–18: Forecasting
Implement demand ingestion.
Integrate seasonal-naive baseline.
Integrate Chronos-2.
Store forecast runs and points.
Build shortage projections.
Deliverable: System can identify projected shortages.
Phase 3 — Hours 18–30: Optimization
Implement transfer decision variables.
Add inventory, reserve, and capacity constraints.
Define shortage minimization objective.
Build optimization APIs.
Add automated solver tests.
Deliverable: System produces valid resource allocation recommendations.
Phase 4 — Hours 30–40: User Experience
Add scenario simulator.
Add forecast charts and shortage summary.
Show transfers before and after.
Implement meaningful loading/error states.
Polish responsive layouts.
Deliverable: Complete user journey.
Phase 5 — Hours 40–48: Stabilization
Execute test suite.
Prepare deterministic demonstration.
Verify deployment.
Document model and data limitations.
Record backup demo.
Finalize repository and submission.
Deliverable: Reliable demonstration and submission.

17. Risks and Mitigations
Risk
Severity
Mitigation
Chronos inference is too slow
High
Precompute a seeded forecast; allow baseline fallback
No credible food-bank demand dataset
High
Disclose use of retail proxy or synthetic scenario
Solver returns infeasible
Medium
Model unavoidable shortage explicitly and present partial allocations
Inventory logic double-counts transfers
High
Immutable forecasts, transactional movements, explicit reservations
Forecast seems accurate only because of leakage
High
Chronological evaluation and strict data cutoff
Backend deployment is unstable
High
Maintain local demo path and prerecorded backup
UI hides the algorithmic contribution
Medium
Show constraints, before/after metrics, and model labels
Scope exceeds 48 hours
High
Enforce P0 first; defer routing, accounts, and advanced AI interface
Users interpret projections as guaranteed outcomes
High
Provenance labels, uncertainty, and explicit decision-support disclaimer
Dataset has too little history
Medium
Minimum-history checks and documented simple fallback

18. Future Roadmap
Phase 2 — Operational Features
Multiple organizations.
Authentication and site-specific roles.
Inventory reservations.
Scheduled incoming deliveries.
Volunteer and vehicle capacity.
Notifications.
Lot-level expiration planning.
Audit trail and reporting.
Phase 3 — Advanced Intelligence
Rolling forecast recalibration.
More sophisticated demand covariates.
Probabilistic stockout estimation with validated coverage.
Real-time inventory streams.
Multi-day stochastic or robust optimization.
Route planning with accurate travel-time data.
Gemini-assisted natural-language scenario creation.
Phase 4 — Organization Integrations
Existing inventory systems.
Donation platforms.
Food-bank operational records.
External warehouse or logistics systems.
These integrations require security review, authorization, domain validation, and operational testing before production use.

19. Design Principles
Model limitations must be visible. Forecast uncertainty is part of the product, not an implementation detail to hide.
Optimization constraints must be testable. A solver result is only as trustworthy as the input data and encoded rules.
No fictitious impact claims. Demonstration outcomes based on synthetic or proxy data must be labeled accordingly.
Human operators retain control. The application proposes plans rather than executing real deliveries automatically.
One reliable capability is better than several incomplete features. The MVP prioritizes prediction-to-action over unnecessary integrations.
Every recommendation must be reproducible. Preserve the model, data snapshot, scenario inputs, and solver results.
Build for graceful degradation. The shortage and optimization modules remain usable when the primary forecasting model is unavailable.

20. Implementation References
Chronos forecasting:https://github.com/amazon-science/chronos-forecasting
OR-Tools:https://developers.google.com/optimization
MAPIE:https://mapie.readthedocs.io/
FastAPI:https://fastapi.tiangolo.com/
Next.js:https://nextjs.org/docs
Neon PostgreSQL:https://neon.com/docs
shadcn/ui:https://ui.shadcn.com/docs
Recharts:https://recharts.org/
Playwright:https://playwright.dev/
M5 forecasting dataset:https://www.kaggle.com/competitions/m5-forecasting-accuracy/overview
Final product definition: PantryPulse is a predictive resource-coordination platform that combines specialist forecasting, transparent uncertainty, and constrained optimization to identify potential shortages and recommend feasible preventive actions.
