/**
 * Hand-written to match apps/api's Pydantic schemas for Milestone 1. ADR
 * 0003 calls for generating this from the FastAPI OpenAPI schema
 * (openapi-typescript) once the API surface stabilizes past Milestone 1 —
 * tracked as follow-up work, not deferred silently.
 */

export type RiskStatus = "draft" | "open" | "monitoring" | "closed";
export type RiskDecision = "accept" | "treat" | "transfer" | "avoid" | "pending";
export type RiskBand = "low" | "moderate" | "high" | "extreme";

export interface ImpactScores {
  financial: number;
  customer_service: number;
  operational_delivery: number;
  legal_regulatory: number;
  reputation: number;
  health_safety: number;
}

export interface RiskAssessmentInput {
  likelihood: number;
  impact_scores: ImpactScores;
  control_effectiveness: number | null;
}

export interface Risk {
  id: string;
  risk_code: string;
  title: string;
  statement: string | null;
  cause: string | null;
  event: string | null;
  impact: string | null;
  category_id: string | null;
  business_process: string | null;
  department: string | null;
  owner_id: string | null;
  accountable_executive_id: string | null;
  status: RiskStatus;
  decision: RiskDecision;
  acceptance_rationale: string | null;
  raised_date: string | null;
  next_review_date: string | null;
  likelihood: number | null;
  overall_impact: number | null;
  inherent_score: number | null;
  inherent_band: RiskBand | null;
  control_effectiveness: number | null;
  residual_score: number | null;
  residual_band: RiskBand | null;
  velocity: string | null;
  confidence: string | null;
  treatment_summary: string | null;
  latest_update: string | null;
  created_at: string;
  updated_at: string;
  version: number;
  appetite_status?: string;
}

export interface RiskCategory {
  id: string;
  name: string;
  parent_id: string | null;
  description: string | null;
}

export interface RiskHistoryEntry {
  id: string;
  version: number;
  field_state: Record<string, unknown>;
  recorded_at: string;
  actor: string | null;
}

export interface ImportJob {
  id: string;
  filename: string;
  status:
    | "uploaded"
    | "mapped"
    | "validated"
    | "previewed"
    | "committing"
    | "committed"
    | "failed";
  created_at: string;
  updated_at: string;
}

export interface ColumnMappingEntry {
  source_column: string;
  domain_field: string | null;
  transform: string | null;
}

export interface ColumnsResponse {
  columns: string[];
  suggested_mapping: ColumnMappingEntry[];
}

export interface ValidationIssue {
  row_number: number;
  field: string | null;
  error_type: string;
  message: string;
  severity: "error" | "warning";
  raw_value: unknown;
}

export interface ValidationResult {
  issue_count: number;
  blocking_error_count: number;
  issues: ValidationIssue[];
}

export interface PreviewRow {
  row_number: number;
  mapped: Record<string, unknown>;
  issues: ValidationIssue[];
}

export interface PreviewResult {
  total_rows: number;
  rows: PreviewRow[];
}

export interface CommitResult {
  job_id: string;
  background_job_id: string;
  status: string;
}

export interface BackgroundJob {
  id: string;
  job_type: string;
  status: "pending" | "running" | "succeeded" | "failed";
  error: string | null;
}

export interface MockLoginResponse {
  access_token: string;
  user_id: string;
  email: string;
  display_name: string;
  roles: string[];
}

export interface BandCount {
  band: string;
  count: number;
}

export interface CategoryExposure {
  category_id: string | null;
  category_name: string;
  risk_count: number;
  avg_residual_score: number | null;
}

export interface VelocityCount {
  velocity: string;
  count: number;
}

export interface HeatmapCell {
  likelihood: number;
  impact: number;
  count: number;
  dominant_band: string | null;
}

export interface TopRiskSummary {
  id: string;
  risk_code: string;
  title: string;
  category_name: string | null;
  residual_score: number | null;
  residual_band: string | null;
  owner_email: string | null;
  next_review_date: string | null;
}

export interface ExecutiveDashboard {
  total_risks: number;
  extreme_count: number;
  high_count: number;
  moderate_count: number;
  low_count: number;
  unscored_count: number;
  overdue_reviews_count: number;
  weak_controls_count: number;
  overdue_actions_count: number;
  risks_outside_appetite_count: number;
  band_distribution: BandCount[];
  category_exposure: CategoryExposure[];
  velocity_distribution: VelocityCount[];
  heatmap: HeatmapCell[];
  top_risks: TopRiskSummary[];
}

export type ControlType = "preventive" | "detective" | "corrective";
export type ControlAutomation = "manual" | "automated";
export type ControlStatus = "draft" | "active" | "retired";
export type ControlTestResult = "effective" | "partially_effective" | "ineffective" | "not_tested";

