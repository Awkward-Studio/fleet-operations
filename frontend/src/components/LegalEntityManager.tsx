"use client";

import React, { useState, useEffect } from "react";
import {
  Building2,
  Landmark,
  Search,
  Plus,
  CheckCircle2,
  XCircle,
  Mail,
  Phone,
  FileText,
  X,
  Eye,
  CreditCard,
  Scale,
} from "lucide-react";
import {
  listBillingEntities,
  createBillingEntity,
  BillingLegalEntity,
} from "@/lib/billingApi";
import { useAuth } from "@/lib/AuthContext";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";

type DetailTab = "overview" | "bank" | "notes";

export default function LegalEntityManager() {
  const { user } = useAuth();
  const canManage =
    user?.role === "admin" ||
    user?.role === "accountant" ||
    user?.role === "commercial" ||
    user?.permissions?.includes("superuser");

  const [entities, setEntities] = useState<BillingLegalEntity[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Search and Filters
  const [search, setSearch] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // Selection & Detail Drawer
  const [selectedEntity, setSelectedEntity] = useState<BillingLegalEntity | null>(null);
  const [showDetailDrawer, setShowDetailDrawer] = useState<boolean>(false);
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");

  // Create Modal
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newEntity, setNewEntity] = useState<Partial<BillingLegalEntity>>({
    legal_name: "",
    trade_name: "",
    pan: "",
    gstin: "",
    state_code: "",
    registered_address: "",
    billing_email: "",
    billing_phone: "",
    bank_name: "",
    bank_account_number: "",
    ifsc_code: "",
    bank_branch: "",
    invoice_notes: "",
    is_active: true,
  });

  const fetchEntities = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listBillingEntities();
      setEntities(data);
    } catch (err: any) {
      setError(err.message || "Failed to load legal entities.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEntities();
  }, []);

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEntity.legal_name?.trim()) {
      setError("Legal name is required.");
      return;
    }

    try {
      setError(null);
      const created = await createBillingEntity(newEntity);
      setSuccess(`Legal entity '${created.legal_name}' created successfully.`);
      setShowCreateModal(false);
      // Reset form
      setNewEntity({
        legal_name: "",
        trade_name: "",
        pan: "",
        gstin: "",
        state_code: "",
        registered_address: "",
        billing_email: "",
        billing_phone: "",
        bank_name: "",
        bank_account_number: "",
        ifsc_code: "",
        bank_branch: "",
        invoice_notes: "",
        is_active: true,
      });
      fetchEntities();
    } catch (err: any) {
      setError(err.message || "Failed to create legal entity.");
    }
  };

  // Filter logic
  const filteredEntities = entities.filter((ent) => {
    const matchesSearch =
      search.trim() === "" ||
      ent.legal_name.toLowerCase().includes(search.toLowerCase()) ||
      (ent.trade_name && ent.trade_name.toLowerCase().includes(search.toLowerCase())) ||
      (ent.pan && ent.pan.toLowerCase().includes(search.toLowerCase())) ||
      (ent.gstin && ent.gstin.toLowerCase().includes(search.toLowerCase()));

    const matchesStatus =
      statusFilter === "ALL" ||
      (statusFilter === "ACTIVE" && ent.is_active) ||
      (statusFilter === "INACTIVE" && !ent.is_active);

    return matchesSearch && matchesStatus;
  });

  // Metrics
  const totalEntities = entities.length;
  const activeEntities = entities.filter((e) => e.is_active).length;
  const missingGstin = entities.filter((e) => !e.gstin).length;

  return (
    <div className="stack" style={{ gap: 24 }}>
      {/* Top Metrics Cards */}
      <section className="metrics">
        <div className="metric-card">
          <div className="metric-header">
            <div className="metric-icon" style={{ background: "rgba(59, 73, 223, 0.15)", color: "var(--accent)" }}>
              <Scale size={20} />
            </div>
            TOTAL ENTITIES
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{totalEntities}</strong>
              <span>Registered Internal Entities</span>
            </div>
            <div className="metric-trend live">Corporate Units</div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <div className="metric-icon" style={{ background: "rgba(34, 197, 94, 0.15)", color: "var(--ok)" }}>
              <CheckCircle2 size={20} />
            </div>
            ACTIVE ENTITIES
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{activeEntities}</strong>
              <span>Billing Units</span>
            </div>
            <div className="metric-trend ok">Operational</div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <div className="metric-icon" style={{ background: "rgba(234, 179, 8, 0.15)", color: "var(--warn)" }}>
              <Landmark size={20} />
            </div>
            WITHOUT GSTIN
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{missingGstin}</strong>
              <span>GST Registration Pending</span>
            </div>
            <div className="metric-trend live">Unregistered</div>
          </div>
        </div>
      </section>

      {/* Notifications */}
      {error && (
        <div style={{ padding: "12px 16px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.25)", borderRadius: 8, color: "var(--danger)", fontSize: 13, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{error}</span>
          <button onClick={() => setError(null)} style={{ background: "none", border: 0, color: "inherit", cursor: "pointer" }}>✕</button>
        </div>
      )}
      {success && (
        <div style={{ padding: "12px 16px", background: "rgba(34, 197, 94, 0.1)", border: "1px solid rgba(34, 197, 94, 0.25)", borderRadius: 8, color: "var(--ok)", fontSize: 13, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{success}</span>
          <button onClick={() => setSuccess(null)} style={{ background: "none", border: 0, color: "inherit", cursor: "pointer" }}>✕</button>
        </div>
      )}

      {/* Search & Filter Bar */}
      <div className="search-filter-bar">
        <div className="search-input-wrapper">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search by legal name, trade name, PAN, GSTIN..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="filter-select-wrapper">
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="ALL">All Statuses</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="INACTIVE">INACTIVE</option>
          </select>
        </div>
        {canManage && (
          <button
            className="button"
            style={{ whiteSpace: "nowrap" }}
            onClick={() => setShowCreateModal(true)}
          >
            <Plus size={16} /> Add Legal Entity
          </button>
        )}
      </div>

      {/* Table for Legal Entities */}
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Legal & Trade Name</TableHead>
              <TableHead>PAN</TableHead>
              <TableHead>GSTIN</TableHead>
              <TableHead>State Code</TableHead>
              <TableHead>Bank / Branch</TableHead>
              <TableHead>Status</TableHead>
              <TableHead style={{ textAlign: "right" }}>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                  Loading legal entities...
                </TableCell>
              </TableRow>
            ) : filteredEntities.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                  No internal legal entities found.
                </TableCell>
              </TableRow>
            ) : (
              filteredEntities.map((ent) => (
                <TableRow
                  key={ent.id}
                  onClick={() => {
                    setSelectedEntity(ent);
                    setShowDetailDrawer(true);
                  }}
                  style={{
                    cursor: "pointer",
                    background: selectedEntity?.id === ent.id ? "rgba(59, 73, 223, 0.08)" : "transparent",
                  }}
                >
                  <TableCell>
                    <div>
                      <strong style={{ color: "#fff", display: "block", fontSize: 14 }}>{ent.legal_name}</strong>
                      {ent.trade_name && (
                        <span style={{ fontSize: 12, color: "var(--muted)" }}>t/a {ent.trade_name}</span>
                      )}
                    </div>
                  </TableCell>

                  <TableCell>
                    <span style={{ fontFamily: "monospace", fontSize: 13, color: "#cbd5e1" }}>
                      {ent.pan || "—"}
                    </span>
                  </TableCell>

                  <TableCell>
                    <span style={{ fontFamily: "monospace", fontSize: 13, color: "#cbd5e1" }}>
                      {ent.gstin || "—"}
                    </span>
                  </TableCell>

                  <TableCell>
                    <span style={{ fontWeight: 600, color: "#fff" }}>
                      {ent.state_code || "—"}
                    </span>
                  </TableCell>

                  <TableCell>
                    {ent.bank_name ? (
                      <div>
                        <strong style={{ display: "block", fontSize: 13, color: "#cbd5e1" }}>{ent.bank_name}</strong>
                        <span style={{ fontSize: 11, color: "var(--muted)" }}>{ent.bank_branch || "Branch"}</span>
                      </div>
                    ) : (
                      <span style={{ color: "var(--muted)" }}>—</span>
                    )}
                  </TableCell>

                  <TableCell>
                    <span className={`status ${ent.is_active ? "ok" : "danger"}`}>
                      {ent.is_active ? "ACTIVE" : "INACTIVE"}
                    </span>
                  </TableCell>

                  <TableCell style={{ textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                      <button
                        className="button secondary"
                        style={{ padding: "6px 12px", fontSize: 12 }}
                        onClick={() => {
                          setSelectedEntity(ent);
                          setShowDetailDrawer(true);
                        }}
                      >
                        <Eye size={14} /> Details
                      </button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Detail Drawer */}
      {showDetailDrawer && selectedEntity && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0, 0, 0, 0.75)", backdropFilter: "blur(8px)", display: "flex", justifyContent: "flex-end", zIndex: 1000 }}>
          <div style={{ width: 680, maxWidth: "100%", background: "var(--panel-strong)", height: "100%", display: "flex", flexDirection: "column", borderLeft: "1px solid var(--line)", boxShadow: "-10px 0 30px rgba(0,0,0,0.5)" }}>
            {/* Drawer Header */}
            <div style={{ padding: 24, borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "flex-start", background: "rgba(15, 23, 42, 0.8)" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#fff" }}>{selectedEntity.legal_name}</h2>
                  <span className={`status ${selectedEntity.is_active ? "ok" : "danger"}`}>
                    {selectedEntity.is_active ? "ACTIVE" : "INACTIVE"}
                  </span>
                </div>
                {selectedEntity.trade_name && (
                  <span style={{ fontSize: 13, color: "var(--muted)", display: "block", marginTop: 4 }}>
                    Trade Name: <strong style={{ color: "#fff" }}>{selectedEntity.trade_name}</strong>
                  </span>
                )}
              </div>
              <button
                onClick={() => setShowDetailDrawer(false)}
                style={{ background: "none", border: 0, color: "var(--muted)", cursor: "pointer", padding: 6 }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Navigation Tabs */}
            <div style={{ display: "flex", borderBottom: "1px solid var(--line)", background: "rgba(0,0,0,0.2)", padding: "0 24px" }}>
              {(["overview", "bank", "notes"] as DetailTab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setDetailTab(tab)}
                  style={{
                    padding: "14px 18px",
                    background: "none",
                    border: 0,
                    borderBottom: detailTab === tab ? "2px solid var(--accent)" : "2px solid transparent",
                    color: detailTab === tab ? "#fff" : "var(--muted)",
                    fontWeight: detailTab === tab ? 600 : 400,
                    fontSize: 13,
                    cursor: "pointer",
                    textTransform: "capitalize",
                  }}
                >
                  {tab === "bank" ? "Bank Details" : tab === "notes" ? "Invoice Notes" : tab}
                </button>
              ))}
            </div>

            {/* Drawer Content */}
            <div style={{ flex: 1, overflowY: "auto", padding: 24 }} className="stack">
              {detailTab === "overview" && (
                <div className="stack" style={{ gap: 20 }}>
                  <div className="panel" style={{ padding: 18 }}>
                    <h4 style={{ margin: "0 0 14px", fontSize: 14, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                      Registration & Compliance
                    </h4>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, fontSize: 13 }}>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block" }}>PAN Number</span>
                        <strong style={{ color: "#fff", fontFamily: "monospace" }}>{selectedEntity.pan || "N/A"}</strong>
                      </div>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block" }}>GSTIN</span>
                        <strong style={{ color: "#fff", fontFamily: "monospace" }}>{selectedEntity.gstin || "N/A"}</strong>
                      </div>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block" }}>State Code</span>
                        <strong style={{ color: "#fff" }}>{selectedEntity.state_code || "N/A"}</strong>
                      </div>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block" }}>Billing Email</span>
                        <span style={{ color: "#fff" }}>{selectedEntity.billing_email || "N/A"}</span>
                      </div>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block" }}>Billing Phone</span>
                        <span style={{ color: "#fff" }}>{selectedEntity.billing_phone || "N/A"}</span>
                      </div>
                      <div style={{ gridColumn: "1 / -1" }}>
                        <span style={{ color: "var(--muted)", display: "block" }}>Registered Address</span>
                        <span style={{ color: "#fff" }}>{selectedEntity.registered_address || "N/A"}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {detailTab === "bank" && (
                <div className="panel" style={{ padding: 18 }}>
                  <h4 style={{ margin: "0 0 14px", fontSize: 14, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                    Remittance Accounts
                  </h4>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, fontSize: 13 }}>
                    <div>
                      <span style={{ color: "var(--muted)", display: "block" }}>Bank Name</span>
                      <strong style={{ color: "#fff" }}>{selectedEntity.bank_name || "N/A"}</strong>
                    </div>
                    <div>
                      <span style={{ color: "var(--muted)", display: "block" }}>Account Number</span>
                      <strong style={{ color: "#fff", fontFamily: "monospace" }}>{selectedEntity.bank_account_number || "N/A"}</strong>
                    </div>
                    <div>
                      <span style={{ color: "var(--muted)", display: "block" }}>IFSC Code</span>
                      <strong style={{ color: "#fff", fontFamily: "monospace" }}>{selectedEntity.ifsc_code || "N/A"}</strong>
                    </div>
                    <div>
                      <span style={{ color: "var(--muted)", display: "block" }}>Branch Name</span>
                      <strong style={{ color: "#fff" }}>{selectedEntity.bank_branch || "N/A"}</strong>
                    </div>
                  </div>
                </div>
              )}

              {detailTab === "notes" && (
                <div className="panel" style={{ padding: 18 }}>
                  <h4 style={{ margin: "0 0 14px", fontSize: 14, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                    Default Invoice Disclaimers & Notes
                  </h4>
                  <div style={{ fontSize: 13, color: "#fff", whiteSpace: "pre-wrap", background: "rgba(0,0,0,0.25)", padding: 12, borderRadius: 6, border: "1px solid var(--line)" }}>
                    {selectedEntity.invoice_notes || "No default notes configured for this entity."}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1100 }}>
          <div className="panel" style={{ width: 680, maxWidth: "90vw", padding: 24, maxHeight: "90vh", overflowY: "auto" }}>
            <h3 style={{ margin: "0 0 20px", color: "#fff", display: "flex", alignItems: "center", gap: 10 }}>
              <Building2 size={22} style={{ color: "var(--accent)" }} />
              New Internal Legal Entity
            </h3>
            <form onSubmit={handleCreateSubmit} className="stack" style={{ gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Legal Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Apex Fleet Operations Pvt Ltd"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newEntity.legal_name || ""}
                    onChange={(e) => setNewEntity({ ...newEntity, legal_name: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Trade / Brand Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Apex Fleet"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newEntity.trade_name || ""}
                    onChange={(e) => setNewEntity({ ...newEntity, trade_name: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>PAN Number</label>
                  <input
                    type="text"
                    placeholder="10-digit PAN"
                    maxLength={10}
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newEntity.pan || ""}
                    onChange={(e) => setNewEntity({ ...newEntity, pan: e.target.value.toUpperCase() })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>GSTIN Number</label>
                  <input
                    type="text"
                    placeholder="15-digit GSTIN"
                    maxLength={15}
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newEntity.gstin || ""}
                    onChange={(e) => setNewEntity({ ...newEntity, gstin: e.target.value.toUpperCase() })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>State Code</label>
                  <input
                    type="text"
                    placeholder="e.g. MH or 27"
                    maxLength={5}
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newEntity.state_code || ""}
                    onChange={(e) => setNewEntity({ ...newEntity, state_code: e.target.value.toUpperCase() })}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Billing Email</label>
                  <input
                    type="email"
                    placeholder="finance@yourcompany.com"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newEntity.billing_email || ""}
                    onChange={(e) => setNewEntity({ ...newEntity, billing_email: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Billing Phone</label>
                  <input
                    type="text"
                    placeholder="e.g. +91 99999 99999"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newEntity.billing_phone || ""}
                    onChange={(e) => setNewEntity({ ...newEntity, billing_phone: e.target.value })}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Registered Office Address</label>
                <textarea
                  rows={2}
                  placeholder="Complete registered physical address..."
                  style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff", resize: "vertical" }}
                  value={newEntity.registered_address || ""}
                  onChange={(e) => setNewEntity({ ...newEntity, registered_address: e.target.value })}
                />
              </div>

              <div style={{ borderTop: "1px solid var(--line)", paddingTop: 16 }}>
                <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--accent)" }}>Bank Account Details</h4>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Bank Name</label>
                    <input
                      type="text"
                      placeholder="e.g. HDFC Bank"
                      style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                      value={newEntity.bank_name || ""}
                      onChange={(e) => setNewEntity({ ...newEntity, bank_name: e.target.value })}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Account Number</label>
                    <input
                      type="text"
                      placeholder="Bank account number"
                      style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                      value={newEntity.bank_account_number || ""}
                      onChange={(newVal) => setNewEntity({ ...newEntity, bank_account_number: newVal.target.value })}
                    />
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>IFSC Code</label>
                    <input
                      type="text"
                      placeholder="11-digit IFSC"
                      maxLength={11}
                      style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                      value={newEntity.ifsc_code || ""}
                      onChange={(e) => setNewEntity({ ...newEntity, ifsc_code: e.target.value.toUpperCase() })}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Branch Name</label>
                    <input
                      type="text"
                      placeholder="Branch location"
                      style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                      value={newEntity.bank_branch || ""}
                      onChange={(e) => setNewEntity({ ...newEntity, bank_branch: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Default Invoice Notes & Disclaimers</label>
                <textarea
                  rows={2}
                  placeholder="Terms, bank guidelines, payment policies (will print on all tax invoices)..."
                  style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff", resize: "vertical" }}
                  value={newEntity.invoice_notes || ""}
                  onChange={(e) => setNewEntity({ ...newEntity, invoice_notes: e.target.value })}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 12 }}>
                <button type="button" className="button secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="button">
                  <Plus size={16} /> Create Entity
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
