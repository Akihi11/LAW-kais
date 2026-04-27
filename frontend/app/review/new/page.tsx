"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { InfoBanner } from "@/components/common/InfoBanner";
import { PageShell } from "@/components/common/PageShell";
import { PerspectiveSelector } from "@/components/upload/PerspectiveSelector";
import { StartReviewButton } from "@/components/upload/StartReviewButton";
import { UploadPanel } from "@/components/upload/UploadPanel";
import { WorkflowProgress } from "@/components/workflow/WorkflowProgress";
import { createReview, toApiErrorPayload } from "@/lib/api";
import { MAX_FILE_SIZE_MB } from "@/lib/constants";
import { getErrorDisplayContent } from "@/lib/error-messages";
import { exceedsFileSizeLimit, isSupportedFile } from "@/lib/review-helpers";
import { useReviewTask } from "@/lib/useReviewTask";
import { ApiErrorPayload, ReviewRole } from "@/lib/types";
import { useReviewStore } from "@/stores/reviewStore";

const PAGE_TITLE = "上传合同文件";
const VIEW_OVERVIEW = "查看结果总览";
const INVALID_FILE_MESSAGE = "仅支持上传 .docx 或 .pdf 文件。";
const EMPTY_FILE_MESSAGE = "请先选择一个 .docx 或 .pdf 合同文件。";
const RESULT_PENDING_MESSAGE = "结果尚未生成，完成后即可查看。";

function isFileValidationError(code: string | undefined) {
  return code === "invalid_file_type" || code === "file_too_large";
}

export default function NewReviewPage() {
  const router = useRouter();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [reviewRole, setReviewRole] = useState<ReviewRole>("乙方");
  const [localError, setLocalError] = useState<ApiErrorPayload | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const taskId = useReviewStore((state) => state.taskId);
  const taskState = useReviewStore((state) => state.taskState);
  const setTaskId = useReviewStore((state) => state.setTaskId);
  const setTaskState = useReviewStore((state) => state.setTaskState);
  const setError = useReviewStore((state) => state.setError);
  const resetTaskData = useReviewStore((state) => state.resetTaskData);

  const { reviewStatus, result, error: taskError } = useReviewTask(taskId ?? "", {
    shouldFetchResult: Boolean(taskId),
    shouldPoll: Boolean(taskId),
  });

  const latestTaskState = reviewStatus?.status ?? taskState;
  const latestWorkflowGroups = reviewStatus?.workflowGroups ?? (result?.taskId === taskId ? result.workflow?.groups : undefined);
  const localErrorDisplay = useMemo(() => getErrorDisplayContent(localError), [localError]);
  const taskErrorDisplay = useMemo(() => getErrorDisplayContent(taskError), [taskError]);
  const canViewOverview = Boolean(taskId && result?.taskId === taskId);

  const handleFileSelect = (file: File | null) => {
    if (!file) {
      setSelectedFile(null);
      setLocalError(null);
      return;
    }

    if (!isSupportedFile(file)) {
      setSelectedFile(null);
      setLocalError({
        code: "invalid_file_type",
        message: INVALID_FILE_MESSAGE,
        detail: null,
      });
      return;
    }

    if (exceedsFileSizeLimit(file)) {
      setSelectedFile(null);
      setLocalError({
        code: "file_too_large",
        message: `文件大小不能超过 ${MAX_FILE_SIZE_MB}MB。`,
        detail: null,
      });
      return;
    }

    setSelectedFile(file);
    setLocalError(null);
  };

  const handleStartReview = async () => {
    if (!selectedFile) {
      setLocalError({
        code: "invalid_file_type",
        message: EMPTY_FILE_MESSAGE,
        detail: null,
      });
      return;
    }

    setIsSubmitting(true);
    setLocalError(null);
    resetTaskData();

    try {
      const response = await createReview(selectedFile, reviewRole);
      setTaskId(response.taskId);
      setTaskState(response.status);
      setError(null);
    } catch (error) {
      const payload = toApiErrorPayload(error);
      setLocalError(payload);
      setError(payload);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleViewOverview = () => {
    if (!canViewOverview || !taskId) {
      return;
    }
    router.push(`/review/${taskId}/overview`);
  };

  const fileValidationMessage = isFileValidationError(localError?.code)
    ? localErrorDisplay?.description ?? localError?.message ?? null
    : null;
  const nonValidationError = localError && !isFileValidationError(localError.code) ? localErrorDisplay : null;

  return (
    <PageShell>
      <div className="space-y-6">
        <div className="section-heading">
          <div>
            <h1 className="section-title">{PAGE_TITLE}</h1>
          </div>
        </div>

        <div className="grid items-stretch gap-6 xl:grid-cols-[minmax(760px,1.35fr)_minmax(420px,0.85fr)]">
          <section className="glass-card flex min-h-[560px] flex-col p-7 xl:h-[calc(100vh-142px)]">
            <div className="min-h-0 flex-1">
              <UploadPanel
                selectedFile={selectedFile}
                onFileSelect={handleFileSelect}
                errorMessage={fileValidationMessage}
              />
            </div>

            <div className="sticky bottom-0 mt-5 rounded-[20px] border border-[#e5e7eb] bg-white px-5 py-5 shadow-[0_-8px_20px_rgba(15,23,42,0.04)]">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <PerspectiveSelector value={reviewRole} onChange={setReviewRole} />

                <div className="flex flex-wrap items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={handleViewOverview}
                    disabled={!canViewOverview}
                    className="secondary-action px-5 py-3 disabled:cursor-not-allowed disabled:border-[#e2e8f0] disabled:bg-[#f8fafc] disabled:text-[#94a3b8]"
                    title={!canViewOverview ? RESULT_PENDING_MESSAGE : undefined}
                  >
                    {VIEW_OVERVIEW}
                  </button>
                  <StartReviewButton
                    disabled={!selectedFile}
                    loading={isSubmitting}
                    onClick={handleStartReview}
                  />
                </div>
              </div>
            </div>

            {nonValidationError ? (
              <div className="mt-5">
                <InfoBanner
                  tone={nonValidationError.tone}
                  title={nonValidationError.title}
                  description={nonValidationError.description}
                />
              </div>
            ) : null}

            {!nonValidationError && taskErrorDisplay && !isFileValidationError(taskError?.code) ? (
              <div className="mt-5">
                <InfoBanner
                  tone={taskErrorDisplay.tone}
                  title={taskErrorDisplay.title}
                  description={taskErrorDisplay.description}
                />
              </div>
            ) : null}
          </section>

          <WorkflowProgress
            reviewStatus={reviewStatus}
            taskState={latestTaskState}
            workflowGroups={latestWorkflowGroups}
            error={isFileValidationError(localError?.code) ? null : taskError}
            title="审查进度"
            heightClassName="min-h-[560px] xl:h-[calc(100vh-142px)]"
          />
        </div>
      </div>
    </PageShell>
  );
}
