"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";

import { getErrorDisplayContent } from "@/lib/error-messages";
import {
  getReadableCurrentStage,
  getTaskStatusLabel,
  getWorkflowStatusBadgeClass,
  getWorkflowStatusLabel,
} from "@/lib/review-helpers";
import {
  ApiErrorPayload,
  ReviewStatusResponse,
  ReviewTaskStatus,
  TaskNode,
  WorkflowExecutionStatus,
  WorkflowGroup,
  WorkflowNode,
} from "@/lib/types";

interface WorkflowProgressProps {
  reviewStatus: ReviewStatusResponse | null;
  taskState?: ReviewTaskStatus | null;
  workflowGroups?: WorkflowGroup[] | null;
  error?: ApiErrorPayload | null;
  title?: string;
  heightClassName?: string;
}

interface DisplayNode {
  id: string;
  name: string;
  status: WorkflowExecutionStatus;
  displayOrder: number | null;
  originalIndex: number;
}

interface NodeIconDefinition {
  keywords: string[];
  label: string;
  src: string;
}

const DEFAULT_TITLE = "审查进度";
const FALLBACK_NODE_NAME = "未命名节点";
const NODE_ICON_MAP: NodeIconDefinition[] = [
  { keywords: ["开始", "start"], label: "开始", src: "/icon/开始.svg" },
  { keywords: ["结束", "end"], label: "结束", src: "/icon/结束.svg" },
  { keywords: ["循环", "loop", "foreach", "for"], label: "循环", src: "/icon/循环.svg" },
  { keywords: ["条件判断", "condition", "if", "branch"], label: "条件判断", src: "/icon/条件判断.svg" },
  { keywords: ["大模型", "llm", "model"], label: "大模型", src: "/icon/大模型.svg" },
  { keywords: ["变量赋值", "变量", "assign", "setvariable"], label: "变量赋值", src: "/icon/变量赋值.svg" },
  { keywords: ["知识检索", "检索", "retrieve", "retrieval", "search"], label: "知识检索", src: "/icon/知识检索.svg" },
  { keywords: ["代码", "code", "script"], label: "代码", src: "/icon/代码.svg" },
];

function parseDateMs(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  if (/^\d+$/.test(trimmed)) {
    const numeric = Number(trimmed);
    if (!Number.isFinite(numeric) || numeric <= 0) {
      return null;
    }

    return numeric > 10_000_000_000 ? numeric : numeric * 1000;
  }

  const parsed = Date.parse(trimmed);
  return Number.isNaN(parsed) ? null : parsed;
}

function resolveWorkflowRunRaw(status: ReviewStatusResponse | null) {
  const raw = status?.raw;
  if (!raw || typeof raw !== "object") {
    return null;
  }

  const workflowRun = (raw as Record<string, unknown>).workflowRun;
  if (!workflowRun || typeof workflowRun !== "object") {
    return null;
  }

  return workflowRun as Record<string, unknown>;
}

function toWorkflowStatus(status: WorkflowExecutionStatus | TaskNode["status"] | null | undefined) {
  if (status === "done" || status === "running" || status === "failed") {
    return status;
  }

  if (status === "success") {
    return "done";
  }

  return "pending";
}

function isVisibleWorkflowStatus(status: WorkflowExecutionStatus | TaskNode["status"] | null | undefined) {
  const workflowStatus = toWorkflowStatus(status);
  return workflowStatus === "done" || workflowStatus === "running" || workflowStatus === "failed";
}

function isEndDisplayNode(name: string) {
  const normalized = name.trim().toLowerCase();
  return normalized === "结束" || normalized === "end";
}

function normalizeNodeName(name: string) {
  return name.replace(/\s+/g, "").toLowerCase();
}

function getNodeIcon(name: string) {
  const normalized = normalizeNodeName(name);
  return NODE_ICON_MAP.find((item) => item.keywords.some((keyword) => normalized.includes(keyword)));
}

function sortDisplayNodes(nodes: DisplayNode[]) {
  return [...nodes].sort((left, right) => {
    const leftIsEnd = isEndDisplayNode(left.name);
    const rightIsEnd = isEndDisplayNode(right.name);
    if (leftIsEnd !== rightIsEnd) {
      return leftIsEnd ? 1 : -1;
    }

    const leftHasOrder = typeof left.displayOrder === "number";
    const rightHasOrder = typeof right.displayOrder === "number";

    if (leftHasOrder && rightHasOrder && left.displayOrder !== right.displayOrder) {
      return (left.displayOrder ?? 0) - (right.displayOrder ?? 0);
    }

    if (leftHasOrder !== rightHasOrder) {
      return leftHasOrder ? -1 : 1;
    }

    return left.originalIndex - right.originalIndex;
  });
}

function getDisplayNodes(workflowGroups?: WorkflowGroup[] | null, taskNodes?: TaskNode[] | null) {
  const flattenedWorkflowNodes = (Array.isArray(workflowGroups) ? workflowGroups : [])
    .flatMap((group) => (Array.isArray(group.nodes) ? group.nodes : []))
    .filter((node): node is WorkflowNode => Boolean(node?.name))
    .filter((node) => isVisibleWorkflowStatus(node.status))
    .map<DisplayNode>((node, index) => ({
      id: `workflow-${index}-${node.name}`,
      name: node.name.trim() || FALLBACK_NODE_NAME,
      status: toWorkflowStatus(node.status),
      displayOrder: typeof node.display_order === "number" ? node.display_order : null,
      originalIndex: index,
    }));

  if (flattenedWorkflowNodes.length) {
    return sortDisplayNodes(flattenedWorkflowNodes);
  }

  const fallbackTaskNodes = (Array.isArray(taskNodes) ? taskNodes : [])
    .filter((node): node is TaskNode => Boolean(node?.nodeId && node?.nodeName))
    .filter((node) => isVisibleWorkflowStatus(node.status))
    .map<DisplayNode>((node, index) => ({
      id: node.nodeId,
      name: node.nodeName.trim() || FALLBACK_NODE_NAME,
      status: toWorkflowStatus(node.status),
      displayOrder: typeof node.display_order === "number" ? node.display_order : null,
      originalIndex: index,
    }));

  return sortDisplayNodes(fallbackTaskNodes);
}

