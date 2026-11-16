// covers: V1-A20
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// W5A-01: the shared primitives carry the look once (spec §4.10): pills, a sage neutral badge, ruled sections.
describe("shared primitives", () => {
  it.each(["default", "xs", "sm", "lg", "icon", "icon-xs"] as const)("a %s button is a pill", (size) => {
    render(<Button size={size}>Run</Button>);
    const classes = screen.getByRole("button", { name: "Run" }).className.split(/\s+/);
    expect(classes).toContain("rounded-full");
    expect(classes.filter((name) => /^rounded-(sm|md|lg|xl)$/.test(name))).toEqual([]);
  });

  it("the neutral badge is a pill on the sage tint, with ink text", () => {
    render(<Badge variant="secondary">OK</Badge>);
    const classes = screen.getByText("OK").className.split(/\s+/);
    expect(classes).toEqual(expect.arrayContaining(["rounded-full", "bg-pp-tint", "text-pp-ink"]));
  });

  it("a card is a ruled section: a top rule, no box, no shadow, no side inset", () => {
    render(<Card data-testid="card"><CardHeader data-testid="header"><CardTitle>Receipts</CardTitle></CardHeader><CardContent data-testid="content">Rows</CardContent></Card>);
    const classes = screen.getByTestId("card").className.split(/\s+/);
    expect(classes).toEqual(expect.arrayContaining(["border-t", "border-pp-rule"]));
    expect(classes.filter((name) => /^(border|bg-card|rounded-.+|shadow-.+)$/.test(name))).toEqual([]);
    for (const part of ["header", "content"]) expect(screen.getByTestId(part).className).not.toMatch(/\bpx-\d/);
    expect(screen.getByText("Receipts").className.split(/\s+/)).toEqual(expect.arrayContaining(["font-serif", "font-medium"]));
  });
});
