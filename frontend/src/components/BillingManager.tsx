"use client";

import React, { useState, useEffect } from "react";
import {
  Receipt,
  FileText,
  Plus,
  Search,
  CheckCircle2,
  AlertTriangle,
  FileCheck,
  Building2,
  DollarSign,
  Download,
  Eye,
  Send,
  Calendar,
  CreditCard,
  Layers,
  ArrowUpRight,
  Filter,
  Check,
  X,
  Clock,
  RefreshCw,
} from "lucide-react";
import { useAuth } from "@/lib/AuthContext";

interface LegalEntity {
  id: number;
  legal_name: string;
  gstin: string;
}

interface InvoiceLine {
  id: number;
  description: string;
  sac_hsn_code: string;
  quantity: number;
  unit_rate: string;
  taxable_value: string;
  cgst_amount: string;
  sgst_amount: string;
  line_total: string;
}

interface Invoice {
  id: number;
  invoice_number: string | null;
  legal_entity_name: string;
  customer_name: string;
  status: "DRAFT" | "ISSUED" | "SENT" | "PARTIALLY_PAID" | "PAID" | "VOID";
  subtotal: string;
  taxable_amount: string;
  cgst_amount: string;
  sgst_amount: string;
  total_amount: string;
  paid_amount: string;
  balance_amount: string;
  issue_date: string | null;
  due_date: string | null;
  lines: InvoiceLine[];
}

