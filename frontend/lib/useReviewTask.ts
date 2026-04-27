"use client";

import { useEffect, useMemo, useState } from "react";

import { ApiError, getReviewResult, getReviewStatus, toApiErrorPayload } from "@/lib/api";
import { MAX_STATUS_POLL_ATTEMPTS, STATUS_POLL_INTERVAL_MS } from "@/lib/constants";
import { useReviewStore } from "@/stores/reviewStore";

interface UseReviewTaskOptions {
  shouldFetchResult?: boolean;
  shouldPoll?: boolean;
}

const POLLING_LIMIT_MESSAGE =
  "\u8f6e\u8be2\u5df2\u8fbe\u5230\u5b89\u5168\u4e0a\u9650\uff0c\u8bf7\u5237\u65b0\u9875\u9762\u540e\u91cd\u8bd5\u3002";

export function useReviewTask(taskId: string, options: UseReviewTaskOptions = {}) {
  const { shouldFetchResult = true, shouldPoll = true } = options;
  const reviewStatus = useReviewStore((state) => state.reviewStatus);
  const result = useReviewStore((state) => state.result);
  const error = useReviewStore((state) => state.error);
  const setTaskId = useReviewStore((state) => state.setTaskId);
  const setTaskState = useReviewStore((state) => state.setTaskState);
  const setReviewStatus = useReviewStore((state) => state.setReviewStatus);
  const setResult = useReviewStore((state) => state.setResult);
  const setError = useReviewStore((state) => state.setError);
  const [isLoading, setIsLoading] = useState(true);

  const taskReviewStatus = useMemo(
    () => (reviewStatus?.taskId === taskId ? reviewStatus : null),
    [reviewStatus, taskId],
  );
  const taskResult = useMemo(
    () => (result?.taskId === taskId ? result : null),
    [result, taskId],
  );

  useEffect(() => {
    if (!taskId) {
      return;
    }

    let active = true;
    let timerId: number | undefined;
    let isSyncing = false;
    let pollAttempts = 0;
    let resultRequested = false;

    const stopPolling = () => {
      if (timerId) {
        window.clearInterval(timerId);
        timerId = undefined;
      }
    };

    const hasResultForTask = () => useReviewStore.getState().result?.taskId === taskId;

    const sync = async () => {
      if (!active || isSyncing) {
        return;
      }

      if (shouldPoll && pollAttempts >= MAX_STATUS_POLL_ATTEMPTS) {
        stopPolling();
        setError({
          code: "polling_limit_reached",
          message: POLLING_LIMIT_MESSAGE,
          detail: {
            maxAttempts: MAX_STATUS_POLL_ATTEMPTS,
            intervalMs: STATUS_POLL_INTERVAL_MS,
          },
        });
        setIsLoading(false);
        return;
      }

      isSyncing = true;
      pollAttempts += 1;

      try {
        const nextStatus = await getReviewStatus(taskId);
        if (!active) {
          return;
        }

        setTaskId(taskId);
        setReviewStatus(nextStatus);
        setTaskState(nextStatus.status);

        if (nextStatus.status !== "succeeded") {
          setResult(null);
        }

        if (nextStatus.status === "failed") {
          stopPolling();
          setError(null);
          return;
        }

        if (shouldFetchResult && nextStatus.status === "succeeded") {
          if (hasResultForTask()) {
            setError(null);
            stopPolling();
            return;
          }

          if (resultRequested) {
            return;
          }

          resultRequested = true;
          try {
            const nextResult = await getReviewResult(taskId);
            if (!active) {
              return;
            }
            setResult(nextResult);
            setError(null);
            stopPolling();
          } catch (error) {
            if (!active) {
              return;
            }

            const payload = toApiErrorPayload(error);
            if (error instanceof ApiError && error.code === "result_not_ready") {
              setError(payload);
              return;
            }
            setError(payload);
          } finally {
            resultRequested = false;
          }

          return;
        }

        setError(null);
      } catch (error) {
        if (!active) {
          return;
        }
        setError(toApiErrorPayload(error));
      } finally {
        isSyncing = false;
        if (active) {
          setIsLoading(false);
        }
      }
    };

    setTaskId(taskId);
    setTaskState(null);
    setReviewStatus(null);
    setResult(null);
    setError(null);
    setIsLoading(true);

    void sync();

    if (shouldPoll) {
      timerId = window.setInterval(() => {
        void sync();
      }, STATUS_POLL_INTERVAL_MS);
    }

    return () => {
      active = false;
      stopPolling();
    };
  }, [
    setError,
    setResult,
    setReviewStatus,
    setTaskId,
    setTaskState,
    shouldFetchResult,
    shouldPoll,
    taskId,
  ]);

  return {
    isLoading,
    reviewStatus: taskReviewStatus,
    result: taskResult,
    error,
  };
}
