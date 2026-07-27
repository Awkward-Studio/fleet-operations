"use client";

import React, { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { 
  getBookingRequests, 
  BookingRequest, 
  BookingRequestStatus,
  approveBookingRequest,
  rejectBookingRequest,
  cancelBookingRequest,
  amendBookingRequest
} from "@/lib/rentalsApi";
import { ArrowLeft, Loader2, AlertCircle, ShieldAlert, CheckCircle, Check, X, ShieldAlert as WarningIcon, History } from "lucide-react";
import Link from "next/link";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function BookingRequestDetail({ params }: PageProps) {
  const resolvedParams = use(params);
  const { user } = useAuth();
  const router = useRouter();
  const bookingRequestId = parseInt(resolvedParams.id);

  const [booking, setBooking] = useState<BookingRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Amendment states
  const [isAmending, setIsAmending] = useState(false);
  const [pickupAddress, setPickupAddress] = useState("");
  const [dropAddress, setDropAddress] = useState("");
  const [costCentre, setCostCentre] = useState("");
  const [poReference, setPoReference] = useState("");
  const [reason, setReason] = useState("");
  const [amendError, setAmendError] = useState<string | null>(null);

  async function loadBooking() {
    setLoading(true);
    setError(null);
    try {
      const data = await getBookingRequests();
      const match = data.find(b => b.id === bookingRequestId);
      if (match) {
        setBooking(match);
        setPickupAddress(match.pickup_address);
        setDropAddress(match.drop_address || "");
        setCostCentre(match.cost_centre || "");
        setPoReference(match.po_reference || "");
      } else {
        setError("Booking request not found.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load booking details.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBooking();
  }, [bookingRequestId]);

  const activeCompany = user?.active_memberships?.[0];
  const isApproverOrAdmin = activeCompany?.role === "approver" || activeCompany?.role === "admin" || user?.permissions?.includes("superuser");

  async function handleApprove() {
    setActionLoading(true);
    try {
      await approveBookingRequest(bookingRequestId);
      await loadBooking();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    setActionLoading(true);
    try {
      await rejectBookingRequest(bookingRequestId);
      await loadBooking();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rejection failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCancel() {
    if (!confirm("Are you sure you want to cancel this booking?")) return;
    setActionLoading(true);
    try {
      await cancelBookingRequest(bookingRequestId);
      await loadBooking();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancellation failed.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleAmend(e: React.FormEvent) {
    e.preventDefault();
    if (!reason.trim()) {
      setAmendError("Please provide a reason for the amendment.");
      return;
    }
    setActionLoading(true);
    setAmendError(null);
    try {
      await amendBookingRequest(bookingRequestId, {
        pickup_address: pickupAddress,
        drop_address: dropAddress || undefined,
        cost_centre: costCentre || undefined,
        po_reference: poReference || undefined,
        reason: reason
      });
      setIsAmending(false);
      setReason("");
      await loadBooking();
    } catch (err) {
      setAmendError(err instanceof Error ? err.message : "Amendment failed.");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: "80px", color: "var(--muted)" }}>
        <Loader2 size={36} className="animate-spin" style={{ margin: "0 auto 16px", color: "var(--accent)" }} />
        Loading request details...
      </div>
    );
  }

  if (error || !booking) {
    return (
      <div style={{ maxWidth: "600px", margin: "40px auto", textAlign: "center" }}>
        <AlertCircle size={48} style={{ color: "#ef4444", marginBottom: "16px" }} />
        <h2 style={{ color: "#fff", fontSize: "20px", fontWeight: 700 }}>Error Loading Request</h2>
        <p style={{ color: "var(--muted)", margin: "8px 0 24px" }}>{error || "Booking request not found"}</p>
        <Link href="/portal" className="button">Back to Dashboard</Link>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px", maxWidth: "1000px" }}>
      {/* Back button */}
      <div>
        <Link href="/portal" style={{ display: "inline-flex", alignItems: "center", gap: "8px", color: "var(--accent)", textDecoration: "none", fontSize: "14px", fontWeight: 600 }}>
          <ArrowLeft size={16} />
          Back to Dashboard
        </Link>
      </div>

      {/* Header Info */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <span style={{ fontSize: "12px", color: "var(--muted)", fontWeight: 700 }}>BOOKING NUMBER</span>
          <h2 style={{ fontSize: "28px", fontWeight: 800, color: "#fff", margin: 0 }}>{booking.booking_number}</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <span style={{
            padding: "8px 16px",
            borderRadius: "8px",
            fontSize: "13px",
            fontWeight: 700,
            textTransform: "uppercase",
            background: "rgba(255,255,255,0.06)",
            color: "var(--muted)"
          }}>
            {booking.status.replace("_", " ")}
          </span>

          {/* Cancel button */}
          {booking.status !== "cancelled" && booking.status !== "completed" && booking.status !== "rejected" && (
            <button className="button secondary danger" onClick={handleCancel} disabled={actionLoading}>
              Cancel Request
            </button>
          )}
        </div>
      </div>

      {/* Main details grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "24px", alignItems: "start" }}>
        
        {/* Left Side: General Info */}
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          
          {/* Passenger & Itinerary Card */}
          <div className="card" style={{ padding: "28px", display: "flex", flexDirection: "column", gap: "24px" }}>
            <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0, borderBottom: "1px solid var(--line)", paddingBottom: "12px" }}>Trip Itinerary</h3>
            
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
              <div>
                <span style={{ display: "block", fontSize: "11px", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase" }}>Passenger</span>
                <strong style={{ display: "block", color: "#fff", fontSize: "15px", marginTop: "4px" }}>{booking.passenger_name}</strong>
                <span style={{ display: "block", color: "var(--muted)", fontSize: "12px", marginTop: "2px" }}>{booking.passenger_phone} | {booking.passenger_email || "No Email"}</span>
              </div>
              
              <div>
                <span style={{ display: "block", fontSize: "11px", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase" }}>Vehicle Category</span>
                <strong style={{ display: "block", color: "#fff", fontSize: "15px", marginTop: "4px" }}>{booking.vehicle_category}</strong>
              </div>

              <div style={{ gridColumn: "span 2" }}>
                <span style={{ display: "block", fontSize: "11px", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase" }}>Pickup Location</span>
                <strong style={{ display: "block", color: "#fff", fontSize: "14px", marginTop: "4px" }}>{booking.pickup_city}</strong>
                <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "13px" }}>{booking.pickup_address}</p>
              </div>

              {booking.drop_address && (
                <div style={{ gridColumn: "span 2" }}>
                  <span style={{ display: "block", fontSize: "11px", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase" }}>Drop Location</span>
                  <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "13px" }}>{booking.drop_address}</p>
                </div>
              )}

              <div>
                <span style={{ display: "block", fontSize: "11px", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase" }}>Pickup At</span>
                <strong style={{ display: "block", color: "#fff", fontSize: "14px", marginTop: "4px" }}>{new Date(booking.pickup_at).toLocaleString()}</strong>
              </div>

              <div>
                <span style={{ display: "block", fontSize: "11px", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase" }}>Expected Return At</span>
                <strong style={{ display: "block", color: "#fff", fontSize: "14px", marginTop: "4px" }}>{new Date(booking.expected_return_at).toLocaleString()}</strong>
              </div>
            </div>
          </div>

          {/* Pending Approval actions for managers */}
          {booking.status === "approval_required" && (
            <div className="card" style={{
              padding: "28px",
              background: "linear-gradient(145deg, #2b2518 0%, #151a29 100%)",
              border: "1px solid #f59e0b",
              display: "flex",
              flexDirection: "column",
              gap: "20px"
            }}>
              <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
                <ShieldAlert size={24} style={{ color: "#f59e0b" }} />
                <div>
                  <h4 style={{ fontSize: "15px", fontWeight: 700, color: "#fff", margin: 0 }}>Approval Required</h4>
                  <p style={{ color: "var(--muted)", fontSize: "13px", margin: "2px 0 0" }}>This request exceeds policy thresholds and requires manager approval.</p>
                </div>
              </div>
              
              {isApproverOrAdmin ? (
                <div style={{ display: "flex", gap: "12px" }}>
                  <button className="button" onClick={handleApprove} disabled={actionLoading} style={{ flex: 1, background: "#10b981", color: "#fff" }}>
                    {actionLoading ? <Loader2 size={16} className="animate-spin" /> : "Approve Booking"}
                  </button>
                  <button className="button secondary danger" onClick={handleReject} disabled={actionLoading} style={{ flex: 1 }}>
                    Reject Booking
                  </button>
                </div>
              ) : (
                <div style={{ fontSize: "12px", color: "var(--muted)" }}>
                  Only authorized company approvers or admins can approve this request.
                </div>
              )}
            </div>
          )}

          {/* Amendment form */}
          {booking.status !== "cancelled" && booking.status !== "completed" && booking.status !== "rejected" && (
            <div className="card" style={{ padding: "28px", display: "flex", flexDirection: "column", gap: "20px" }}>
              <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                Amend Booking Itinerary
                <button className="button secondary small" onClick={() => setIsAmending(!isAmending)}>
                  {isAmending ? "Hide Form" : "Amend Details"}
                </button>
              </h3>

              {isAmending && (
                <form onSubmit={handleAmend} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                  {amendError && <div style={{ color: "#ef4444", fontSize: "13px" }}>{amendError}</div>}
                  <div className="field">
                    <label>Pickup Address</label>
                    <textarea value={pickupAddress} onChange={e => setPickupAddress(e.target.value)} required />
                  </div>
                  <div className="field">
                    <label>Drop Address (Optional)</label>
                    <textarea value={dropAddress} onChange={e => setDropAddress(e.target.value)} />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                    <div className="field">
                      <label>Cost Centre</label>
                      <input type="text" value={costCentre} onChange={e => setCostCentre(e.target.value)} />
                    </div>
                    <div className="field">
                      <label>PO Reference</label>
                      <input type="text" value={poReference} onChange={e => setPoReference(e.target.value)} />
                    </div>
                  </div>
                  <div className="field">
                    <label>Reason for Amendment</label>
                    <input type="text" placeholder="e.g. Flight schedule change" value={reason} onChange={e => setReason(e.target.value)} required />
                  </div>
                  <button type="submit" className="button" disabled={actionLoading} style={{ alignSelf: "flex-end" }}>
                    Save & Submit Amendment
                  </button>
                </form>
              )}
            </div>
          )}

          {/* Audit trail / Amendments list */}
          {booking.amendments && booking.amendments.length > 0 && (
            <div className="card" style={{ padding: "28px", display: "flex", flexDirection: "column", gap: "20px" }}>
              <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                <History size={18} />
                Amendment Log
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {booking.amendments.map((a) => (
                  <div key={a.id} style={{ borderLeft: "2px solid var(--accent)", paddingLeft: "16px", display: "flex", flexDirection: "column", gap: "6px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "var(--muted)" }}>
                      <span>Amended by <strong>{a.amended_by_username || "User"}</strong></span>
                      <span>{new Date(a.created_at).toLocaleString()}</span>
                    </div>
                    <p style={{ margin: 0, fontSize: "13px", color: "#fff" }}>
                      Reason: <em>"{a.reason}"</em>
                    </p>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", fontSize: "11px", color: "var(--muted)", marginTop: "4px" }}>
                      {Object.entries(a.changes).map(([field, val]) => (
                        <span key={field} style={{ background: "rgba(255,255,255,0.04)", padding: "2px 6px", borderRadius: "4px" }}>
                          <strong>{field}</strong> → {String(val)}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>

        {/* Right Side: Price Details & Billing Info */}
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          
          {/* Quote snapshot */}
          <div className="card" style={{ padding: "28px", display: "flex", flexDirection: "column", gap: "20px" }}>
            <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0, borderBottom: "1px solid var(--line)", paddingBottom: "12px" }}>Quote snapshot</h3>
            
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--muted)", fontSize: "13px" }}>Base Price:</span>
                <strong style={{ color: "#fff", fontSize: "15px" }}>₹{parseFloat((booking.quote_base_price ?? 0).toString()).toFixed(2)}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--muted)", fontSize: "13px" }}>Driver Allowance:</span>
                <strong style={{ color: "#fff", fontSize: "14px" }}>₹{parseFloat((booking.quote_driver_allowance ?? 0).toString()).toFixed(2)}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--muted)", fontSize: "13px" }}>Extra Hour Charge:</span>
                <strong style={{ color: "#fff", fontSize: "14px" }}>₹{parseFloat((booking.quote_extra_hour_rate ?? 0).toString()).toFixed(2)}/hour</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--muted)", fontSize: "13px" }}>Extra Km Charge:</span>
                <strong style={{ color: "#fff", fontSize: "14px" }}>₹{parseFloat((booking.quote_extra_km_rate ?? 0).toString()).toFixed(2)}/km</strong>
              </div>
            </div>
          </div>

          {/* References Card */}
          <div className="card" style={{ padding: "28px", display: "flex", flexDirection: "column", gap: "20px" }}>
            <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0, borderBottom: "1px solid var(--line)", paddingBottom: "12px" }}>References</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div>
                <span style={{ display: "block", fontSize: "11px", color: "var(--muted)", fontWeight: 700 }}>COST CENTRE</span>
                <strong style={{ display: "block", color: "#fff", fontSize: "13px", marginTop: "2px" }}>{booking.cost_centre || "Not Provided"}</strong>
              </div>
              <div>
                <span style={{ display: "block", fontSize: "11px", color: "var(--muted)", fontWeight: 700 }}>PO REFERENCE</span>
                <strong style={{ display: "block", color: "#fff", fontSize: "13px", marginTop: "2px" }}>{booking.po_reference || "Not Provided"}</strong>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
