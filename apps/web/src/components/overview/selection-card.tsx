import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { cn } from "@/lib/utils";
import { SPRING } from "./atlas-motion";
import type { SelectionContext } from "./schematic-map";

type Props = {
  open: boolean;
  onClose: () => void;
  dock: SelectionContext;
  /** Pixel offset from the dock spot (desktop, dragged by the card's grip). */
  offset: { dx: number; dy: number };
  /** Stable key per selected site: the content crossfades between sites while the card stays open. */
  contentKey: string;
  label: string;
  lifted: boolean;
  onCloseAutoFocus: (event: Event) => void;
  children: React.ReactNode;
};

/**
 * The docked selection card. Radix supplies the dialog semantics, Escape, outside-click dismissal and
 * focus return; Motion's AnimatePresence owns enter and exit (spring in, quick fade out), so the
 * portal and content stay mounted (forceMount) until the exit finishes. Reduced motion: no movement.
 */
export function SelectionCard({ open, onClose, dock, offset, contentKey, label, lifted, onCloseAutoFocus, children }: Props) {
  const reduced = useReducedMotion();
  return (
    <PopoverPrimitive.Root open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <PopoverPrimitive.Anchor asChild>
        <span aria-hidden="true" className="pointer-events-none absolute h-0" style={{ left: dock.left, top: dock.top, width: dock.width }} />
      </PopoverPrimitive.Anchor>
      <AnimatePresence>
        {open && (
          <PopoverPrimitive.Portal forceMount key="selection-card">
            <PopoverPrimitive.Content
              forceMount
              asChild
              side={dock.side}
              align="start"
              sideOffset={0}
              avoidCollisions={false}
              aria-label={label}
              onCloseAutoFocus={onCloseAutoFocus}
            >
              <motion.div
                data-selection-card
                className={cn(
                  "relative z-50 rounded-md border bg-popover p-3 text-popover-foreground outline-hidden transition-shadow duration-150",
                  lifted ? "shadow-xl ring-1 ring-primary/40" : "shadow-md",
                )}
                style={{ width: dock.width, translate: `${offset.dx}px ${offset.dy}px` }}
                initial={reduced ? false : { opacity: 0, y: dock.side === "top" ? 14 : -14, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={reduced ? { opacity: 0, transition: { duration: 0 } } : { opacity: 0, y: dock.side === "top" ? 8 : -8, transition: { duration: 0.15, ease: "easeIn" } }}
                transition={SPRING}
              >
                <AnimatePresence initial={false} mode="popLayout">
                  <motion.div
                    key={contentKey}
                    initial={reduced ? false : { opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={reduced ? { opacity: 0, transition: { duration: 0 } } : { opacity: 0, x: -10, transition: { duration: 0.12 } }}
                    transition={SPRING}
                  >
                    {children}
                  </motion.div>
                </AnimatePresence>
              </motion.div>
            </PopoverPrimitive.Content>
          </PopoverPrimitive.Portal>
        )}
      </AnimatePresence>
    </PopoverPrimitive.Root>
  );
}
