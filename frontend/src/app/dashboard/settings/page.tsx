"use client";

import { useState } from "react";
import { useAnalysis } from "@/lib/analysis-context";
import { ErrorPanel, LoadingPanel } from "@/components/dashboard/states";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { API_URL } from "@/lib/api";
import { toast } from "sonner";
import { MaterialIcon } from "@/components/ui/material-icon";

export default function SettingsPage() {
  const { data, loading, error } = useAnalysis();
  const [apiUrl, setApiUrl] = useState(API_URL);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [darkMode, setDarkMode] = useState(false);

  if (loading && !data) return <LoadingPanel />;
  if (error && !data) return <ErrorPanel message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold text-md-on-background">Settings</h1>
        <p className="text-sm text-md-on-surface-variant">
          Connection and display preferences for your CloudPilot workspace.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="bg-md-surface-container-low rounded-xl p-5 border border-md-outline-variant">
          <h2 className="font-semibold text-md-on-surface mb-4 flex items-center gap-2">
            <MaterialIcon name="dns" className="text-primary" />
            API Connection
          </h2>
          <div className="space-y-4">
            <div className="flex gap-2">
              <Input
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                className="font-mono text-xs rounded-full border-md-outline-variant"
              />
              <Button
                variant="outline"
                onClick={() => {
                  navigator.clipboard?.writeText(apiUrl);
                  toast.success("API URL copied");
                }}
                className="rounded-full border-md-outline-variant"
              >
                <MaterialIcon name="content_copy" className="text-[18px]" />
              </Button>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-md-outline-variant bg-md-surface-container p-3 text-sm">
              <span className="text-md-on-surface-variant">Backend status</span>
              <span className="bg-primary/10 text-primary text-xs font-bold px-2 py-0.5 rounded">Connected</span>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-md-outline-variant bg-md-surface-container p-3 text-sm">
              <span className="text-md-on-surface-variant">Review engine</span>
              <span className="font-medium text-md-on-surface">{data.review.provider}</span>
            </div>
          </div>
        </div>

        <div className="bg-md-surface-container-low rounded-xl p-5 border border-md-outline-variant">
          <h2 className="font-semibold text-md-on-surface mb-4 flex items-center gap-2">
            <MaterialIcon name="tune" className="text-primary" />
            Preferences
          </h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-md-on-surface">Dark theme</p>
                <p className="text-xs text-md-on-surface-variant">Switch to a dark workspace.</p>
              </div>
              <Switch checked={darkMode} onCheckedChange={setDarkMode} />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-md-on-surface">Auto-refresh analysis</p>
                <p className="text-xs text-md-on-surface-variant">Re-analyze when the optimization mode changes.</p>
              </div>
              <Switch checked={autoRefresh} onCheckedChange={setAutoRefresh} />
            </div>
            <div className="rounded-lg border border-md-outline-variant bg-md-surface-container p-3 text-xs leading-relaxed text-md-on-surface-variant">
              The analysis engine runs locally while the AI review is powered by
              the configured LLM provider (HuggingFace by default). All
              recommendations come from the deterministic rules engine.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
