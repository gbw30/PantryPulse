"use client";

import { useEffect, useRef, useState, useSyncExternalStore, type PointerEvent, type WheelEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  Boxes,
  ChevronDown,
  CircleHelp,
  Compass,
  Filter,
  Focus,
  House,
  Layers2,
  Minus,
  Moon,
  Package,
  Plus,
  Sun,
} from "lucide-react";
import { ForecastChart } from "./forecast-chart";
import { Network3D } from "./network-3d";
import { buildOutlook, coverFor, formatMeals } from "./outlook-data";
import "./design-lab.css";

type Theme = "dark" | "light";
type Status = "hub" | "needs" | "covered";
type Site = {
  id: string;
  code: string;
  name: string;
  x: number;
  y: number;
  status: Status;
  need: number;
  note: string;
};

const sites: Site[] = [
  { id: "hub", code: "HUB", name: "Gator Hub", x: 500, y: 338, status: "hub", need: 0, note: "Central distribution hub" },
  { id: "riverbend", code: "RB", name: "Riverbend", x: 575, y: 94, status: "needs", need: 120, note: "Needs support by Tuesday" },
  { id: "oak", code: "OT", name: "Oak Terrace", x: 205, y: 194, status: "needs", need: 90, note: "Needs support this week" },
  { id: "cedar", code: "CG", name: "Cedar Grove", x: 800, y: 211, status: "covered", need: 0, note: "Demand covered this week" },
  { id: "maple", code: "MC", name: "Maple Crossing", x: 176, y: 486, status: "covered", need: 0, note: "Demand covered this week" },
  { id: "willow", code: "WC", name: "Willow Creek", x: 536, y: 568, status: "covered", need: 0, note: "Demand covered this week" },
  { id: "pine", code: "PR", name: "Pine Ridge", x: 827, y: 494, status: "covered", need: 0, note: "Demand covered this week" },
];

const paths: Record<string, string> = {
  riverbend: "M 500 338 Q 538 211 575 94",
  oak: "M 500 338 Q 345 295 205 194",
  cedar: "M 500 338 Q 662 290 800 211",
  maple: "M 500 338 Q 336 402 176 486",
  willow: "M 500 338 Q 518 458 536 568",
  pine: "M 500 338 Q 659 407 827 494",
};

const SEAL_RADIUS = 26;
const SEAL_CIRCUMFERENCE = 2 * Math.PI * SEAL_RADIUS;

// Site marker: the ring fills with days of cover (out of 7). The dashed remainder marks uncovered days,
// and the corner badge repeats the status as a shape so colour is never the only signal.
function SiteSeal({ site }: { site: Site }) {
  const cover = coverFor(site.id);
  const covered = (cover?.fraction ?? 1) * SEAL_CIRCUMFERENCE;
  if (site.status === "hub") {
    return (
      <svg className="lab-node-seal" viewBox="0 0 72 72" aria-hidden="true">
        <polygon className="lab-hub-shape" points="36,4 63.7,20 63.7,52 36,68 8.3,52 8.3,20" />
        <polygon className="lab-hub-inner" points="36,11 57.6,23.5 57.6,48.5 36,61 14.4,48.5 14.4,23.5" />
        <circle className="lab-seal-select" cx="36" cy="36" r="35" />
        <text className="lab-seal-id" x="36" y="37">{site.code}</text>
      </svg>
    );
  }
  return (
    <svg className="lab-node-seal" viewBox="0 0 64 64" aria-hidden="true">
      <circle className="lab-seal-fill" cx="32" cy="32" r="31" />
      <circle className="lab-seal-track" cx="32" cy="32" r={SEAL_RADIUS} />
      {site.status === "needs" && <circle className="lab-seal-gap" cx="32" cy="32" r={SEAL_RADIUS} transform="rotate(-90 32 32)" />}
      <circle className="lab-seal-arc" cx="32" cy="32" r={SEAL_RADIUS} strokeDasharray={`${covered} ${SEAL_CIRCUMFERENCE}`} transform="rotate(-90 32 32)" />
      <circle className="lab-seal-select" cx="32" cy="32" r="31" />
      <text className="lab-seal-id" x="32" y="33">{site.code}</text>
      <circle className="lab-seal-badge" cx="53" cy="11" r="8" />
      {site.status === "needs"
        ? <path className="lab-seal-badge-mark" d="M53 6.5 v5 M53 14.4 v.1" />
        : <path className="lab-seal-badge-mark" d="M49.3 11.2 l2.6 2.6 l4.6 -5" />}
    </svg>
  );
}

