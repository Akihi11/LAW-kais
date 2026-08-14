export const PRESET_REPORT_TASK_ID = "preset-report";
export const PRESET_REPORT_OVERVIEW_PATH = `/review/${PRESET_REPORT_TASK_ID}/overview`;

export function isPresetReportTask(taskId: string | null | undefined) {
  return taskId === PRESET_REPORT_TASK_ID;
}
