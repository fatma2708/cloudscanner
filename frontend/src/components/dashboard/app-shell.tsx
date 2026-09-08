"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAnalysis } from "@/lib/analysis-context";
import { MaterialIcon } from "@/components/ui/material-icon";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: "grid_view" },
  { href: "/dashboard/comparison", label: "Cloud Compare", icon: "cloud_queue" },
  { href: "/dashboard/finops", label: "FinOps", icon: "payments" },
  { href: "/dashboard/score", label: "Score", icon: "grade" },
  { href: "/dashboard/architecture", label: "Architecture", icon: "hub" },
];

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="bg-md-surface-container-low border-r border-md-outline-variant hidden md:flex flex-col w-60 h-screen fixed left-0 top-0 pt-16 pb-4 px-2 z-40">
      <ul className="flex flex-col gap-0.5 flex-1 px-1">
        {NAV.map((item) => {
          const isActive =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);

          return (
            <li key={item.href}>
              <Link
                href={item.href}
                onClick={onNavigate}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm",
                  isActive
                    ? "bg-md-secondary-container text-md-on-secondary-container font-medium"
                    : "text-md-on-surface-variant hover:bg-md-surface-container-highest"
                )}
              >
                <MaterialIcon name={item.icon} className="text-[20px]" filled={isActive} />
                <span>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function Topbar({ onMenuOpen }: { onMenuOpen: () => void }) {
  const { repoUrl } = useAnalysis();

  return (
    <header className="bg-md-surface border-b border-md-outline-variant fixed top-0 w-full z-50 flex justify-between items-center px-4 h-14 md:pl-60">
      <div className="flex items-center gap-3">
        <button
          className="md:hidden text-md-on-surface-variant hover:bg-md-surface-container-high p-2 rounded-full transition-colors"
          onClick={onMenuOpen}
          aria-label="Open navigation menu"
        >
          <MaterialIcon name="menu" />
        </button>
        <Link href="/" className="flex items-center gap-2">
          <MaterialIcon name="cloud_done" className="text-primary text-xl" filled />
          <span className="text-lg font-bold text-primary tracking-tight hidden sm:inline">CloudPilot AI</span>
        </Link>
      </div>
      {repoUrl && (
        <span className="text-xs text-md-on-surface-variant font-mono truncate max-w-xs hidden sm:block">
          {repoUrl.replace(/^https?:\/\/(www\.)?github\.com\//, "")}
        </span>
      )}
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-md-background text-md-on-background flex flex-col md:flex-row pb-16 md:pb-0">
      <Topbar onMenuOpen={() => setMobileOpen(true)} />

      <aside className="hidden md:block">
        <Sidebar />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-60">
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <main className="flex-1 w-full md:ml-60 pt-14">
        <div className="p-4 md:p-6 max-w-6xl mx-auto">{children}</div>
      </main>

      <nav className="md:hidden fixed bottom-0 left-0 w-full z-50 flex justify-around items-center px-4 py-2.5 bg-md-surface-container border-t border-md-outline-variant">
        <Link href="/dashboard" aria-label="Overview" className="flex flex-col items-center justify-center text-md-on-surface-variant h-10 w-10 hover:bg-md-primary-container/20 rounded-full transition-colors">
          <MaterialIcon name="home" className="text-[20px]" />
        </Link>
        <Link href="/dashboard/finops" aria-label="FinOps" className="flex flex-col items-center justify-center text-md-on-surface-variant h-10 w-10 hover:bg-md-primary-container/20 rounded-full transition-colors">
          <MaterialIcon name="payments" className="text-[20px]" />
        </Link>
        <Link href="/dashboard/comparison" aria-label="Cloud Compare" className="flex flex-col items-center justify-center text-md-on-surface-variant h-10 w-10 hover:bg-md-primary-container/20 rounded-full transition-colors">
          <MaterialIcon name="cloud_queue" className="text-[20px]" />
        </Link>
      </nav>
    </div>
  );
}
