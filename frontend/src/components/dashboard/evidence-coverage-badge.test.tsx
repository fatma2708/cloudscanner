import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OverviewPage from "@/app/dashboard/page";
import ScorePage from "@/app/dashboard/score/page";
import {
  EVIDENCE_COVERAGE_INCOMPLETE_THRESHOLD,
  EvidenceCoverageBadge,
} from "./evidence-coverage-badge";
import type { AnalysisResult } from "@/lib/types";

vi.mock("@/lib/analysis-context", () => ({
  useAnalysis: vi.fn(),
}));

import { useAnalysis } from "@/lib/analysis-context";

const mockedUseAnalysis = vi.mocked(useAnalysis);

function makeData(coveragePct: number, unexpanded: string[]): AnalysisResult {
  const low = coveragePct < EVIDENCE_COVERAGE_INCOMPLETE_THRESHOLD;
  return {
    resources: [],
    modules: [],
    graph: { nodes: [], edges: [], groups: [], topology_count: 0 },
    recommendations: [],
    scores: {
      overall: 64,
      grade: "C",
      categories: [
        {
          key: "cost",
          label: "Cost",
          score: 60,
          max: 100,
          weight: 0.3,
          findings: 0,
          deductions: 0,
          signals: [],
          explanation: { findings_detail: [], signals_detail: [], to_improve: [], evidence_examined: true },
        },
      ],
      evidence_coverage: low ? "low" : "high",
      evidence_coverage_pct: coveragePct,
      coverage_notes: [],
      evidence_dimensions: [
        {
          name: "Module contents",
          status: unexpanded.length ? "partial" : "available",
          detail: unexpanded.length
            ? `${unexpanded.length} module(s) not inspected: ${unexpanded.join(", ")}`
            : "All modules expanded and inspected",
        },
      ],
      evidence_coverage_formula: "",
      modules_unexpanded: unexpanded,
    },
    costs: {
      current_monthly: 18,
      known_monthly: 18,
      usage_monthly: 0,
      usage_available: false,
      confidence: { level: "low", breakdown: {}, notes: [], reasons: ["No billing data provided"] },
      detailed: [],
      modules_unquantified: unexpanded.map((address) => ({ address, reason: "Module source not included" })),
    },
    comparison: { baseline_provider: "aws", baseline_monthly: 18, providers: [] },
    carbon: {
      rating: "moderate",
      greener_regions: [],
      region_emissions: {},
      potential: "minimal",
      methodology_notes: [],
      notes: [],
    },
    finops: {
      current_monthly: 18,
      optimized_monthly: 18,
      monthly_savings: 0,
      annual_savings: 0,
      savings_pct: 0,
      usage_monthly: 0,
      usage_available: false,
      by_service: [],
      trend: [],
    },
    optimization: {
      mode: "balanced",
      label: "Balanced",
      description: "",
      current_monthly: 18,
      optimized_monthly: 18,
      monthly_savings: 0,
      annual_savings: 0,
      savings_pct: 0,
      applied_recommendations: 0,
      generated_code_blocks: 0,
      code: "",
    },
    review: { provider: "aws", executive_summary: "", architecture_review: "", detailed_notes: [], risks: [] },
    analysis_metadata: {
      llm_provider: "none",
      llm_model: "",
      llm_provider_label: "Not used",
      rules_evaluated: 0,
      resources_parsed: 0,
      cost_estimates_confident: "low",
      evidence_coverage: low ? "low" : "high",
      evidence_coverage_pct: coveragePct,
    },
    summary: {
      resource_count: 5,
      data_source_count: 0,
      total_block_count: 209,
      providers: ["aws"],
      services: [],
      regions: ["us-east-1"],
      modules: unexpanded,
      variables: [],
      current_monthly: 18,
      known_monthly: 18,
      usage_monthly: 0,
      usage_available: false,
      cost_confidence: { level: "low", breakdown: {}, notes: [], reasons: [] },
      optimized_monthly: 12,
      monthly_savings: 6,
      annual_savings: 72,
      score: 64,
      grade: "C",
      dimensions_assessed: 4,
      dimensions_total: 6,
      evidence_coverage: low ? "low" : "high",
      evidence_coverage_pct: coveragePct,
      unexpanded_module_count: unexpanded.length,
    },
    crim: null,
  };
}

function makeContext(data: AnalysisResult) {
  return {
    data,
    loading: false,
    error: null,
    mode: "balanced",
    refresh: vi.fn(),
    refreshing: false,
    repoUrl: "https://github.com/acme/infra",
    analyzeGithub: vi.fn(),
    analyzeDemo: vi.fn(),
  };
}

describe("EvidenceCoverageBadge component", () => {
  it("renders the warning with the module count when coverage is below the threshold", () => {
    render(<EvidenceCoverageBadge coveragePct={15} unexpandedModules={3} />);
    expect(screen.getByText(/3 modules not inspected/)).toBeInTheDocument();
  });

  it("renders nothing when coverage is at or above the threshold", () => {
    render(<EvidenceCoverageBadge coveragePct={EVIDENCE_COVERAGE_INCOMPLETE_THRESHOLD} unexpandedModules={3} />);
    expect(screen.queryByText(/Incomplete/)).not.toBeInTheDocument();
  });

  it("renders nothing when every module was inspected even if coverage is low", () => {
    render(<EvidenceCoverageBadge coveragePct={15} unexpandedModules={0} />);
    expect(screen.queryByText(/Incomplete/)).not.toBeInTheDocument();
  });
});

describe("Evidence coverage warning on cards", () => {
  beforeEach(() => {
    mockedUseAnalysis.mockReset();
  });

  it("Overview: warning is rendered on the Monthly Cost card and the score panel when coverage is below threshold", () => {
    mockedUseAnalysis.mockReturnValue(makeContext(makeData(15, ["module.vpc", "module.db", "module.eks"])));
    render(<OverviewPage />);
    expect(screen.getAllByText(/3 modules not inspected/)).toHaveLength(2);
  });

  it("Overview: no warning when coverage is at or above threshold", () => {
    mockedUseAnalysis.mockReturnValue(makeContext(makeData(85, ["module.vpc", "module.db"])));
    render(<OverviewPage />);
    expect(screen.queryByText(/Incomplete/)).not.toBeInTheDocument();
  });

  it("Score: warning is rendered on the Score card when coverage is below threshold", () => {
    mockedUseAnalysis.mockReturnValue(makeContext(makeData(15, ["module.vpc", "module.eks"])));
    render(<ScorePage />);
    expect(screen.getByText(/2 modules not inspected/)).toBeInTheDocument();
  });

  it("Score: no warning when coverage is at or above threshold", () => {
    mockedUseAnalysis.mockReturnValue(makeContext(makeData(85, ["module.vpc", "module.eks"])));
    render(<ScorePage />);
    expect(screen.queryByText(/Incomplete/)).not.toBeInTheDocument();
  });

  it("Overview: no warning when modules are not counted despite low coverage", () => {
    mockedUseAnalysis.mockReturnValue(makeContext(makeData(15, [])));
    render(<OverviewPage />);
    expect(screen.queryByText(/Incomplete/)).not.toBeInTheDocument();
  });
});