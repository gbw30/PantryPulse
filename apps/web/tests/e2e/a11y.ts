import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type TestInfo } from "@playwright/test";

// Automated WCAG 2.1 AA scan. Supplementary evidence only: keyboard, focus,
// chart text alternative and screenshot review remain required (SPEC-V5 §14).
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const BLOCKING = new Set(["serious", "critical"]);

type Options = {
  // enforce=false records serious/critical violations as annotations instead of failing.
  // Use it only with a named reason and a tracked follow-up; product screens must enforce.
  enforce?: boolean;
  reason?: string;
};

export async function expectNoSeriousA11yViolations(page: Page, testInfo: TestInfo, label: string, options: Options = {}) {
  const { enforce = true, reason } = options;
  if (!enforce && !reason) throw new Error("Report-only a11y scans need a reason.");
  // Exclusions and disabled rules must name the rule and reason inline; none are used yet.
  // Let running CSS transitions finish first: a button fading from disabled to enabled is briefly
  // semi-transparent, and scanning mid-fade reports a contrast failure that no settled state has.
  // Infinite animations (the design lab) never finish, so only finite ones are awaited, capped at 1s.
  await page.evaluate(() => Promise.race([
    Promise.all(document.getAnimations()
      .filter((animation) => Number.isFinite(animation.effect?.getComputedTiming().endTime ?? Infinity))
      .map((animation) => animation.finished.catch(() => undefined))),
    new Promise((resolve) => setTimeout(resolve, 1000)),
  ]));
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const blocking = results.violations.filter((v) => BLOCKING.has(v.impact ?? ""));
  const advisory = results.violations.filter((v) => !BLOCKING.has(v.impact ?? ""));
  for (const v of advisory) {
    testInfo.annotations.push({ type: "a11y-advisory", description: `${label}: ${v.id} (${v.impact}) x${v.nodes.length}` });
  }
  const summary = blocking.map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
  if (!enforce) {
    for (const line of summary) {
      testInfo.annotations.push({ type: "a11y-known", description: `${label}: ${line} — ${reason}` });
    }
    return;
  }
  expect(summary, `serious/critical axe violations at ${label}`).toEqual([]);
}
