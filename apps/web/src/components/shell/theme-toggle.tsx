import { useSyncExternalStore } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { applyTheme, currentTheme, type ThemeChoice } from "@/lib/theme";
import { cn } from "@/lib/utils";

const SPRING = { type: "spring", stiffness: 250, damping: 22 } as const;

// `.dark` on <html> is the source of truth (set by the boot script before paint, then by applyTheme).
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

/**
 * Dark/light theme toggle for the shared top bar (PP-52 decision 5). The accessible name says what a
 * press does. The server render assumes light; after hydration the icon and name follow the real theme.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const theme = useSyncExternalStore<ThemeChoice>(subscribe, currentTheme, () => "light");
  const reduced = useReducedMotion();
  const next: ThemeChoice = theme === "dark" ? "light" : "dark";
  const label = `Switch to ${next} theme`;
  return (
    <Button asChild variant="ghost" size="icon" className={cn("size-11 md:size-9", className)}>
      <motion.button type="button" aria-label={label} onClick={() => applyTheme(next)} whileTap={{ scale: 0.92 }} transition={SPRING}>
        <AnimatePresence initial={false} mode="wait">
          <motion.span
            key={theme}
            className="grid place-items-center"
            initial={reduced ? false : { opacity: 0, rotate: -60, scale: 0.6 }}
            animate={{ opacity: 1, rotate: 0, scale: 1 }}
            exit={reduced ? { opacity: 0, transition: { duration: 0 } } : { opacity: 0, rotate: 60, scale: 0.6, transition: { duration: 0.1 } }}
            transition={SPRING}
          >
            {theme === "dark" ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
          </motion.span>
        </AnimatePresence>
      </motion.button>
    </Button>
  );
}
