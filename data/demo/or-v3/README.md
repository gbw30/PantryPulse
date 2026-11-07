# or-v3 Retail oracle fixtures (W1-S01, V1-SPEC §12 item 2)

Fictional, hand-derived fixtures for `RETAIL_OPTIMIZED` (V1-A15). Each fixture has at most 2 locations, 2 products and 3 batches. `*.input.json` is an `or-input-v3` scenario (`app/schemas/v1_planning.py:ORInputV3`). `*.expected.json` holds the values derived below by hand, before any solver code existed. Weights are the v1 defaults `w_exp = 1`, `w_lost = 1` (V1-SPEC §6.2), unless a test edits them.

## Rules the derivations use

These are the Retail rules of V1-SPEC §6.2. Each one maps to a check in the independent verifier.

- **Days.** Day 1 is `first_planning_date` (2026-11-02); day 7 is 2026-11-08. "Day *i*" below is 1-based.
- **Selling.** Each day, a location sells its demand target from available, unexpired stock, FEFO: earliest expiry first (non-expiring last), then earliest availability, then batch id. Unmet demand is a **lost sale**.
- **Expiry.** A batch is sellable through its expiry date. Units left unsold after an expiry date inside the horizon are **expired**, including a batch that expires on day 7.
- **Dispatch (BD-50).** One batch per route, shipped on day 1 from the sender's on-hand batches. It arrives on day 1 + `travel_days` and is sellable from that day. A batch is eligible for a route only if it is non-expiring or expires on or after the arrival date. Each sender's shipment takes its eligible batches FEFO.
- **Relaxed BD-51 (Retail only).** Every transferred unit must sell at the receiver before its expiry and by day 7.
- **Sender protection (BD-49 for stores).** Without any inbound transfer, a sender must still sell its whole seven-day forecast and end every day at or above its reserve floor (0 in every fixture).
- **DCs never receive.** In `HUB_ONLY` only DCs send.
- **Objective.** Each product minimizes `w_exp × expired + w_lost × lost` over the 7 days. In USD the objective is multiplied by `unit_value_usd`. Ties go to fewer moved units (declared tie-break; it never changes the objective).
- **Per product (W0 decision).** Each product is solved alone. Shared capacity is split before solving by weight share, floored: `cap × weight_p // Σ weight`.
  - UNITS weight = need × `handling_units_per_unit`.
  - USD weight = need × `handling_units_per_unit` × `unit_value_usd` (CR-w1-solver-2).
  - Retail need = baseline lost sales + baseline expired units.
  - A product whose share is below one unit's handling is reported as "capacity share too small to move one unit", not optimized.
- **No unit totals across products.** In UNITS a method objective exists only for a one-product scenario. Multi-product fixtures list per-product objectives. USD totals are summed.

## retail-expiry-transfer

Store A: `a1` 10 units expiring 11-04 (day 3) and `a2` 10 non-expiring, selling 1/day. Store B: `b1` 6 non-expiring, selling 3/day. Route A→B, 1 day. Price $2.50.

- **Baseline (no transfers).**
  - A sells `a1` on days 1–3 (3 units), and the other 7 units of `a1` expire. Then `a2` covers days 4–7. A has 0 lost sales.
  - B sells `b1` on days 1–2 (6 units) and loses days 3–7 (15 units).
  - Expired 7, lost 15, objective 22.
- **Shipping y units.** FEFO packing takes `a1` first. The sublot arrives on day 2 and expires on day 3, and B sells it before `b1`, so B can sell at most 3 + 3 = 6 of it.
  - y ≤ 6. At y = 7 one `a1` unit would be unsold at the receiver, which violates relaxed BD-51.
  - A stays protected: `a1` leftover 10 − y ≥ 3 covers days 1–3, then `a2` covers days 4–7.
  - Each unit removes one expiry at A and one lost sale at B, so the objective is 22 − 2y.
- **Optimum y = 6** (from `a1`), ship 11-02, arrive 11-03.
  - A: 4 left of `a1`, sells 3, so **1 expires**.
  - B: day 1 `b1` 3; days 2–3 sublot 3 + 3; day 4 `b1` 3; days 5–7 lost, so **lost 9**.
  - **Objective 10 units = $25.00.**

## retail-lost-vs-waste

