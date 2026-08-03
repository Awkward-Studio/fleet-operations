"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { ArrowLeft, User, Car, MapPin, Calendar, Activity, ShieldCheck, Clock, Receipt } from "lucide-react";
import { AuthGuard } from "@/components/AuthGuard";
import { getTripDetails } from "@/lib/api";

const TripTrajectoryMap = dynamic(() => import("@/components/TripTrajectoryMap"), {
  ssr: false,
  loading: () => (
    <div style={{ height: 360, background: "var(--panel-strong)", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)", fontSize: 13 }}>
      Loading interactive route map engine...
    </div>
  ),
});

export default function TripDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const tripId = Number(resolvedParams.id);
  const [trip, setTrip] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadTrip() {
      try {
        setLoading(true);
        const data = await getTripDetails(tripId);
        setTrip(data);
        setError(null);
      } catch (err: any) {
        setError(err.message || "Failed to load trip");
      } finally {
        setLoading(false);
      }
    }
    loadTrip();
  }, [tripId]);

  const statusColor = (status: string) => {
    switch ((status || "").toLowerCase()) {
      case "active":
        return "#10b981";
      case "completed":
        return "#3b82f6";
      case "en_route_pickup":
        return "#eab308";
      case "cancelled":
        return "#ef4444";
      default:
        return "#6b7280";
    }
  };

  return (
    <AuthGuard>
      <div style={{ minHeight: "100vh", backgroundColor: "var(--background)", color: "var(--foreground)", padding: "24px 20px" }}>
        <div style={{ maxWidth: 1000, margin: "0 auto" }}>
          {/* Header Bar */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
            <Link
              href="/trips"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                color: "var(--accent)",
                textDecoration: "none",
                fontSize: 14,
                fontWeight: 600,
              }}
            >
              <ArrowLeft size={18} /> Back to Trips Board
            </Link>
            {trip && (
              <span
                style={{
                  padding: "4px 12px",
                  borderRadius: 20,
                  fontSize: 12,
                  fontWeight: 800,
                  backgroundColor: `${statusColor(trip.status)}22`,
                  color: statusColor(trip.status),
                  border: `1px solid ${statusColor(trip.status)}66`,
                  textTransform: "uppercase",
                }}
              >
                {trip.status}
              </span>
            )}
          </div>

          {loading ? (
            <div style={{ padding: 60, textAlign: "center", color: "var(--muted)", background: "var(--panel)", borderRadius: 12, border: "1px solid var(--line)" }}>
              Loading trip #{tripId} details...
            </div>
          ) : error ? (
            <div style={{ padding: 30, color: "var(--danger)", background: "var(--panel)", borderRadius: 12, border: "1px solid var(--line)" }}>
              {error}
            </div>
          ) : trip ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {/* Trip Title Card */}
              <div style={{ background: "var(--panel)", padding: 20, borderRadius: 12, border: "1px solid var(--line)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <h1 style={{ fontSize: 24, fontWeight: 900, margin: 0 }}>
                      Trip #{trip.id}: {trip.pickup_city} ➔ {trip.drop_city}
                    </h1>
                    <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
                      Booking Type: <strong style={{ color: "var(--foreground)" }}>{trip.booking_type}</strong> | Duty: <strong style={{ color: "var(--foreground)" }}>{trip.duty_type}</strong> | Category: <strong style={{ color: "var(--foreground)" }}>{trip.vehicle_category || "Standard"}</strong>
                    </div>
                  </div>
                  {trip.status === "completed" && (
                    <Link
                      href={`/billing?trip=${trip.id}`}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        background: "var(--panel-strong)",
                        color: "var(--foreground)",
                        border: "1px solid var(--line)",
                        padding: "8px 14px",
                        borderRadius: 6,
                        fontSize: 13,
                        fontWeight: 600,
                        textDecoration: "none",
                      }}
                    >
                      <Receipt size={16} /> Review Billing Closeout
                    </Link>
                  )}
                </div>
              </div>

              {/* Metadata Cards Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
                <div style={{ background: "var(--panel)", padding: 16, borderRadius: 10, border: "1px solid var(--line)" }}>
                  <div style={{ fontSize: 12, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6, fontWeight: 700, marginBottom: 8 }}>
                    <User size={16} /> CUSTOMER & PASSENGER
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 800 }}>{trip.customer_name || "Direct Customer"}</div>
                  {trip.ota_source && <div style={{ fontSize: 12, color: "var(--accent)", marginTop: 2 }}>Source: {trip.ota_source}</div>}
                  {trip.passenger_name && <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>Passenger: {trip.passenger_name} ({trip.passenger_phone || "N/A"})</div>}
                </div>

                <div style={{ background: "var(--panel)", padding: 16, borderRadius: 10, border: "1px solid var(--line)" }}>
                  <div style={{ fontSize: 12, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6, fontWeight: 700, marginBottom: 8 }}>
                    <Car size={16} /> ASSIGNED VEHICLE & DRIVER
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 800 }}>
                    {trip.assigned_vehicle_reg || "Unassigned Vehicle"}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
                    Driver: {trip.assigned_driver_name || "Unassigned Driver"}
                  </div>
                </div>

                <div style={{ background: "var(--panel)", padding: 16, borderRadius: 10, border: "1px solid var(--line)" }}>
                  <div style={{ fontSize: 12, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6, fontWeight: 700, marginBottom: 8 }}>
                    <Clock size={16} /> SCHEDULE & TIMELINE
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 700 }}>
                    Pickup: {new Date(trip.pickup_at).toLocaleString()}
                  </div>
                  {trip.estimated_drop_at && (
                    <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
                      Est. Drop: {new Date(trip.estimated_drop_at).toLocaleString()}
                    </div>
                  )}
                </div>
              </div>

              {/* Live Trajectory & Map Section */}
              <div style={{ background: "var(--panel)", padding: 20, borderRadius: 12, border: "1px solid var(--line)" }}>
                <h3 style={{ fontSize: 16, fontWeight: 800, margin: "0 0 16px 0", display: "flex", alignItems: "center", gap: 8 }}>
                  <MapPin size={18} /> Route Trajectory & Live GPS Logs
                </h3>
                <TripTrajectoryMap
                  tripId={trip.id}
                  pickupCity={trip.pickup_city}
                  dropCity={trip.drop_city}
                  pickupLat={trip.pickup_latitude}
                  pickupLng={trip.pickup_longitude}
                  dropLat={trip.drop_latitude}
                  dropLng={trip.drop_longitude}
                  isLive={trip.status === "active" || trip.status === "en_route_pickup"}
                />
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </AuthGuard>
  );
}
