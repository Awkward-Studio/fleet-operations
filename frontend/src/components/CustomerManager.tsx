"use client";

import React, { useState, useEffect } from "react";
import {
  Building2,
  Users,
  FileText,
  Search,
  Plus,
  Pencil,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Mail,
  Phone,
  Shield,
  CreditCard,
  Check,
  X,
  FileCheck
} from "lucide-react";
import {
  CorporateCustomer,
  CustomerContact,
  CorporateContract,
  getCustomers,
  createCustomer,
  updateCustomer,
  deleteCustomer,
  getCustomerContacts,
  createCustomerContact,
  updateCustomerContact,
  deleteCustomerContact,
  getContracts,
} from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";

type DetailTab = "overview" | "contacts" | "contracts" | "terms";

export default function CustomerManager() {
  const { user } = useAuth();
  const isCommercialAdmin =
    user?.role === "admin" ||
    user?.role === "commercial" ||
    user?.role === "accountant" ||
    user?.permissions?.includes("write_customers");

  const [customers, setCustomers] = useState<CorporateCustomer[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Search and Filters
  const [search, setSearch] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // Selection & Detail
  const [selectedCustomer, setSelectedCustomer] = useState<CorporateCustomer | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");
  const [customerContacts, setCustomerContacts] = useState<CustomerContact[]>([]);
  const [customerContracts, setCustomerContracts] = useState<CorporateContract[]>([]);

  // Modals
  const [showCustomerModal, setShowCustomerModal] = useState<boolean>(false);
  const [editingCustomer, setEditingCustomer] = useState<Partial<CorporateCustomer> | null>(null);
  const [showContactModal, setShowContactModal] = useState<boolean>(false);
  const [editingContact, setEditingContact] = useState<Partial<CustomerContact> | null>(null);

  useEffect(() => {
    fetchCustomers();
  }, [search, statusFilter]);

  useEffect(() => {
    if (selectedCustomer) {
      fetchCustomerDetails(selectedCustomer.id);
    }
  }, [selectedCustomer?.id]);

  const fetchCustomers = async () => {
    try {
      setLoading(true);
      setError(null);
      const params: any = {};
      if (search.trim()) params.search = search.trim();
      if (statusFilter !== "ALL") params.status = statusFilter;

      const data = await getCustomers(params);
      setCustomers(data);
      if (data.length > 0 && !selectedCustomer) {
        setSelectedCustomer(data[0]);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load customers.");
    } finally {
      setLoading(false);
    }
  };

  const fetchCustomerDetails = async (customerId: number) => {
    try {
      const [contacts, contracts] = await Promise.all([
        getCustomerContacts(customerId),
        getContracts({ customer: customerId }),
      ]);
      setCustomerContacts(contacts);
      setCustomerContracts(contracts);
    } catch (err: any) {
      console.error("Error fetching customer details:", err);
    }
  };

  const handleSaveCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCustomer) return;

    try {
      setError(null);
      if (editingCustomer.id) {
        const updated = await updateCustomer(editingCustomer.id, editingCustomer);
        setCustomers((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
        if (selectedCustomer?.id === updated.id) {
          setSelectedCustomer(updated);
        }
        setSuccess(`Customer '${updated.display_name}' updated successfully.`);
      } else {
        const created = await createCustomer(editingCustomer);
        setCustomers((prev) => [created, ...prev]);
        setSelectedCustomer(created);
        setSuccess(`Customer '${created.display_name}' created successfully.`);
      }
      setShowCustomerModal(false);
      setEditingCustomer(null);
    } catch (err: any) {
      setError(err.message || "Failed to save customer.");
    }
  };

  const handleDeactivateCustomer = async (customer: CorporateCustomer) => {
    if (!confirm(`Are you sure you want to deactivate '${customer.display_name}'?`)) return;

    try {
      setError(null);
      const res = await deleteCustomer(customer.id);
      setSuccess(res.detail || "Customer deactivated.");
      fetchCustomers();
      if (selectedCustomer?.id === customer.id) {
        setSelectedCustomer({ ...customer, is_active: false, status: "INACTIVE" });
      }
    } catch (err: any) {
      setError(err.message || "Failed to deactivate customer.");
    }
  };

  const handleSaveContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingContact || !selectedCustomer) return;

    try {
      setError(null);
      if (editingContact.id) {
        await updateCustomerContact(editingContact.id, editingContact);
        setSuccess("Contact updated successfully.");
      } else {
        await createCustomerContact(selectedCustomer.id, editingContact);
        setSuccess("Contact created successfully.");
      }
      setShowContactModal(false);
      setEditingContact(null);
      fetchCustomerDetails(selectedCustomer.id);
    } catch (err: any) {
      setError(err.message || "Failed to save contact.");
    }
  };

  const handleDeleteContact = async (contactId: number) => {
    if (!confirm("Are you sure you want to delete this contact?")) return;

    try {
      setError(null);
      await deleteCustomerContact(contactId);
      setSuccess("Contact deleted.");
      if (selectedCustomer) fetchCustomerDetails(selectedCustomer.id);
    } catch (err: any) {
      setError(err.message || "Failed to delete contact.");
    }
  };

  const activeCount = customers.filter((c) => c.status === "ACTIVE").length;
  const poRequiredCount = customers.filter((c) => c.po_required).length;

  return (
    <div className="stack" style={{ gap: 24 }}>
      {/* Top Metric Cards matching Console Design System */}
      <section className="metrics">
        <div className="metric">
          <div className="metric-header">
            <div style={{ background: "rgba(59, 73, 223, 0.15)", padding: 8, borderRadius: "50%", color: "var(--accent)" }}>
              <Building2 size={16} />
            </div>
            TOTAL CUSTOMERS
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{customers.length}</strong>
              <span>Corporate Accounts</span>
            </div>
            <div className="metric-trend up">
              <CheckCircle2 size={12} /> {activeCount} Active
            </div>
          </div>
        </div>

        <div className="metric">
          <div className="metric-header">
            <div style={{ background: "rgba(34, 197, 94, 0.15)", padding: 8, borderRadius: "50%", color: "var(--ok)" }}>
              <FileCheck size={16} />
            </div>
            CONTRACT COVERAGE
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{customers.filter((c) => c.active_contract_summary).length}</strong>
              <span>With Active Rates</span>
            </div>
            <div className="metric-trend live">Verified</div>
          </div>
        </div>

        <div className="metric">
          <div className="metric-header">
            <div style={{ background: "rgba(234, 179, 8, 0.15)", padding: 8, borderRadius: "50%", color: "var(--warn)" }}>
              <CreditCard size={16} />
            </div>
            CREDIT TERMS
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>30</strong>
              <span>Avg Credit Days</span>
            </div>
            <div className="metric-trend live">Standard</div>
          </div>
        </div>

        <div className="metric">
          <div className="metric-header">
            <div style={{ background: "rgba(139, 92, 246, 0.15)", padding: 8, borderRadius: "50%", color: "#8b5cf6" }}>
              <Shield size={16} />
            </div>
            PO MANDATORY
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{poRequiredCount}</strong>
              <span>Strict Accounts</span>
            </div>
            <div className="metric-trend live">Enforced</div>
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

      {/* Main Grid: Directory + Detail */}
      <section className="grid">
        {/* Left Column: Search & Directory List */}
        <div className="stack">
          {/* Search Filter Bar */}
          <div className="search-filter-bar">
            <div className="search-input-wrapper">
              <Search size={16} className="search-icon" />
              <input
                type="text"
                placeholder="Search by code, legal name, GSTIN..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="filter-select-wrapper">
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="ALL">All Statuses</option>
                <option value="ACTIVE">ACTIVE</option>
                <option value="INACTIVE">INACTIVE</option>
                <option value="SUSPENDED">SUSPENDED</option>
              </select>
            </div>
            {isCommercialAdmin && (
              <button
                className="button"
                style={{ whiteSpace: "nowrap" }}
                onClick={() => {
                  setEditingCustomer({
                    code: "",
                    legal_name: "",
                    display_name: "",
                    status: "ACTIVE",
                    is_active: true,
                    gstin: "",
                    billing_address: "",
                    billing_email: "",
                    billing_phone: "",
                    payment_terms_days: 30,
                    po_required: false,
                  });
                  setShowCustomerModal(true);
                }}
              >
                <Plus size={16} /> Add Corporate
              </button>
            )}
          </div>

          {/* Directory List Cards */}
          <div className="stack" style={{ maxHeight: 620, overflowY: "auto", paddingRight: 4 }}>
            {loading ? (
              <div style={{ padding: 32, textAlign: "center", color: "var(--muted)", fontSize: 14 }}>
                Loading corporate accounts...
              </div>
            ) : customers.length === 0 ? (
              <div className="availability-item" style={{ textAlign: "center", color: "var(--muted)", padding: 32 }}>
                No corporate accounts found.
              </div>
            ) : (
              customers.map((c) => {
                const isSelected = selectedCustomer?.id === c.id;
                return (
                  <div
                    key={c.id}
                    onClick={() => setSelectedCustomer(c)}
                    style={{
                      background: isSelected ? "var(--sidebar-active)" : "var(--panel)",
                      border: `1px solid ${isSelected ? "var(--accent)" : "var(--line)"}`,
                      borderRadius: 12,
                      padding: 16,
                      cursor: "pointer",
                      transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                      boxShadow: isSelected ? "0 4px 20px var(--accent-glow)" : "var(--card-shadow)"
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <strong style={{ color: "#fff", fontSize: 15 }}>{c.display_name}</strong>
                          <span style={{ fontSize: 11, fontFamily: "monospace", padding: "2px 6px", background: "rgba(255, 255, 255, 0.08)", borderRadius: 4, color: "var(--muted)" }}>
                            {c.code}
                          </span>
                        </div>
                        <span style={{ fontSize: 12, color: "var(--muted)", display: "block", marginTop: 4 }}>
                          {c.legal_name}
                        </span>
                      </div>
                      <span className={`status ${c.status === "ACTIVE" ? "ok" : c.status === "INACTIVE" ? "danger" : "warn"}`}>
                        {c.status}
                      </span>
                    </div>

                    <div style={{ display: "flex", justifyContent: "space-between", marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--line)", fontSize: 12, color: "var(--muted)" }}>
                      <div>
                        <span>GSTIN: </span>
                        <strong style={{ color: "#e2e8f0", fontFamily: "monospace" }}>{c.gstin || "N/A"}</strong>
                      </div>
                      <div>
                        <span>Credit: </span>
                        <strong style={{ color: "#e2e8f0" }}>{c.payment_terms_days} days</strong>
                      </div>
                    </div>

                    {c.active_contract_summary && (
                      <div style={{ marginTop: 10, padding: "6px 10px", background: "rgba(59, 73, 223, 0.12)", border: "1px solid rgba(59, 73, 223, 0.25)", borderRadius: 6, fontSize: 11, color: "#a5b4fc", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span>📄 {c.active_contract_summary.title}</span>
                        <span style={{ background: "rgba(0,0,0,0.3)", padding: "2px 6px", borderRadius: 4 }}>
                          {c.active_contract_summary.version_name}
                        </span>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Customer Details */}
        <div>
          {selectedCustomer ? (
            <div className="section">
              <div className="section-header" style={{ flexDirection: "column", alignItems: "stretch", gap: 12, padding: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <h2 style={{ fontSize: 20, margin: 0, color: "#fff" }}>{selectedCustomer.display_name}</h2>
                      <span style={{ background: "rgba(59, 73, 223, 0.2)", border: "1px solid var(--accent)", color: "#a5b4fc", padding: "2px 8px", borderRadius: 6, fontSize: 11, fontFamily: "monospace" }}>
                        {selectedCustomer.code}
                      </span>
                    </div>
                    <span style={{ fontSize: 13, color: "var(--muted)", marginTop: 4, display: "block" }}>
                      {selectedCustomer.legal_name}
                    </span>
                  </div>
                  {isCommercialAdmin && (
                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        className="button secondary"
                        style={{ padding: "6px 12px", fontSize: 12 }}
                        onClick={() => {
                          setEditingCustomer(selectedCustomer);
                          setShowCustomerModal(true);
                        }}
                      >
                        <Pencil size={14} /> Edit Profile
                      </button>
                      {selectedCustomer.is_active && (
                        <button
                          className="button secondary"
                          style={{ padding: "6px 12px", fontSize: 12, color: "var(--danger)" }}
                          onClick={() => handleDeactivateCustomer(selectedCustomer)}
                        >
                          <Trash2 size={14} /> Deactivate
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {/* Section Navigation Tabs */}
                <div style={{ display: "flex", gap: 8, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
                  {[
                    { id: "overview", label: "Overview" },
                    { id: "contacts", label: `Contacts (${customerContacts.length})` },
                    { id: "contracts", label: `Contracts (${customerContracts.length})` },
                    { id: "terms", label: "Billing & Terms" },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setDetailTab(tab.id as DetailTab)}
                      style={{
                        background: detailTab === tab.id ? "var(--sidebar-active)" : "transparent",
                        border: `1px solid ${detailTab === tab.id ? "var(--accent)" : "transparent"}`,
                        borderRadius: 6,
                        color: detailTab === tab.id ? "#fff" : "var(--muted)",
                        padding: "8px 14px",
                        fontSize: 13,
                        fontWeight: 600,
                        cursor: "pointer",
                        transition: "all 0.15s"
                      }}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="section-body" style={{ padding: 20 }}>
                {detailTab === "overview" && (
                  <div className="stack" style={{ gap: 16 }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                      <div className="availability-item">
                        <span style={{ fontSize: 11, textTransform: "uppercase", color: "var(--muted)", fontWeight: 700 }}>Account Status</span>
                        <strong style={{ fontSize: 16, marginTop: 4, display: "block" }}>{selectedCustomer.status}</strong>
                        <span style={{ fontSize: 12, marginTop: 4 }}>Active Record: {selectedCustomer.is_active ? "Yes" : "No"}</span>
                      </div>
                      <div className="availability-item">
                        <span style={{ fontSize: 11, textTransform: "uppercase", color: "var(--muted)", fontWeight: 700 }}>Tax Registration</span>
                        <strong style={{ fontSize: 16, marginTop: 4, display: "block", fontFamily: "monospace" }}>
                          {selectedCustomer.gstin || "Not Registered"}
                        </strong>
                        <span style={{ fontSize: 12, marginTop: 4 }}>GSTIN Verification Code</span>
                      </div>
                    </div>

                    <div className="availability-item">
                      <span style={{ fontSize: 11, textTransform: "uppercase", color: "var(--muted)", fontWeight: 700, display: "block", marginBottom: 6 }}>
                        Default Dispatch Contact
                      </span>
                      <strong style={{ fontSize: 15 }}>{selectedCustomer.booking_contact_name || "N/A"}</strong>
                      <div style={{ display: "flex", gap: 16, marginTop: 6, fontSize: 13, color: "var(--muted)" }}>
                        {selectedCustomer.booking_contact_email && <span>📧 {selectedCustomer.booking_contact_email}</span>}
                        {selectedCustomer.booking_contact_phone && <span>📞 {selectedCustomer.booking_contact_phone}</span>}
                      </div>
                    </div>

                    {selectedCustomer.notes && (
                      <div className="availability-item">
                        <span style={{ fontSize: 11, textTransform: "uppercase", color: "var(--muted)", fontWeight: 700, display: "block", marginBottom: 6 }}>
                          Account Notes & Operating Directives
                        </span>
                        <span style={{ fontSize: 13, color: "#e2e8f0", whiteSpace: "pre-wrap" }}>{selectedCustomer.notes}</span>
                      </div>
                    )}
                  </div>
                )}

                {detailTab === "contacts" && (
                  <div className="stack" style={{ gap: 16 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <strong style={{ color: "#fff", fontSize: 14 }}>Associated Account Contacts</strong>
                      {isCommercialAdmin && (
                        <button
                          className="button"
                          style={{ padding: "6px 12px", fontSize: 12 }}
                          onClick={() => {
                            setEditingContact({
                              name: "",
                              contact_type: "PRIMARY",
                              phone: "",
                              email: "",
                              is_primary: customerContacts.length === 0,
                            });
                            setShowContactModal(true);
                          }}
                        >
                          <Plus size={14} /> Add Contact
                        </button>
                      )}
                    </div>

                    {customerContacts.length === 0 ? (
                      <div className="availability-item" style={{ textAlign: "center", color: "var(--muted)", padding: 24 }}>
                        No contacts listed for this corporate account.
                      </div>
                    ) : (
                      <div className="stack" style={{ gap: 10 }}>
                        {customerContacts.map((ct) => (
                          <div key={ct.id} className="availability-item" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <div>
                              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <strong style={{ fontSize: 14 }}>{ct.name}</strong>
                                {ct.is_primary && (
                                  <span className="status ok" style={{ fontSize: 9 }}>PRIMARY</span>
                                )}
                                <span style={{ fontSize: 10, padding: "2px 6px", background: "rgba(255,255,255,0.06)", borderRadius: 4, color: "var(--muted)" }}>
                                  {ct.contact_type}
                                </span>
                              </div>
                              <div style={{ display: "flex", gap: 16, marginTop: 6, fontSize: 12, color: "var(--muted)" }}>
                                {ct.email && <span>📧 {ct.email}</span>}
                                {ct.phone && <span>📞 {ct.phone}</span>}
                              </div>
                            </div>
                            {isCommercialAdmin && (
                              <div style={{ display: "flex", gap: 6 }}>
                                <button
                                  className="button secondary"
                                  style={{ padding: "4px 8px", fontSize: 11 }}
                                  onClick={() => {
                                    setEditingContact(ct);
                                    setShowContactModal(true);
                                  }}
                                >
                                  Edit
                                </button>
                                <button
                                  className="button secondary"
                                  style={{ padding: "4px 8px", fontSize: 11, color: "var(--danger)" }}
                                  onClick={() => handleDeleteContact(ct.id)}
                                >
                                  Delete
                                </button>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {detailTab === "contracts" && (
                  <div className="stack" style={{ gap: 16 }}>
                    <strong style={{ color: "#fff", fontSize: 14 }}>Active & Draft Commercial Contracts</strong>
                    {customerContracts.length === 0 ? (
                      <div className="availability-item" style={{ textAlign: "center", color: "var(--muted)", padding: 24 }}>
                        No commercial rate contracts configured for this account.
                      </div>
                    ) : (
                      <div className="stack" style={{ gap: 10 }}>
                        {customerContracts.map((ctr) => (
                          <div key={ctr.id} className="availability-item">
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <div>
                                <strong style={{ fontSize: 15 }}>{ctr.title}</strong>
                                <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: 8 }}>({ctr.version_name})</span>
                              </div>
                              <span className={`status ${ctr.status === "ACTIVE" ? "ok" : "warn"}`}>
                                {ctr.status}
                              </span>
                            </div>
                            <div style={{ display: "flex", gap: 20, marginTop: 8, fontSize: 12, color: "var(--muted)" }}>
                              <span>Effective: {ctr.effective_start} to {ctr.effective_end || "Ongoing"}</span>
                              <span>Taxes: CGST {ctr.cgst_rate}% + SGST {ctr.sgst_rate}%</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {detailTab === "terms" && (
                  <div className="stack" style={{ gap: 16 }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                      <div className="availability-item">
                        <span style={{ fontSize: 11, textTransform: "uppercase", color: "var(--muted)", fontWeight: 700 }}>Payment Credit Window</span>
                        <strong style={{ fontSize: 20, marginTop: 4, display: "block", color: "var(--ok)" }}>
                          {selectedCustomer.payment_terms_days} Days
                        </strong>
                      </div>
                      <div className="availability-item">
                        <span style={{ fontSize: 11, textTransform: "uppercase", color: "var(--muted)", fontWeight: 700 }}>PO Enforcement</span>
                        <strong style={{ fontSize: 16, marginTop: 4, display: "block", color: selectedCustomer.po_required ? "var(--warn)" : "var(--muted)" }}>
                          {selectedCustomer.po_required ? "Mandatory Purchase Order" : "Optional PO"}
                        </strong>
                      </div>
                    </div>

                    <div className="availability-item">
                      <span style={{ fontSize: 11, textTransform: "uppercase", color: "var(--muted)", fontWeight: 700, display: "block", marginBottom: 6 }}>
                        Billing Identity & Address
                      </span>
                      <span style={{ fontSize: 13, color: "#fff", fontWeight: 600, display: "block" }}>{selectedCustomer.billing_email || "No email"}</span>
                      <span style={{ fontSize: 13, color: "var(--muted)", marginTop: 4, display: "block", whiteSpace: "pre-wrap" }}>
                        {selectedCustomer.billing_address || "No formal address recorded."}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="section" style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>
              Select a corporate account from the left directory list to view account details and contracts.
            </div>
          )}
        </div>
      </section>

      {/* Customer Modal */}
      {showCustomerModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", backdropFilter: "blur(8px)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div style={{ background: "var(--panel-strong)", border: "1px solid var(--line)", borderRadius: 16, width: "100%", maxWidth: 640, overflow: "hidden", boxShadow: "0 20px 50px rgba(0,0,0,0.6)" }}>
            <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: 18, color: "#fff" }}>
                {editingCustomer?.id ? "Edit Corporate Customer Profile" : "Create New Corporate Account"}
              </h3>
              <button onClick={() => setShowCustomerModal(false)} style={{ background: "none", border: 0, color: "var(--muted)", cursor: "pointer", fontSize: 18 }}>✕</button>
            </div>

            <form onSubmit={handleSaveCustomer} style={{ padding: 24 }} className="stack">
              <div className="form-grid">
                <div className="field">
                  <label>Customer Code *</label>
                  <input
                    type="text"
                    required
                    value={editingCustomer?.code || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, code: e.target.value })}
                    placeholder="e.g. ACME01"
                  />
                </div>
                <div className="field">
                  <label>Account Status</label>
                  <select
                    value={editingCustomer?.status || "ACTIVE"}
                    onChange={(e: any) => setEditingCustomer({ ...editingCustomer, status: e.target.value })}
                  >
                    <option value="ACTIVE">ACTIVE</option>
                    <option value="INACTIVE">INACTIVE</option>
                    <option value="SUSPENDED">SUSPENDED</option>
                  </select>
                </div>
              </div>

              <div className="form-grid">
                <div className="field">
                  <label>Display Name *</label>
                  <input
                    type="text"
                    required
                    value={editingCustomer?.display_name || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, display_name: e.target.value })}
                    placeholder="e.g. ACME Corp"
                  />
                </div>
                <div className="field">
                  <label>Legal Registered Name *</label>
                  <input
                    type="text"
                    required
                    value={editingCustomer?.legal_name || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, legal_name: e.target.value })}
                    placeholder="e.g. ACME Logistics Pvt Ltd"
                  />
                </div>
              </div>

              <div className="form-grid">
                <div className="field">
                  <label>GSTIN Number</label>
                  <input
                    type="text"
                    value={editingCustomer?.gstin || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, gstin: e.target.value })}
                    placeholder="27AAAAA0000A1Z5"
                    style={{ fontFamily: "monospace" }}
                  />
                </div>
                <div className="field">
                  <label>Credit Window (Days)</label>
                  <input
                    type="number"
                    value={editingCustomer?.payment_terms_days || 30}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, payment_terms_days: parseInt(e.target.value) || 0 })}
                  />
                </div>
              </div>

              <div className="form-grid">
                <div className="field">
                  <label>Billing Email</label>
                  <input
                    type="email"
                    value={editingCustomer?.billing_email || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, billing_email: e.target.value })}
                    placeholder="accounts@acme.com"
                  />
                </div>
                <div className="field">
                  <label>Billing Phone</label>
                  <input
                    type="text"
                    value={editingCustomer?.billing_phone || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, billing_phone: e.target.value })}
                    placeholder="+91 9876543210"
                  />
                </div>
              </div>

              <div className="field">
                <label>Billing Address</label>
                <textarea
                  rows={2}
                  value={editingCustomer?.billing_address || ""}
                  onChange={(e) => setEditingCustomer({ ...editingCustomer, billing_address: e.target.value })}
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 10, paddingTop: 4 }}>
                <input
                  type="checkbox"
                  id="po_required"
                  checked={editingCustomer?.po_required || false}
                  onChange={(e) => setEditingCustomer({ ...editingCustomer, po_required: e.target.checked })}
                />
                <label htmlFor="po_required" style={{ fontSize: 13, color: "#e2e8f0" }}>
                  Enforce Mandatory Purchase Order (PO) for trip dispatches
                </label>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
                <button type="button" className="button secondary" onClick={() => setShowCustomerModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="button">
                  Save Customer Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Contact Modal */}
      {showContactModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", backdropFilter: "blur(8px)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div style={{ background: "var(--panel-strong)", border: "1px solid var(--line)", borderRadius: 16, width: "100%", maxWidth: 440, overflow: "hidden", boxShadow: "0 20px 50px rgba(0,0,0,0.6)" }}>
            <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: 16, color: "#fff" }}>
                {editingContact?.id ? "Edit Account Contact" : "Add New Account Contact"}
              </h3>
              <button onClick={() => setShowContactModal(false)} style={{ background: "none", border: 0, color: "var(--muted)", cursor: "pointer", fontSize: 18 }}>✕</button>
            </div>

            <form onSubmit={handleSaveContact} style={{ padding: 20 }} className="stack">
              <div className="field">
                <label>Contact Name *</label>
                <input
                  type="text"
                  required
                  value={editingContact?.name || ""}
                  onChange={(e) => setEditingContact({ ...editingContact, name: e.target.value })}
                />
              </div>

              <div className="form-grid">
                <div className="field">
                  <label>Contact Role</label>
                  <select
                    value={editingContact?.contact_type || "PRIMARY"}
                    onChange={(e) => setEditingContact({ ...editingContact, contact_type: e.target.value })}
                  >
                    <option value="PRIMARY">PRIMARY</option>
                    <option value="BILLING">BILLING</option>
                    <option value="DISPATCH">DISPATCH</option>
                    <option value="COMMERCIAL">COMMERCIAL</option>
                    <option value="EMERGENCY">EMERGENCY</option>
                    <option value="OTHER">OTHER</option>
                  </select>
                </div>
                <div className="field">
                  <label>Phone Number</label>
                  <input
                    type="text"
                    value={editingContact?.phone || ""}
                    onChange={(e) => setEditingContact({ ...editingContact, phone: e.target.value })}
                  />
                </div>
              </div>

              <div className="field">
                <label>Email Address</label>
                <input
                  type="email"
                  value={editingContact?.email || ""}
                  onChange={(e) => setEditingContact({ ...editingContact, email: e.target.value })}
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8, paddingTop: 4 }}>
                <input
                  type="checkbox"
                  id="is_primary"
                  checked={editingContact?.is_primary || false}
                  onChange={(e) => setEditingContact({ ...editingContact, is_primary: e.target.checked })}
                />
                <label htmlFor="is_primary" style={{ fontSize: 13, color: "#e2e8f0" }}>Designate as primary contact</label>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
                <button type="button" className="button secondary" onClick={() => setShowContactModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="button">
                  Save Contact
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
