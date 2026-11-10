// covers: V1-A04
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PresenterFooter } from "@/components/shell/presenter-footer";
import { PresenterProvider } from "@/components/shell/presenter-session";

// N1 (review of #129): a login the server never answers must still end. After 10 s the form treats it as a
// failed sign-in: it says so and empties the password field, so nothing that records the page later holds it.
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

it("a login that never answers times out after 10 s, says so and empties the password field", async () => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  // Like a real fetch: it never settles unless its signal aborts.
  const fetch = vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => reject(init.signal?.reason));
  }));
  vi.stubGlobal("fetch", fetch);
  render(<PresenterProvider><PresenterFooter /></PresenterProvider>);
  await act(async () => {}); // With no pp_csrf cookie the session settles as a visitor without a request.
  fireEvent.click(screen.getByRole("button", { name: "Presenter sign in" }));
  const password = screen.getByLabelText("Password") as HTMLInputElement;
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: "presenter" } });
  fireEvent.change(password, { target: { value: "Canary-Pw-7Q2x" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(fetch).toHaveBeenCalledWith("/api/v1/presenter/login", expect.objectContaining({ method: "POST" }));

  await act(async () => { await vi.advanceTimersByTimeAsync(9_999); });
  expect(screen.getByRole("button", { name: "Signing in…" })).toBeDisabled();
  expect(password.value).toBe("Canary-Pw-7Q2x");

  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(screen.getByRole("alert")).toHaveTextContent("Sign-in timed out. Try again.");
  expect(password.value).toBe("");
  expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
});
