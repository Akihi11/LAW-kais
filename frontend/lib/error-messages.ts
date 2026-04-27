import { MAX_FILE_SIZE_MB, MAX_STATUS_POLL_ATTEMPTS, STATUS_POLL_INTERVAL_MS } from "@/lib/constants";
import { ApiErrorPayload } from "@/lib/types";

export interface ErrorDisplayContent {
  tone: "info" | "warning" | "error";
  title: string;
  description: string;
}

const pollWindowSeconds = Math.round((MAX_STATUS_POLL_ATTEMPTS * STATUS_POLL_INTERVAL_MS) / 1000);

export function getErrorDisplayContent(error: ApiErrorPayload | null | undefined): ErrorDisplayContent | null {
  if (!error) {
    return null;
  }

  switch (error.code) {
    case "task_not_found":
      return {
        tone: "error",
        title: "任务不存在",
        description: "该任务可能已失效、尚未创建，或后端服务已重启。",
      };
    case "result_not_ready":
      return {
        tone: "warning",
        title: "结果尚未生成",
        description: "当前任务仍在处理，审查结果生成后即可查看。",
      };
    case "invalid_file_type":
      return {
        tone: "error",
        title: "文件类型不支持",
        description: "仅支持上传 .docx 或 .pdf 合同文件。",
      };
    case "file_too_large":
      return {
        tone: "error",
        title: "文件过大",
        description: `单个文件不能超过 ${MAX_FILE_SIZE_MB}MB。`,
      };
    case "invalid_review_role":
      return {
        tone: "error",
        title: "审查视角无效",
        description: "请重新选择甲方或乙方后再提交。",
      };
    case "provider_not_configured":
      return {
        tone: "error",
        title: "正式工作流未配置完成",
        description: "请检查后端腾讯元器相关配置是否已正确设置。",
      };
    case "provider_auth_failed":
      return {
        tone: "error",
        title: "上游鉴权失败",
        description: "请检查腾讯云工作流的鉴权配置。",
      };
    case "provider_request_failed":
      return {
        tone: "error",
        title: "上游请求失败",
        description:
          typeof error.message === "string" && error.message.trim()
            ? error.message
            : "工作流请求未成功完成，请稍后重试或查看后端日志。",
      };
    case "provider_response_invalid":
      return {
        tone: "error",
        title: "上游响应不可解析",
        description: "上游已返回内容，但当前结果暂时无法被正确解析。",
      };
    case "task_failed":
      return {
        tone: "error",
        title: "任务执行失败",
        description: "后台审查任务已结束，但执行过程中发生错误。",
      };
    case "provider_not_implemented":
      return {
        tone: "warning",
        title: "Provider 尚未实现",
        description: "当前 Provider 仍未完成实现，请优先使用正式工作流或 Mock 模式。",
      };
    case "internal_error":
      return {
        tone: "error",
        title: "系统错误",
        description:
          typeof error.message === "string" && error.message.trim().length > 0
            ? error.message
            : "系统出现异常，请稍后重试。",
      };
    case "polling_limit_reached":
      return {
        tone: "warning",
        title: "轮询已停止",
        description: `已等待约 ${pollWindowSeconds} 秒，任务仍未结束，请稍后重新进入页面查看。`,
      };
    default:
      return {
        tone: "error",
        title: "请求失败",
        description:
          typeof error.message === "string" && error.message.trim().length > 0
            ? error.message
            : "发生未知错误，请稍后重试。",
      };
  }
}
