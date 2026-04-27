"use client";

import { type ReactNode, useMemo } from "react";

import { InfoBanner } from "@/components/common/InfoBanner";
import { PageShell } from "@/components/common/PageShell";
import { FullReport } from "@/components/overview/FullReport";
import { OverviewHeader } from "@/components/overview/OverviewHeader";
import { RiskStats } from "@/components/overview/RiskStats";
import { WorkflowProgress } from "@/components/workflow/WorkflowProgress";
import { getErrorDisplayContent } from "@/lib/error-messages";
import { getOverviewSummary } from "@/lib/result-helpers";
import { getRiskLevelBadgeClass, getTaskStatusLabel } from "@/lib/review-helpers";
import { useReviewTask } from "@/lib/useReviewTask";
import { useReviewStore } from "@/stores/reviewStore";

interface OverviewPageProps {
  params: {
    taskId: string;
  };
}

const PANEL_TITLE = "结果总览";
const WAITING_TITLE = "正在审查中";
const WAITING_DESCRIPTION = "审查结果生成后将在此展示。";

function SummaryCard({ label, value, badgeClassName }: { label: string; value: ReactNode; badgeClassName?: string }) {
  return (
    <div className="subtle-card px-5 py-5 text-center">
      <div className="text-sm text-[#64748b]">{label}</div>
      <div className="mt-3 text-[20px] font-extrabold text-[#0f2345]">
        {badgeClassName ? <span className={`status-pill text-sm ${badgeClassName}`}>{value}</span> : value}
      </div>
    </div>
  );
}

export default function OverviewPage({ params }: OverviewPageProps) {
  const taskId = decodeURIComponent(params.taskId);
  const taskState = useReviewStore((state) => state.taskState);
  const { isLoading, reviewStatus, result, error } = useReviewTask(taskId, {
    shouldFetchResult: true,
    shouldPoll: true,
  });

  const isCompleted = result?.taskId === taskId;
  const errorDisplay = getErrorDisplayContent(error);
  const workflowGroups = reviewStatus?.workflowGroups ?? result?.workflow?.groups ?? null;
  const overview = useMemo(() => getOverviewSummary(result), [result]);

  return (
    <PageShell>
      <div className="space-y-6">
        <OverviewHeader />

        {reviewStatus?.errorMessage ? (
          <InfoBanner tone="error" title="任务执行失败" description={reviewStatus.errorMessage} />
        ) : null}

        {!isCompleted ? (
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(420px,0.9fr)]">
            <section className="glass-card p-7">
              <h2 className="text-[22px] font-extrabold text-[#0f2345]">{PANEL_TITLE}</h2>
              <div className="mt-5 rounded-[20px] border border-[#e5e7eb] bg-[#f8fafc] p-6">
                <div className="text-[24px] font-extrabold text-[#0f2345]">
                  {errorDisplay?.title ?? (isLoading ? WAITING_TITLE : WAITING_TITLE)}
                </div>
                <div className="mt-3 text-sm leading-8 text-[#64748b]">
                  {errorDisplay?.description ?? WAITING_DESCRIPTION}
                </div>
                <div className="mt-4 text-sm text-[#64748b]">
                  当前状态：{getTaskStatusLabel(reviewStatus?.status ?? taskState ?? null)}
                </div>
              </div>
            </section>

            <WorkflowProgress
              reviewStatus={reviewStatus}
              taskState={taskState}
              workflowGroups={workflowGroups}
              error={error}
              title="审查进度"
              heightClassName="min-h-[420px]"
            />
          </div>
        ) : (
          <div className="space-y-5">
            <section className="glass-card p-7">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <SummaryCard label="合同类型" value={overview.contractType ?? "—"} />
                <SummaryCard
                  label="总体风险等级"
                  value={overview.overallRiskLevel ?? "—"}
                  badgeClassName={overview.overallRiskLevel ? getRiskLevelBadgeClass(overview.overallRiskLevel) : undefined}
                />
                <SummaryCard
                  label="人工复核判断"
                  value={
                    overview.needManualReview === true
                      ? "需要人工复核"
                      : overview.needManualReview === false
                        ? "无需人工复核"
                        : "待确认"
                  }
                />
              </div>

              <div className="mt-5 rounded-[20px] border border-[#e5e7eb] bg-[#f8fafc] px-6 py-5">
                <div className="text-sm text-[#64748b]">总体结论</div>
                <div className="mt-3 text-[16px] leading-8 text-[#1f2937]">{overview.overallConclusion ?? "—"}</div>
              </div>
            </section>

            <RiskStats stats={overview.stats} needManualReview={overview.needManualReview} />

            <FullReport report={overview.finalReviewReport} />
          </div>
        )}
      </div>
    </PageShell>
  );
}
