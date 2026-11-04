// covers: V1-A21
import { describe, expect, it } from "vitest";
import { cn } from "@/lib/utils";

describe("vitest kit", () => {
  it("resolves the @ alias and runs in jsdom with jest-dom matchers", () => {
    expect(cn("a", false && "b", "c")).toBe("a c");
    const el = document.createElement("p");
    el.textContent = "ready";
    document.body.append(el);
    expect(el).toBeInTheDocument();
    expect(window.matchMedia("(min-width: 1px)").matches).toBe(true);
  });
});
