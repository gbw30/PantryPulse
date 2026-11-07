import { api, type Schema } from "./planning-api";

export type Network = Schema["Network"];

/** v1 network reads (README "Interfaces frozen in W0-08"). Presenter-only; a visitor gets 401. */
export const networkApi = {
  list: () => api<Schema["NetworkList"]>("networks"),
  get: (networkId: string) => api<Network>(`networks/${encodeURIComponent(networkId)}`),
};
