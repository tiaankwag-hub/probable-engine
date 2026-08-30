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
