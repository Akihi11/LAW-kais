import {
  ApiErrorPayload,
  CreateReviewResponse,
  ReviewResultResponse,
  ReviewRole,
  ReviewStatusResponse,
} from "@/lib/types";

const API_BASE_PATH = process.env.NEXT_PUBLIC_API_BASE_PATH ?? "/api";

export class ApiError extends Error {
  code: string;
  status: number;
  detail: unknown | null;

  constructor(payload: ApiErrorPayload, status: number) {
    super(payload.message);
    this.name = "ApiError";
    this.code = payload.code;
    this.status = status;
    this.detail = payload.detail;
  }
}

function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return typeof candidate.code === "string" && typeof candidate.message === "string";
}

function joinApiPath(path: string) {
  const normalizedBase = API_BASE_PATH.endsWith("/") ? API_BASE_PATH.slice(0, -1) : API_BASE_PATH;
  return `${normalizedBase}${path}`;
}

async function parseJson(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  return response.json();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(joinApiPath(path), {
      cache: "no-store",
      ...init,
    });
  } catch {
    throw new ApiError(
      {
        code: "internal_error",
        message: "请求未能发送到后端，请检查网络或确认服务是否已经启动。",
        detail: null,
      },
      500,
    );
  }

  const payload = await parseJson(response);

  if (!response.ok) {
    const errorPayload = isApiErrorPayload(payload)
      ? payload
      : {
          code: "internal_error",
          message: `请求失败（HTTP ${response.status}）。`,
          detail: payload,
        };
    throw new ApiError(errorPayload, response.status);
  }

  return payload as T;
}

export function toApiErrorPayload(error: unknown): ApiErrorPayload {
  if (error instanceof ApiError) {
    return {
      code: error.code,
      message: error.message,
      detail: error.detail,
    };
  }

  return {
    code: "internal_error",
    message: "发生未知错误，请稍后重试。",
    detail: null,
  };
}

export async function createReview(file: File, reviewRole: ReviewRole) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("review_role", reviewRole);

  return request<CreateReviewResponse>("/contract-review/tasks", {
    method: "POST",
    body: formData,
  });
}

export async function getReviewStatus(taskId: string) {
  return request<ReviewStatusResponse>(`/contract-review/tasks/${taskId}`, {
    method: "GET",
  });
}

export async function getReviewResult(taskId: string) {
  return request<ReviewResultResponse>(`/contract-review/tasks/${taskId}/result`, {
    method: "GET",
  });
}
