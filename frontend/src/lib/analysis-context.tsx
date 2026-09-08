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
  refresh: () => Promise<void>;
  refreshing: boolean;
  repoUrl: string | null;
  analyzeGithub: (url: string) => Promise<void>;
  analyzeDemo: () => Promise<void>;
}

const AnalysisContext = createContext<AnalysisContextValue | null>(null);

function fetchAnalysis(url: string, mode: string) {
  return api.analyzeGithub(url, mode);
}

const DEMO_LABEL = "Demo project";

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
  const [mode] = useState("balanced");

  const analyzeGithub = useCallback(async (url: string) => {
    setRepoUrl(url);
    sessionStorage.setItem("cloudpilot_github_url", url);
    setData(null);
    setError(null);
    setRefreshing(true);
    try {
      const result = await fetchAnalysis(url, mode);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze repository");
    } finally {
      setRefreshing(false);
    }
  }, [mode]);

  const analyzeDemo = useCallback(async () => {
    setRepoUrl(DEMO_LABEL);
    sessionStorage.removeItem("cloudpilot_github_url");
    setData(null);
    setError(null);
    setRefreshing(true);
    try {
      setData(await api.analyze(mode));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the demo project");
    } finally {
      setRefreshing(false);
    }
  }, [mode]);

  const refresh = useCallback(async () => {
    if (repoUrl === DEMO_LABEL) {
      await analyzeDemo();
      return;
    }
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
  }, [analyzeDemo, mode, repoUrl]);

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
      refresh,
      refreshing,
      repoUrl,
      analyzeGithub,
      analyzeDemo,
    }),
    [data, loading, error, mode, refresh, refreshing, repoUrl, analyzeGithub, analyzeDemo],
  );

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>;
}

export function useAnalysis(): AnalysisContextValue {
  const ctx = useContext(AnalysisContext);
  if (!ctx) throw new Error("useAnalysis must be used within an AnalysisProvider");
  return ctx;
}
