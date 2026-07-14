"use client";

import { useAuth } from "@/lib/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Loader2 } from "lucide-react";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "var(--background, #0b0f19)",
        color: "var(--foreground, #ffffff)"
      }}>
        <Loader2 size={36} className="animate-spin" style={{ color: "var(--accent-strong, #3b82f6)", marginBottom: 16 }} />
        <span style={{ fontSize: 13, color: "var(--muted, #6b7280)", fontWeight: 500, letterSpacing: "0.05em" }}>LOADING CONSOLE...</span>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return <>{children}</>;
}
