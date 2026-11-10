// covers: V1-A04
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { PresenterFooter } from "@/components/shell/presenter-footer";
import { ApiError } from "@/lib/planning-api";

// H1 (review of #129): the form keeps no password after a failed sign-in, so nothing that records the page
// afterwards (an accessibility snapshot, a screenshot, a test's error-context.md) can capture it.
const signIn = vi.fn();
vi.mock("@/components/shell/presenter-session", async (load) => ({
  ...(await load<typeof import("@/components/shell/presenter-session")>()),
  usePresenter: () => ({ state: "visitor", signIn, signOut: vi.fn() }),
}));

it("a failed sign-in empties the password field, keeps the username and says why", async () => {
  signIn.mockRejectedValue(new ApiError("RATE_LIMITED", 429));
  render(<PresenterFooter />);
  fireEvent.click(screen.getByRole("button", { name: "Presenter sign in" }));
  const username = screen.getByLabelText("Username") as HTMLInputElement;
  const password = screen.getByLabelText("Password") as HTMLInputElement;
  fireEvent.change(username, { target: { value: "presenter" } });
  fireEvent.change(password, { target: { value: "Canary-Pw-7Q2x" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toBeVisible();
  expect(signIn).toHaveBeenCalledWith("presenter", "Canary-Pw-7Q2x");
  await waitFor(() => expect(password.value).toBe(""));
  expect(username.value).toBe("presenter");
  expect(password).toHaveFocus();
});
