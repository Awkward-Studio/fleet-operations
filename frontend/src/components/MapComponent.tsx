"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

interface MapComponentProps {
  onLocationSelected: (data: {
    pickupLat: number | null;
    pickupLng: number | null;
    pickupCity: string;
    dropLat: number | null;
    dropLng: number | null;
    dropCity: string;
    distanceKm: number | null;
  }) => void;
  pickupLat?: number | null;
  pickupLng?: number | null;
  pickupCityProp?: string | null;
  dropLat?: number | null;
  dropLng?: number | null;
  dropCityProp?: string | null;
}

export default function MapComponent({
  onLocationSelected,
  pickupLat: initialPickupLat,
  pickupLng: initialPickupLng,
  pickupCityProp,
  dropLat: initialDropLat,
  dropLng: initialDropLng,
  dropCityProp,
}: MapComponentProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const pickupMarkerRef = useRef<L.Marker | null>(null);
  const dropMarkerRef = useRef<L.Marker | null>(null);
  const polylineRef = useRef<L.Polyline | null>(null);

  const [pickup, setPickup] = useState<{ lat: number; lng: number; city: string } | null>(
    initialPickupLat && initialPickupLng
      ? { lat: Number(initialPickupLat), lng: Number(initialPickupLng), city: "" }
      : null
  );
  const [drop, setDrop] = useState<{ lat: number; lng: number; city: string } | null>(
    initialDropLat && initialDropLng
      ? { lat: Number(initialDropLat), lng: Number(initialDropLng), city: "" }
      : null
  );
  const [distance, setDistance] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Custom marker icons using CSS for a sleek look
  const createMarkerIcon = (label: "P" | "D", color: string) => {
    return L.divIcon({
      className: `custom-map-marker-${label}`,
      html: `
        <div style="
          background-color: ${color};
          width: 28px;
          height: 28px;
          border-radius: 50%;
          border: 3px solid #fff;
          box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-weight: 800;
          font-size: 13px;
          transition: transform 0.2s ease;
        ">
          ${label}
        </div>
      `,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });
  };

  const pickupIcon = createMarkerIcon("P", "#10b981"); // emerald green
  const dropIcon = createMarkerIcon("D", "#ef4444"); // rose red

  // Geocode lat/lng to city name via Nominatim
  const reverseGeocode = async (lat: number, lng: number): Promise<string> => {
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}&zoom=10`
      );
      if (!response.ok) throw new Error("Geocoding failed");
      const data = await response.json();
      const addr = data.address || {};
      
      // Select the most appropriate city representation
      const city =
        addr.city ||
        addr.town ||
        addr.village ||
        addr.suburb ||
        addr.county ||
        addr.state_district ||
        addr.state ||
        "Unknown Location";
      return city;
    } catch (err) {
      console.error("Reverse geocoding error:", err);
      return "Selected Location";
    }
  };

  // Route path and distance via OSRM
  const getRouteDetails = async (
    startLat: number,
    startLng: number,
    endLat: number,
    endLng: number
  ): Promise<{ distanceKm: number; coordinates: [number, number][] } | null> => {
    try {
      const response = await fetch(
        `https://router.project-osrm.org/route/v1/driving/${startLng},${startLat};${endLng},${endLat}?overview=full&geometries=geojson`
      );
      if (!response.ok) throw new Error("Routing failed");
      const data = await response.json();
      if (data.code === "Ok" && data.routes && data.routes.length > 0) {
        const route = data.routes[0];
        const distKm = Number((route.distance / 1000).toFixed(2));
        // OSRM returns coordinates as [lng, lat], Leaflet wants [lat, lng]
        const coords = route.geometry.coordinates.map((c: [number, number]) => [c[1], c[0]] as [number, number]);
        return { distanceKm: distKm, coordinates: coords };
      }
    } catch (err) {
      console.error("OSRM route error:", err);
    }
    return null;
  };

  // Initial map setup
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    // Center on Pune, India by default
    const defaultCenter: L.LatLngExpression = [18.5204, 73.8567];
    const defaultZoom = 8;

    const map = L.map(mapContainerRef.current, {
      center: defaultCenter,
      zoom: defaultZoom,
      zoomControl: true,
    });

    // Dark-themed tiles from CartoDB (Dark Matter) for custom premium aesthetic
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 19,
    }).addTo(map);

    mapRef.current = map;

    // Handle map click
    map.on("click", async (e: L.LeafletMouseEvent) => {
      const { lat, lng } = e.latlng;
      setLoading(true);
      setError(null);

      // Simple cycle:
      // 1. If no pickup, set pickup
      // 2. If pickup exists but no drop, set drop
      // 3. If both exist, reset and set new pickup (clear drop)
      if (!pickupMarkerRef.current) {
        const cityName = await reverseGeocode(lat, lng);
        setPickup({ lat, lng, city: cityName });
      } else if (pickupMarkerRef.current && !dropMarkerRef.current) {
        const cityName = await reverseGeocode(lat, lng);
        setDrop({ lat, lng, city: cityName });
      } else {
        // Reset both
        if (polylineRef.current) {
          polylineRef.current.remove();
          polylineRef.current = null;
        }
        if (dropMarkerRef.current) {
          dropMarkerRef.current.remove();
          dropMarkerRef.current = null;
        }
        setDrop(null);
        setDistance(null);

        const cityName = await reverseGeocode(lat, lng);
        setPickup({ lat, lng, city: cityName });
      }
      setLoading(false);
    });

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // Update pickup marker on map when pickup state changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !pickup) return;

    if (pickupMarkerRef.current) {
      pickupMarkerRef.current.setLatLng([pickup.lat, pickup.lng]);
    } else {
      const marker = L.marker([pickup.lat, pickup.lng], {
        icon: pickupIcon,
        draggable: true,
      }).addTo(map);

      // Handle dragend
      marker.on("dragend", async (e) => {
        const target = e.target as L.Marker;
        const { lat, lng } = target.getLatLng();
        setLoading(true);
        const cityName = await reverseGeocode(lat, lng);
        setPickup({ lat, lng, city: cityName });
        setLoading(false);
      });

      pickupMarkerRef.current = marker;
    }

    // Pan map to marker if there is no drop marker yet
    if (!drop) {
      map.panTo([pickup.lat, pickup.lng]);
    }
  }, [pickup]);

  // Update drop marker and handle routing when drop state changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (!drop) {
      if (dropMarkerRef.current) {
        dropMarkerRef.current.remove();
        dropMarkerRef.current = null;
      }
      if (polylineRef.current) {
        polylineRef.current.remove();
        polylineRef.current = null;
      }
      return;
    }

    if (dropMarkerRef.current) {
      dropMarkerRef.current.setLatLng([drop.lat, drop.lng]);
    } else {
      const marker = L.marker([drop.lat, drop.lng], {
        icon: dropIcon,
        draggable: true,
      }).addTo(map);

      // Handle dragend
      marker.on("dragend", async (e) => {
        const target = e.target as L.Marker;
        const { lat, lng } = target.getLatLng();
        setLoading(true);
        const cityName = await reverseGeocode(lat, lng);
        setDrop({ lat, lng, city: cityName });
        setLoading(false);
      });

      dropMarkerRef.current = marker;
    }

    // Perform routing if both points are defined
    if (pickup) {
      setLoading(true);
      getRouteDetails(pickup.lat, pickup.lng, drop.lat, drop.lng).then((routeDetails) => {
        if (routeDetails) {
          setDistance(routeDetails.distanceKm);

          // Update/Create polyline path
          if (polylineRef.current) {
            polylineRef.current.setLatLngs(routeDetails.coordinates);
          } else {
            polylineRef.current = L.polyline(routeDetails.coordinates, {
              color: "#3b82f6", // premium blue route line
              weight: 4,
              opacity: 0.8,
              dashArray: "1, 8", // dotted/dashed route line for sleek style
            }).addTo(map);
          }

          // Fit map boundaries to include both markers
          const bounds = L.latLngBounds(
            [pickup.lat, pickup.lng],
            [drop.lat, drop.lng]
          );
          map.fitBounds(bounds, { padding: [40, 40] });
        } else {
          setError("Could not calculate driving route. Setting straight line.");
          // Fallback straight line
          const straightCoords: [number, number][] = [
            [pickup.lat, pickup.lng],
            [drop.lat, drop.lng],
          ];
          if (polylineRef.current) {
            polylineRef.current.setLatLngs(straightCoords);
          } else {
            polylineRef.current = L.polyline(straightCoords, {
              color: "#ef4444",
              weight: 3,
              dashArray: "5, 5",
            }).addTo(map);
          }
          // Straight line estimation using simple math (Haversine approximation)
          const R = 6371; // km
          const dLat = ((drop.lat - pickup.lat) * Math.PI) / 180;
          const dLon = ((drop.lng - pickup.lng) * Math.PI) / 180;
          const a =
            Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos((pickup.lat * Math.PI) / 180) *
              Math.cos((drop.lat * Math.PI) / 180) *
              Math.sin(dLon / 2) *
              Math.sin(dLon / 2);
          const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
          const straightDist = Number((R * c).toFixed(2));
          setDistance(straightDist);
        }
        setLoading(false);
      });
    }
  }, [drop, pickup]);

  // Prop-sync: update state when parent updates coordinates (e.g. from autocomplete)
  useEffect(() => {
    if (initialPickupLat !== undefined && initialPickupLng !== undefined) {
      if (initialPickupLat === null || initialPickupLng === null) {
        if (pickupMarkerRef.current) {
          pickupMarkerRef.current.remove();
          pickupMarkerRef.current = null;
        }
        setPickup(null);
      } else {
        const targetCity = pickupCityProp || "";
        if (!pickup || Math.abs(pickup.lat - initialPickupLat) > 0.0001 || Math.abs(pickup.lng - initialPickupLng) > 0.0001) {
          setPickup({ lat: initialPickupLat, lng: initialPickupLng, city: targetCity });
        }
      }
    }
  }, [initialPickupLat, initialPickupLng, pickupCityProp]);

  useEffect(() => {
    if (initialDropLat !== undefined && initialDropLng !== undefined) {
      if (initialDropLat === null || initialDropLng === null) {
        if (dropMarkerRef.current) {
          dropMarkerRef.current.remove();
          dropMarkerRef.current = null;
        }
        setDrop(null);
      } else {
        const targetCity = dropCityProp || "";
        if (!drop || Math.abs(drop.lat - initialDropLat) > 0.0001 || Math.abs(drop.lng - initialDropLng) > 0.0001) {
          setDrop({ lat: initialDropLat, lng: initialDropLng, city: targetCity });
        }
      }
    }
  }, [initialDropLat, initialDropLng, dropCityProp]);

  // Synchronize locations back to parent component
  useEffect(() => {
    onLocationSelected({
      pickupLat: pickup?.lat ?? null,
      pickupLng: pickup?.lng ?? null,
      pickupCity: pickup?.city ?? "",
      dropLat: drop?.lat ?? null,
      dropLng: drop?.lng ?? null,
      dropCity: drop?.city ?? "",
      distanceKm: distance,
    });
  }, [pickup, drop, distance]);

  // Helper to clear map inputs
  const handleResetMap = () => {
    if (polylineRef.current) {
      polylineRef.current.remove();
      polylineRef.current = null;
    }
    if (pickupMarkerRef.current) {
      pickupMarkerRef.current.remove();
      pickupMarkerRef.current = null;
    }
    if (dropMarkerRef.current) {
      dropMarkerRef.current.remove();
      dropMarkerRef.current = null;
    }
    setPickup(null);
    setDrop(null);
    setDistance(null);
    setError(null);
    if (mapRef.current) {
      mapRef.current.setView([18.5204, 73.8567], 8);
    }
  };

  return (
    <div style={{ position: "relative", width: "100%", marginTop: 12, marginBottom: 12 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 6,
        }}
      >
        <span style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>
          INTERACTIVE ROUTE MAP
        </span>
        {(pickup || drop) && (
          <button
            type="button"
            onClick={handleResetMap}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--danger)",
              fontSize: 12,
              cursor: "pointer",
              padding: 0,
              fontWeight: 500,
            }}
          >
            Clear Pins
          </button>
        )}
      </div>

      <div
        ref={mapContainerRef}
        style={{
          height: 260,
          width: "100%",
          borderRadius: 8,
          border: "1px solid var(--line)",
          background: "var(--panel-strong)",
          zIndex: 10,
        }}
      />

      <div
        style={{
          marginTop: 8,
          fontSize: 12,
          color: "var(--muted)",
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981", display: "inline-block" }}></span>
          Pickup: <strong style={{ color: "#fff" }}>{pickup ? `${pickup.city} (${pickup.lat.toFixed(4)}, ${pickup.lng.toFixed(4)})` : "Not set (Click map)"}</strong>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ef4444", display: "inline-block" }}></span>
          Drop: <strong style={{ color: "#fff" }}>{drop ? `${drop.city} (${drop.lat.toFixed(4)}, ${drop.lng.toFixed(4)})` : "Not set (Click map)"}</strong>
        </span>
        {distance !== null && (
          <span style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#3b82f6", display: "inline-block" }}></span>
            Calculated Route Distance: <strong style={{ color: "var(--accent)", fontSize: 13 }}>{distance} km</strong>
          </span>
        )}
      </div>

      {loading && (
        <div
          style={{
            position: "absolute",
            top: 28,
            right: 8,
            background: "rgba(0,0,0,0.75)",
            padding: "4px 8px",
            borderRadius: 4,
            color: "#fff",
            fontSize: 11,
            zIndex: 100,
            pointerEvents: "none",
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          Updating route...
        </div>
      )}

      {error && (
        <div
          style={{
            color: "var(--danger)",
            fontSize: 11,
            marginTop: 4,
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
}
