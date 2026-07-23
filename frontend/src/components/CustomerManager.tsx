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
  FileCheck,
  Eye,
  ChevronRight,
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
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";

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

  // Selection & Detail Drawer
  const [selectedCustomer, setSelectedCustomer] = useState<CorporateCustomer | null>(null);
  const [showDetailDrawer, setShowDetailDrawer] = useState<boolean>(false);
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
    } catch (err: any) {
      setError(err.message || "Failed to load customers.");
    } finally {
      setLoading(false);
    }
  };

  const fetchCustomerDetails = async (customerId: number) => {
    try {
      const [contactsData, contractsData] = await Promise.all([
        getCustomerContacts(customerId),
        getContracts({ customer_id: customerId }),
      ]);
      setCustomerContacts(contactsData);
      setCustomerContracts(contractsData);
    } catch (err: any) {
      console.error("Failed to load customer sub-resources", err);
    }
  };

  const handleSaveCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCustomer) return;
    try {
      setError(null);
      if (editingCustomer.id) {
        const updated = await updateCustomer(editingCustomer.id, editingCustomer);
        setSuccess(`Corporate account '${updated.display_name}' updated successfully.`);
        if (selectedCustomer?.id === updated.id) {
          setSelectedCustomer(updated);
        }
      } else {
        const created = await createCustomer(editingCustomer);
        setSuccess(`Corporate account '${created.display_name}' created successfully.`);
        setSelectedCustomer(created);
        setShowDetailDrawer(true);
      }
      setShowCustomerModal(false);
      setEditingCustomer(null);
      fetchCustomers();
    } catch (err: any) {
      setError(err.message || "Failed to save customer.");
    }
  };

  const handleDeleteCustomer = async (cust: CorporateCustomer) => {
    if (!confirm(`Are you sure you want to delete corporate account '${cust.display_name}'?`)) return;
    try {
      setError(null);
      await deleteCustomer(cust.id);
      setSuccess(`Customer '${cust.display_name}' removed.`);
      if (selectedCustomer?.id === cust.id) {
        setSelectedCustomer(null);
        setShowDetailDrawer(false);
      }
      fetchCustomers();
    } catch (err: any) {
      setError(err.message || "Failed to delete customer.");
    }
  };

  const handleSaveContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustomer || !editingContact) return;
    try {
      setError(null);
      if (editingContact.id) {
        await updateCustomerContact(selectedCustomer.id, editingContact.id, editingContact);
        setSuccess("Contact updated.");
      } else {
        await createCustomerContact(selectedCustomer.id, editingContact);
        setSuccess("New contact added.");
      }
      setShowContactModal(false);
      setEditingContact(null);
      fetchCustomerDetails(selectedCustomer.id);
    } catch (err: any) {
      setError(err.message || "Failed to save contact.");
    }
  };

  const handleDeleteContact = async (contactId: number) => {
    if (!selectedCustomer) return;
    if (!confirm("Are you sure you want to delete this contact person?")) return;
    try {
      setError(null);
      await deleteCustomerContact(selectedCustomer.id, contactId);
      setSuccess("Contact removed.");
      fetchCustomerDetails(selectedCustomer.id);
    } catch (err: any) {
      setError(err.message || "Failed to delete contact.");
    }
  };

  // Metrics
  const totalCustomers = customers.length;
  const activeCustomers = customers.filter((c) => c.status === "ACTIVE").length;
  const poRequiredCount = customers.filter((c) => c.po_required).length;

  return (
    <div className="stack" style={{ gap: 24 }}>
      {/* Top Metrics Cards */}
      <section className="metrics">
        <div className="metric-card">
          <div className="metric-header">
            <div className="metric-icon" style={{ background: "rgba(59, 73, 223, 0.15)", color: "var(--accent)" }}>
              <Building2 size={20} />
            </div>
            TOTAL CORPORATES
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{totalCustomers}</strong>
              <span>Registered Accounts</span>
            </div>
            <div className="metric-trend live">Active System</div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <div className="metric-icon" style={{ background: "rgba(34, 197, 94, 0.15)", color: "var(--ok)" }}>
              <CheckCircle2 size={20} />
            </div>
            ACTIVE ACCOUNTS
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{activeCustomers}</strong>
              <span>Verified Commercial</span>
            </div>
            <div className="metric-trend ok">Operational</div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <div className="metric-icon" style={{ background: "rgba(234, 179, 8, 0.15)", color: "var(--warn)" }}>
              <Shield size={20} />
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

      {/* Search & Filter Bar */}
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
            <Plus size={16} /> Add Corporate Customer
          </button>
        )}
      </div>

      {/* Shadcn UI Table for Corporate Customers */}
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer Code</TableHead>
              <TableHead>Company & Display Name</TableHead>
              <TableHead>GSTIN</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Credit Terms</TableHead>
              <TableHead>PO Policy</TableHead>
              <TableHead>Active Contract</TableHead>
              <TableHead>Billing Email</TableHead>
              <TableHead style={{ textAlign: "right" }}>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={9} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                  Loading corporate accounts...
                </TableCell>
              </TableRow>
            ) : customers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                  No corporate accounts match your filter criteria.
                </TableCell>
              </TableRow>
            ) : (
              customers.map((c) => (
                <TableRow
                  key={c.id}
                  onClick={() => {
                    setSelectedCustomer(c);
                    setShowDetailDrawer(true);
                  }}
                  style={{
                    background: selectedCustomer?.id === c.id ? "rgba(59, 73, 223, 0.08)" : "transparent",
                  }}
                >
                  <TableCell>
                    <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--accent)", padding: "4px 8px", background: "rgba(59, 73, 223, 0.12)", borderRadius: 6 }}>
                      {c.code}
                    </span>
                  </TableCell>

                  <TableCell>
                    <div>
                      <strong style={{ color: "#fff", display: "block", fontSize: 14 }}>{c.display_name}</strong>
                      <span style={{ fontSize: 12, color: "var(--muted)" }}>{c.legal_name}</span>
                    </div>
                  </TableCell>

                  <TableCell>
                    <span style={{ fontFamily: "monospace", fontSize: 13, color: "#cbd5e1" }}>
                      {c.gstin || "N/A"}
                    </span>
                  </TableCell>

                  <TableCell>
                    <span className={`status ${c.status === "ACTIVE" ? "ok" : c.status === "INACTIVE" ? "danger" : "warn"}`}>
                      {c.status}
                    </span>
                  </TableCell>

                  <TableCell>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <CreditCard size={14} style={{ color: "var(--muted)" }} />
                      <span>{c.payment_terms_days} Days</span>
                    </div>
                  </TableCell>

                  <TableCell>
                    {c.po_required ? (
                      <span style={{ color: "var(--warn)", fontSize: 12, display: "flex", alignItems: "center", gap: 4, fontWeight: 600 }}>
                        <Shield size={13} /> Strict PO
                      </span>
                    ) : (
                      <span style={{ color: "var(--muted)", fontSize: 12 }}>Optional</span>
                    )}
                  </TableCell>

                  <TableCell>
                    {c.active_contract_summary ? (
                      <div style={{ fontSize: 12, color: "#a5b4fc", display: "flex", alignItems: "center", gap: 6 }}>
                        <FileCheck size={14} />
                        <span>{c.active_contract_summary.title}</span>
                      </div>
                    ) : (
                      <span style={{ fontSize: 12, color: "var(--muted)" }}>No Active Contract</span>
                    )}
                  </TableCell>

                  <TableCell>
                    <span style={{ fontSize: 13, color: "#cbd5e1" }}>{c.billing_email || "N/A"}</span>
                  </TableCell>

                  <TableCell style={{ textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                      <button
                        className="button secondary"
                        style={{ padding: "6px 12px", fontSize: 12 }}
                        onClick={() => {
                          setSelectedCustomer(c);
                          setShowDetailDrawer(true);
                        }}
                      >
                        <Eye size={14} /> Details
                      </button>
                      {isCommercialAdmin && (
                        <>
                          <button
                            className="button secondary"
                            style={{ padding: "6px 10px", fontSize: 12 }}
                            onClick={() => {
                              setEditingCustomer(c);
                              setShowCustomerModal(true);
                            }}
                          >
                            <Pencil size={13} />
                          </button>
                          <button
                            className="button secondary"
                            style={{ padding: "6px 10px", fontSize: 12, color: "var(--danger)" }}
                            onClick={() => handleDeleteCustomer(c)}
                          >
                            <Trash2 size={13} />
                          </button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Customer Detail Drawer / Modal */}
      {showDetailDrawer && selectedCustomer && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0, 0, 0, 0.75)", backdropFilter: "blur(8px)", display: "flex", justifyContent: "flex-end", zIndex: 1000 }}>
          <div style={{ width: 680, maxWidth: "100%", background: "var(--panel-strong)", height: "100%", display: "flex", flexDirection: "column", borderLeft: "1px solid var(--line)", boxShadow: "-10px 0 30px rgba(0,0,0,0.5)" }}>
            {/* Drawer Header */}
            <div style={{ padding: 24, borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "flex-start", background: "rgba(15, 23, 42, 0.8)" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#fff" }}>{selectedCustomer.display_name}</h2>
                  <span className={`status ${selectedCustomer.status === "ACTIVE" ? "ok" : "danger"}`}>
                    {selectedCustomer.status}
                  </span>
                </div>
                <span style={{ fontSize: 13, color: "var(--muted)", display: "block", marginTop: 4 }}>
                  Code: <strong style={{ color: "var(--accent)", fontFamily: "monospace" }}>{selectedCustomer.code}</strong> • {selectedCustomer.legal_name}
                </span>
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
              {(["overview", "contacts", "contracts", "terms"] as DetailTab[]).map((tab) => (
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
                  {tab}
                </button>
              ))}
            </div>

            {/* Drawer Content */}
            <div style={{ flex: 1, overflowY: "auto", padding: 24 }} className="stack">
              {detailTab === "overview" && (
                <div className="stack" style={{ gap: 20 }}>
                  <div className="panel" style={{ padding: 18 }}>
                    <h4 style={{ margin: "0 0 14px", fontSize: 14, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                      Company Profile & Tax Details
                    </h4>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, fontSize: 13 }}>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block" }}>Legal Name</span>
                        <strong style={{ color: "#fff" }}>{selectedCustomer.legal_name}</strong>
                      </div>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block" }}>GSTIN</span>
                        <strong style={{ color: "#fff", fontFamily: "monospace" }}>{selectedCustomer.gstin || "N/A"}</strong>
                      </div>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block" }}>Billing Email</span>
                        <span style={{ color: "#fff" }}>{selectedCustomer.billing_email || "N/A"}</span>
                      </div>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block" }}>Billing Phone</span>
                        <span style={{ color: "#fff" }}>{selectedCustomer.billing_phone || "N/A"}</span>
                      </div>
                      <div style={{ gridColumn: "1 / -1" }}>
                        <span style={{ color: "var(--muted)", display: "block" }}>Billing Address</span>
                        <span style={{ color: "#fff" }}>{selectedCustomer.billing_address || "N/A"}</span>
                      </div>
                    </div>
                  </div>

                  <div className="panel" style={{ padding: 18 }}>
                    <h4 style={{ margin: "0 0 14px", fontSize: 14, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                      Credit & Billing Rules
                    </h4>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, fontSize: 13 }}>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block" }}>Payment Terms</span>
                        <strong style={{ color: "#fff" }}>{selectedCustomer.payment_terms_days} Days Net</strong>
                      </div>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block" }}>Purchase Order</span>
                        <strong style={{ color: selectedCustomer.po_required ? "var(--warn)" : "#fff" }}>
                          {selectedCustomer.po_required ? "Mandatory for Invoicing" : "Optional"}
                        </strong>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {detailTab === "contacts" && (
                <div className="stack" style={{ gap: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <h4 style={{ margin: 0, fontSize: 14, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                      Authorized Contacts ({customerContacts.length})
                    </h4>
                    {isCommercialAdmin && (
                      <button
                        className="button"
                        style={{ padding: "6px 12px", fontSize: 12 }}
                        onClick={() => {
                          setEditingContact({
                            name: "",
                            designation: "",
                            email: "",
                            phone: "",
                            contact_type: "PRIMARY",
                            is_primary: customerContacts.length === 0,
                          });
                          setShowContactModal(true);
                        }}
                      >
                        <Plus size={14} /> Add Contact
                      </button>
                    )}
                  </div>

                  <div className="stack" style={{ gap: 10 }}>
                    {customerContacts.length === 0 ? (
                      <div style={{ textAlign: "center", color: "var(--muted)", padding: 24, background: "rgba(0,0,0,0.2)", borderRadius: 8 }}>
                        No contacts listed for this corporate account.
                      </div>
                    ) : (
                      customerContacts.map((contact) => (
                        <div key={contact.id} className="panel" style={{ padding: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <div>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <strong style={{ color: "#fff", fontSize: 14 }}>{contact.name}</strong>
                              <span style={{ fontSize: 11, padding: "2px 6px", background: "rgba(255,255,255,0.08)", borderRadius: 4, color: "var(--muted)" }}>
                                {contact.contact_type}
                              </span>
                              {contact.is_primary && (
                                <span style={{ fontSize: 10, padding: "2px 6px", background: "rgba(34, 197, 94, 0.15)", color: "var(--ok)", borderRadius: 4, fontWeight: 700 }}>
                                  PRIMARY
                                </span>
                              )}
                            </div>
                            <span style={{ fontSize: 12, color: "var(--muted)", display: "block", marginTop: 2 }}>{contact.designation || "N/A"}</span>
                            <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: 12, color: "#cbd5e1" }}>
                              {contact.email && <span><Mail size={12} style={{ inlineSize: 12, marginRight: 4 }} />{contact.email}</span>}
                              {contact.phone && <span><Phone size={12} style={{ inlineSize: 12, marginRight: 4 }} />{contact.phone}</span>}
                            </div>
                          </div>
                          {isCommercialAdmin && (
                            <div style={{ display: "flex", gap: 6 }}>
                              <button
                                className="button secondary"
                                style={{ padding: 6 }}
                                onClick={() => {
                                  setEditingContact(contact);
                                  setShowContactModal(true);
                                }}
                              >
                                <Pencil size={12} />
                              </button>
                              <button
                                className="button secondary"
                                style={{ padding: 6, color: "var(--danger)" }}
                                onClick={() => handleDeleteContact(contact.id)}
                              >
                                <Trash2 size={12} />
                              </button>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {detailTab === "contracts" && (
                <div className="stack" style={{ gap: 16 }}>
                  <h4 style={{ margin: 0, fontSize: 14, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                    Contract History ({customerContracts.length})
                  </h4>
                  {customerContracts.length === 0 ? (
                    <div style={{ textAlign: "center", color: "var(--muted)", padding: 24, background: "rgba(0,0,0,0.2)", borderRadius: 8 }}>
                      No contracts associated with this customer.
                    </div>
                  ) : (
                    customerContracts.map((contract) => (
                      <div key={contract.id} className="panel" style={{ padding: 16 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                          <div>
                            <strong style={{ color: "#fff", fontSize: 15 }}>{contract.title}</strong>
                            <span style={{ fontSize: 12, color: "var(--muted)", display: "block", marginTop: 2 }}>
                              Version: {contract.version_name} • Code: {contract.contract_code}
                            </span>
                          </div>
                          <span className={`status ${contract.status === "ACTIVE" ? "ok" : "warn"}`}>
                            {contract.status}
                          </span>
                        </div>
                        <div style={{ marginTop: 12, fontSize: 12, color: "var(--muted)", display: "flex", gap: 16 }}>
                          <span>Valid: <strong style={{ color: "#fff" }}>{contract.start_date}</strong> to <strong style={{ color: "#fff" }}>{contract.end_date || "Ongoing"}</strong></span>
                          <span>Rates: <strong style={{ color: "#fff" }}>{contract.rates_count} Packages</strong></span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {detailTab === "terms" && (
                <div className="panel" style={{ padding: 18 }}>
                  <h4 style={{ margin: "0 0 14px", fontSize: 14, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                    SLA & Commercial Policies
                  </h4>
                  <div className="stack" style={{ gap: 12, fontSize: 13, color: "#cbd5e1" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--line)", paddingBottom: 8 }}>
                      <span>Garage to Garage Metering</span>
                      <strong style={{ color: "#fff" }}>Enforced</strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--line)", paddingBottom: 8 }}>
                      <span>Toll & Parking Reimbursement</span>
                      <strong style={{ color: "#fff" }}>Actuals Attached to Invoice</strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--line)", paddingBottom: 8 }}>
                      <span>GST Rate Applicability</span>
                      <strong style={{ color: "#fff" }}>5% SAC 9966 (RCM/Forward)</strong>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Customer Create/Edit Modal */}
      {showCustomerModal && editingCustomer && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1100 }}>
          <div className="panel" style={{ width: 560, maxWidth: "90vw", padding: 24 }}>
            <h3 style={{ margin: "0 0 20px", color: "#fff" }}>
              {editingCustomer.id ? "Edit Corporate Customer" : "New Corporate Customer"}
            </h3>
            <form onSubmit={handleSaveCustomer} className="stack" style={{ gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Customer Code *</label>
                  <input
                    type="text"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingCustomer.code || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, code: e.target.value.toUpperCase() })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Status</label>
                  <select
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingCustomer.status || "ACTIVE"}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, status: e.target.value as any })}
                  >
                    <option value="ACTIVE">ACTIVE</option>
                    <option value="INACTIVE">INACTIVE</option>
                    <option value="SUSPENDED">SUSPENDED</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Display Name *</label>
                <input
                  type="text"
                  required
                  style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                  value={editingCustomer.display_name || ""}
                  onChange={(e) => setEditingCustomer({ ...editingCustomer, display_name: e.target.value })}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Legal Name *</label>
                <input
                  type="text"
                  required
                  style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                  value={editingCustomer.legal_name || ""}
                  onChange={(e) => setEditingCustomer({ ...editingCustomer, legal_name: e.target.value })}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>GSTIN Number</label>
                  <input
                    type="text"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingCustomer.gstin || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, gstin: e.target.value.toUpperCase() })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Payment Terms (Days)</label>
                  <input
                    type="number"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingCustomer.payment_terms_days || 30}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, payment_terms_days: parseInt(e.target.value) })}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Billing Email</label>
                  <input
                    type="email"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingCustomer.billing_email || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, billing_email: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Billing Phone</label>
                  <input
                    type="text"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingCustomer.billing_phone || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, billing_phone: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                <input
                  type="checkbox"
                  id="po_req"
                  checked={editingCustomer.po_required || false}
                  onChange={(e) => setEditingCustomer({ ...editingCustomer, po_required: e.target.checked })}
                />
                <label htmlFor="po_req" style={{ fontSize: 13, color: "#fff", cursor: "pointer" }}>
                  Require Purchase Order (PO) number for invoicing
                </label>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 12 }}>
                <button type="button" className="button secondary" onClick={() => setShowCustomerModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="button">
                  Save Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Contact Modal */}
      {showContactModal && editingContact && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1200 }}>
          <div className="panel" style={{ width: 440, maxWidth: "90vw", padding: 24 }}>
            <h3 style={{ margin: "0 0 16px", color: "#fff" }}>
              {editingContact.id ? "Edit Contact" : "Add Authorized Contact"}
            </h3>
            <form onSubmit={handleSaveContact} className="stack" style={{ gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Contact Name *</label>
                <input
                  type="text"
                  required
                  style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                  value={editingContact.name || ""}
                  onChange={(e) => setEditingContact({ ...editingContact, name: e.target.value })}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Designation</label>
                <input
                  type="text"
                  style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                  value={editingContact.designation || ""}
                  onChange={(e) => setEditingContact({ ...editingContact, designation: e.target.value })}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Email</label>
                  <input
                    type="email"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContact.email || ""}
                    onChange={(e) => setEditingContact({ ...editingContact, email: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Phone</label>
                  <input
                    type="text"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContact.phone || ""}
                    onChange={(e) => setEditingContact({ ...editingContact, phone: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 12 }}>
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
