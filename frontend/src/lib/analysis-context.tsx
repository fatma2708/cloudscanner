"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import type { AnalysisResult } from "@/lib/types";

interface AnalysisContextValue {
  data: AnalysisResult | null;
  loading: boolean;
  error: string | null;
  mode: string;
  setMode: (mode: string) => void;
  refresh: () => Promise<void>;
  refreshing: boolean;
  repoUrl: string | null;
  analyzeGithub: (url: string) => Promise<void>;
}

const AnalysisContext = createContext<AnalysisContextValue | null>(null);

export const OPTIMIZATION_MODES: Record<string, { label: string; description: string }> = {
  balanced: { label: "Balanced", description: "The best overall mix of cost, reliability and sustainability." },
  "lowest-cost": { label: "Lowest Cost", description: "Aggressively cut spend, even if it trades some reliability." },
  "startup-budget": { label: "Startup Budget", description: "Bare-metal savings with the fewest moving parts." },
  "lowest-carbon": { label: "Lowest Carbon", description: "Minimize embodied and operational emissions." },
  "lowest-latency": { label: "Lowest Latency", description: "Prefer the fastest paths and nearest regions." },
  reliability: { label: "Reliability", description: "Maximum resilience, redundancy and failover." },
  security: { label: "Security", description: "Hardening-first posture for sensitive workloads." },
};

function fetchAnalysis(url: string, mode: string) {
  return api.analyzeGithub(url, mode);
}

function getInitialUrl(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("cloudpilot_github_url") ?? null;
}

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const savedUrl = getInitialUrl();
  const [repoUrl, setRepoUrl] = useState<string | null>(savedUrl);
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(!!savedUrl);
  const [mode, setMode] = useState("balanced");

  const analyzeGithub = useCallback(async (url: string) => {
    setRepoUrl(url);
    sessionStorage.setItem("cloudpilot_github_url", url);
    setData(null);
    setError(null);
    setRefreshing(true);
    try {
      const result = await fetchAnalysis(url, "balanced");
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze repository");
    } finally {
      setRefreshing(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    const currentUrl = sessionStorage.getItem("cloudpilot_github_url");
    if (!currentUrl) return;
    setRefreshing(true);
    setError(null);
    try {
      const result = await fetchAnalysis(currentUrl, mode);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze repository");
    } finally {
      setRefreshing(false);
    }
  }, [mode]);

  useEffect(() => {
    const url = sessionStorage.getItem("cloudpilot_github_url");
    if (!url) return;
    let cancelled = false;
    fetchAnalysis(url, "balanced").then(
      (result) => {
        if (!cancelled) setData(result);
      },
      (err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to analyze repository");
      },
    ).finally(() => {
      if (!cancelled) setRefreshing(false);
    });
    return () => { cancelled = true; };
  }, []);

  const loading = data === null && error === null;

  const value = useMemo(
    () => ({
      data,
      loading,
      error,
      mode,
      setMode,
      refresh,
      refreshing,
      repoUrl,
      analyzeGithub,
    }),
    [data, loading, error, mode, refresh, refreshing, repoUrl, analyzeGithub],
  );

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>;
}

export function useAnalysis(): AnalysisContextValue {
  const ctx = useContext(AnalysisContext);
  if (!ctx) throw new Error("useAnalysis must be used within an AnalysisProvider");
  return ctx;
}