export function BillingManager() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<"invoices" | "generator">("invoices");
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [entities, setEntities] = useState<LegalEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState<string>("");

  // Filters
  const [search, setSearch] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // Generator form state
  const [selectedEntityId, setSelectedEntityId] = useState<string>("");
  const [tripIdsInput, setTripIdsInput] = useState<string>("");
  const [genError, setGenError] = useState<string | null>(null);
  const [genSuccess, setGenSuccess] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    fetchInvoices();
    fetchEntities();
  }, []);

  const fetchInvoices = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/billing/invoices/");
      if (res.ok) {
        const data = await res.json();
        setInvoices(data.results || data);
      }
    } catch (e) {
      console.error(e);
      setError("Failed to connect to billing service.");
    } finally {
      setLoading(false);
    }
  };

  const fetchEntities = async () => {
    try {
      const res = await fetch("/api/billing/entities/");
      if (res.ok) {
        const data = await res.json();
        const list = data.results || data;
        setEntities(list);
        if (list.length > 0) setSelectedEntityId(String(list[0].id));
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleGenerateDraft = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenError(null);
    setGenSuccess(null);
    setGenerating(true);

    const tripIds = tripIdsInput
      .split(",")
      .map((s) => parseInt(s.trim()))
      .filter((n) => !isNaN(n));

    if (!selectedEntityId || tripIds.length === 0) {
      setGenError("Please select a Legal Entity and enter valid Trip IDs.");
      setGenerating(false);
      return;
    }

    try {
      const res = await fetch("/api/billing/invoices/generate_draft/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          legal_entity_id: parseInt(selectedEntityId),
          trip_ids: tripIds,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setGenSuccess(`Draft Invoice #${data.id} generated successfully with ₹${parseFloat(data.total_amount).toFixed(2)} total.`);
        setTripIdsInput("");
        fetchInvoices();
        setActiveTab("invoices");
      } else {
        setGenError(data.detail || "Failed to generate draft invoice.");
      }
    } catch (err: any) {
      setGenError(err.message || "An error occurred during draft generation.");
    } finally {
      setGenerating(false);
    }
  };

  const handleIssueInvoice = async (invoiceId: number) => {
    try {
      const res = await fetch(`/api/billing/invoices/${invoiceId}/issue/`, {
        method: "POST",
      });
      if (res.ok) {
        setSuccess(`Invoice #${invoiceId} issued & posted to subledger successfully!`);
        setTimeout(() => setSuccess(null), 4000);
        fetchInvoices();
      } else {
        const data = await res.json();
        setError(data.detail || "Issuance failed.");
      }
    } catch (e: any) {
      setError(e.message || "Error issuing invoice.");
    }
  };

  const handlePreviewHtml = async (inv: Invoice) => {
    try {
      const res = await fetch(`/api/billing/invoices/${inv.id}/html_preview/`);
      if (res.ok) {
        const html = await res.text();
        setPreviewTitle(inv.invoice_number || `Draft Invoice #${inv.id}`);
        setPreviewHtml(html);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleExportTally = async (inv: Invoice) => {
    try {
      const res = await fetch(`/api/billing/invoices/${inv.id}/tally_xml/`);
      if (res.ok) {
        const xml = await res.text();
        const blob = new Blob([xml], { type: "application/xml" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Tally_Voucher_${inv.invoice_number || inv.id}.xml`;
        a.click();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const filteredInvoices = invoices.filter((inv) => {
    const query = search.toLowerCase().trim();
    const matchesSearch =
      !query ||
      (inv.invoice_number && inv.invoice_number.toLowerCase().includes(query)) ||
      inv.customer_name.toLowerCase().includes(query) ||
      inv.legal_entity_name.toLowerCase().includes(query);
    const matchesStatus = statusFilter === "ALL" || inv.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const totalOutstanding = invoices
    .filter((i) => i.status === "ISSUED" || i.status === "PARTIALLY_PAID")
    .reduce((sum, i) => sum + parseFloat(i.balance_amount || "0"), 0);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "ISSUED":
        return <span style={{ background: "rgba(34, 197, 94, 0.15)", color: "var(--ok)", border: "1px solid rgba(34, 197, 94, 0.3)", padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600 }}>ISSUED</span>;
      case "PAID":
        return <span style={{ background: "rgba(59, 130, 246, 0.15)", color: "var(--info)", border: "1px solid rgba(59, 130, 246, 0.3)", padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600 }}>PAID</span>;
      case "PARTIALLY_PAID":
        return <span style={{ background: "rgba(234, 179, 8, 0.15)", color: "var(--warn)", border: "1px solid rgba(234, 179, 8, 0.3)", padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600 }}>PARTIAL</span>;
      case "DRAFT":
      default:
        return <span style={{ background: "rgba(100, 116, 139, 0.2)", color: "#cbd5e1", border: "1px solid rgba(148, 163, 184, 0.3)", padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600 }}>DRAFT</span>;
    }
  };

  return (
    <div className="stack" style={{ gap: 24 }}>
      {/* Metric Strip matching Application Console layout */}
      <section className="metrics">
        <div className="metric">
          <div className="metric-header">
            <div style={{ background: "rgba(59, 73, 223, 0.15)", padding: 8, borderRadius: "50%", color: "var(--accent)" }}>
              <Receipt size={16} />
            </div>
            TOTAL INVOICES
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{invoices.length}</strong>
              <span>Registered Documents</span>
            </div>
            <div className="metric-trend live">Active</div>
          </div>
        </div>

        <div className="metric">
          <div className="metric-header">
            <div style={{ background: "rgba(234, 179, 8, 0.15)", padding: 8, borderRadius: "50%", color: "var(--warn)" }}>
              <Clock size={16} />
            </div>
            DRAFT QUEUE
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{invoices.filter((i) => i.status === "DRAFT").length}</strong>
              <span>Pending Review</span>
            </div>
            <div className="metric-trend live">Action Required</div>
          </div>
        </div>

        <div className="metric">
          <div className="metric-header">
            <div style={{ background: "rgba(34, 197, 94, 0.15)", padding: 8, borderRadius: "50%", color: "var(--ok)" }}>
              <FileCheck size={16} />
            </div>
            ISSUED & SETTLED
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{invoices.filter((i) => i.status === "ISSUED" || i.status === "PAID").length}</strong>
              <span>Posted Invoices</span>
            </div>
            <div className="metric-trend up">
              <CheckCircle2 size={12} /> Balanced
            </div>
          </div>
        </div>

        <div className="metric">
          <div className="metric-header">
            <div style={{ background: "rgba(59, 130, 246, 0.15)", padding: 8, borderRadius: "50%", color: "var(--info)" }}>
              <DollarSign size={16} />
            </div>
            OUTSTANDING AR
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>₹{totalOutstanding.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong>
              <span>Receivables Balance</span>
            </div>
            <div className="metric-trend live">Subledger Sync</div>
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

      {/* Control Bar & Tabs */}
      <div className="search-filter-bar" style={{ display: "flex", justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 12, flex: 1, alignItems: "center" }}>
          {activeTab === "invoices" && (
            <>
              <div className="search-input-wrapper">
                <Search size={16} className="search-icon" />
                <input
                  type="text"
                  placeholder="Search by invoice #, customer, entity..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>

              <div className="filter-select-wrapper">
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                  <option value="ALL">All Statuses</option>
                  <option value="DRAFT">DRAFT</option>
                  <option value="ISSUED">ISSUED</option>
                  <option value="PARTIALLY_PAID">PARTIALLY PAID</option>
                  <option value="PAID">PAID</option>
                </select>
              </div>
            </>
          )}
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => setActiveTab("invoices")}
            className={activeTab === "invoices" ? "primary-btn" : "secondary-btn"}
            style={{ padding: "8px 14px", fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}
          >
            <Receipt size={14} />
            Invoice Register
          </button>
          <button
            onClick={() => setActiveTab("generator")}
            className={activeTab === "generator" ? "primary-btn" : "secondary-btn"}
            style={{ padding: "8px 14px", fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}
          >
            <Plus size={14} />
            New Invoice Draft
          </button>
        </div>
      </div>

      {/* Main Tab 1: Invoice Register */}
      {activeTab === "invoices" && (
        <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
          {loading ? (
            <div style={{ padding: 48, textAlign: "center", color: "var(--muted)", fontSize: 14 }}>Loading invoice records...</div>
          ) : filteredInvoices.length === 0 ? (
            <div style={{ padding: 48, textAlign: "center", color: "var(--muted)", fontSize: 14 }}>No invoice records found matching your query.</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "var(--panel-strong)", borderBottom: "1px solid var(--line)", color: "var(--muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    <th style={{ padding: "12px 16px" }}>Invoice #</th>
                    <th style={{ padding: "12px 16px" }}>Legal Entity</th>
                    <th style={{ padding: "12px 16px" }}>Customer</th>
                    <th style={{ padding: "12px 16px" }}>Status</th>
                    <th style={{ padding: "12px 16px", textAlign: "right" }}>Taxable (₹)</th>
                    <th style={{ padding: "12px 16px", textAlign: "right" }}>GST (₹)</th>
                    <th style={{ padding: "12px 16px", textAlign: "right" }}>Grand Total (₹)</th>
                    <th style={{ padding: "12px 16px", textAlign: "center" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredInvoices.map((inv) => (
                    <tr key={inv.id} style={{ borderBottom: "1px solid var(--line)" }} className="table-row-hover">
                      <td style={{ padding: "14px 16px", fontFamily: "monospace", fontWeight: 700, color: "var(--accent-strong)" }}>{inv.invoice_number || `DRAFT-${inv.id}`}</td>
                      <td style={{ padding: "14px 16px", color: "var(--muted)" }}>{inv.legal_entity_name}</td>
                      <td style={{ padding: "14px 16px", fontWeight: 600, color: "var(--ink)" }}>{inv.customer_name}</td>
                      <td style={{ padding: "14px 16px" }}>{getStatusBadge(inv.status)}</td>
                      <td style={{ padding: "14px 16px", textAlign: "right", color: "var(--muted)" }}>₹{parseFloat(inv.taxable_amount).toFixed(2)}</td>
                      <td style={{ padding: "14px 16px", textAlign: "right", color: "var(--muted)" }}>₹{(parseFloat(inv.cgst_amount) + parseFloat(inv.sgst_amount)).toFixed(2)}</td>
                      <td style={{ padding: "14px 16px", textAlign: "right", fontWeight: 700, color: "var(--ink)" }}>₹{parseFloat(inv.total_amount).toFixed(2)}</td>
                      <td style={{ padding: "14px 16px", textAlign: "center" }}>
                        <div style={{ display: "flex", justifyContent: "center", gap: 6 }}>
                          <button
                            onClick={() => handlePreviewHtml(inv)}
                            title="Tax Invoice HTML Preview"
                            style={{ padding: "6px 10px", borderRadius: 6, background: "var(--panel-strong)", border: "1px solid var(--line)", color: "var(--ink)", fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}
                          >
                            <Eye size={13} />
                            Preview
                          </button>
                          <button
                            onClick={() => handleExportTally(inv)}
                            title="Export Tally Prime XML"
                            style={{ padding: "6px 10px", borderRadius: 6, background: "var(--panel-strong)", border: "1px solid var(--line)", color: "var(--info)", fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}
                          >
                            <Download size={13} />
                            Tally XML
                          </button>
                          {inv.status === "DRAFT" && (
                            <button
                              onClick={() => handleIssueInvoice(inv.id)}
                              title="Issue Invoice & Post Journal"
                              style={{ padding: "6px 12px", borderRadius: 6, background: "var(--ok)", border: "none", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}
                            >
                              <Send size={13} />
                              Issue
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Main Tab 2: Draft Invoice Generator */}
      {activeTab === "generator" && (
        <div className="panel" style={{ maxWidth: 650, margin: "0 auto", width: "100%", padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ borderBottom: "1px solid var(--line)", paddingBottom: 14 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: "var(--ink)", margin: 0 }}>Generate Draft Tax Invoice</h2>
            <p style={{ color: "var(--muted)", fontSize: 13, margin: "4px 0 0" }}>Consolidate billing-ready trip closeouts into an official GST tax invoice draft with snapshot pricing.</p>
          </div>

          {genError && (
            <div style={{ padding: "12px 16px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.25)", borderRadius: 8, color: "var(--danger)", fontSize: 13 }}>
              {genError}
            </div>
          )}

          {genSuccess && (
            <div style={{ padding: "12px 16px", background: "rgba(34, 197, 94, 0.1)", border: "1px solid rgba(34, 197, 94, 0.25)", borderRadius: 8, color: "var(--ok)", fontSize: 13 }}>
              {genSuccess}
            </div>
          )}

          <form onSubmit={handleGenerateDraft} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)" }}>Issuer Legal Entity</label>
              <select
                value={selectedEntityId}
                onChange={(e) => setSelectedEntityId(e.target.value)}
                style={{ width: "100%", background: "var(--panel-strong)", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "var(--ink)", outline: "none" }}
              >
                {entities.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.legal_name} (GSTIN: {e.gstin})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)" }}>Completed Trip IDs (Comma Separated)</label>
              <input
                type="text"
                placeholder="e.g. 1, 2, 5"
                value={tripIdsInput}
                onChange={(e) => setTripIdsInput(e.target.value)}
                style={{ width: "100%", background: "var(--panel-strong)", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "var(--ink)", outline: "none" }}
              />
              <span style={{ fontSize: 11, color: "var(--muted)" }}>Only trips marked as COMPLETED with approved closeouts will be accepted.</span>
            </div>

            <button
              type="submit"
              disabled={generating}
              className="primary-btn"
              style={{
                marginTop: 8,
                padding: "12px 18px",
                fontSize: 14,
                fontWeight: 600,
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                gap: 8,
                opacity: generating ? 0.7 : 1,
              }}
            >
              {generating ? "Calculating & Generating Draft..." : "Generate Invoice Draft"}
            </button>
          </form>
        </div>
      )}

      {/* Tax Invoice Preview Modal */}
      {previewHtml && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0, 0, 0, 0.75)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", padding: 24, zIndex: 1000 }}>
          <div style={{ background: "#ffffff", borderRadius: 12, width: "100%", maxWidth: 900, maxHeight: "90vh", display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)" }}>
            <div style={{ background: "var(--panel-strong)", padding: "14px 20px", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Receipt size={18} style={{ color: "var(--accent)" }} />
                <span style={{ fontWeight: 700, fontSize: 14, color: "var(--ink)" }}>Tax Invoice Preview — {previewTitle}</span>
              </div>
              <button onClick={() => setPreviewHtml(null)} style={{ background: "none", border: 0, color: "var(--muted)", fontSize: 18, cursor: "pointer", fontWeight: 700 }}>
                ✕
              </button>
            </div>
            <div style={{ flex: 1, padding: 16, overflowY: "auto", background: "#f8fafc" }}>
              <iframe title="Invoice Preview" srcDoc={previewHtml} style={{ width: "100%", height: 650, border: 0 }} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default BillingManager;
