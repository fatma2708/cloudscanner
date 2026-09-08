"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { MaterialIcon } from "@/components/ui/material-icon";

export default function LandingPage() {
  const router = useRouter();
  const [url, setUrl] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    sessionStorage.setItem("cloudpilot_github_url", trimmed);
    router.push("/dashboard");
  }

  return (
    <div className="min-h-screen bg-md-background text-md-on-background antialiased flex flex-col">
      <header className="flex items-center justify-between px-6 h-16 border-b border-md-outline-variant">
        <div className="flex items-center gap-2.5">
          <MaterialIcon name="cloud_done" className="text-primary text-2xl" filled />
          <span className="font-bold text-primary text-lg tracking-tight">CloudPilot AI</span>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-xl text-center">
          <MaterialIcon name="cloud_done" className="text-primary text-5xl mb-6" filled />
          <h1 className="text-4xl md:text-5xl font-black tracking-tight leading-tight mb-4">
            Analyze your Terraform
            <br />
            <span className="text-primary">in seconds.</span>
          </h1>
          <p className="text-md-on-surface-variant mb-10 max-w-md mx-auto leading-relaxed">
            Paste a GitHub repo containing Terraform files. Get cost estimates, security findings, optimization fixes, and a production score.
          </p>

          <form onSubmit={handleSubmit} className="flex gap-3 max-w-lg mx-auto">
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              required
              aria-label="GitHub repository URL"
              className="flex-1 px-5 py-3.5 rounded-full bg-md-surface-container-lowest border border-md-outline-variant text-md-on-surface placeholder:text-md-on-surface-variant/60 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors text-sm"
            />
            <button
              type="submit"
              className="px-7 py-3.5 rounded-full bg-primary text-md-on-primary font-bold text-sm hover:opacity-90 transition-opacity inline-flex items-center gap-2 shrink-0"
            >
              Analyze
              <MaterialIcon name="arrow_forward" className="text-[18px]" />
            </button>
          </form>

          <p className="mt-4 text-xs text-md-on-surface-variant/60">
            Must be a public repository with .tf or .tofu files
          </p>
        </div>
      </main>

      <footer className="py-6 text-center text-xs text-md-on-surface-variant/50 border-t border-md-outline-variant">
        CloudPilot AI — Terraform analysis and optimization
      </footer>
    </div>
  );
}
