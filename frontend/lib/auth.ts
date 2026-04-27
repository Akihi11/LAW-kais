export const AUTH_COOKIE_NAME = "law-admin-session";
export const AUTH_COOKIE_VALUE = "authenticated";
export const AUTH_STORAGE_KEY = "law-admin-user";
export const AUTH_USERNAME = "admin";
export const AUTH_PASSWORD = "admin";
const AUTH_MAX_AGE_SECONDS = 60 * 60 * 24 * 7;

export function getSafeNextPath(candidate: string | null | undefined) {
  if (!candidate || !candidate.startsWith("/") || candidate.startsWith("//")) {
    return "/review/new";
  }

  if (candidate.startsWith("/login")) {
    return "/review/new";
  }

  return candidate;
}

export function setAuthSession(username = AUTH_USERNAME) {
  if (typeof document === "undefined") {
    return;
  }

  document.cookie = `${AUTH_COOKIE_NAME}=${AUTH_COOKIE_VALUE}; path=/; max-age=${AUTH_MAX_AGE_SECONDS}; SameSite=Lax`;
  window.localStorage.setItem(AUTH_STORAGE_KEY, username);
}

export function clearAuthSession() {
  if (typeof document === "undefined") {
    return;
  }

  document.cookie = `${AUTH_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax`;
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

export function hasAuthSessionInBrowser() {
  if (typeof document === "undefined") {
    return false;
  }

  return document.cookie
    .split(";")
    .map((item) => item.trim())
    .some((item) => item === `${AUTH_COOKIE_NAME}=${AUTH_COOKIE_VALUE}`);
}
