import { IssueFilter, ReviewRole } from "@/lib/types";

export const REVIEW_ROLES: ReviewRole[] = ["甲方", "乙方"];
export const ACCEPTED_FILE_TYPES = ".docx,.pdf";
export const ALLOWED_FILE_EXTENSIONS = [".docx", ".pdf"];
export const MAX_FILE_SIZE_MB = 3.5;
export const STATUS_POLL_INTERVAL_MS = 3000;
export const MAX_STATUS_POLL_ATTEMPTS = 200;

export const ISSUE_FILTER_OPTIONS: Array<{ value: IssueFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "high", label: "高风险" },
  { value: "medium", label: "中风险" },
  { value: "low", label: "低风险" },
  { value: "other", label: "其他" },
];
