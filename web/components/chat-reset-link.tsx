"use client";

import { useRouter } from "next/navigation";

export function ChatResetLink({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const router = useRouter();

  function handleClick(e: React.MouseEvent<HTMLAnchorElement>) {
    e.preventDefault();
    router.push("/chat?t=" + Date.now());
  }

  return (
    <a href="/chat" onClick={handleClick} className={className}>
      {children}
    </a>
  );
}
