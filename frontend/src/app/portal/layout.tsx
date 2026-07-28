"use client";

import React, { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import { 
  LayoutDashboard, 
  CalendarClock, 
  Users, 
  LogOut, 
  Building2, 
  Loader2, 
  ChevronDown, 
  ArrowLeftRight 
  , Receipt, FileSpreadsheet
} from "lucide-react";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [profileOpen, setProfileOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "var(--background)",
        color: "var(--ink)"
      }}>
        <Loader2 size={36} className="animate-spin" style={{ color: "var(--accent)" }} />
      </div>
    );
  }

  const memberships = user.active_memberships || [];
  if (memberships.length === 0 && !user.permissions?.includes("superuser")) {
    return (
      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "var(--background)",
        color: "var(--ink)",
        padding: "20px",
        textAlign: "center"
      }}>
        <Building2 size={64} style={{ color: "var(--muted)", marginBottom: "20px" }} />
        <h1 style={{ fontSize: "24px", fontWeight: 700, marginBottom: "8px" }}>No Corporate Access</h1>
        <p style={{ color: "var(--muted)", maxWidth: "420px", marginBottom: "24px" }}>
          Your user account is not associated with any active corporate customer organization. Please contact your company administrator to receive an invitation.
        </p>
        <button className="button" onClick={() => logout()}>Log Out</button>
      </div>
    );
  }

  const activeCompany = memberships[0];

  const menuItems = [
    { href: "/portal", label: "Dashboard", icon: LayoutDashboard },
    { href: "/portal/booking-requests/new", label: "Bookings", icon: CalendarClock },
    { href: "/portal/guests", label: "Guests", icon: Users },
    { href: "/portal/invoices", label: "Invoices", icon: Receipt },
    { href: "/portal/statements", label: "Statements", icon: FileSpreadsheet },
  ];

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--background)", color: "var(--ink)" }}>
      {/* Sidebar */}
      <aside style={{
        width: "260px",
        background: "var(--panel-strong)",
        borderRight: "1px solid var(--line)",
        display: "flex",
        flexDirection: "column",
        padding: "20px"
      }}>
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "32px", padding: "4px" }}>
          <div style={{
            background: "linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%)",
            color: "#fff",
            width: "36px",
            height: "36px",
            borderRadius: "8px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 4px 10px var(--accent-glow)"
          }}>
            <Building2 size={18} />
          </div>
          <div>
            <strong style={{ display: "block", fontSize: "14px", color: "#fff" }}>
              {activeCompany?.company_name || "Corporate Portal"}
            </strong>
            <span style={{ display: "block", fontSize: "11px", color: "var(--muted)" }}>
              Role: {activeCompany?.role?.toUpperCase() || "REQUESTER"}
            </span>
          </div>
        </div>

        {/* Navigation */}
        <nav style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1 }}>
          {menuItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || (item.href !== "/portal" && pathname.startsWith(item.href));
            return (
              <Link 
                key={item.href}
                href={item.href}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "10px 14px",
                  borderRadius: "10px",
                  fontSize: "14px",
                  fontWeight: 500,
                  color: active ? "#fff" : "var(--muted)",
                  background: active ? "var(--accent-glow)" : "transparent",
                  border: active ? "1px solid var(--line)" : "1px solid transparent",
                  transition: "all 0.2s"
                }}
              >
                <Icon size={18} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Footer profile & controls */}
        <div style={{ marginTop: "auto", position: "relative" }}>
          <div 
            onClick={() => setProfileOpen(!profileOpen)}
            style={{ 
              display: "flex", 
              alignItems: "center", 
              gap: 12, 
              padding: "12px", 
              background: "rgba(255,255,255,0.03)", 
              borderRadius: 12, 
              border: "1px solid var(--line)", 
              cursor: "pointer" 
            }}
          >
            <div style={{ 
              width: 32, 
              height: 32, 
              borderRadius: "50%", 
              background: "linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%)", 
              display: "flex", 
              alignItems: "center", 
              fontSize: 13, 
              fontWeight: "bold", 
              color: "#fff", 
              justifyContent: "center" 
            }}>
              {(user?.first_name?.[0] || user?.username?.[0] || "U").toUpperCase()}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <strong style={{ display: "block", fontSize: 13, color: "#fff", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {user?.first_name ? `${user.first_name} ${user.last_name}` : user?.username}
              </strong>
              <span style={{ display: "block", fontSize: 11, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {user?.email}
              </span>
            </div>
            <ChevronDown size={14} style={{ color: "var(--muted)" }} />
          </div>
          
          {profileOpen && (
            <div style={{
              position: "absolute",
              bottom: "100%",
              left: 0,
              right: 0,
              marginBottom: 8,
              background: "var(--panel-strong)",
              border: "1px solid var(--line)",
              borderRadius: 8,
              padding: 4,
              boxShadow: "0 -4px 15px rgba(0,0,0,0.3)",
              zIndex: 1000
            }}>
              {user.permissions?.includes("superuser") && (
                <Link href="/" style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  color: "var(--accent)",
                  padding: "10px 12px",
                  fontSize: 13,
                  fontWeight: 500,
                  borderRadius: 6,
                  textDecoration: "none"
                }}>
                  <ArrowLeftRight size={14} />
                  Fleet Console
                </Link>
              )}
              <button 
                onClick={() => {
                  setProfileOpen(false);
                  logout();
                }}
                style={{
                  width: "100%",
                  textAlign: "left",
                  background: "transparent",
                  border: 0,
                  color: "var(--danger)",
                  padding: "10px 12px",
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: "pointer",
                  borderRadius: 6,
                  display: "flex",
                  alignItems: "center",
                  gap: 8
                }}
              >
                <LogOut size={14} />
                Logout
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main Workspace */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Topbar */}
        <header style={{
          height: "64px",
          borderBottom: "1px solid var(--line)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 32px",
          background: "var(--panel)"
        }}>
          <div>
            <h1 style={{ fontSize: "18px", fontWeight: 700, margin: 0, color: "#fff" }}>
              Corporate Travel Desk
            </h1>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <span style={{ fontSize: "13px", color: "var(--muted)" }}>
              Active Session: <strong>{activeCompany?.company_name}</strong>
            </span>
          </div>
        </header>

        {/* Content */}
        <main style={{ flex: 1, padding: "32px", overflowY: "auto" }}>
          {children}
        </main>
      </div>
    </div>
  );
}