function formatElapsedTime(totalMs: number) {
  const totalSeconds = Math.max(0, Math.floor(totalMs / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function getTimerBounds(reviewStatus: ReviewStatusResponse | null, taskState?: ReviewTaskStatus | null) {
  const workflowRun = resolveWorkflowRunRaw(reviewStatus);
  const startedAtMs =
    parseDateMs(reviewStatus?.createdAt) ??
    parseDateMs(typeof workflowRun?.CreateTime === "string" ? workflowRun.CreateTime : null) ??
    parseDateMs(typeof workflowRun?.StartTime === "string" ? workflowRun.StartTime : null);

  const completedAtMs =
    parseDateMs(reviewStatus?.completedAt) ??
    parseDateMs(typeof workflowRun?.EndTime === "string" ? workflowRun.EndTime : null) ??
    ((taskState === "succeeded" || taskState === "failed") ? parseDateMs(reviewStatus?.updatedAt) : null);

  return { startedAtMs, completedAtMs };
}

export function WorkflowProgress({
  reviewStatus,
  taskState,
  workflowGroups,
  error,
  title = DEFAULT_TITLE,
  heightClassName = "min-h-[480px]",
}: WorkflowProgressProps) {
  const errorDisplay = getErrorDisplayContent(error);
  const visibleNodes = useMemo(
    () => getDisplayNodes(workflowGroups, reviewStatus?.nodes),
    [reviewStatus?.nodes, workflowGroups],
  );
  const hasTaskStarted = Boolean(reviewStatus || taskState || errorDisplay);
  const statusLabel = getTaskStatusLabel(reviewStatus?.status ?? taskState ?? null);
  const currentStageLabel = getReadableCurrentStage(reviewStatus);
  const { startedAtMs, completedAtMs } = useMemo(
    () => getTimerBounds(reviewStatus, reviewStatus?.status ?? taskState ?? null),
    [reviewStatus, taskState],
  );
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    setNowMs(Date.now());
    if (!startedAtMs || completedAtMs) {
      return;
    }

    const timer = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, [completedAtMs, startedAtMs]);

  const elapsedMs = startedAtMs ? Math.max(0, (completedAtMs ?? nowMs) - startedAtMs) : null;

  return (
    <aside className={`glass-card flex flex-col overflow-hidden p-6 ${heightClassName}`}>
      <div>
        <h2 className="text-[24px] font-extrabold text-[#0f2345]">{title}</h2>
      </div>

      {errorDisplay ? (
        <div className="info-banner info-banner-error mt-5">
          <p className="font-semibold">{errorDisplay.title}</p>
          <p className="mt-1">{errorDisplay.description}</p>
        </div>
      ) : null}

      {hasTaskStarted ? (
        <div className="mt-5 rounded-[20px] border border-[#e5e7eb] bg-[#f8fafc] p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-[#6f7c8d]">当前阶段</p>
              <p className="mt-2 text-[22px] font-semibold text-[#0f2345]">{currentStageLabel}</p>
            </div>
            <span className="status-pill bg-[#eef2ff] text-[#4f46e5]">{statusLabel}</span>
          </div>

          <div className="mt-4 flex items-center justify-between gap-4 rounded-[16px] border border-[#e5e7eb] bg-white px-4 py-3">
            <div className="text-sm text-[#64748b]">已运行</div>
            <div className="text-[18px] font-extrabold text-[#0f2345]">
              {elapsedMs !== null ? formatElapsedTime(elapsedMs) : "--:--"}
            </div>
          </div>
        </div>
      ) : (
        <div className="empty-state-card mt-5">尚未启动审查任务。</div>
      )}

      <div className="mt-5 min-h-0 flex-1 overflow-y-auto pr-1">
        {visibleNodes.length ? (
          <div className="space-y-2">
            {visibleNodes.map((node, index) => {
              const isActive = node.status === "running";
              const nodeIcon = getNodeIcon(node.name);

              return (
                <div
                  key={node.id}
                  className={`flex items-center gap-3 rounded-[14px] border px-3 py-3 ${
                    isActive ? "border-[#c7d2fe] bg-[#eef2ff]" : "border-[#eef2f7] bg-white"
                  }`}
                >
                  <span className="w-7 text-right text-sm font-bold text-[#737373]">{index + 1}.</span>

                  {nodeIcon ? (
                    <Image
                      src={nodeIcon.src}
                      alt={nodeIcon.label}
                      width={24}
                      height={24}
                      className="h-6 w-6 flex-none rounded-[6px] bg-white object-cover shadow-sm"
                    />
                  ) : (
                    <span className="inline-flex h-6 w-6 flex-none items-center justify-center rounded-[6px] bg-[#e2e8f0] text-xs font-bold text-[#475569]">
                      ·
                    </span>
                  )}

                  <span className="min-w-0 flex-1 truncate text-[15px] text-[#334155]">{node.name}</span>
                  <span className={`status-pill ${getWorkflowStatusBadgeClass(node.status)}`}>
                    {getWorkflowStatusLabel(node.status)}
                  </span>
                </div>
              );
            })}
          </div>
        ) : hasTaskStarted ? (
          <div className="empty-state-card">工作流已启动，等待已执行节点回传。</div>
        ) : null}
      </div>
    </aside>
  );
}
