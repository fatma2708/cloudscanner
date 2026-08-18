"use client";

import type { ReactNode } from "react";
import { AnalysisProvider } from "@/lib/analysis-context";
import { AppShell } from "@/components/dashboard/app-shell";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AnalysisProvider>
      <AppShell>{children}</AppShell>
    </AnalysisProvider>
  );
}
