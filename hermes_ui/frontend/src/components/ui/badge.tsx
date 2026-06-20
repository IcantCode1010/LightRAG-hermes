import * as React from "react";
import { cn } from "@/lib/utils";

export function Badge({
  className,
  tone,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: "ok" | "warn" | "error" }) {
  return <span className={cn("badge", tone && `badge-${tone}`, className)} {...props} />;
}
