"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import {
  ApiErrorPayload,
  IssueFilter,
  ReviewResultResponse,
  ReviewStatusResponse,
  ReviewTaskStatus,
} from "@/lib/types";

interface ReviewStoreState {
  taskId: string | null;
  taskState: ReviewTaskStatus | null;
  reviewStatus: ReviewStatusResponse | null;
  progress: number;
  result: ReviewResultResponse | null;
  currentFilter: IssueFilter;
  expandedIssueId: string | null;
  error: ApiErrorPayload | null;
  setTaskId: (taskId: string | null) => void;
  setTaskState: (taskState: ReviewTaskStatus | null) => void;
  setReviewStatus: (reviewStatus: ReviewStatusResponse | null) => void;
  setResult: (result: ReviewResultResponse | null) => void;
  setFilter: (filter: IssueFilter) => void;
  setExpandedIssueId: (issueId: string | null) => void;
  setError: (error: ApiErrorPayload | null) => void;
  resetTaskData: () => void;
}

export const useReviewStore = create<ReviewStoreState>()(
  persist(
    (set) => ({
      taskId: null,
      taskState: null,
      reviewStatus: null,
      progress: 0,
      result: null,
      currentFilter: "all",
      expandedIssueId: null,
      error: null,
      setTaskId: (taskId) => set({ taskId }),
      setTaskState: (taskState) => set({ taskState }),
      setReviewStatus: (reviewStatus) =>
        set({
          reviewStatus,
          taskState: reviewStatus?.status ?? null,
          progress: reviewStatus?.progress ?? 0,
        }),
      setResult: (result) => set({ result }),
      setFilter: (currentFilter) => set({ currentFilter }),
      setExpandedIssueId: (expandedIssueId) => set({ expandedIssueId }),
      setError: (error) => set({ error }),
      resetTaskData: () =>
        set({
          taskId: null,
          taskState: null,
          reviewStatus: null,
          progress: 0,
          result: null,
          currentFilter: "all",
          expandedIssueId: null,
          error: null,
        }),
    }),
    {
      name: "contract-review-workbench",
      partialize: (state) => ({
        taskId: state.taskId,
        currentFilter: state.currentFilter,
        expandedIssueId: state.expandedIssueId,
      }),
    },
  ),
);