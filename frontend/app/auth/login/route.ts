import { NextRequest, NextResponse } from "next/server";

import {
  AUTH_COOKIE_NAME,
  AUTH_COOKIE_VALUE,
  AUTH_MAX_AGE_SECONDS,
  AUTH_PASSWORD,
  AUTH_USERNAME,
} from "@/lib/auth";
import { getSessionCookieSecurity } from "@/lib/server-auth";

export async function POST(request: NextRequest) {
  let credentials: { username?: unknown; password?: unknown };

  try {
    credentials = await request.json();
  } catch {
    return NextResponse.json({ success: false, message: "Invalid request body." }, { status: 400 });
  }

  if (credentials.username !== AUTH_USERNAME || credentials.password !== AUTH_PASSWORD) {
    return NextResponse.json({ success: false, message: "Invalid credentials." }, { status: 401 });
  }

  const response = NextResponse.json({ success: true });
  response.cookies.set({
    name: AUTH_COOKIE_NAME,
    value: AUTH_COOKIE_VALUE,
    httpOnly: true,
    path: "/",
    maxAge: AUTH_MAX_AGE_SECONDS,
    ...getSessionCookieSecurity(request),
  });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
