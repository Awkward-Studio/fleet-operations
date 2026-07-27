"use client";

import React, { useEffect, useState } from "react";
import { 
  getGuestProfiles, 
  createGuestProfile, 
  GuestProfile 
} from "@/lib/rentalsApi";
import { useAuth } from "@/lib/AuthContext";
import { Loader2, Plus, Users, Search, AlertCircle, CheckCircle2 } from "lucide-react";

export default function GuestDirectory() {
  const { user } = useAuth();
  const [guests, setGuests] = useState<GuestProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState("");

  // Add guest modal state
  const [isAdding, setIsAdding] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function loadGuests() {
    setLoading(true);
    setError(null);
    try {
      const data = await getGuestProfiles();
      setGuests(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load guest profiles.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadGuests();
  }, []);

  async function handleAddGuest(e: React.FormEvent) {
    e.preventDefault();
    if (!user?.active_memberships?.[0]) return;
    
    setAddError(null);
    setSuccess(null);
    
    try {
      await createGuestProfile({
        company: user.active_memberships[0].company_id,
        name: name,
        phone: phone,
        email: email || undefined,
        employee_id: employeeId || undefined,
        is_active: true
      });
      setIsAdding(false);
      setName("");
      setPhone("");
      setEmail("");
      setEmployeeId("");
      setSuccess("Guest profile added successfully!");
      setTimeout(() => setSuccess(null), 3000);
      await loadGuests();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Failed to add guest profile.");
    }
  }

  const filteredGuests = React.useMemo(() => {
    return guests.filter(g => 
      g.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      g.phone.includes(searchQuery) ||
      (g.email && g.email.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (g.employee_id && g.employee_id.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  }, [guests, searchQuery]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyItems: "center", justifyContent: "space-between" }}>
        <div>
          <h2 style={{ fontSize: "24px", fontWeight: 800, color: "#fff", margin: 0 }}>Guest Directory</h2>
          <p style={{ color: "var(--muted)", margin: "4px 0 0" }}>Manage profiles of employees and travelers associated with your company.</p>
        </div>
        <button className="button" onClick={() => setIsAdding(true)} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Plus size={16} />
          Add Guest Profile
        </button>
      </div>

      {success && (
        <div style={{
          background: "rgba(16,185,129,0.08)",
          border: "1px solid rgba(16,185,129,0.2)",
          padding: "16px",
          color: "#10b981",
          borderRadius: "8px",
          display: "flex",
          alignItems: "center",
          gap: "8px"
        }}>
          <CheckCircle2 size={18} />
          {success}
        </div>
      )}

      {/* Search Bar */}
      <div className="search-filter-bar" style={{ padding: 0, border: 0, background: "transparent", boxShadow: "none" }}>
        <div className="search-input-wrapper" style={{ flex: 1 }}>
          <Search size={18} className="search-icon" />
          <input 
            type="text" 
            placeholder="Search by guest name, phone, email, or employee ID..." 
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {error && (
        <div className="error" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Guest Directory table */}
      {loading ? (
        <div style={{ textAlign: "center", padding: "40px", color: "var(--muted)" }}>
          <Loader2 size={24} className="animate-spin" style={{ margin: "0 auto 12px" }} />
          Loading guest profiles...
        </div>
      ) : filteredGuests.length === 0 ? (
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
          <Users size={48} style={{ color: "var(--muted)" }} />
          <div>
            <h4 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", margin: 0 }}>No Guests Found</h4>
            <p style={{ color: "var(--muted)", margin: "4px 0 0", fontSize: "14px" }}>Start building your guest profile directory for quick bookings.</p>
          </div>
          <button className="button" onClick={() => setIsAdding(true)}>
            Add Guest Profile
          </button>
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
                <th style={{ padding: "16px 24px", color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>GUEST NAME</th>
                <th style={{ padding: "16px 24px", color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>PHONE NUMBER</th>
                <th style={{ padding: "16px 24px", color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>EMAIL ADDRESS</th>
                <th style={{ padding: "16px 24px", color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>EMPLOYEE ID</th>
                <th style={{ padding: "16px 24px", color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>STATUS</th>
              </tr>
            </thead>
            <tbody>
              {filteredGuests.map((g) => (
                <tr key={g.id} style={{ borderBottom: "1px solid var(--line)", transition: "background 0.2s" }} onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.01)"} onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
                  <td style={{ padding: "20px 24px", fontWeight: 600, color: "#fff" }}>{g.name}</td>
                  <td style={{ padding: "20px 24px" }}>{g.phone}</td>
                  <td style={{ padding: "20px 24px" }}>{g.email || "—"}</td>
                  <td style={{ padding: "20px 24px" }}>{g.employee_id || "—"}</td>
                  <td style={{ padding: "20px 24px" }}>
                    <span style={{
                      display: "inline-flex",
                      padding: "2px 6px",
                      borderRadius: "4px",
                      fontSize: "11px",
                      fontWeight: 600,
                      backgroundColor: g.is_active ? "rgba(16,185,129,0.1)" : "rgba(255,255,255,0.05)",
                      color: g.is_active ? "#10b981" : "var(--muted)"
                    }}>
                      {g.is_active ? "ACTIVE" : "INACTIVE"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Guest Modal */}
      {isAdding && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0,0,0,0.6)",
          backdropFilter: "blur(4px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 10000,
          padding: "20px"
        }}>
          <div className="card" style={{ width: "100%", maxWidth: "500px", padding: "32px", display: "flex", flexDirection: "column", gap: "24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ fontSize: "18px", fontWeight: 700, color: "#fff", margin: 0 }}>Add Guest Profile</h3>
              <button style={{ background: "transparent", border: 0, color: "var(--muted)", cursor: "pointer" }} onClick={() => setIsAdding(false)}>
                ✕
              </button>
            </div>

            {addError && <div style={{ color: "#ef4444", fontSize: "13px" }}>{addError}</div>}

            <form onSubmit={handleAddGuest} style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              <div className="field">
                <label>Full Name</label>
                <input type="text" placeholder="e.g. Alice Traveller" value={name} onChange={e => setName(e.target.value)} required />
              </div>
              <div className="field">
                <label>Phone Number</label>
                <input type="tel" placeholder="e.g. 9876543210" value={phone} onChange={e => setPhone(e.target.value)} required />
              </div>
              <div className="field">
                <label>Email Address (Optional)</label>
                <input type="email" placeholder="e.g. alice@example.com" value={email} onChange={e => setEmail(e.target.value)} />
              </div>
              <div className="field">
                <label>Employee ID (Optional)</label>
                <input type="text" placeholder="e.g. EMP102" value={employeeId} onChange={e => setEmployeeId(e.target.value)} />
              </div>
              <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end", marginTop: "8px" }}>
                <button type="button" className="button secondary" onClick={() => setIsAdding(false)}>
                  Cancel
                </button>
                <button type="submit" className="button">
                  Save Profile
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