function siteStatusLine(site: Site) {
  if (site.status === "hub") return "Distribution hub";
  const cover = coverFor(site.id);
  if (!cover) return "";
  return cover.days >= 7 ? "7+ days of cover" : `${cover.days.toFixed(1)} days of cover`;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function subscribeReducedMotion(onChange: () => void) {
  const query = window.matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function getReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Render static markup on the server and on the first hydration pass.
function getServerReducedMotion() { return true; }

export default function DesignLabPage() {
  const [theme, setTheme] = useState<Theme>("dark");
  const [selectedId, setSelectedId] = useState("riverbend");
  const [filter, setFilter] = useState<"all" | "needs" | "covered">("all");
  const [motionOn, setMotionOn] = useState(true);
  const [view, setView] = useState<"2d" | "3d">("2d");
  const [zoom, setZoom] = useState(1);
  const mapRef = useRef<HTMLDivElement>(null);
  const [mapSize, setMapSize] = useState({ width: 1000, height: 660 });
  const fitScale = Math.min(1, Math.max(1, mapSize.width - 32) / 1000, Math.max(1, mapSize.height - 88) / 660);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [explainOpen, setExplainOpen] = useState(false);
  const [forecastOpen, setForecastOpen] = useState(false);
  const drag = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const prefersReducedMotion = useSyncExternalStore(subscribeReducedMotion, getReducedMotion, getServerReducedMotion);
  const animate = motionOn && !prefersReducedMotion;
  const selected = sites.find((site) => site.id === selectedId) ?? sites[1];
  const outlook = buildOutlook(selected.id, selected.name);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const observer = new ResizeObserver(([entry]) => {
      setMapSize({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(map);
    return () => observer.disconnect();
  }, [view]);

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest("button")) return;
    drag.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!drag.current) return;
    setPan({
      x: drag.current.panX + event.clientX - drag.current.x,
      y: drag.current.panY + event.clientY - drag.current.y,
    });
  }

  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function onWheel(event: WheelEvent<HTMLDivElement>) {
    event.preventDefault();
    setZoom((current) => clamp(current + (event.deltaY < 0 ? 0.08 : -0.08), 0.7, 1.7));
  }

  return (
    <main className={`lab lab-${theme} ${animate ? "lab-animated" : ""}`}>
      <div className="lab-shell">
        <aside className="lab-rail" aria-label="Main navigation">
          <div className="lab-mark" aria-label="PantryPulse"><svg viewBox="0 0 26 26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2 14h5l3-8 5 15 3-7h6" /></svg></div>
          <div className="lab-rail-links">
            <button className="lab-rail-link is-active" aria-label="Network" title="Network"><Compass size={21} /></button>
            <button className="lab-rail-link" aria-label="Scenarios" title="Scenarios"><Layers2 size={21} /></button>
            <button className="lab-rail-link" aria-label="Inventory" title="Inventory"><Boxes size={21} /></button>
          </div>
          <button className="lab-rail-link lab-rail-help" aria-label="Help" title="Help"><CircleHelp size={20} /></button>
        </aside>

        <div className="lab-main">
          <header className="lab-topbar">
            <div className="lab-wordmark">Pantry<span>Pulse</span><small> / Design lab</small></div>
            <div className="lab-topbar-right">
              <span className="lab-demo-tag"><span /> Simulated network</span>
              <button className="lab-theme-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
                {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
                <span>{theme === "dark" ? "Light" : "Dark"}</span>
              </button>
            </div>
          </header>

          <div className="lab-workspace">
            <div className="lab-title-row">
              <div>
                <div className="lab-eyebrow"><span className="lab-eyebrow-line" /> Network overview, week of Oct 19</div>
                <h1>Where does the network need help?</h1>
                <p>See the distribution picture at a glance. Select a location for the details that matter.</p>
              </div>
              <div className="lab-title-actions">
                <button className="lab-select-button"><span>Meals</span><ChevronDown size={15} /></button>
                <button className="lab-select-button"><span>Oct 19–25</span><ChevronDown size={15} /></button>
              </div>
            </div>

            <div className="lab-summary" aria-label="Executive summary">
              <div className="lab-summary-item"><span className="lab-summary-icon attention"><Activity size={19} /></span><div><strong>2 of 6</strong><span>pantries need support</span></div></div>
              <div className="lab-summary-item"><span className="lab-summary-icon"><Package size={19} /></span><div><strong>80 <em>meals</em></strong><span>proposed to move</span></div></div>
              <div className="lab-summary-item"><span className="lab-summary-icon"><ArrowDownRight size={19} /></span><div><strong>1 <em>draft</em></strong><span>route to review</span></div></div>
            </div>

            <section className="lab-stage" aria-label="Distribution network explorer">
              <div className="lab-stage-header">
                <div className="lab-stage-title"><span className="lab-live-dot" /> Distribution network <span>Hub · 6 pantries</span></div>
                <div className="lab-view-switch" role="group" aria-label="Network view">
                  <button aria-pressed={view === "2d"} className={view === "2d" ? "selected" : ""} onClick={() => setView("2d")}>2D</button>
                  <button aria-pressed={view === "3d"} className={view === "3d" ? "selected" : ""} onClick={() => setView("3d")}>3D</button>
                </div>
                <div className="lab-filter-row" role="group" aria-label="Filter locations">
                  <Filter size={15} />
                  {(["all", "needs", "covered"] as const).map((option) => (
                    <button key={option} className={filter === option ? "selected" : ""} onClick={() => setFilter(option)}>{option === "all" ? "All" : option === "needs" ? "Needs support" : "Covered"}</button>
                  ))}
                </div>
                {view === "2d" && <label className="lab-location-picker">Location
                  <select value={selectedId} onChange={(event) => { setSelectedId(event.target.value); setExplainOpen(false); setForecastOpen(false); }}>
                    {sites.map((site) => <option key={site.id} value={site.id}>{site.name} — {site.status === "hub" ? "Hub" : site.status === "needs" ? "Needs support" : "Covered"}</option>)}
                  </select>
                </label>}
              </div>

              {view === "3d" ? <Network3D sites={sites} selectedId={selectedId} filter={filter} theme={theme} animate={animate} onSelect={(id) => { setSelectedId(id); setExplainOpen(false); setForecastOpen(false); }} onFallback={() => setView("2d")} /> : <div ref={mapRef} className="lab-map" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp} onWheel={onWheel}>
                <div className="lab-map-topo" aria-hidden="true" />
                <div className="lab-world" style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${fitScale * zoom})` }}>
                  <svg className="lab-edges" viewBox="0 0 1000 660" aria-hidden="true">
                    <defs>
                      <linearGradient id="labRoute" x1="0" x2="1" y1="1" y2="0"><stop offset="0" stopColor="#5ed9bd" /><stop offset="1" stopColor="#f3ba74" /></linearGradient>
                    </defs>
                    {sites.filter((site) => site.id !== "hub").map((site) => {
                      const dimmed = filter !== "all" && filter !== site.status;
                      const active = site.id === selectedId;
                      return <g key={site.id} className={dimmed ? "lab-dimmed" : ""}>
                        <path d={paths[site.id]} className="lab-edge-base" />
                        {active && <path d={paths[site.id]} className="lab-edge-active" />}
                        {active && site.id === "riverbend" && animate && <path d={paths[site.id]} className="lab-edge-flow" />}
                      </g>;
                    })}
                  </svg>
                  {sites.map((site) => {
                    const dimmed = site.status !== "hub" && filter !== "all" && filter !== site.status;
                    const active = site.id === selectedId;
                    return (
                      <motion.button
                        key={site.id}
                        type="button"
                        className={`lab-node lab-node-${site.status} ${active ? "is-selected" : ""} ${dimmed ? "lab-dimmed" : ""}`}
                        style={{ left: site.x, top: site.y }}
                        animate={{ scale: active ? 1.06 : 1 }}
                        transition={animate ? { type: "spring", stiffness: 250, damping: 22 } : { duration: 0 }}
                        onClick={() => { setSelectedId(site.id); setExplainOpen(false); setForecastOpen(false); }}
                        aria-pressed={active}
                        aria-label={`${site.name}, ${site.status === "hub" ? "central hub" : site.status === "needs" ? "needs support" : "covered"}, ${siteStatusLine(site)}`}
                      >
                        <SiteSeal site={site} />
                        <span className="lab-node-text"><strong>{site.name}</strong><small>{siteStatusLine(site)}</small></span>
                      </motion.button>
                    );
                  })}
                  {selectedId === "riverbend" && <div className="lab-route-label" style={{ left: 545, top: 210 }}><Package size={13} /> 80 meals proposed</div>}
                </div>
                <div className="lab-map-hint">Drag to move, scroll to zoom</div>
                <div className="lab-map-controls" aria-label="Map controls">
                  <button onClick={() => setZoom((value) => clamp(value + 0.15, 0.7, 1.7))} aria-label="Zoom in"><Plus size={17} /></button>
                  <button onClick={() => setZoom((value) => clamp(value - 0.15, 0.7, 1.7))} aria-label="Zoom out"><Minus size={17} /></button>
                  <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} aria-label="Fit network"><Focus size={17} /></button>
                </div>
              </div>}

              <div className="lab-stage-footer">
                <div className="lab-legend"><span><i className="needs" /> Needs support</span><span><i className="covered" /> Covered</span><span><i className="hub" /> Hub</span><span className="lab-route-key"><b /> Suggested route</span></div>
                <div className="lab-stage-fineprint">Planning example · amounts are illustrative</div>
              </div>
            </section>

            <section className="lab-outlook" aria-labelledby="lab-outlook-title">
              <div className="lab-outlook-head">
                <div>
                  <h2 id="lab-outlook-title">Seven-day outlook{outlook ? <> for {selected.name}</> : null}</h2>
                  <p>Meals on hand at the end of each day, Oct 15 to Oct 25</p>
                </div>
                <span className="lab-provenance">Illustrative forecast on simulated data</span>
              </div>
              {outlook ? <>
                <div className="lab-outlook-body">
                  <ForecastChart outlook={outlook} animate={animate} />
                  <dl className="lab-outlook-facts">
                    <div><dt>First shortage</dt><dd className={outlook.firstShortageDay ? "risk" : ""}>{outlook.firstShortageDay ?? "None this week"}</dd></div>
                    <div><dt>{outlook.endWith !== null ? "Sun 25 without route" : "On hand Sun 25"}</dt><dd className={outlook.endWithout < 0 ? "risk" : ""}>{formatMeals(outlook.endWithout)} <small>meals</small></dd></div>
                    {outlook.endWith !== null && <div><dt>Sun 25 with {outlook.transferQty}-meal route</dt><dd className={outlook.endWith < 0 ? "risk" : ""}>{formatMeals(outlook.endWith)} <small>meals</small></dd></div>}
                  </dl>
                </div>
                <div className="lab-legend lab-outlook-legend" aria-hidden="true">
                  <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke="var(--lab-fg)" strokeWidth="2.4" /></svg> Observed</span>
                  <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke="var(--lab-forecast)" strokeWidth="2.2" strokeDasharray="7 5" /></svg> Forecast without route</span>
                  {outlook.endWith !== null && <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke="var(--lab-accent)" strokeWidth="2.8" strokeDasharray="2 4" strokeLinecap="round" /></svg> Forecast with route</span>}
                  <span><i className="lab-swatch-band" /> Raw quantile range, not a calibrated interval</span>
                  <span><i className="lab-swatch-unmet" /> Below zero is unmet demand</span>
                </div>
                <p className="lab-outlook-summary">{outlook.summary}</p>
                <details className="lab-outlook-table">
                  <summary>View data table</summary>
                  <div className="lab-outlook-table-scroll" tabIndex={0} role="region" aria-label="Outlook data table">
                    <table>
                      <caption>Meals on hand at end of day for {selected.name}. Negative values are unmet demand.</caption>
                      <thead><tr><th scope="col">Day</th><th scope="col">Observed</th><th scope="col">Forecast without route</th>{outlook.endWith !== null && <th scope="col">Forecast with route</th>}<th scope="col">Raw quantile range</th></tr></thead>
                      <tbody>{outlook.points.map((point) => <tr key={point.day}><th scope="row">{point.day}</th><td>{point.observed !== undefined ? formatMeals(point.observed) : "n/a"}</td><td>{point.withoutRoute !== undefined ? formatMeals(point.withoutRoute) : "n/a"}</td>{outlook.endWith !== null && <td>{point.withRoute !== undefined ? formatMeals(point.withRoute) : "n/a"}</td>}<td>{point.range && point.range[0] !== point.range[1] ? `${formatMeals(point.range[0])} to ${formatMeals(point.range[1])}` : "n/a"}</td></tr>)}</tbody>
                    </table>
                  </div>
                </details>
              </> : <p className="lab-outlook-summary">The hub holds supply for the network and has no demand forecast. Select a pantry to see its outlook.</p>}
            </section>
          </div>
        </div>

        <aside className="lab-inspector" aria-label="Location details">
          <div className="lab-inspector-top"><span>Location inspector</span><Compass size={17} /></div>
          <AnimatePresence mode="wait">
            <motion.div key={selected.id} className="lab-inspector-body" initial={animate ? { opacity: 0, y: 10 } : false} animate={{ opacity: 1, y: 0 }} exit={animate ? { opacity: 0, y: -8 } : undefined} transition={{ duration: 0.22 }}>
              <div className="lab-location-badge"><span className={`lab-location-icon ${selected.status}`}><House size={23} /></span><span>{selected.status === "hub" ? "Distribution hub" : "Community pantry"}</span></div>
              <h2>{selected.name}</h2>
              <span className={`lab-status lab-status-${selected.status}`}><span /> {selected.status === "hub" ? "Hub" : selected.status === "needs" ? "Needs support" : "Covered"}</span>
              <div className="lab-inspector-rule" />
              {selected.id === "riverbend" ? <>
                <p className="lab-inspector-question">Can we cover this location’s need?</p>
                <p className="lab-inspector-answer">Partially. The hub can provide 80 of the 120 meals needed by Tuesday.</p>
                <div className="lab-coverage-visual"><div><span style={{ width: "66.67%" }} /></div><small>67% covered by proposed route</small></div>
                <div className="lab-figures"><div><strong>120</strong><span>meals needed</span></div><div><strong>80</strong><span>can be sent</span></div><div className="gap"><strong>40</strong><span>still needed</span></div></div>
                <div className="lab-route-card"><span className="lab-route-icon"><Package size={17} /></span><div><small>Suggested route</small><strong>Gator Hub <ArrowRight size={15} /> Riverbend</strong></div><span>80</span></div>
              </> : selected.status === "needs" ? <>
                <p className="lab-inspector-question">What is the remaining need?</p>
                <p className="lab-inspector-answer">{selected.name} needs support this week. No confirmed route is proposed in this sample.</p>
                <div className="lab-single-figure"><strong>{selected.need}</strong><span>meals still needed</span></div>
              </> : <>
                <p className="lab-inspector-question">What is the current status?</p>
                <p className="lab-inspector-answer">{selected.note}. Select a pantry that needs support to review a possible route.</p>
              </>}
              <div className="lab-inspector-rule" />
              <button className="lab-disclosure" aria-expanded={explainOpen} onClick={() => setExplainOpen(!explainOpen)}><span><Activity size={17} /> Why is this location highlighted?</span><ChevronDown size={16} /></button>
              {explainOpen && <p className="lab-disclosure-copy">{selected.status === "needs" ? "Expected demand exceeds the meals currently available to this pantry in the example scenario." : "The example scenario shows this location covered for the selected week."}</p>}
              <button className="lab-disclosure" aria-expanded={forecastOpen} onClick={() => setForecastOpen(!forecastOpen)}><span><ArrowDownRight size={17} /> Forecast notes</span><ChevronDown size={16} /></button>
              {forecastOpen && <p className="lab-disclosure-copy">A seven-day need estimate informs this view. Forecasts do not change physical inventory.</p>}
            </motion.div>
          </AnimatePresence>
          <div className="lab-inspector-bottom">Select any location on the map to explore its status.</div>
        </aside>
      </div>

      <div className="lab-experiment-bar" aria-label="Design lab controls">
        <div className="lab-experiment-label"><strong>Component lab</strong><span>Prototype only. Amounts and routes are illustrative.</span></div>
        <label className="lab-motion-toggle"><input type="checkbox" checked={motionOn} onChange={(event) => setMotionOn(event.target.checked)} /><span>Route motion</span></label>
      </div>
    </main>
  );
}
