import type { Schema } from "./planning-api";

export type NetworkMode = Schema["Network"]["mode"];
export type TransferMode = Schema["TransferMode"];

// V1-SPEC §6.2: one vocabulary per network mode. TransferMode enums are shared; only labels change.
const VOCABULARY = {
  PANTRY: {
    mode: "Pantry",
    sender: "Hub", senders: "hubs", receiver: "Pantry", receivers: "pantries",
    types: { hub: "Hub", pantry: "Pantry" } as Record<string, string>,
    transfer: { HUB_ONLY: "Hub → pantries only", HUB_AND_PANTRY: "Hub and pantries → pantries" },
  },
  RETAIL: {
    mode: "Retail",
    sender: "Distribution center", senders: "distribution centers", receiver: "Store", receivers: "stores",
    types: { distribution_center: "Distribution center", store: "Store" } as Record<string, string>,
    transfer: { HUB_ONLY: "DC → stores only", HUB_AND_PANTRY: "DC and stores → stores" },
  },
} as const satisfies Record<NetworkMode, unknown>;

export const vocabularyFor = (mode: NetworkMode) => VOCABULARY[mode];

export const transferModeLabel = (mode: NetworkMode, transfer: TransferMode) => VOCABULARY[mode].transfer[transfer];

/** Label for a `locations.csv` `type` value. A type from the other mode is a data error, never relabeled. */
export function roleLabel(mode: NetworkMode, type: string) {
  const label = VOCABULARY[mode].types[type];
  if (!label) throw new Error(`"${type}" is not a ${mode} location type`);
  return label;
}

/** "Pantry mode · hubs and pantries" */
export const modeSummary = (mode: NetworkMode) => `${VOCABULARY[mode].mode} mode · ${VOCABULARY[mode].senders} and ${VOCABULARY[mode].receivers}`;
