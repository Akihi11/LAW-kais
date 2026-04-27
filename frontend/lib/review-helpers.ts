import { ALLOWED_FILE_EXTENSIONS, MAX_FILE_SIZE_MB } from "@/lib/constants";
import {
  ContractSection,
  IssueFilter,
  IssueItem,
  IssueLevel,
  ReviewStatusResponse,
  ReviewTaskStatus,
  RiskLevel,
  WorkflowExecutionStatus,
} from "@/lib/types";

export function getFileExtension(fileName: string) {
  const lastDotIndex = fileName.lastIndexOf(".");
  if (lastDotIndex === -1) {
    return "";
  }
  return fileName.slice(lastDotIndex).toLowerCase();
}

export function isSupportedFile(file: File) {
  return ALLOWED_FILE_EXTENSIONS.includes(getFileExtension(file.name));
}

export function exceedsFileSizeLimit(file: File) {
  return file.size > MAX_FILE_SIZE_MB * 1024 * 1024;
}

export function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function getTaskStatusLabel(status: ReviewTaskStatus | null) {
  if (!status) {
    return "未开始";
  }

  switch (status) {
    case "created":
      return "已创建";
    case "uploading":
      return "上传中";
    case "queued":
      return "排队中";
    case "running":
      return "执行中";
    case "succeeded":
      return "已完成";
    case "failed":
      return "执行失败";
    default:
      return status;
  }
}

export function getLevelLabel(level: IssueLevel) {
  switch (level) {
    case "high":
      return "高风险";
    case "medium":
      return "中风险";
    case "low":
      return "低风险";
    default:
      return level;
  }
}

export function getIssueLevelBadgeClass(level: IssueLevel) {
  switch (level) {
    case "high":
      return "bg-[#fee2e2] text-[#ef4444]";
    case "medium":
      return "bg-[#fef3c7] text-[#d97706]";
    case "low":
      return "bg-[#dbeafe] text-[#2563eb]";
    default:
      return "bg-[#f3f4f6] text-[#6b7280]";
  }
}

export function getRiskLevelBadgeClass(level: RiskLevel) {
  switch (level) {
    case "高":
      return "bg-[#fee2e2] text-[#ef4444]";
    case "中":
      return "bg-[#fef3c7] text-[#d97706]";
    case "低":
      return "bg-[#dbeafe] text-[#2563eb]";
    default:
      return "bg-[#f3f4f6] text-[#6b7280]";
  }
}

export function getRiskLevelTextClass(level: RiskLevel) {
  switch (level) {
    case "高":
      return "text-[#ef4444]";
    case "中":
      return "text-[#d97706]";
    case "低":
      return "text-[#2563eb]";
    default:
      return "text-[#6b7280]";
  }
}

export function getWorkflowStatusLabel(status?: WorkflowExecutionStatus | null) {
  switch (status) {
    case "done":
      return "已完成";
    case "running":
      return "执行中";
    case "failed":
      return "执行失败";
    case "pending":
    default:
      return "等待中";
  }
}

export function getWorkflowStatusBadgeClass(status?: WorkflowExecutionStatus | null) {
  switch (status) {
    case "done":
      return "bg-[#dcfce7] text-[#16a34a]";
    case "running":
      return "bg-[#e0e7ff] text-[#4f46e5]";
    case "failed":
      return "bg-[#fee2e2] text-[#ef4444]";
    case "pending":
    default:
      return "bg-[#f3f4f6] text-[#6b7280]";
  }
}

export function getReviewStageLabel(status: ReviewStatusResponse | null, taskStatus?: ReviewTaskStatus | null) {
  if (status?.currentStageLabel?.trim()) {
    return status.currentStageLabel;
  }

  switch (taskStatus) {
    case "created":
      return "任务已创建，等待开始";
    case "uploading":
      return "文件上传中";
    case "queued":
      return "任务排队中";
    case "running":
      return "工作流执行中";
    case "succeeded":
      return "任务已完成";
    case "failed":
      return "任务执行失败";
    default:
      return "等待任务开始";
  }
}

export function getReviewProgressValue(status: ReviewStatusResponse | null, taskStatus?: ReviewTaskStatus | null) {
  if (typeof status?.progress === "number") {
    return Math.max(0, Math.min(100, status.progress));
  }

  if (taskStatus === "succeeded") {
    return 100;
  }

  return 0;
}

export function countIssuesByFilter(issues: IssueItem[], filter: IssueFilter) {
  if (filter === "all") {
    return issues.length;
  }
  return issues.filter((issue) => issue.level === filter).length;
}

export function filterIssues(issues: IssueItem[], filter: IssueFilter) {
  if (filter === "all") {
    return issues;
  }
  return issues.filter((issue) => issue.level === filter);
}

export function getIssueLocationTag(issue: IssueItem) {
  return issue.anchor?.trim() ? "可定位原文" : "待人工定位";
}

function normalizeText(value: string) {
  return value
    .replace(/\s+/g, "")
    .replace(/[，。；：、“”‘’（）【】《》\-]/g, "")
    .toLowerCase();
}

function findArticleTokens(value: string) {
  return value.match(/第[一二三四五六七八九十百千万0-9]+?条/g) ?? [];
}

export function resolveIssueTargetSectionId(issue: IssueItem, sections: ContractSection[]) {
  if (!sections.length) {
    return null;
  }

  const exact = sections.find((section) => section.id === issue.anchor);
  if (exact) {
    return exact.id;
  }

  const articleTokens = findArticleTokens(issue.position ?? "");
  const evidenceSnippet = normalizeText(issue.evidence ?? "").slice(0, 18);
  const originalSnippet = normalizeText(issue.original ?? "").slice(0, 18);
  const titleSnippet = normalizeText(issue.title).slice(0, 10);

  let bestSection = sections[0];
  let bestScore = -1;

  for (const section of sections) {
    const searchable = normalizeText(`${section.title} ${section.paragraphs.join(" ")}`);
    let score = 0;

    for (const token of articleTokens) {
      if (searchable.includes(normalizeText(token))) {
        score += 10;
      }
    }

    if (evidenceSnippet && searchable.includes(evidenceSnippet)) {
      score += 6;
    }

    if (originalSnippet && searchable.includes(originalSnippet)) {
      score += 6;
    }

    if (titleSnippet && searchable.includes(titleSnippet)) {
      score += 3;
    }

    if (score > bestScore) {
      bestScore = score;
      bestSection = section;
    }
  }

  return bestSection.id;
}

export function getReadableCurrentStage(status: ReviewStatusResponse | null) {
  return getReviewStageLabel(status, status?.status ?? null);
}
