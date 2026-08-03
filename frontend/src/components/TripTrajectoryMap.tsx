"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { getTripLocationLogs } from "@/lib/api";

interface LocationLog {
  id: number;
  latitude: number | string;
  longitude: number | string;
  speed_kmh?: number | null;
  heading?: number | null;
  timestamp: string;
}

interface TripTrajectoryMapProps {
  tripId: number;
  pickupCity?: string;
  dropCity?: string;
  pickupLat?: number | null;
  pickupLng?: number | null;
  dropLat?: number | null;
  dropLng?: number | null;
  isLive?: boolean;
}

export default function TripTrajectoryMap({
  tripId,
  pickupCity,
  dropCity,
  pickupLat,
  pickupLng,
  dropLat,
  dropLng,
  isLive = true,
}: TripTrajectoryMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const trajectoryPolylineRef = useRef<L.Polyline | null>(null);
  const vehicleMarkerRef = useRef<L.Marker | null>(null);
  const pickupMarkerRef = useRef<L.Marker | null>(null);
  const dropMarkerRef = useRef<L.Marker | null>(null);
  const waypointMarkersRef = useRef<L.Marker[]>([]);

  const [logs, setLogs] = useState<LocationLog[]>([]);
  const [totalPings, setTotalPings] = useState(0);
  const [latestPing, setLatestPing] = useState<LocationLog | null>(null);
  const [lastFetchTime, setLastFetchTime] = useState<Date>(new Date());
  const [secondsAgo, setSecondsAgo] = useState(0);
  const [nextExpectedSeconds, setNextExpectedSeconds] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const createIcon = (label: string, bg: string, size = 30) => {
    return L.divIcon({
      className: `custom-marker-${label}`,
      html: `
        <div style="
          background-color: ${bg};
          width: ${size}px;
          height: ${size}px;
          border-radius: 50%;
          border: 2px solid #fff;
          box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-weight: 800;
          font-size: ${size > 24 ? 13 : 10}px;
        ">
          ${label}
        </div>
      `,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });
  };

  const fetchLocationData = async () => {
    try {
      const data = await getTripLocationLogs(tripId);
      const rawLogs: LocationLog[] = data.logs || [];

      // Sort logs strictly in ascending order by timestamp (oldest first, newest last)
      const sortedLogs = [...rawLogs].sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );

      setLogs(sortedLogs);
      setTotalPings(data.total_pings || sortedLogs.length);
      setLatestPing(data.latest_ping || (sortedLogs.length > 0 ? sortedLogs[sortedLogs.length - 1] : null));
      setLastFetchTime(new Date());
      setNextExpectedSeconds(30);
      setError(null);
    } catch (err: any) {
      console.error("Fetch location logs error:", err);
      setError(err.message || "Failed to load location logs");
    } finally {
      setLoading(false);
    }
  };

  // Ticking 1-second interval for timers
  useEffect(() => {
    const timer = setInterval(() => {
      if (latestPing) {
        const pingTime = new Date(latestPing.timestamp).getTime();
        const diff = Math.max(0, Math.floor((Date.now() - pingTime) / 1000));
        setSecondsAgo(diff);
      } else {
        const fetchDiff = Math.max(0, Math.floor((Date.now() - lastFetchTime.getTime()) / 1000));
        setSecondsAgo(fetchDiff);
      }

      setNextExpectedSeconds((prev) => (prev <= 1 ? 30 : prev - 1));
    }, 1000);

    return () => clearInterval(timer);
  }, [latestPing, lastFetchTime]);

  useEffect(() => {
    fetchLocationData();
    if (!isLive) return;

    const interval = setInterval(() => {
      fetchLocationData();
    }, 30000); // 30 second auto-refresh

    return () => clearInterval(interval);
  }, [tripId, isLive]);

  // Map initialization
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [18.5204, 73.8567],
      zoom: 8,
      zoomControl: true,
    });

    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 19,
    }).addTo(map);

    mapRef.current = map;

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // Update map features
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const bounds = L.latLngBounds([]);

    // Clear old waypoint markers
    waypointMarkersRef.current.forEach((m) => m.remove());
    waypointMarkersRef.current = [];

    if (pickupLat && pickupLng) {
      const pLat = Number(pickupLat);
      const pLng = Number(pickupLng);
      if (!pickupMarkerRef.current) {
        pickupMarkerRef.current = L.marker([pLat, pLng], {
          icon: createIcon("P", "#10b981", 32),
        })
          .bindPopup(`<b>Pickup:</b> ${pickupCity || "Pickup Location"}`)
          .addTo(map);
      } else {
        pickupMarkerRef.current.setLatLng([pLat, pLng]);
      }
      bounds.extend([pLat, pLng]);
    }

    if (dropLat && dropLng) {
      const dLat = Number(dropLat);
      const dLng = Number(dropLng);
      if (!dropMarkerRef.current) {
        dropMarkerRef.current = L.marker([dLat, dLng], {
          icon: createIcon("D", "#ef4444", 32),
        })
          .bindPopup(`<b>Drop:</b> ${dropCity || "Dropoff Location"}`)
          .addTo(map);
      } else {
        dropMarkerRef.current.setLatLng([dLat, dLng]);
      }
      bounds.extend([dLat, dLng]);
    }

    if (logs && logs.length > 0) {
      // Build distinct coordinates in chronological sequence
      const coords: [number, number][] = [];
      logs.forEach((log, index) => {
        const lat = Number(log.latitude);
        const lng = Number(log.longitude);
        if (isNaN(lat) || isNaN(lng)) return;

        coords.push([lat, lng]);

        // Draw numbered waypoint pin for each ping along the sequence
        const timeStr = new Date(log.timestamp).toLocaleTimeString();
        const speedStr = log.speed_kmh ? `${log.speed_kmh} km/h` : "Stationary";
        const pingNum = index + 1;

        const marker = L.marker([lat, lng], {
          icon: createIcon(`${pingNum}`, "#0284c7", 22),
        })
          .bindPopup(`<b>Ping #${pingNum}</b><br/>Time: ${timeStr}<br/>Speed: ${speedStr}`)
          .addTo(map);

        waypointMarkersRef.current.push(marker);
        bounds.extend([lat, lng]);
      });

      if (coords.length > 0) {
        if (trajectoryPolylineRef.current) {
          trajectoryPolylineRef.current.setLatLngs(coords);
        } else {
          trajectoryPolylineRef.current = L.polyline(coords, {
            color: "#38bdf8",
            weight: 4,
            opacity: 0.9,
            dashArray: "6, 6",
            lineCap: "round",
          }).addTo(map);
        }

        const lastLog = logs[logs.length - 1];
        const lastCoord: [number, number] = [Number(lastLog.latitude), Number(lastLog.longitude)];
        const speedText = lastLog.speed_kmh ? `${lastLog.speed_kmh} km/h` : "N/A";
        const timeText = new Date(lastLog.timestamp).toLocaleTimeString();

        if (!vehicleMarkerRef.current) {
          vehicleMarkerRef.current = L.marker(lastCoord, {
            icon: createIcon("🚗", "#3b82f6", 34),
          })
            .bindPopup(`<b>Latest Vehicle Location</b><br/>Speed: ${speedText}<br/>Recorded: ${timeText}`)
            .addTo(map);
        } else {
          vehicleMarkerRef.current.setLatLng(lastCoord);
          vehicleMarkerRef.current.setPopupContent(
            `<b>Latest Vehicle Location</b><br/>Speed: ${speedText}<br/>Recorded: ${timeText}`
          );
        }
      }
    }

    if (bounds.isValid()) {
      setTimeout(() => {
        map.invalidateSize();
        map.fitBounds(bounds, { padding: [35, 35], maxZoom: 15 });
      }, 100);
    }
  }, [logs, pickupLat, pickupLng, dropLat, dropLng, pickupCity, dropCity]);

  const handleFitBounds = () => {
    const map = mapRef.current;
    if (!map) return;
    const bounds = L.latLngBounds([]);
    if (pickupLat && pickupLng) bounds.extend([Number(pickupLat), Number(pickupLng)]);
    if (dropLat && dropLng) bounds.extend([Number(dropLat), Number(dropLng)]);
    logs.forEach((log) => {
      const lat = Number(log.latitude);
      const lng = Number(log.longitude);
      if (!isNaN(lat) && !isNaN(lng)) bounds.extend([lat, lng]);
    });
    if (bounds.isValid()) {
      map.invalidateSize();
      map.fitBounds(bounds, { padding: [35, 35], maxZoom: 15 });
    }
  };

  return (
    <div style={{ position: "relative", width: "100%" }}>
      {/* Live Timer Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 10,
          padding: "8px 12px",
          background: "var(--panel)",
          borderRadius: 8,
          border: "1px solid var(--line)",
          fontSize: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: totalPings > 0 ? "#10b981" : "#eab308" }}></span>
          <span style={{ fontWeight: 700, color: "var(--foreground)" }}>
            {totalPings > 0 ? `LIVE GPS TRAJECTORY (${totalPings} pings)` : "NO PINGS YET"}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ color: "var(--accent)", fontWeight: 600 }}>
            ⏱️ Last Updated: {secondsAgo}s ago
          </span>
          {isLive && (
            <span style={{ color: "#10b981", fontWeight: 700 }}>
              🔄 Next Expected In: {nextExpectedSeconds}s
            </span>
          )}
          <button
            onClick={handleFitBounds}
            style={{
              background: "var(--panel-strong)",
              color: "var(--accent)",
              border: "1px solid var(--line)",
              padding: "3px 10px",
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            🎯 Fit Route
          </button>
        </div>
      </div>

      <div
        ref={mapContainerRef}
        style={{
          height: 340,
          width: "100%",
          borderRadius: 10,
          border: "1px solid var(--line)",
          background: "var(--panel-strong)",
          zIndex: 1,
        }}
      />

      {loading && (
        <div
          style={{
            position: "absolute",
            top: 50,
            right: 12,
            background: "rgba(0,0,0,0.8)",
            color: "#fff",
            padding: "4px 10px",
            borderRadius: 6,
            fontSize: 11,
            zIndex: 10,
          }}
        >
          Updating live GPS data...
        </div>
      )}

      {error && (
        <div style={{ color: "var(--danger)", fontSize: 12, marginTop: 6 }}>
          {error}
        </div>
      )}

      {logs && logs.length > 0 && (
        <div style={{ marginTop: 12, maxHeight: 140, overflowY: "auto", border: "1px solid var(--line)", borderRadius: 6, padding: 8, background: "var(--panel)" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", marginBottom: 6 }}>
            CHRONOLOGICAL PING SEQUENCE (OLDEST #1 ➔ LATEST #{logs.length})
          </div>
          {logs.map((log, idx) => (
            <div key={log.id || idx} style={{ display: "flex", justifyContent: "space-between", fontSize: 11, padding: "3px 0", borderBottom: "1px dashed var(--line)" }}>
              <span style={{ fontWeight: 700, color: "var(--accent)" }}>Ping #{idx + 1}</span>
              <span>📍 {Number(log.latitude).toFixed(5)}, {Number(log.longitude).toFixed(5)}</span>
              <span>{log.speed_kmh ? `${log.speed_kmh} km/h` : "Stationary"}</span>
              <span style={{ color: "var(--muted)" }}>{new Date(log.timestamp).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
