"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  AUTH_PASSWORD,
  AUTH_USERNAME,
  hasAuthSessionInBrowser,
  setAuthSession,
} from "@/lib/auth";

const PAGE_TITLE = "\u5408\u540c\u5ba1\u67e5\u5de5\u4f5c\u53f0";
const USERNAME_LABEL = "\u767b\u5f55\u540d";
const PASSWORD_LABEL = "\u5bc6\u7801";
const SUBMIT_LABEL = "\u767b\u5f55";
const REGISTER_LABEL = "\u6ce8\u518c";
const ALT_LOGIN_LABEL = "\u6216\u9009\u62e9\u5176\u4ed6\u767b\u5f55\u65b9\u5f0f";
const YUANBAO_LOGIN_LABEL = "\u817e\u8baf\u5143\u5b9d\u767b\u5f55";
const DELI_LOGIN_LABEL = "\u5c0f\u7406AI\u767b\u5f55";
const INVALID_CREDENTIALS =
  "\u767b\u5f55\u540d\u6216\u5bc6\u7801\u9519\u8bef\uff0c\u8bf7\u8f93\u5165 admin / admin\u3002";

interface LoginFormProps {
  nextPath: string;
}

export function LoginForm({ nextPath }: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!hasAuthSessionInBrowser()) {
      return;
    }

    window.location.replace(nextPath);
  }, [nextPath]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const submittedUsername = String(formData.get("username") ?? "").trim();
    const submittedPassword = String(formData.get("password") ?? "");

    if (submittedUsername !== AUTH_USERNAME || submittedPassword !== AUTH_PASSWORD) {
      setErrorMessage(INVALID_CREDENTIALS);
      return;
    }

    setAuthSession(submittedUsername);
    setErrorMessage(null);
    window.location.assign(nextPath);
  };

  return (
    <section className="login-card">
      <h1 className="login-title">{PAGE_TITLE}</h1>

      <form className="login-form" onSubmit={handleSubmit}>
        <label className="login-field">
          <span className="login-label">{USERNAME_LABEL}</span>
          <input
            type="text"
            name="username"
            value={username}
            onChange={(event) => {
              setUsername(event.target.value);
              if (errorMessage) {
                setErrorMessage(null);
              }
            }}
            className="login-input"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="admin"
          />
        </label>

        <label className="login-field">
          <span className="login-label">{PASSWORD_LABEL}</span>
          <input
            type="password"
            name="password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              if (errorMessage) {
                setErrorMessage(null);
              }
            }}
            className="login-input"
            autoComplete="current-password"
            placeholder="admin"
          />
        </label>

        {errorMessage ? <div className="info-banner info-banner-error">{errorMessage}</div> : null}

        <div className="login-action-grid">
          <button type="submit" className="primary-action login-submit">
            {SUBMIT_LABEL}
          </button>

          <button type="button" className="login-register-button">
            {REGISTER_LABEL}
          </button>
        </div>

        <div className="login-divider" aria-hidden="true">
          <span>{ALT_LOGIN_LABEL}</span>
        </div>

        <div className="login-provider-list">
          <button type="button" className="login-provider-button login-provider-button-yuanbao">
            {YUANBAO_LOGIN_LABEL}
          </button>
          <button type="button" className="login-provider-button login-provider-button-deli">
            {DELI_LOGIN_LABEL}
          </button>
        </div>
      </form>
    </section>
  );
}
