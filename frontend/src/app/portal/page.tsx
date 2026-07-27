"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { 
  getBookingRequests, 
  BookingRequest, 
  BookingRequestStatus 
} from "@/lib/rentalsApi";
import { 
  CalendarClock, 
  Plus, 
  Clock, 
  CheckCircle2, 
  XCircle, 
  FileSpreadsheet,
  AlertCircle
} from "lucide-react";

export default function PortalDashboard() {
  const [requests, setRequests] = useState<BookingRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadRequests() {
      try {
        const data = await getBookingRequests();
        setRequests(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load booking requests.");
      } finally {
        setLoading(false);
      }
    }
    loadRequests();
  }, []);

  const stats = React.useMemo(() => {
    const total = requests.length;
    const pending = requests.filter(r => r.status === "approval_required").length;
    const approved = requests.filter(r => ["approved", "accepted", "dispatched", "active"].includes(r.status)).length;
    const completed = requests.filter(r => r.status === "completed").length;
    return { total, pending, approved, completed };
  }, [requests]);

  function getStatusStyle(status: BookingRequestStatus) {
    switch (status) {
      case "approved":
      case "accepted":
      case "completed":
        return { bg: "rgba(16, 185, 129, 0.12)", color: "#10b981" };
      case "approval_required":
        return { bg: "rgba(245, 158, 11, 0.12)", color: "#f59e0b" };
      case "submitted":
        return { bg: "rgba(59, 130, 246, 0.12)", color: "#3b82f6" };
      case "rejected":
      case "cancelled":
        return { bg: "rgba(239, 68, 68, 0.12)", color: "#ef4444" };
      default:
        return { bg: "rgba(255, 255, 255, 0.08)", color: "var(--muted)" };
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
      {/* Welcome / Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h2 style={{ fontSize: "24px", fontWeight: 800, color: "#fff", margin: 0 }}>Overview</h2>
          <p style={{ color: "var(--muted)", margin: "4px 0 0" }}>Real-time status of your corporate travel requests.</p>
        </div>
        <div style={{ display: "flex", gap: "12px" }}>
          <Link href="/portal/booking-requests/new" className="button" style={{ display: "flex", alignItems: "center", gap: "8px", textDecoration: "none" }}>
            <Plus size={16} />
            New Booking Request
          </Link>
        </div>
      </div>

      {/* Stats Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "20px" }}>
        <div className="card" style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--muted)" }}>TOTAL REQUESTS</span>
            <FileSpreadsheet size={18} style={{ color: "var(--accent)" }} />
          </div>
          <span style={{ fontSize: "28px", fontWeight: 800, color: "#fff" }}>{stats.total}</span>
        </div>

        <div className="card" style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--muted)" }}>PENDING APPROVAL</span>
            <Clock size={18} style={{ color: "#f59e0b" }} />
          </div>
          <span style={{ fontSize: "28px", fontWeight: 800, color: "#f59e0b" }}>{stats.pending}</span>
        </div>

        <div className="card" style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--muted)" }}>APPROVED / ACTIVE</span>
            <CheckCircle2 size={18} style={{ color: "#10b981" }} />
          </div>
          <span style={{ fontSize: "28px", fontWeight: 800, color: "#10b981" }}>{stats.approved}</span>
        </div>

        <div className="card" style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--muted)" }}>COMPLETED</span>
            <CheckCircle2 size={18} style={{ color: "#10b981" }} />
          </div>
          <span style={{ fontSize: "28px", fontWeight: 800, color: "#fff" }}>{stats.completed}</span>
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        <h3 style={{ fontSize: "18px", fontWeight: 700, color: "#fff", margin: 0 }}>Recent Booking Requests</h3>
        
        {error && (
          <div className="error" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: "center", padding: "40px", color: "var(--muted)" }}>
            <Loader2 size={24} className="animate-spin" style={{ margin: "0 auto 12px" }} />
            Loading bookings...
          </div>
        ) : requests.length === 0 ? (
          <div style={{
            background: "var(--panel)",
            border: "1px solid var(--line)",
            borderRadius: "12px",
            padding: "60px 20px",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "16px"
          }}>
            <CalendarClock size={48} style={{ color: "var(--muted)" }} />
            <div>
              <h4 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", margin: 0 }}>No Bookings Yet</h4>
              <p style={{ color: "var(--muted)", margin: "4px 0 0", fontSize: "14px" }}>Start requesting corporate packages for your travelers.</p>
            </div>
            <Link href="/portal/booking-requests/new" className="button" style={{ textDecoration: "none" }}>
              Submit First Request
            </Link>
          </div>
        ) : (
          <div style={{
            background: "var(--panel)",
            border: "1px solid var(--line)",
            borderRadius: "12px",
            overflow: "hidden"
          }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
              <thead>
                <tr style={{ background: "rgba(255,255,255,0.02)", borderBottom: "1px solid var(--line)" }}>
                  <th style={{ padding: "16px 24px", color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>BOOKING NO.</th>
                  <th style={{ padding: "16px 24px", color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>PASSENGER</th>
                  <th style={{ padding: "16px 24px", color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>PICKUP CITY & DATETIME</th>
                  <th style={{ padding: "16px 24px", color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>VEHICLE CATEGORY</th>
                  <th style={{ padding: "16px 24px", color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>BASE PRICE</th>
                  <th style={{ padding: "16px 24px", color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>STATUS</th>
                  <th style={{ padding: "16px 24px", color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {requests.slice(0, 10).map((r) => {
                  const style = getStatusStyle(r.status);
                  return (
                    <tr key={r.id} style={{ borderBottom: "1px solid var(--line)", transition: "background 0.2s" }} onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.01)"} onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
                      <td style={{ padding: "20px 24px", fontWeight: 600, color: "#fff" }}>{r.booking_number}</td>
                      <td style={{ padding: "20px 24px" }}>
                        <strong style={{ display: "block", color: "#fff", fontSize: "14px" }}>{r.passenger_name}</strong>
                        <span style={{ display: "block", color: "var(--muted)", fontSize: "12px" }}>{r.passenger_phone}</span>
                      </td>
                      <td style={{ padding: "20px 24px" }}>
                        <strong style={{ display: "block", color: "#fff", fontSize: "14px" }}>{r.pickup_city}</strong>
                        <span style={{ display: "block", color: "var(--muted)", fontSize: "12px" }}>{new Date(r.pickup_at).toLocaleString()}</span>
                      </td>
                      <td style={{ padding: "20px 24px" }}>{r.vehicle_category}</td>
                      <td style={{ padding: "20px 24px", fontWeight: 600 }}>₹{parseFloat((r.quote_base_price ?? 0).toString()).toFixed(2)}</td>
                      <td style={{ padding: "20px 24px" }}>
                        <span style={{
                          display: "inline-flex",
                          alignItems: "center",
                          padding: "4px 8px",
                          borderRadius: "6px",
                          fontSize: "12px",
                          fontWeight: 600,
                          backgroundColor: style.bg,
                          color: style.color
                        }}>
                          {r.status.toUpperCase().replace("_", " ")}
                        </span>
                      </td>
                      <td style={{ padding: "20px 24px" }}>
                        <Link href={`/portal/booking-requests/${r.id}`} style={{
                          color: "var(--accent)",
                          textDecoration: "none",
                          fontSize: "13px",
                          fontWeight: 600
                        }}>
                          Manage
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// Simple loader helper
function Loader2({ size, className, style }: { size: number; className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={{ width: size, height: size, fill: "none", stroke: "currentColor", ...style }} viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M21 21v-5h-.581m0 0a8.003 8.003 0 11-15.357-2" />
    </svg>
  );
}
