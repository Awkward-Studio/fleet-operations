"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { 
  getPortalPackages, 
  getPortalQuote, 
  getGuestProfiles, 
  createBookingRequest, 
  RentalPackage, 
  GuestProfile, 
  SignedQuoteResponse 
} from "@/lib/rentalsApi";
import { ArrowLeft, Loader2, AlertCircle, Check } from "lucide-react";
import Link from "next/link";

export default function NewBookingRequest() {
  const { user } = useAuth();
  const router = useRouter();

  // Seeding states
  const [guests, setGuests] = useState<GuestProfile[]>([]);
  const [packages, setPackages] = useState<RentalPackage[]>([]);
  const [loadingGuests, setLoadingGuests] = useState(true);

  // Form states
  const [useGuestDir, setUseGuestDir] = useState(true);
  const [selectedGuestId, setSelectedGuestId] = useState<string>("");
  const [passengerName, setPassengerName] = useState("");
  const [passengerPhone, setPassengerPhone] = useState("");
  const [passengerEmail, setPassengerEmail] = useState("");

  const [pickupCity, setPickupCity] = useState("Mumbai");
  const [selectedPackageId, setSelectedPackageId] = useState<string>("");
  const [vehicleCategory, setVehicleCategory] = useState("Sedan");
  const [pickupAddress, setPickupAddress] = useState("");
  const [dropAddress, setDropAddress] = useState("");
  const [pickupAt, setPickupAt] = useState("");
  const [expectedReturnAt, setExpectedReturnAt] = useState("");
  const [costCentre, setCostCentre] = useState("");
  const [poReference, setPoReference] = useState("");

  // Quote state
  const [quote, setQuote] = useState<SignedQuoteResponse | null>(null);
  const [loadingQuote, setLoadingQuote] = useState(false);
  const [quoteError, setQuoteError] = useState<string | null>(null);

  // Submit states
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const activeCompany = user?.active_memberships?.[0];

  useEffect(() => {
    async function loadGuests() {
      try {
        const data = await getGuestProfiles();
        setGuests(data);
      } catch (err) {
        console.error("Failed to load guests:", err);
      } finally {
        setLoadingGuests(false);
      }
    }
    loadGuests();
  }, []);

  // Reload packages when city changes
  useEffect(() => {
    async function loadPackages() {
      if (!activeCompany) return;
      try {
        const data = await getPortalPackages(activeCompany.company_id, pickupCity);
        setPackages(data);
        if (data.length > 0) {
          setSelectedPackageId(String(data[0].id));
        } else {
          setSelectedPackageId("");
        }
      } catch (err) {
        console.error("Failed to load packages:", err);
      }
    }
    loadPackages();
  }, [pickupCity, activeCompany]);

  // Fetch quote when city, package, category change
  useEffect(() => {
    async function fetchQuote() {
      if (!activeCompany || !pickupCity || !selectedPackageId || !vehicleCategory) {
        setQuote(null);
        return;
      }
      setLoadingQuote(true);
      setQuoteError(null);
      try {
        const data = await getPortalQuote({
          company_id: activeCompany.company_id,
          pickup_city: pickupCity,
          package_id: parseInt(selectedPackageId),
          vehicle_category: vehicleCategory
        });
        setQuote(data);
      } catch (err) {
        setQuoteError(err instanceof Error ? err.message : "Unable to retrieve quote.");
        setQuote(null);
      } finally {
        setLoadingQuote(false);
      }
    }
    fetchQuote();
  }, [pickupCity, selectedPackageId, vehicleCategory, activeCompany]);

  // Sync guest fields if a guest profile is selected
  useEffect(() => {
    if (useGuestDir && selectedGuestId) {
      const g = guests.find(guest => String(guest.id) === selectedGuestId);
      if (g) {
        setPassengerName(g.name);
        setPassengerPhone(g.phone);
        setPassengerEmail(g.email || "");
      }
    }
  }, [selectedGuestId, useGuestDir, guests]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!activeCompany) return;

    setSubmitting(true);
    setFormError(null);

    const payload = {
      company: activeCompany.company_id,
      guest: useGuestDir && selectedGuestId ? parseInt(selectedGuestId) : null,
      passenger_name: passengerName,
      passenger_phone: passengerPhone,
      passenger_email: passengerEmail || undefined,
      pickup_city: pickupCity,
      package: parseInt(selectedPackageId),
      vehicle_category: vehicleCategory,
      pickup_address: pickupAddress,
      drop_address: dropAddress || undefined,
      pickup_at: new Date(pickupAt).toISOString(),
      expected_return_at: new Date(expectedReturnAt).toISOString(),
      cost_centre: costCentre || undefined,
      po_reference: poReference || undefined,
      quote_signature: quote?.signature || undefined
    };

    try {
      await createBookingRequest(payload);
      router.push("/portal");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to submit booking request.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px", maxWidth: "800px" }}>
      {/* Back button */}
      <div>
        <Link href="/portal" style={{ display: "inline-flex", alignItems: "center", gap: "8px", color: "var(--accent)", textDecoration: "none", fontSize: "14px", fontWeight: 600 }}>
          <ArrowLeft size={16} />
          Back to Dashboard
        </Link>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        <h2 style={{ fontSize: "24px", fontWeight: 800, color: "#fff", margin: 0 }}>Request Travel Booking</h2>
        <p style={{ color: "var(--muted)", margin: 0 }}>Discover rates and request a trip for your corporate guest or employee.</p>
      </div>

      {formError && (
        <div className="error" style={{ display: "flex", alignItems: "center", gap: "8px", padding: "16px" }}>
          <AlertCircle size={18} />
          {formError}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
        
        {/* Section 1: Passenger Info */}
        <div className="card" style={{ padding: "28px", display: "flex", flexDirection: "column", gap: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0, borderBottom: "1px solid var(--line)", paddingBottom: "12px" }}>Passenger Details</h3>
          
          <div style={{ display: "flex", gap: "24px" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px", cursor: "pointer" }}>
              <input type="radio" checked={useGuestDir} onChange={() => { setUseGuestDir(true); setPassengerName(""); setPassengerPhone(""); setPassengerEmail(""); }} />
              Select from Guest Directory
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px", cursor: "pointer" }}>
              <input type="radio" checked={!useGuestDir} onChange={() => { setUseGuestDir(false); setSelectedGuestId(""); setPassengerName(""); setPassengerPhone(""); setPassengerEmail(""); }} />
              Enter Details Manually
            </label>
          </div>

          {useGuestDir ? (
            <div className="field">
              <label>Select Guest Profile</label>
              {loadingGuests ? (
                <div>Loading guests...</div>
              ) : (
                <select value={selectedGuestId} onChange={(e) => setSelectedGuestId(e.target.value)} required>
                  <option value="">-- Choose Profile --</option>
                  {guests.map(g => (
                    <option key={g.id} value={g.id}>{g.name} ({g.phone})</option>
                  ))}
                </select>
              )}
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
              <div className="field">
                <label>Passenger Name</label>
                <input type="text" placeholder="John Doe" value={passengerName} onChange={e => setPassengerName(e.target.value)} required />
              </div>
              <div className="field">
                <label>Passenger Phone</label>
                <input type="tel" placeholder="9876543210" value={passengerPhone} onChange={e => setPassengerPhone(e.target.value)} required />
              </div>
              <div className="field" style={{ gridColumn: "span 2" }}>
                <label>Passenger Email (Optional)</label>
                <input type="email" placeholder="john.doe@example.com" value={passengerEmail} onChange={e => setPassengerEmail(e.target.value)} />
              </div>
            </div>
          )}
        </div>

        {/* Section 2: Itinerary & Vehicle */}
        <div className="card" style={{ padding: "28px", display: "flex", flexDirection: "column", gap: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0, borderBottom: "1px solid var(--line)", paddingBottom: "12px" }}>Itinerary Details</h3>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
            <div className="field">
              <label>Pickup City</label>
              <select value={pickupCity} onChange={e => setPickupCity(e.target.value)}>
                <option value="Mumbai">Mumbai</option>
                <option value="Pune">Pune</option>
                <option value="Delhi">Delhi</option>
                <option value="Bengaluru">Bengaluru</option>
              </select>
            </div>

            <div className="field">
              <label>Vehicle Category</label>
              <select value={vehicleCategory} onChange={e => setVehicleCategory(e.target.value)}>
                <option value="Sedan">Sedan</option>
                <option value="SUV">SUV (Innova / Ertiga)</option>
                <option value="Luxury">Luxury Sedan</option>
              </select>
            </div>

            <div className="field" style={{ gridColumn: "span 2" }}>
              <label>Rental Package (Contracted)</label>
              <select value={selectedPackageId} onChange={e => setSelectedPackageId(e.target.value)} required>
                {packages.length === 0 ? (
                  <option value="">No active packages discovered for this city</option>
                ) : (
                  packages.map(p => (
                    <option key={p.id} value={p.id}>{p.name} (Hours: {p.included_hours}, Km: {p.included_km})</option>
                  ))
                )}
              </select>
            </div>

            <div className="field" style={{ gridColumn: "span 2" }}>
              <label>Pickup Address</label>
              <textarea placeholder="Specify terminal gates, hotel name, or complete pickup address" value={pickupAddress} onChange={e => setPickupAddress(e.target.value)} required style={{ minHeight: "80px", resize: "vertical" }} />
            </div>

            <div className="field" style={{ gridColumn: "span 2" }}>
              <label>Drop Address (Optional)</label>
              <textarea placeholder="Destination address" value={dropAddress} onChange={e => setDropAddress(e.target.value)} style={{ minHeight: "80px", resize: "vertical" }} />
            </div>

            <div className="field">
              <label>Pickup Date & Time</label>
              <input type="datetime-local" value={pickupAt} onChange={e => setPickupAt(e.target.value)} required />
            </div>

            <div className="field">
              <label>Expected Return Date & Time</label>
              <input type="datetime-local" value={expectedReturnAt} onChange={e => setExpectedReturnAt(e.target.value)} required />
            </div>
          </div>
        </div>

        {/* Section 3: Cost Center, PO, and Quotes */}
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "20px", alignItems: "start" }}>
          {/* Policy Fields */}
          <div className="card" style={{ padding: "28px", display: "flex", flexDirection: "column", gap: "24px" }}>
            <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0, borderBottom: "1px solid var(--line)", paddingBottom: "12px" }}>Billing References</h3>
            <div className="field">
              <label>Cost Centre</label>
              <input type="text" placeholder="e.g. HR-MUMBAI-02" value={costCentre} onChange={e => setCostCentre(e.target.value)} />
            </div>
            <div className="field">
              <label>Purchase Order (PO) Reference</label>
              <input type="text" placeholder="e.g. PO-882291" value={poReference} onChange={e => setPoReference(e.target.value)} />
            </div>
          </div>

          {/* Pricing Quote card */}
          <div className="card" style={{
            padding: "28px",
            background: "linear-gradient(145deg, #1f2538 0%, #151a29 100%)",
            border: "1px solid var(--accent)",
            boxShadow: "0 8px 30px var(--accent-glow)",
            display: "flex",
            flexDirection: "column",
            gap: "20px"
          }}>
            <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              Authoritative Quote
              {loadingQuote && <Loader2 size={16} className="animate-spin" />}
            </h3>

            {quoteError && (
              <div style={{ color: "#ef4444", fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}>
                <AlertCircle size={14} />
                {quoteError}
              </div>
            )}

            {!quote && !loadingQuote && !quoteError && (
              <div style={{ color: "var(--muted)", fontSize: "13px", textAlign: "center", padding: "20px 0" }}>
                Select city, package, and vehicle category to compute quote pricing.
              </div>
            )}

            {quote && (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid rgba(255,255,255,0.06)", paddingBottom: "8px" }}>
                  <span style={{ color: "var(--muted)", fontSize: "13px" }}>Base Price:</span>
                  <strong style={{ color: "#fff", fontSize: "15px" }}>₹{parseFloat(quote.base_price).toFixed(2)}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid rgba(255,255,255,0.06)", paddingBottom: "8px" }}>
                  <span style={{ color: "var(--muted)", fontSize: "13px" }}>Allowance per day:</span>
                  <strong style={{ color: "#fff", fontSize: "14px" }}>₹{parseFloat(quote.driver_allowance).toFixed(2)}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid rgba(255,255,255,0.06)", paddingBottom: "8px" }}>
                  <span style={{ color: "var(--muted)", fontSize: "13px" }}>Included Distance:</span>
                  <strong style={{ color: "#fff", fontSize: "14px" }}>{quote.included_km} km</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid rgba(255,255,255,0.06)", paddingBottom: "8px" }}>
                  <span style={{ color: "var(--muted)", fontSize: "13px" }}>Included Time:</span>
                  <strong style={{ color: "#fff", fontSize: "14px" }}>{quote.included_hours} hours</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid rgba(255,255,255,0.06)", paddingBottom: "8px" }}>
                  <span style={{ color: "var(--muted)", fontSize: "12px" }}>Extra Charges:</span>
                  <span style={{ color: "var(--muted)", fontSize: "12px", textAlign: "right" }}>
                    ₹{quote.extra_km_rate}/km • ₹{quote.extra_hour_rate}/hour
                  </span>
                </div>
                <div style={{
                  background: "rgba(16,185,129,0.08)",
                  border: "1px solid rgba(16,185,129,0.2)",
                  borderRadius: "8px",
                  padding: "10px",
                  fontSize: "11px",
                  color: "#10b981",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px"
                }}>
                  <Check size={14} />
                  Cryptographic Quote Signed & Verified
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Submit */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "16px" }}>
          <Link href="/portal" className="button secondary" style={{ textDecoration: "none" }}>
            Cancel
          </Link>
          <button type="submit" className="button" disabled={submitting || !quote} style={{ minWidth: "160px" }}>
            {submitting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Submitting...
              </>
            ) : (
              "Submit Request"
            )}
          </button>
        </div>

      </form>
    </div>
  );
}
