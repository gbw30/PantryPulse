import { cn } from "@/lib/utils"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("rounded-md bg-accent", className)} // static (ART-DIRECTION Loading: no pulsing; W5-UI03 finite motion)
      {...props}
    />
  )
}

export { Skeleton }
