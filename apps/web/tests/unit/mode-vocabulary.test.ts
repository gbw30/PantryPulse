// covers: V1-A14, V1-A15
import { describe, expect, it } from "vitest";
import { roleLabel, transferModeLabel, vocabularyFor } from "@/lib/mode-vocabulary";

describe("mode vocabulary (V1-SPEC §6.2)", () => {
  it("transfer mode labels per network mode", () => {
    expect(transferModeLabel("PANTRY", "HUB_ONLY")).toBe("Hub → pantries only");
    expect(transferModeLabel("RETAIL", "HUB_ONLY")).toBe("DC → stores only");
    expect(transferModeLabel("PANTRY", "HUB_AND_PANTRY")).toBe("Hub and pantries → pantries");
    expect(transferModeLabel("RETAIL", "HUB_AND_PANTRY")).toBe("DC and stores → stores");
  });

  it("role labels per mode", () => {
    expect(roleLabel("PANTRY", "hub")).toBe("Hub");
    expect(roleLabel("PANTRY", "pantry")).toBe("Pantry");
    expect(roleLabel("RETAIL", "distribution_center")).toBe("Distribution center");
    expect(roleLabel("RETAIL", "store")).toBe("Store");
    // A location type from the other mode is never relabeled as this mode's role.
    expect(() => roleLabel("PANTRY", "store")).toThrow(/not a PANTRY location type/);
    expect(vocabularyFor("PANTRY")).toMatchObject({ mode: "Pantry", senders: "hubs", receivers: "pantries" });
    expect(vocabularyFor("RETAIL")).toMatchObject({ mode: "Retail", senders: "distribution centers", receivers: "stores" });
  });
});