Store A: `a1` 1 unit expiring 11-03 (day 2) and `a2` 10 units expiring 11-30 (beyond the horizon), selling 1/day. Store B: `b1` 5 expiring 11-06 (day 5), selling 1/day. Route A→B, 1 day. Price $4.00.

- **Baseline.**
  - A sells `a1` on day 1, then `a2` on days 2–7. Nothing expires; 4 units are left.
  - B sells `b1` on days 1–5 and loses days 6–7.
  - Expired 0, lost 2, objective 2.
- **Shipping y units.** FEFO packing takes `a1` (1 unit) first, then `a2`. Both arrive on day 2.
  - At B the `a1` sublot (expiry day 2) sells first on day 2. It pushes one `b1` unit past its day-5 expiry.
  - The `a2` sublot sells after `b1`, on days 6–7, so at most 2 `a2` units can sell, giving y ≤ 3.
  - A stays protected: `a2` 10 − (y − 1) ≥ 7.

| y | expired | lost | objective (1:1) | objective (w_exp = 3) |
|---|---|---|---|---|
| 0 | 0 | 2 | 2 | 2 |
| 1 | 1 | 2 | 3 | 5 |
| 2 | 1 | 1 | 2 | 4 |
| 3 | 1 | 0 | **1** | 3 |

- **Optimum y = 3** (`a1` 1 + `a2` 2): it accepts 1 expired unit to recover 2 lost sales. **Expired 1, lost 0, objective 1 unit = $4.00.**
- With `w_exp = 3` the trade reverses, and the optimum is no transfer, objective 2 (used by `test_weights_editable`).

## retail-usd-flip (CR-w1-solver-2: shared capacity binds, so the plan changes with the measure)

DC North: Lettuce `p1` 4 units expiring 11-04 (day 3), at $1.00; Olive oil `q1` 10 bottles, non-expiring, at $10.00. The DC sells neither. Store B sells 2/day of each and holds no stock. Route DC→B, 1 day, `capacity_per_batch` 4 handling units. Both products have 1 handling unit per unit.

- **Baseline.** Lettuce: 4 expired, 14 lost. Oil: 0 expired, 14 lost.
- **Needs.** Lettuce 14 + 4 = 18; oil 14.
- **Within a share.**
  - Lettuce arrives on day 2 and expires on day 3, so at most 2 + 2 = 4 can sell. Each unit removes 1 expiry and 1 lost sale (−2).
  - Oil can sell up to 12 units (days 2–7). Each unit removes 1 lost sale (−1).
- **UNITS split.** Weights 18 and 14. Lettuce gets 4 × 18 // 32 = **2**; oil gets 4 × 14 // 32 = **1**. One handling unit stays unused because of the floor.
  - Lettuce y = 2: expired 2, lost 12, objective 14.
  - Oil y = 1: expired 0, lost 13, objective 13.
  - No units total is computed, because cases and bottles are different units.
- **USD split.** Weights 18 × 1 × 1.00 = 18 and 14 × 1 × 10.00 = 140. Lettuce gets 4 × 18 // 158 = **0**, which is below one unit's handling, so lettuce is reported as "capacity share too small to move one unit". Oil gets 4 × 140 // 158 = **3**.
  - Lettuce: no transfer; expired 4, lost 14, objective $18.00.
  - Oil y = 3: lost 11, objective $110.00.
  - **USD total $128.00.**
- **The plan changes:** UNITS ships 2 lettuce + 1 oil; USD ships 3 oil. For reference, a single network model would also flip: units prefers 4 lettuce (−8), USD prefers 4 oil (−$40 against −$8).

## retail-usd-no-flip (same network, no route capacity)

Same as `retail-usd-flip` without `capacity_per_batch`, so no shared limit binds.

