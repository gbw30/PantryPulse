# Proposed Backend Behavior in Simple Terms

> **Current authority:** [Project specification V5](SPEC-V5.md). Plain-language historical explanation. V5 governs accepted behavior, review-only plans, explicit transfer modes and the actual main/forecasting-branch state.

PantryPulse is meant to help someone running a food-distribution network answer three questions:

1. **What supplies do we have?**
2. **Where might we run short?**
3. **How could we move supplies to help?**

The **backend** is the part behind the screens that stores information, performs calculations, and sends results to the website. The document describes how that backend is intended to work; these features are mostly still proposed.

**1. It starts by keeping organized records.**

Think of the database as a collection of connected spreadsheets:

| Records | What they tell us |
|---|---|
| Organizations | Who runs the network |
| Sites | Where supplies are stored or distributed |
| Products | What is being distributed, such as meals or water bottles |
| Inventory batches | How much of each product is at each site, and when it expires |
| Demand history | What people requested, received, and went without |
| Donation history | What donated supplies arrived in the past |
| Expected deliveries | What supplies are scheduled to arrive |
| Operating rules | How much each site can receive, what it must keep, and which movements are possible |
| Planning rules | How to balance shortages, priority, cost, and waste |
| Events | What someone changed, approved, or completed |

Each record has a unique identifier so the system can connect information correctly. For example, a batch of meals points to both its product record and the pantry holding it.

The system also distinguishes **when something happened** from **which day it belongs to**. A pantry’s daily demand follows that pantry’s local calendar.

**2. It calculates how much stock can actually be used or shared.**

A pantry reporting “100 meals” does not mean all 100 can be sent elsewhere.

Some might already be promised to another pantry. Some might expire before delivery. The pantry might need some for its own visitors.

For example:

```text
100 meals physically present
− 20 already promised
− 50 needed locally
− 10 required as a reserve
= 20 available to share
```

The backend checks all those conditions before recommending a transfer.

It also tracks supplies by **batch**, called a “lot” in the document. Two batches of the same meals can have different expiration dates. When both are eligible, the system should use the batch expiring sooner first.

Expired batches stay in the records so the organization can review what happened.

If someone reports that five meals were damaged, the backend records a stock adjustment with a reason. It checks the change, updates the balance, and keeps a history.

Two technical protections help keep these records consistent:

- An **inventory version** is a revision number. A request based on an older revision can be rejected because the stock has changed.
- A **transaction** makes related database changes succeed together. For example, updating stock and recording the adjustment must both succeed.

Plans based on outdated stock become **stale**, meaning they need to be checked or recalculated.

A physical stock count is handled separately: counting 90 meals when the system expects 100 first creates a discrepancy to investigate.

**3. It uses past activity to estimate future demand and donations.**

The backend builds daily histories for each location and product.

For example:

```text
Pantry A — meal requests:
Monday: 40
Tuesday: 46
Wednesday: 43
...
```

That daily sequence is a **time series**.

A forecasting model examines the sequence and estimates the next seven days. The proposed system can use Chronos-2, with a simpler backup such as using the previous comparable weekday.

The distinction between **requested** and **served** matters:

```text
People requested 60 meals.
The pantry supplied 45.
15 requests went unmet.
```

The system should learn from the 60 requested. Learning only from the 45 supplied could make a pantry that regularly runs out appear to need less food.

A missing record also stays different from zero:

- **Zero:** someone recorded that there were no requests.
- **Missing:** the system does not know how many requests occurred.

Donations are forecast separately. Predicting that 30 donated meals might arrive does not turn them into a confirmed delivery.

Forecasts can contain a central estimate and lower/upper estimates. For example:

> “The central estimate is around 43 meals, with lower and higher possible demand.”

The backend saves which model made the prediction, what history it used, and whether a backup was needed. It preserves precise values for analysis, while the planner rounds required quantities upward to whole units.

**4. It works through future days to find shortages.**

A forecast estimates demand. The next calculation asks whether the available supplies can cover that demand.

For each day, the backend considers:

```text
Usable stock
+ supplies arriving in time
− supplies leaving
− demand
```

It also accounts for expiration and existing commitments.

Suppose a pantry has 40 meals:

| Day | Demand | Meals served | Unmet requests |
|---|---:|---:|---:|
| Today | 50 | 40 | 10 |
| Tomorrow | 40 | 0 | 40 |

Total unmet demand is **50 meals**.

The system counts each day’s unmet demand once. Yesterday’s 10 missed meals are not automatically added to tomorrow’s requests.

The output tells the website:

