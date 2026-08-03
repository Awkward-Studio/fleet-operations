"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { X, MapPin, Calendar, Car, User, Clock, ShieldCheck, Activity } from "lucide-react";
import { getTripDetails } from "@/lib/api";

const TripTrajectoryMap = dynamic(() => import("./TripTrajectoryMap"), {
  ssr: false,
  loading: () => (
    <div style={{ height: 320, background: "var(--panel-strong)", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)", fontSize: 13 }}>
      Loading interactive map engine...
    </div>
  ),
});

export interface TripDetailModalProps {
  tripId: number | null;
  onClose: () => void;
}

export function TripDetailModal({ tripId, onClose }: TripDetailModalProps) {
  const [trip, setTrip] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTripDetails = async () => {
    if (!tripId) return;
    try {
      setLoading(true);
      const data = await getTripDetails(tripId);
      setTrip(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load trip details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTripDetails();
  }, [tripId]);

  if (!tripId) return null;

  const statusColor = (status: string) => {
    switch ((status || "").toLowerCase()) {
      case "active":
        return "#10b981"; // emerald
      case "completed":
        return "#3b82f6"; // blue
      case "en_route_pickup":
        return "#eab308"; // yellow
      case "cancelled":
        return "#ef4444"; // red
      default:
        return "#6b7280"; // gray
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 820,
          maxHeight: "90vh",
          backgroundColor: "var(--panel)",
          border: "1px solid var(--line)",
          borderRadius: 12,
          boxShadow: "0 20px 50px rgba(0, 0, 0, 0.5)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--line)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "var(--panel-strong)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 18, fontWeight: 800, color: "var(--foreground)" }}>
              Trip #{tripId} Details
            </span>
            {trip && (
              <span
                style={{
                  padding: "3px 10px",
                  borderRadius: 20,
                  fontSize: 12,
                  fontWeight: 700,
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
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--muted)",
              cursor: "pointer",
              padding: 4,
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Content */}
        <div style={{ padding: 20, overflowY: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
          {loading && !trip ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
              Loading trip details...
            </div>
          ) : error ? (
            <div style={{ padding: 20, color: "var(--danger)" }}>{error}</div>
          ) : trip ? (
            <>
              {/* Top Details Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
                <div style={{ background: "var(--panel-strong)", padding: 12, borderRadius: 8, border: "1px solid var(--line)" }}>
                  <div style={{ fontSize: 11, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }}>
                    <User size={14} /> CUSTOMER / BOOKING
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 700, marginTop: 4 }}>{trip.customer_name || "Direct Customer"}</div>
                  <div style={{ fontSize: 12, color: "var(--accent)", marginTop: 2 }}>{trip.booking_type} • {trip.duty_type}</div>
                </div>

                <div style={{ background: "var(--panel-strong)", padding: 12, borderRadius: 8, border: "1px solid var(--line)" }}>
                  <div style={{ fontSize: 11, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }}>
                    <Car size={14} /> ASSIGNED VEHICLE & DRIVER
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 700, marginTop: 4 }}>
                    {trip.assigned_vehicle_reg || "Unassigned Vehicle"}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                    Driver: {trip.assigned_driver_name || "Unassigned Driver"}
                  </div>
                </div>

                <div style={{ background: "var(--panel-strong)", padding: 12, borderRadius: 8, border: "1px solid var(--line)" }}>
                  <div style={{ fontSize: 11, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }}>
                    <MapPin size={14} /> ROUTE CITIES
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 700, marginTop: 4 }}>
                    {trip.pickup_city} ➔ {trip.drop_city}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                    Category: {trip.vehicle_category || "Standard"}
                  </div>
                </div>
              </div>

              {/* Live Trajectory Map */}
              <div style={{ background: "var(--panel-strong)", padding: 16, borderRadius: 10, border: "1px solid var(--line)" }}>
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
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
