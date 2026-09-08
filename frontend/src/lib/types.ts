export type Severity = "critical" | "high" | "medium" | "low";
export type Confidence = "high" | "medium" | "low" | "unknown";
export type CostClassification = "fixed" | "usage_based" | "estimated" | "unknown";
export type ModuleExpansion = "expanded" | "partially_expanded" | "unexpanded";
export type CrimCategory = "NETWORK_SECURITY" | "DATA_SECURITY" | "OBSERVABILITY";

export interface CrimClassification {
  category: CrimCategory | null;
  confidence: number;
  abstained: boolean;
  reason?: string | null;
  model?: string;
}

export interface CrimSummary {
  name?: string;
  version?: string;
  threshold?: number;
  ml_unavailable?: boolean;
  classified?: number;
  abstained?: number;
  unclassified?: number;
  resources?: number;
}

export interface TerraformResource {
  id: string;
  resource_type: string;
  name: string;
  provider: string;
  service: string;
  kind: string;
  label: string;
  region: string;
  attributes: Record<string, unknown> & { _monthly_cost?: number };
  references: string[];
  line: number;
  module: string;
  monthly_cost: number;
  address?: string;
  is_data?: boolean;
  billable?: boolean;
  source_file?: string;
  module_address?: string;
  ml_classification?: CrimClassification | null;
}

export interface ModuleInfo {
  address: string;
  name: string;
  source: string;
  version: string | null;
  source_type: string;
  configuration: Record<string, unknown>;
  source_file: string;
  source_line: number;
  expansion: ModuleExpansion;
  resource_count: number;
  data_source_count: number;
  child_modules: string[];
  references: string[];
  note: string;
}

export interface ScoreFindingDetail {
  title: string;
  severity: string;
  confidence: Confidence;
  deduction: number;
}

export interface ScoreExplanation {
  findings_detail: ScoreFindingDetail[];
  signals_detail: string[];
  to_improve: string[];
  evidence_examined: boolean;
}

export interface ScoreCategory {
  key: string;
  label: string;
  score: number | null;
  max: number;
  weight: number;
  findings: number;
  deductions: number;
  signals: string[];
  evidence_status?: "available" | "insufficient_evidence";
  explanation: ScoreExplanation;
}

export interface EvidenceDimension {
  name: string;
  status: "available" | "partial" | "unavailable";
  detail: string;
}

export interface Scores {
  overall: number | null;
  grade: string;
  categories: ScoreCategory[];
  evidence_coverage: Confidence;
  evidence_coverage_pct: number;
  coverage_notes: string[];
  evidence_dimensions: EvidenceDimension[];
  evidence_coverage_formula: string;
  unassessed_categories?: string[];
  scope?: "root_configuration_only" | "complete_configuration";
  scope_label?: string;
  scope_notes?: string[];
  modules_unexpanded?: string[];
}

export interface Explanation {
  why: string;
  impact: string;
  cost_saved: string;
  performance: string;
  reliability: string;
  security: string;
}

export interface Recommendation {
  key: string;
  title: string;
  description: string;
  severity: Severity;
  category: string;
  category_label: string;
  confidence: Confidence;
  target: string[];
  savings_monthly: number;
  risk: string;
  difficulty: string;
  improvement: string;
  source_file?: string;
  source_line?: number;
  explanation: Explanation;
  implementation: string[];
  evidence: string[];
  modes?: string[];
  generated_code?: Record<string, unknown> | null;
  generated_code_hcl?: string | null;
  ml_classification?: CrimClassification | null;
}

export interface CostEstimateDetail {
  resource_id: string;
  kind: string;
  name: string;
  monthly_cost: number;
  known_cost: number;
  usage_cost: number;
  confidence: Confidence;
  cost_classification: CostClassification;
  assumptions: string;
}

export interface CostConfidence {
  level: Confidence;
  breakdown: Record<string, number>;
  notes: string[];
  reasons: string[];
}

export interface UnquantifiedModule {
  address: string;
  reason: string;
}

export interface CostSummary {
  current_monthly: number;
  known_monthly: number;
  usage_monthly: number;
  usage_available: boolean;
  confidence: CostConfidence;
  detailed: CostEstimateDetail[];
  modules_unquantified?: UnquantifiedModule[];
}

export interface FinopsService {
  service: string;
  service_label: string;
  monthly: number;
  yearly: number;
  pct: number;
}

export interface FinopsTrendPoint {
  month: string;
  current?: number;
  optimized?: number;
}

