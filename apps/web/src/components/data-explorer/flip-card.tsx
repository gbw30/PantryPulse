"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type FlipFace = { title: string; content: React.ReactNode };

type Props = {
  /** data-flip value; each card keeps its own face state. */
  name: string;
  front: FlipFace;
  back: FlipFace;
  /** Flips are disabled until data arrives. */
  disabled?: boolean;
  /** Seconds; Motion skips the rotation under reduced motion (MotionConfig reducedMotion="user"). */
  duration: number;
  /** Where the flip control sits: under the faces (KPI) or in the header corner (analytics). */
  control: "bottom" | "top";
  className?: string;
  faceClassName?: string;
  /** Extra attributes for the root (e.g. data-kpi). */
  rootProps?: Record<`data-${string}`, string>;
};

/**
 * FlipCard: two faces in one fixed footprint. The hidden face is inert and aria-hidden, the new face is
 * announced once, and a user-initiated flip moves focus to the new face's heading. Flipping never
 * fetches, filters or changes the size of anything around it.
 */
export function FlipCard({ name, front, back, disabled, duration, control, className, faceClassName, rootProps }: Props) {
  const [face, setFace] = useState<"front" | "back">("front");
  const [announcement, setAnnouncement] = useState("");
  const userFlip = useRef(false);
  const frontHeading = useRef<HTMLHeadingElement>(null);
  const backHeading = useRef<HTMLHeadingElement>(null);
  const other = face === "front" ? back : front;

  useEffect(() => {
    if (!userFlip.current) return;
    userFlip.current = false;
    (face === "front" ? frontHeading : backHeading).current?.focus();
  }, [face]);

  function flip() {
    userFlip.current = true;
    setAnnouncement(`Showing ${other.title}`);
    setFace((current) => (current === "front" ? "back" : "front"));
  }

  const renderFace = (which: "front" | "back", content: FlipFace) => {
    const hidden = face !== which;
    return (
      <div
        data-face={which}
        inert={hidden}
        aria-hidden={hidden ? "true" : undefined}
        className={cn("absolute inset-0 flex flex-col overflow-hidden rounded-xl border border-border bg-card [backface-visibility:hidden]", faceClassName, control === "bottom" ? "pb-14" : "pt-0")}
        style={which === "back" ? { transform: "rotateY(180deg)" } : undefined}
      >
        <h2
          ref={which === "front" ? frontHeading : backHeading}
          tabIndex={-1}
          className={cn("text-sm font-semibold text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring", control === "top" ? "pr-48 text-base max-sm:pr-0" : "")}
        >
          {content.title}
        </h2>
        {content.content}
      </div>
    );
  };

  return (
    <section data-flip={name} {...rootProps} aria-label={`${front.title} or ${back.title}`} className={cn("relative [perspective:1400px]", className)}>
      <motion.div
        className="relative size-full [transform-style:preserve-3d]"
        initial={false}
        animate={{ rotateY: face === "front" ? 0 : 180 }}
        transition={{ duration, ease: "easeInOut" }}
      >
        {renderFace("front", front)}
        {renderFace("back", back)}
      </motion.div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={flip}
        className={cn("absolute z-10 h-auto min-h-9 gap-1.5 bg-card px-2.5 py-1.5 text-xs whitespace-normal", control === "bottom" ? "right-3 bottom-3 left-3 justify-center sm:left-auto" : "top-3 right-3 max-sm:top-auto max-sm:right-3 max-sm:bottom-3 max-sm:left-3")}
      >
        <RefreshCw className="size-3.5" aria-hidden="true" />
        Show {other.title}
      </Button>
      <p aria-live="polite" className="sr-only">{announcement}</p>
    </section>
  );
}
