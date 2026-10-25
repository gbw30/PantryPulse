// Colour theme: `.dark` on <html> switches the --pp-* tokens (globals.css). The choice is a per-viewer
// convenience in localStorage; with no stored choice the OS preference applies. Storage can be
// unavailable (private windows, blocked site data), so every access is guarded.

export type ThemeChoice = "light" | "dark";

export const THEME_STORAGE_KEY = "pp-theme";

export function readStoredTheme(): ThemeChoice | null {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

export function systemTheme(): ThemeChoice {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function currentTheme(): ThemeChoice {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function applyTheme(choice: ThemeChoice, persist = true) {
  document.documentElement.classList.toggle("dark", choice === "dark");
  if (!persist) return;
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // The toggle still works for this page view.
  }
}

/** Runs before hydration (inline in the root layout) so the page never flashes the wrong theme. */
export const THEME_BOOT_SCRIPT = `(function(){try{var t=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});if(t!=="light"&&t!=="dark"){t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}document.documentElement.classList.toggle("dark",t==="dark")}catch(e){}})();`;