export interface Finops {
  current_monthly: number;
  optimized_monthly: number;
  monthly_savings: number;
  annual_savings: number;
  savings_pct: number;
  usage_monthly: number;
  usage_available: boolean;
  by_service: FinopsService[];
  trend: FinopsTrendPoint[];
  wasted_instances?: number;
  spot_recommendation?: { eligible: number; potential_savings: number };
  rightsizing?: { instances: number; potential_savings: number };
}

export type ComparisonStatus = "comparable" | "partially_comparable" | "not_comparable";

export interface ProviderComparison {
  provider: string;
  label: string;
  region: string;
  status: ComparisonStatus;
  comparison_confidence: "high" | "medium" | "low" | "none";
  estimated_monthly_cost: number | null;
  yearly: number | null;
  breakdown: Record<string, number> | null;
  unsupported_services: string[];
  supported_services: string[];
  coverage_pct: number;
  mapping_coverage_pct?: number;
  architecture_equivalence?: "high" | "medium" | "low";
  cost_type?: "known_baseline" | "estimated" | null;
  availability: string;
  notes: string[];
  sustainability_note: string;
  delta_vs_baseline?: number | null;
  delta_pct?: number | null;
}

export interface Comparison {
  baseline_provider: string;
  baseline_monthly: number;
  providers: ProviderComparison[];
}

export interface GraphNode {
  id: string;
  label: string;
  displayName: string;
  name: string;
  type: string;
  resourceAddress: string;
  category: string;
  kind: string;
  service: string;
  group: string;
  region: string;
  status: string;
  is_data: boolean;
  layer: "primary" | "supporting" | "implementation";
  metrics: {
    monthly_cost: number;
    cost_classification: CostClassification;
    cost_confidence: Confidence;
  };
  icon: string;
  is_module?: boolean;
  expansion?: ModuleExpansion;
  module_source?: string | null;
  module_version?: string | null;
  source_type?: string;
  note?: string;
  resource_count?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
}

export interface GraphGroup {
  id: string;
  label: string;
  color: string;
  kind: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  groups: GraphGroup[];
  topology_count: number;
}

export interface Carbon {
  rating: "low" | "moderate" | "high";
  greener_regions: string[];
  region_emissions: Record<string, string>;
  potential: "minimal" | "moderate" | "significant";
  methodology_notes: string[];
  notes: string[];
}

export interface Optimization {
  mode: string;
  label: string;
  description: string;
  current_monthly: number;
  optimized_monthly: number;
  monthly_savings: number;
  annual_savings: number;
  savings_pct: number;
  applied_recommendations: number;
  generated_code_blocks: number;
  code: string;
  code_validated?: boolean;
  code_warnings?: string[];
}

export interface Review {
  provider: string;
  executive_summary: string;
  architecture_review: string;
  detailed_notes: string[];
  risks: string[];
}

export interface AnalysisMetadata {
  llm_provider: string;
  llm_model: string;
  llm_provider_label: string;
  rules_evaluated: number;
  resources_parsed: number;
  cost_estimates_confident: Confidence;
  evidence_coverage: Confidence;
  evidence_coverage_pct: number;
  modules_detected?: number;
  modules_expanded?: number;
}

export interface Summary {
  resource_count: number;
  data_source_count: number;
  total_block_count: number;
  providers: string[];
  services: string[];
  regions: string[];
  modules: string[];
  variables: string[];
  current_monthly: number;
  known_monthly: number;
  usage_monthly: number;
  usage_available: boolean;
  cost_confidence: CostConfidence;
  optimized_monthly: number;
  monthly_savings: number;
  annual_savings: number;
  score: number | null;
  grade: string;
  dimensions_assessed: number;
  dimensions_total: number;
  evidence_coverage: Confidence;
  evidence_coverage_pct: number;
  module_count?: number;
  unexpanded_module_count?: number;
  scope?: "root_configuration_only" | "complete_configuration";
  scope_label?: string;
}

export interface AnalysisResult {
  resources: TerraformResource[];
  modules?: ModuleInfo[];
  graph: Graph;
  recommendations: Recommendation[];
  scores: Scores;
  costs: CostSummary;
  comparison: Comparison;
  carbon: Carbon;
  finops: Finops;
  optimization: Optimization;
  review: Review;
  analysis_metadata: AnalysisMetadata;
  summary: Summary;
  crim?: CrimSummary | null;
}
