"use client";

import { useState } from "react";
import { useAnalysis } from "@/lib/analysis-context";
import { ErrorPanel } from "@/components/dashboard/states";
import { ArchitectureCanvas } from "@/components/architecture/Canvas";

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <svg viewBox="0 0 24 24" className="w-12 h-12 text-blue-500" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
      </svg>
      <h2 className="text-xl font-bold text-gray-900">No architecture yet</h2>
      <p className="text-sm text-gray-500">Analyze a repo first to see the resource map.</p>
    </div>
  );
}

export default function ArchitecturePage() {
  const { data, loading, error } = useAnalysis();
  const [showSupporting, setShowSupporting] = useState(false);

  if (error && !data) return <ErrorPanel message={error} />;
  if (!data && !loading) return <EmptyState />;
  if (loading && !data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-200 border-t-blue-500" />
      </div>
    );
  }
  if (!data) return null;

  return (
    <ArchitectureCanvas
      graph={data.graph}
      showSupporting={showSupporting}
      onToggleSupporting={setShowSupporting}
      summary={data.summary}
    />
  );
}
