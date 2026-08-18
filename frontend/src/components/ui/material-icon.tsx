"use client";

import { cn } from "@/lib/utils";

interface MaterialIconProps {
  name: string;
  className?: string;
  filled?: boolean;
  size?: number;
}

export function MaterialIcon({ name, className, filled, size }: MaterialIconProps) {
  return (
    <span
      className={cn("material-symbols-outlined", filled && "fill", className)}
      style={size ? { fontSize: size } : undefined}
    >
      {name}
    </span>
  );
}
