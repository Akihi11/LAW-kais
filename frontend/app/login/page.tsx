import Image from "next/image";

import { LoginForm } from "@/components/auth/LoginForm";
import loginBackground from "@/images/1.png";
import { getSafeNextPath } from "@/lib/auth";

interface LoginPageProps {
  searchParams?: {
    next?: string | string[];
  };
}

export default function LoginPage({ searchParams }: LoginPageProps) {
  const nextCandidate = Array.isArray(searchParams?.next) ? searchParams?.next[0] : searchParams?.next;
  const nextPath = getSafeNextPath(nextCandidate);

  return (
    <main className="login-shell">
      <div className="login-background" aria-hidden="true">
        <Image
          src={loginBackground}
          alt=""
          fill
          priority
          className="login-background-image"
          sizes="100vw"
        />
        <div className="login-background-overlay" />
      </div>

      <div className="login-content">
        <LoginForm nextPath={nextPath} />
      </div>
    </main>
  );
}
