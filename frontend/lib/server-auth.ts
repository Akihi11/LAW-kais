import type { NextRequest } from "next/server";

export function getSessionCookieSecurity(request: NextRequest) {
  const forwardedProtocol = request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim();
  const isSecure = forwardedProtocol === "https" || request.nextUrl.protocol === "https:";

  if (isSecure) {
    return {
      secure: true,
      sameSite: "none" as const,
      partitioned: true,
    };
  }

  return {
    secure: false,
    sameSite: "lax" as const,
    partitioned: false,
  };
}
