"use client";

import { useAuth } from "@/lib/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect, useState, FormEvent } from "react";
import { Route, Lock, User, Loader2 } from "lucide-react";

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.push("/");
    }
  }, [user, loading, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await login({ username, password });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid username or password.");
      setSubmitting(false);
    }
  }

  if (loading || user) {
    return (
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "var(--background)",
        color: "var(--ink)"
      }}>
        <Loader2 size={36} className="animate-spin" style={{ color: "var(--accent-strong, #3b406e)" }} />
      </div>
    );
  }

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      minHeight: "100vh",
      background: "radial-gradient(circle at center, #1b2030 0%, var(--background) 70%)",
      padding: "20px"
    }}>
      <div style={{
        width: "100%",
        maxWidth: "420px",
        background: "var(--panel)",
        border: "1px solid var(--line)",
        borderRadius: "16px",
        padding: "40px 32px",
        boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
        backdropFilter: "blur(var(--glass-blur))",
        display: "flex",
        flexDirection: "column",
        gap: "24px"
      }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "12px", textAlign: "center" }}>
          <div style={{
            alignItems: "center",
            background: "linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%)",
            borderRadius: "12px",
            color: "#fff",
            display: "inline-flex",
            height: "48px",
            justifyContent: "center",
            width: "48px",
            boxShadow: "0 0 20px var(--accent-glow)"
          }}>
            <Route size={24} />
          </div>
          <div>
            <h2 style={{ fontSize: "24px", fontWeight: 800, margin: 0, color: "#fff", letterSpacing: "-0.5px" }}>Welcome Back</h2>
            <p style={{ color: "var(--muted)", fontSize: "14px", margin: "4px 0 0" }}>Sign in to manage your fleet operations</p>
          </div>
        </div>

        {error && (
          <div className="error" style={{ fontSize: "13px", padding: "12px 16px" }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <div className="field">
            <label htmlFor="username">Username</label>
            <div style={{ position: "relative" }}>
              <User size={16} style={{ position: "absolute", left: "14px", top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
              <input
                id="username"
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                style={{ paddingLeft: "42px" }}
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="password">Password</label>
            <div style={{ position: "relative" }}>
              <Lock size={16} style={{ position: "absolute", left: "14px", top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
              <input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={{ paddingLeft: "42px" }}
              />
            </div>
          </div>

          <button
            type="submit"
            className="button"
            disabled={submitting}
            style={{ width: "100%", justifyContent: "center", marginTop: "8px", background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)", boxShadow: "0 4px 12px rgba(37, 99, 235, 0.2)" }}
          >
            {submitting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Signing in...
              </>
            ) : (
              "Sign In"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