- When the first shortage is expected.
- How much demand may go unmet each day.
- How much stock may remain.
- Which incoming supplies were assumed.
- Whether the calculation used central or more cautious assumptions.

A cautious estimate is useful for planning, but it does not automatically tell us an exact percentage chance of running out.

**5. Users can explore a “what if” situation.**

A **scenario** is a saved hypothetical situation.

Examples include:

- Demand increases by 25%.
- A donation is cancelled.
- A delivery is delayed.
- A location becomes unavailable.

If the baseline forecast is 40 meals per day, a 25% increase becomes 50.

The system stores this assumption separately, so the original history and forecast remain available.

It also saves the stock, deliveries, rules, and other inputs used for a plan. This saved set is called a **snapshot**.

A snapshot lets someone later ask:

> “What information did the system use when it recommended this?”

**6. It calculates possible transfers and chooses a plan.**

The optimizer is the part that decides how much to move between locations.

It considers questions such as:

- Can Pantry B spare 20 meals?
- Can Pantry A receive them?
- Will they arrive before they are needed?
- Will the meals still be eligible for use?
- Would sending them create a shortage at B?

These are the rules every recommendation must satisfy.

The system then compares valid choices according to a planning policy. V4 proposes two approaches:

| Approach | Plain-language meaning |
|---|---|
| `CLASSICAL_GP` | Balance shortfalls using conventional priorities |
| `EGP_PI_INSPIRED` | Also consider documented site-level vulnerability and how unevenly shortages are distributed |

A **normalized shortfall** expresses unmet need as a share:

```text
Needs 100 meals, receives 60 → 40% unmet
Needs 20 meals, receives 12 → 40% unmet
```

That helps compare locations of different sizes.

The research-inspired approach can give some shortfalls greater importance using documented site attributes. It also asks:

- **Absolute deprivation:** Is this site’s weighted shortfall above a chosen threshold?
- **Relative deprivation:** Is its weighted shortfall substantially worse than its comparison group’s average?

Both approaches use the same supplies and operating constraints. Their priorities can produce different recommendations, and the comparison should show the trade-offs.

After a plan is produced, another calculation checks that it obeys the rules and measures its effects. Sending meals only helps projected service if they arrive in time to meet demand.

**7. The output is a recommendation with an explanation.**

Using the document’s example:

| | Pantry A | Pantry B |
|---|---:|---:|
| Meals currently present | 40 | 100 |
| Expected two-day demand | 80 | 60 |
| Required reserve | 0 | 20 |

A is short 40 meals. B can cover its own demand, keep its reserve, and share 20.

A feasible recommendation is:

> “Send 20 meals from B to A. A’s projected unmet demand falls from 40 to 20. B can still meet its own demand and retain 20.”

The result includes the origin, destination, product, batch, quantity, assumptions, and expected effects.

It also explains the solver’s confidence in the decision:

- **Feasible:** the plan follows the rules.
- **Optimal:** the solver proved it is best under the selected mathematical objective.
- **Infeasible:** the hard rules contradict one another.
- **Unknown:** the solver did not establish a usable result within its limits.

A shortage can remain even in a valid plan.

Generating this recommendation leaves physical stock unchanged. Under the proposed later approval workflow:

1. **Approval** reserves the meals.
2. **Completion** records that the movement occurred.
3. The backend subtracts stock at the origin and adds it at the destination together.

An **idempotency key** identifies an operation so retrying the same request cannot transfer the stock twice.

**8. The API lets the website request each step and retrieve its results.**

The **API** is the set of requests the website can send to the backend.

| Website action | Backend response |
|---|---|
| Open the dashboard | Return saved stock and shortage summaries |
| Start forecasting | Create a job and return a tracking ID |
| Check that job | Report whether it is waiting, running, finished, or failed |
| View forecasts | Return daily predictions |
| Create a scenario | Validate and save the assumptions |
| Check shortages | Return projected deficits |
| Compare allocation methods | Return both plans and their differences |
| Open a plan | Return its recommendations and explanations |

A `GET` request generally retrieves information. A `POST` request submits an action or creates something.

Forecasting may take time, so the backend first returns a job ID. The website checks that ID until results are ready. Opening the dashboard retrieves saved information without starting another forecast.

The document also names response codes:

- **202:** the job was accepted.
- **422:** the submitted information is invalid.
- **409:** the request conflicts with newer stock or policy information.

For supplier replenishment, the backend can produce a draft proposal describing what to order, estimated cost, and expected arrival. In the proposed MVP, that remains a simulated recommendation; it does not place a real vendor order.
