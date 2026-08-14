import presetReportData from "@/data/preset-report.json";
import { isPresetReportTask } from "@/lib/routes";
import type { ReviewResultResponse } from "@/lib/types";

const PRESET_REPORT = presetReportData as ReviewResultResponse;

export function getPresetReport(taskId: string): ReviewResultResponse | null {
  if (!isPresetReportTask(taskId)) {
    return null;
  }

  return PRESET_REPORT;
}
