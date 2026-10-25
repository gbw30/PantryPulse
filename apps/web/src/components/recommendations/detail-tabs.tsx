"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import {
  actionRows, decimal, fraction, isUsable, METHOD_LABEL, productInfo, products, remainingNeed, shortId, siteName, transferModeLabel, units,
  type ActionRow, type Loaded, type MethodOutcome, type Rational,
} from "./model";
import { TransferRecommendation } from "./action-plan";
import { ConstraintBadge, LINK, SolverStatus } from "./vocabulary";

function Panel({ title, description, children, className }: { title: string; description?: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={cn("min-w-0 gap-3 py-4", className)}>
      <div className="px-4">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      <div className="grid gap-3 px-4">{children}</div>
    </Card>
  );
}

/** Site Recommendations: the same saved plan filtered by site, receiving vs sending kept apart. */
export function SiteRecommendations({ loaded, method, siteId, onSite, selectedKey, onSelect }: {
  loaded: Loaded; method: MethodOutcome; siteId: string; onSite: (siteId: string) => void; selectedKey: string | null; onSelect: (row: ActionRow) => void;
}) {
  const sites = loaded.scenario.payload.package.sites;
  const rows = actionRows(loaded, method);
  const receiving = rows.filter((row) => row.assignment.destination_id === siteId);
  const sending = rows.filter((row) => row.assignment.source_id === siteId);
  const reserves = loaded.scenario.payload.package.reserves.filter((reserve) => reserve.site_id === siteId);
  const lots = [...new Map([...receiving, ...sending].map((row) => [row.assignment.original_lot_id, row])).values()];
  const residual = remainingNeed(loaded, method).filter((item) => item.siteId === siteId);
  const name = siteName(loaded, siteId);
  const list = (items: ActionRow[], empty: string) => items.length === 0
    ? <p className="text-sm text-muted-foreground">{empty}</p>
    : <ul className="grid gap-2">{items.map((row) => <TransferRecommendation key={row.key} row={row} selected={row.key === selectedKey} onSelect={onSelect} compact />)}</ul>;
  return (
    <div className="grid gap-4">
      <div className="grid w-full gap-1 sm:w-[300px]">
        <span id="rec-site-label" className="text-xs font-medium text-muted-foreground">Site</span>
        <Select value={siteId} onValueChange={onSite}>
          <SelectTrigger aria-labelledby="rec-site-label" className="h-10 w-full bg-card"><SelectValue /></SelectTrigger>
          <SelectContent>
            {sites.map((site) => <SelectItem key={site.id} value={site.id}>{site.name}{site.role === "HUB" ? " · hub" : ""}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={`Receiving at ${name}`} description="Transfers this site would receive in the saved plan.">
          <div data-site-receiving>{list(receiving, "No transfers arrive at this site in this plan.")}</div>
        </Panel>
        <Panel title={`Sending from ${name}`} description="Transfers that leave this site; its reserve floors stay protected.">
          <div data-site-sending>{list(sending, "No transfers leave this site in this plan.")}</div>
        </Panel>
        <Panel title="Reserve floors" description="Stock the site keeps for itself, per product, from the frozen scenario.">
          {reserves.length === 0 ? <p className="text-sm text-muted-foreground">No reserve floor recorded for this site.</p> : (
            <ul className="grid gap-1 text-sm">
              {reserves.map((reserve) => {
                const product = productInfo(loaded, reserve.product_id);
                const same = reserve.floors.every((floor) => floor === reserve.floors[0]);
                return (
                  <li key={reserve.product_id} className="flex justify-between gap-3">
                    <span className="text-foreground">{product.name}</span>
                    <span className="font-medium text-foreground tabular-nums">
                      {reserve.floors.length === 0 ? "Unavailable" : same ? `${units(reserve.floors[0], product.unit)} each planning day` : reserve.floors.map((floor) => units(floor, product.unit)).join(", ")}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
        <Panel title="Affected lots and residual need">
          {lots.length === 0 ? <p className="text-sm text-muted-foreground">No lots at this site are moved by this plan.</p> : (
            <ul className="grid gap-1 text-sm">
              {lots.map((row) => (
                <li key={row.assignment.original_lot_id} className="text-foreground">
                  Lot {shortId(row.assignment.original_lot_id)} · {row.product.name} · {row.assignment.expires_on ? `expires ${row.assignment.expires_on}` : "non-expiring"}
                </li>
              ))}
            </ul>
          )}
          {residual.length === 0 ? <p className="text-sm text-foreground">No unmet need remains at this site with this plan.</p> : (
            <ul className="grid gap-1 text-sm">
              {residual.map((item) => (
                <li key={item.product.id} className="flex justify-between gap-3">
                  <span className="text-foreground">Unmet · {item.product.name}</span>
                  <span className="font-medium text-foreground tabular-nums">{units(item.unmet, item.product.unit)} of {units(item.target, item.product.unit)}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}

const CONSTRAINTS = ["FEFO lot order", "Donor reserve floors", "Route and site capacity", "Stock conservation"];

/** Network Optimization: read-only method pair on one frozen scenario. Runs nothing. */
export function NetworkOptimization({ loaded, method }: { loaded: Loaded; method: MethodOutcome }) {
  const methods = loaded.comparison.result.methods;
  const sameInputs = methods.every((item) => item.operational_hash === loaded.comparison.result.operational_hash);
  const passed = isUsable(method);
  const payload = loaded.scenario.payload;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Method pair" description={`Frozen scenario ${shortId(loaded.comparison.scenario_id)} · ${transferModeLabel(loaded.comparison.result.transfer_mode)} · ${payload.planning_days}-day window from ${payload.package.first_planning_date}`}>
        <ul className="grid gap-2">
          {methods.map((item) => (
            <li key={item.method} className="grid gap-1 rounded-lg border border-border p-3">
              <SolverStatus method={item} showMethod />
              <p className="text-xs text-muted-foreground">
                Settings {shortId(item.settings_hash)} · policy {shortId(item.policy_hash)} · search {item.search_seconds}s
                {item.error_code ? <> · error code <code className="font-mono">{item.error_code}</code></> : null}
              </p>
            </li>
          ))}
        </ul>
        <p className="text-sm text-foreground">{sameInputs ? "Both methods read the same frozen inputs (operational hash " + shortId(loaded.comparison.result.operational_hash) + ")." : "The methods' input hashes differ; do not compare them side by side."}</p>
        <p className="text-xs text-muted-foreground">EGP-PI-inspired is a bounded, research-inspired subset of goal programming; it does not reproduce the full published formulation. This tab reads the saved comparison and starts no optimization.</p>
        <Link className={cn(LINK, "w-fit text-sm")} href={`/scenarios?comparison=${loaded.comparison.id}`}>Open in Scenario Lab</Link>
      </Panel>
      <Panel title={`Constraints · ${METHOD_LABEL[method.method]} plan`} description="Hard constraints, claimed only when the independent replay passed.">
        <ul className="grid gap-2">{CONSTRAINTS.map((label) => <ConstraintBadge key={label} label={label} passed={passed} />)}</ul>
        <h3 className="text-sm font-semibold text-foreground">Uncovered demand</h3>
        {passed ? (
          <ul className="grid gap-1 text-sm">
            {products(loaded).map((product) => {
              const unmet = (method.verification?.metrics?.goals ?? []).filter((goal) => goal.product_id === product.id).reduce((sum, goal) => sum + goal.unmet, 0);
              return <li key={product.id} className="flex justify-between gap-3"><span>{product.name}</span><span className="font-medium tabular-nums">{units(unmet, product.unit)}</span></li>;
            })}
          </ul>
        ) : <p className="text-sm text-muted-foreground">Unavailable: this method has no verified plan.</p>}
      </Panel>
    </div>
  );
}

function RationalCell({ value }: { value: Rational | null }) {
  if (!value) return <TableCell>N/A</TableCell>;
  return <TableCell className="tabular-nums"><span title={`Exactly ${fraction(value)}`}>{decimal(value)}</span></TableCell>;
}

const Flag = ({ name, value }: { name: string; value: boolean }) => <TableCell><span className="sr-only">{name} </span>{value ? "yes" : "no"}</TableCell>;

/** FairnessBreakdown: per-goal outcome and AP/RP indicators of the selected verified plan. */
export function ImpactFairness({ loaded, method }: { loaded: Loaded; method: MethodOutcome }) {
  const metrics = isUsable(method) ? method.verification?.metrics ?? null : null;
  if (!metrics) return <Panel title="Impact & Fairness"><p className="text-sm text-muted-foreground">Unavailable: the {METHOD_LABEL[method.method]} method has no verified plan.</p></Panel>;
  return (
    <div className="grid gap-4">
      <Panel title={`Per-goal outcome · ${METHOD_LABEL[method.method]} plan`}
        description="Every beneficiary × product goal from the saved plan. Decimals are rounded to four places; hover a value for the exact fraction.">
        <p className="text-xs text-muted-foreground">AP and RP are the absolute- and relative-poverty threshold flags of the goal model. The vulnerability attributes are SIMULATED and describe fictional institutions, not people. In this simulated scenario they show how the plan treats each goal; they do not establish that one method is better.</p>
        <div role="region" aria-label="Per-goal outcome table" tabIndex={0} className="overflow-x-auto rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <div className="min-w-[860px]">
            <Table>
              <TableCaption className="sr-only">Per-goal outcome for the {METHOD_LABEL[method.method]} plan; quantities in each product&apos;s unit</TableCaption>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  {["Site", "Product", "Target", "Fulfilled", "Unmet", "Service ratio", "Deficit", "Weighted deficit", "Vulnerability", "AP", "RP"].map((label) => <TableHead key={label}>{label}</TableHead>)}
                </TableRow>
              </TableHeader>
              <TableBody>
                {metrics.goals.map((goal) => {
                  const product = productInfo(loaded, goal.product_id);
                  return (
                    <TableRow key={`${goal.site_id}|${goal.product_id}`}>
                      <TableCell className="font-medium">{siteName(loaded, goal.site_id)}</TableCell>
                      <TableCell>{product.name} ({product.unit})</TableCell>
                      <TableCell className="tabular-nums">{units(goal.target, product.unit)}</TableCell>
                      <TableCell className="tabular-nums">{units(goal.fulfilled, product.unit)}</TableCell>
                      <TableCell className="tabular-nums">{units(goal.unmet, product.unit)}</TableCell>
                      <RationalCell value={goal.service_ratio} />
                      <RationalCell value={goal.deficit} />
                      <RationalCell value={goal.weighted_deficit} />
                      <RationalCell value={goal.vulnerability} />
                      <Flag name="AP" value={goal.ap} />
                      <Flag name="RP" value={goal.rp} />
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </div>
      </Panel>
      <Panel title="Group counts per product" description="How many goals carry an AP or RP flag, out of the group size.">
        <Table>
          <TableCaption className="sr-only">Group counts per product</TableCaption>
          <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Product</TableHead><TableHead>Goals</TableHead><TableHead>AP flags</TableHead><TableHead>RP flags</TableHead></TableRow></TableHeader>
          <TableBody>
            {metrics.groups.map((group) => (
              <TableRow key={group.product_id}>
                <TableCell>{productInfo(loaded, group.product_id).name}</TableCell>
                <TableCell className="tabular-nums">{group.size}</TableCell>
                <TableCell className="tabular-nums">{group.ap_count}</TableCell>
                <TableCell className="tabular-nums">{group.rp_count}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Panel>
    </div>
  );
}