export interface Control {
  id: string;
  control_code: string;
  name: string;
  description: string | null;
  control_type: ControlType;
  automation: ControlAutomation;
  owner_id: string | null;
  frequency: string | null;
  design_effectiveness: number | null;
  operating_effectiveness: number | null;
  last_tested: string | null;
  next_test: string | null;
  evidence: string | null;
  status: ControlStatus;
  created_at: string;
  updated_at: string;
}

export interface ControlTest {
  id: string;
  control_id: string;
  tester: string;
  test_date: string;
  test_method: string | null;
  result: ControlTestResult;
  evidence: string | null;
  finding: string | null;
  remediation_action: string | null;
  created_at: string;
}

export type ActionPriority = "low" | "medium" | "high" | "critical";
export type ActionStatus = "open" | "in_progress" | "completed" | "cancelled";

export interface Action {
  id: string;
  action_code: string;
  risk_id: string | null;
  title: string;
  description: string | null;
  owner_id: string | null;
  due_date: string | null;
  priority: ActionPriority;
  status: ActionStatus;
  completion_percent: number;
  expected_risk_reduction: number | null;
  evidence: string | null;
  completed_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface RiskAppetite {
  id: string;
  category_id: string | null;
  business_unit: string | null;
  appetite_band: string;
  tolerance_band: string;
  limit_value: number | null;
  effective_from: string;
  effective_to: string | null;
}

export interface WeakControlSummary {
  id: string;
  control_code: string;
  name: string;
  operating_effectiveness: number | null;
  design_effectiveness: number | null;
}

export interface OverdueActionSummary {
  id: string;
  action_code: string;
  title: string;
  due_date: string | null;
  owner_email: string | null;
  risk_id: string | null;
}

export interface BreachRiskSummary {
  id: string;
  risk_code: string;
  title: string;
  residual_band: string | null;
  appetite_status: string;
}

export interface GovernanceHealth {
  weak_controls_count: number;
  weak_controls: WeakControlSummary[];
  overdue_actions_count: number;
  overdue_actions: OverdueActionSummary[];
  overdue_reviews_count: number;
  appetite_status_counts: Record<string, number>;
  breach_risks: BreachRiskSummary[];
}

export interface Snapshot {
  id: string;
  label: string;
  period_end: string;
  created_at: string;
  risk_count: number;
}

export interface ChangedRisk {
  id: string;
  risk_code: string;
  title: string;
  from_band?: string | null;
  to_band?: string | null;
  from_owner_id?: string | null;
  to_owner_id?: string | null;
  from_status?: string | null;
  to_status?: string | null;
}

export interface WhatChanged {
  since_snapshot_id: string;
  since_label: string;
  since_period_end: string;
  new_risks: ChangedRisk[];
  closed_risks: ChangedRisk[];
  escalated_risks: ChangedRisk[];
  downgraded_risks: ChangedRisk[];
  owner_changes: ChangedRisk[];
  appetite_changes: ChangedRisk[];
}

export interface TrendPoint {
  label: string;
  period_end: string;
  total_risks: number;
  low: number;
  moderate: number;
  high: number;
  extreme: number;
}

export type IssueStatus = "open" | "resolved";

export interface Issue {
  id: string;
  issue_code: string;
  risk_id: string | null;
  control_id: string | null;
  description: string;
  source: string | null;
  status: IssueStatus;
  created_at: string;
  updated_at: string;
}

export type IncidentSeverity = "low" | "moderate" | "high" | "critical";

export interface Incident {
  id: string;
  incident_code: string;
  risk_id: string | null;
  control_id: string | null;
  description: string;
  incident_date: string;
  severity: IncidentSeverity;
  suggests_likelihood_increase: boolean;
  review_triggered_at: string | null;
  created_at: string;
  updated_at: string;
}

export type ReportType = "pdf_executive_summary" | "pptx_one_slide" | "pptx_two_slide_elt";
export type ReportRunStatus = "pending" | "running" | "succeeded" | "failed";

export interface ReportRun {
  id: string;
  report_type: ReportType;
  status: ReportRunStatus;
  period_start: string | null;
  period_end: string | null;
  scope: Record<string, unknown>;
  error: string | null;
  created_at: string;
  generated_at: string | null;
  download_url: string | null;
}

export interface ScoringConfig {
  id: string;
  version: number;
  dimension_weights: Record<string, number>;
  band_thresholds: [number, string][];
  max_reduction_fraction: number;
  max_control_effectiveness: number;
  is_active: boolean;
  created_at: string;
}
