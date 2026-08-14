import { NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIE_NAME } from "@/lib/auth";
import { getSessionCookieSecurity } from "@/lib/server-auth";

export async function POST(request: NextRequest) {
  const response = NextResponse.json({ success: true });
  response.cookies.set({
    name: AUTH_COOKIE_NAME,
    value: "",
    httpOnly: true,
    path: "/",
    maxAge: 0,
    expires: new Date(0),
    ...getSessionCookieSecurity(request),
  });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
