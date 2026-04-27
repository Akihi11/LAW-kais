export type ReviewRole = "甲方" | "乙方";

export type ReviewTaskStatus =
  | "created"
  | "uploading"
  | "queued"
  | "running"
  | "succeeded"
  | "failed";

export type WorkflowExecutionStatus = "pending" | "running" | "done" | "failed";
export type TaskNodeStatus = "waiting" | "running" | "success" | "failed";
export type IssueLevel = "high" | "medium" | "low";
export type RiskLevel = "高" | "中" | "低";
export type IssueFilter = "all" | IssueLevel | "other";

export interface ApiErrorPayload {
  code: string;
  message: string;
  detail: unknown | null;
}

export interface CreateReviewResponse {
  success?: boolean;
  provider?: string | null;
  taskId: string;
  requestId?: string | null;
  status: ReviewTaskStatus;
  message?: string | null;
}

export interface TaskNode {
  nodeId: string;
  nodeName: string;
  status: TaskNodeStatus;
  startedAt?: string | null;
  finishedAt?: string | null;
  input?: Record<string, unknown> | unknown[] | string | null;
  output?: Record<string, unknown> | unknown[] | string | null;
  error?: string | null;
  nodeType?: string | null;
  display_order?: number | null;
}

export interface WorkflowNode {
  name: string;
  status?: WorkflowExecutionStatus | null;
  display_order?: number | null;
}

export interface WorkflowGroup {
  name: string;
  status?: WorkflowExecutionStatus | null;
  nodes?: WorkflowNode[] | null;
}

export interface WorkflowInfo {
  groups?: WorkflowGroup[] | null;
}

export interface ReviewStatusResponse {
  success?: boolean;
  provider?: string | null;
  taskId: string;
  requestId?: string | null;
  visitorBizId?: string | null;
  status: ReviewTaskStatus;
  currentStage: string;
  currentStageLabel: string;
  progress: number;
  errorMessage: string | null;
  message?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  completedAt?: string | null;
  workflowGroups?: WorkflowGroup[] | null;
  nodes?: TaskNode[] | null;
  raw?: Record<string, unknown> | null;
}

export interface BasicInfo {
  contractName?: string | null;
  contractType?: string | null;
  perspective?: ReviewRole | null;
}

export interface SummaryInfo {
  riskLevel?: string | null;
  conclusion?: string | null;
}

export interface StatsInfo {
  high?: number | null;
  medium?: number | null;
  low?: number | null;
  manualReview?: boolean | null;
}

export interface ClauseRiskStats {
  high_count?: number | null;
  medium_count?: number | null;
  low_count?: number | null;
  extra_risk_topic_count?: number | null;
}

export interface ClauseOrderedFinding {
  clause_order?: number | null;
  clause_title?: string | null;
  clause_type?: string | null;
  core_issue?: string | null;
  evidence_position?: string | null;
  evidence_quote?: string | null;
  need_manual_review?: boolean | null;
  revision_suggestion?: string | null;
  proposed_amendment?: string | null;
  risk_level?: string | null;
  risk_reason?: string | null;
}

export interface ExtraRiskTopic {
  topic_name?: string | null;
  topic_category?: string | null;
  core_issue?: string | null;
  evidence_position?: string | null;
  evidence_quote?: string | null;
  suggested_action?: string | null;
  need_manual_review?: boolean | null;
  risk_level?: string | null;
  why_not_in_13?: string | null;
  related_clause_titles?: string[] | null;
}

export interface IssueItem {
  id: string;
  title: string;
  level: IssueLevel;
  position?: string | null;
  summary?: string | null;
  evidence?: string | null;
  suggestion?: string | null;
  original?: string | null;
  revised?: string | null;
  anchor?: string | null;
}

export interface ContractSection {
  id: string;
  title: string;
  paragraphs: string[];
}

export interface ReviewResultResponse {
  taskId: string;
  status: ReviewTaskStatus;
  contract_type?: string | null;
  overall_conclusion?: string | null;
  overall_risk_level?: string | null;
  need_manual_review?: boolean | null;
  clause_risk_stats?: ClauseRiskStats | null;
  clause_ordered_findings?: ClauseOrderedFinding[] | null;
  extra_risk_topics?: ExtraRiskTopic[] | null;
  final_review_report?: string | null;
  workflow?: WorkflowInfo | null;
  contractSections: ContractSection[];
  basicInfo?: BasicInfo | null;
  summary?: SummaryInfo | null;
  stats?: StatsInfo | null;
  fullReport?: string | null;
  issues?: IssueItem[] | null;
}
