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
  Warehouse,
} from "lucide-react";
import { Network3D } from "./network-3d";
import "./design-lab.css";

type Theme = "dark" | "light";
type NodeTreatment = "orbit" | "pin" | "ledger";
type Status = "hub" | "needs" | "covered";
type Site = {
  id: string;
  name: string;
  x: number;
  y: number;
  status: Status;
  need: number;
  note: string;
};

const sites: Site[] = [
  { id: "hub", name: "Gator Hub", x: 500, y: 338, status: "hub", need: 0, note: "Central distribution hub" },
  { id: "riverbend", name: "Riverbend", x: 575, y: 94, status: "needs", need: 120, note: "Needs support by Tuesday" },
  { id: "oak", name: "Oak Terrace", x: 205, y: 194, status: "needs", need: 90, note: "Needs support this week" },
  { id: "cedar", name: "Cedar Grove", x: 800, y: 211, status: "covered", need: 0, note: "Demand covered this week" },
  { id: "maple", name: "Maple Crossing", x: 176, y: 486, status: "covered", need: 0, note: "Demand covered this week" },
  { id: "willow", name: "Willow Creek", x: 536, y: 568, status: "covered", need: 0, note: "Demand covered this week" },
  { id: "pine", name: "Pine Ridge", x: 827, y: 494, status: "covered", need: 0, note: "Demand covered this week" },
];

const paths: Record<string, string> = {
  riverbend: "M 500 338 Q 538 211 575 94",
  oak: "M 500 338 Q 345 295 205 194",
  cedar: "M 500 338 Q 662 290 800 211",
  maple: "M 500 338 Q 336 402 176 486",
  willow: "M 500 338 Q 518 458 536 568",
  pine: "M 500 338 Q 659 407 827 494",
};

const treatments: { id: NodeTreatment; label: string; description: string }[] = [
  { id: "orbit", label: "Orbit", description: "Layered rings and emphasis" },
  { id: "pin", label: "Pin", description: "Map marker silhouette" },
  { id: "ledger", label: "Ledger", description: "Compact status marker" },
];

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
  const [treatment, setTreatment] = useState<NodeTreatment>("orbit");
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
          <div className="lab-mark" aria-label="PantryPulse"><span className="lab-mark-leaf">◕</span></div>
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
                <div className="lab-eyebrow"><span className="lab-eyebrow-line" /> NETWORK OVERVIEW <span className="lab-eyebrow-dot">·</span> THIS WEEK</div>
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
                    const Icon = site.status === "hub" ? Warehouse : House;
                    return (
                      <motion.button
                        key={site.id}
                        type="button"
                        className={`lab-node lab-node-${treatment} lab-node-${site.status} ${active ? "is-selected" : ""} ${dimmed ? "lab-dimmed" : ""}`}
                        style={{ left: site.x, top: site.y }}
                        animate={{ scale: active ? 1.07 : 1 }}
                        transition={animate ? { type: "spring", stiffness: 250, damping: 22 } : { duration: 0 }}
                        onClick={() => { setSelectedId(site.id); setExplainOpen(false); setForecastOpen(false); }}
                        aria-pressed={active}
                        aria-label={`${site.name}, ${site.status === "hub" ? "central hub" : site.status === "needs" ? "needs support" : "covered"}`}
                      >
                        <span className="lab-node-symbol"><Icon size={site.status === "hub" ? 25 : 20} strokeWidth={1.8} /></span>
                        <span className="lab-node-text"><strong>{site.name}</strong><small>{site.status === "hub" ? "CENTRAL HUB" : site.status === "needs" ? "NEEDS SUPPORT" : "COVERED"}</small></span>
                      </motion.button>
                    );
                  })}
                  {selectedId === "riverbend" && <div className="lab-route-label" style={{ left: 545, top: 210 }}><Package size={13} /> 80 meals proposed</div>}
                </div>
                <div className="lab-map-hint"><span className="lab-hint-icon">✦</span> Drag to move · Scroll to zoom</div>
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
          </div>
        </div>

        <aside className="lab-inspector" aria-label="Location details">
          <div className="lab-inspector-top"><span>LOCATION INSPECTOR</span><Compass size={17} /></div>
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
                <div className="lab-route-card"><span className="lab-route-icon"><Package size={17} /></span><div><small>SUGGESTED ROUTE</small><strong>Gator Hub <ArrowRight size={15} /> Riverbend</strong></div><span>80</span></div>
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
          <div className="lab-inspector-bottom"><span className="lab-small-star">✳</span> Select any location on the map to explore its status.</div>
        </aside>
      </div>

      <div className="lab-experiment-bar" aria-label="Design lab controls">
        <div className="lab-experiment-label"><span className="lab-experiment-spark">✦</span><strong>Component lab</strong><span>Compare treatments in the same dashboard</span></div>
        <div className="lab-experiment-controls"><span>Node treatment</span><div className="lab-segmented" role="group" aria-label="Node treatment">{treatments.map((item) => <button key={item.id} className={treatment === item.id ? "active" : ""} onClick={() => setTreatment(item.id)} title={item.description}>{item.label}</button>)}</div></div>
        <label className="lab-motion-toggle"><input type="checkbox" checked={motionOn} onChange={(event) => setMotionOn(event.target.checked)} /><span>Route motion</span></label>
      </div>
    </main>
  );
}
