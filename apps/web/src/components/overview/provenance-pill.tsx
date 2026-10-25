import { cn } from "@/lib/utils";

/** ProvenancePill: names where displayed numbers come from. Text in ink; the dot is decorative. */
export function ProvenancePill({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border border-pp-teal/30 bg-pp-teal-soft px-2.5 py-0.5 text-xs font-medium whitespace-nowrap text-foreground", className)}>
      <span aria-hidden="true" className="size-1.5 rounded-full bg-pp-teal" />
      {children}
    </span>
  );
}