- Lettuce y = 4 (it can't sell more before expiry): expired 0, lost 10, objective 10 = $10.00.
- Oil y = 10 (all the stock): lost 4, objective 4 = $40.00.
- **Both measures give the same plan; the USD total is $50.00.**

## retail-nothing-to-move

Store A: `a1` 5 units expiring 11-03 (day 2) and `a2` 3 non-expiring. A's sales forecast is 0. Store B: `b1` 7 non-expiring, selling 1/day. Route A→B, 2 days (arrival 11-04). Price $3.00.

- `a1` expires before it could arrive, so it is not eligible for the route.
- `a2` is eligible. At B it would arrive on day 3 and queue behind `b1` (same expiry, `b1` available earlier). `b1` covers all 7 days, so a shipped `a2` unit would never sell, which violates relaxed BD-51. No transfer is feasible or useful.
- **No transfers: expired 5 (`a1` at A), lost 0, objective 5 units = $15.00.**

## retail-day5-expiry

Store A: `a1` 6 units expiring 11-06 (day 5 of 7). A's sales forecast is 0. Store B has no stock and sells 1/day. Route A→B, 2 days (arrival 11-04, day 3). Price $1.25.

- **Baseline.** Expired 6, lost 7, objective 13.
- **Shipping y.** The sublot sells on days 3, 4 and 5 (through its expiry), so y ≤ 3. Each unit removes 1 expiry and 1 lost sale.
- **Optimum y = 3.**
  - A: 3 expire.
  - B: lost on days 1–2 and 6–7, so 4 lost.
  - **Objective 7 units = $8.75.**
- Pantry BD-51 with a 3-day window would accept only the day-3 sale, so only 1 unit could move. Retail's relaxed rule is what lets 3 move (`test_bd51_relaxed_retail_only`).

## pantry-four-methods

Pantry mode, HUB_ONLY, window `planning_days = 2`, the default policy (λ 100 %, β 50 %, AP threshold 7500, RP threshold 2500, caps 2500 bp, γ 100 %/100 %, ε 100 bp/100 bp). Central Hub has `h1`, 4 non-expiring cases of canned beans. The hub has no demand, so all 4 cases are protected surplus. Routes Hub→P1, P2 and P3 take 1 day: a case shipped on 11-02 arrives on 11-03 (day 2) and can only serve day-2 demand, which is at most 3 per pantry. The pantries hold no stock. Every pantry also has demand 1 on each of days 3–7. That demand is outside the window, so it changes no target (`test_goals_use_the_window_only`).

| Pantry | Demand day 1, day 2 | Window target | poverty, SNAP | v = 1 + λ × (½ poverty + ½ SNAP) |
|---|---|---|---|---|
| P1 | 0, 3 | 3 | 0.4, 0.4 | 1.4 |
| P2 | 3, 3 | 6 | 0, 0 | 1 |
| P3 | 3, 3 | 6 | 0.2, 0.2 | 1.2 |

Notation: q = floor(10000 × v × unmet / target). W = Σq, Z = max q. GP uses v = 1. There is no route cost, so the cost term is absent. Nothing expires, so the waste term is 0.

- **EQUAL_SHARE.** Receivers in first-deficit order are P2, P3 (day 1), then P1 (day 2). Water-filling 4 over 3 gives 1 each, and the remainder goes to P2. **P1 1, P2 2, P3 1.**
- **MOST_URGENT_FIRST.** P2 first: it wants 6 and can use 3. P3 gets the last 1. **P2 3, P3 1.**
- **CLASSICAL_GP: P1 2, P2 1, P3 1.**
  - q = (3333, 8333, 8333), so W + Z = 19999 + 8333 = 28332.
  - The closest rival, P1 3 with P2 or P3 1, has q = (0, 8333, 10000): W + Z = 18333 + 10000 = 28333, so it loses by one quantization step.
  - Compiled coefficients (q₁, q₂, q₃, Z, waste) = (50, 50, 50, 50, 1). **Objective 50 × 28332 = 1 416 600.**
- **EGP_PI_INSPIRED: P1 2, P2 2.**
  - q = (4666, 6666, 12000), so W = 23332 and Z = 12000.
  - AP: only P3 is above 7500. AP excess = max(0, 10000 × 1 − 2500 × 3) = 2500.
  - RP: 3 × 12000 − 23332 = 12668 > 7500, so only P3 is flagged. RP excess = 2500.
  - Compiled coefficients (q×3, Z, AP, RP, waste) = (150, 150, 150, 150, 100, 100, 3). **Objective 150 × 35332 + 100 × 5000 = 5 799 800.**
  - The GP plan scores 6 199 850 under EGP: q = (4666, 8333, 10000) gives 150 × 32999. P2 and P3 are both above the AP threshold, so AP excess is 20000 − 7500 = 12500. No goal is RP-flagged.

An enumeration of every feasible plan (`test_pantry_oracle`) confirms that each optimum is unique. `test_ap_flag_unset_at_equality` covers the AP boundary: a goal at exactly q = 7500 is not flagged. This is arithmetic on a fictional fixture, not evidence that either method is fairer.
