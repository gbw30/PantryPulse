import type { Page } from "@playwright/test";

// The motion recorder shared by v1-a11y.spec.ts (W3-W03) and v1-motion.spec.ts (W5-UI03).

// Animated properties that move, scale or resize something (WCAG 2.3.3). Colour, opacity and focus-ring
// changes are not motion and stay allowed.
export const MOTION = /^(transform|translate|scale|rotate|top|right|bottom|left|inset|width|height|max-height|max-width|margin|padding)/;
/** One animation or transition the page started; endMs is its delay plus active duration (Infinity if it never ends). */
export type Started = { kind: string; name: string; props: string[]; infinite: boolean; endMs: number; target: string };

/** Records every animation, transition and script-driven transform the page starts, before its own scripts run. */
export async function recordMotion(page: Page) {
  await page.addInitScript(() => {
    const started: Started[] = [];
    // Per element: the transforms seen, the start of the current run of changes and its recorded entry.
    const transforms = new Map<Element, { seen: Set<string>; runStart: number; last: number; entry?: Started }>();
    Object.assign(window, { __started: started, __transforms: transforms, __inlineAt: 0 });
    const label = (el: Element) => [el.tagName.toLowerCase(), el.id && `#${el.id}`, el.getAttribute("data-slot") && `[${el.getAttribute("data-slot")}]`,
      el.getAttribute("aria-label") && `"${el.getAttribute("aria-label")}"`].filter(Boolean).join("");
    const props = (frames: Keyframe[]) => [...new Set(frames.flatMap(Object.keys))].filter((k) => !["offset", "computedOffset", "easing", "composite"].includes(k));
    const record = (kind: string, name: string, animation: Animation | undefined, target: Element, fallback: string[] = []) => started.push({
      kind, name, target: label(target),
      props: animation?.effect instanceof KeyframeEffect ? props(animation.effect.getKeyframes()) : fallback,
      infinite: animation?.effect?.getComputedTiming().iterations === Infinity,
      endMs: Number(animation?.effect?.getComputedTiming().endTime ?? 0),
    });
    document.addEventListener("animationstart", (event) => {
      const target = event.target as Element;
      // One that ended before it could be read counts as motion ("unknown"): the check fails closed.
      record("css-animation", event.animationName, target.getAnimations().find((a) => (a as CSSAnimation).animationName === event.animationName), target, ["unknown"]);
    }, true);
    document.addEventListener("transitionrun", (event) => {
      const target = event.target as Element;
      const transition = target.getAnimations().find((a) => (a as CSSTransition).transitionProperty === event.propertyName);
      record("css-transition", event.propertyName, transition, target, [event.propertyName]);
    }, true);
    const animate = Element.prototype.animate;
    Element.prototype.animate = function (this: Element, ...args: Parameters<Element["animate"]>) {
      const animation = animate.apply(this, args);
      record("script-animation", "animate()", animation, this);
      return animation;
    };
    // Script-driven motion (requestAnimationFrame) shows only as inline transforms (or SVG draw offsets) changing frame by frame. A run
    // is changes less than 100 ms apart; endMs is the longest run seen (an enter and a later exit are two runs).
    new MutationObserver((records) => {
      const now = performance.now();
      for (const r of records) {
        const el = r.target as HTMLElement;
        // Motion draws SVG paths (pathLength) through the stroke-dash attributes, not inline style.
        const svgDraw = r.attributeName !== "style";
        const value = svgDraw ? `${el.getAttribute("stroke-dasharray")} / ${el.getAttribute("stroke-dashoffset")}` : el.style?.transform;
        if (!value) continue;
        Object.assign(window, { __inlineAt: now });
        const track = transforms.get(el) ?? { seen: new Set<string>(), runStart: now, last: now };
        if (now - track.last > 100) track.runStart = now;
        track.last = now;
        track.seen.add(value);
        transforms.set(el, track);
        if (track.seen.size === 3 && !track.entry) {
          track.entry = svgDraw
            ? { kind: "svg-draw", name: "", props: ["stroke-dasharray"], infinite: false, endMs: 0, target: label(el) }
            : { kind: "inline-transform", name: "", props: ["transform"], infinite: false, endMs: 0, target: label(el) };
          started.push(track.entry);
        }
        if (track.entry) {
          track.entry.name = [...track.seen].slice(0, 3).join(" → ");
          track.entry.endMs = Math.max(track.entry.endMs, now - track.runStart);
        }
      }
    }).observe(document, { subtree: true, attributes: true, attributeFilter: ["style", "stroke-dasharray", "stroke-dashoffset"] });
  });
}

/** Resolves once script-driven transforms and SVG draws have not changed for 150 ms (capped at limitMs). */
export const inlineQuiet = (page: Page, limitMs: number) => page.evaluate((limit) => new Promise<void>((done) => {
  const start = performance.now();
  const tick = () => {
    const at = (window as unknown as { __inlineAt: number }).__inlineAt;
    if (performance.now() - at > 150 || performance.now() - start > limit) done();
    else setTimeout(tick, 50);
  };
  tick();
}), limitMs);

/** Everything the page has started so far. */
export const started = (page: Page) => page.evaluate(() => (window as unknown as { __started: Started[] }).__started);

/** What the page has started so far that moves something on screen, or never ends. */
export const moving = async (page: Page) => (await page.evaluate(() => (window as unknown as { __started: Started[] }).__started))
  .filter((s) => s.infinite || s.props.some((p) => p === "unknown" || MOTION.test(p)));

/**
 * Every element whose computed transition would move or resize it: a layout property, or "all", with a
 * non-zero duration. The recorder above sees a transition only when a size change happens to land after
 * the first style pass, which depends on load; this reads the styles themselves, so it never depends on timing.
 */
export const movingTransitions = (page: Page) => page.evaluate((source) => {
  const motion = new RegExp(source);
  const label = (el: Element) => [el.tagName.toLowerCase(), el.getAttribute("data-slot") && `[${el.getAttribute("data-slot")}]`,
    el.getAttribute("aria-label") && `"${el.getAttribute("aria-label")}"`].filter(Boolean).join("");
  return [...new Set([...document.querySelectorAll("*")].flatMap((el) => {
    const style = getComputedStyle(el);
    const durations = style.transitionDuration.split(",").map((d) => parseFloat(d));
    return style.transitionProperty.split(",").map((p) => p.trim())
      .filter((p, i) => (p === "all" || motion.test(p)) && durations[i % durations.length] > 0)
      .map((p) => `${label(el)}: ${p}`);
  }))];
}, MOTION.source);

