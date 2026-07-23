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
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";

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
      setError("Failed to load billing invoices.");
    } finally {
      setLoading(false);
    }
  };

  const fetchEntities = async () => {
    try {
      const res = await fetch("/api/billing/legal-entities/");
      if (res.ok) {
        const data = await res.json();
        setEntities(data.results || data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handlePreviewPdf = async (invoiceId: number, invNum: string) => {
    try {
      const res = await fetch(`/api/billing/invoices/${invoiceId}/pdf/`);
      if (res.ok) {
        const html = await res.text();
        setPreviewHtml(html);
        setPreviewTitle(`Tax Invoice #${invNum || invoiceId}`);
      } else {
        alert("Failed to render PDF HTML");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleExportTally = (invoiceId: number, invNum: string) => {
    window.open(`/api/billing/invoices/${invoiceId}/export_tally_xml/`, "_blank");
  };

  const handleIssueInvoice = async (invoiceId: number) => {
    try {
      const res = await fetch(`/api/billing/invoices/${invoiceId}/issue/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (res.ok) {
        setSuccess("Invoice issued successfully!");
        fetchInvoices();
      } else {
        const errData = await res.json();
        setError(errData.detail || "Failed to issue invoice");
      }
    } catch (e: any) {
      setError(e.message || "Failed to issue invoice");
    }
  };

  const handleGenerateInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenError(null);
    setGenSuccess(null);
    if (!selectedEntityId) {
      setGenError("Please select a Legal Entity.");
      return;
    }
    const rawIds = tripIdsInput
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0)
      .map((s) => parseInt(s, 10))
      .filter((n) => !isNaN(n));

    if (rawIds.length === 0) {
      setGenError("Please enter at least one valid numeric Trip ID.");
      return;
    }

    setGenerating(true);
    try {
      const res = await fetch("/api/billing/invoices/generate_from_trips/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          legal_entity_id: parseInt(selectedEntityId, 10),
          trip_ids: rawIds,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setGenSuccess(`Invoice draft ${data.invoice_number || "#" + data.id} created with ${data.lines?.length || 0} line items.`);
        setTripIdsInput("");
        fetchInvoices();
      } else {
        const data = await res.json();
        setGenError(data.detail || data.error || "Invoice generation failed.");
      }
    } catch (err: any) {
      setGenError(err.message || "Network error generating invoice.");
    } finally {
      setGenerating(false);
    }
  };

  // Filter logic
  const filteredInvoices = invoices.filter((inv) => {
    const matchesSearch =
      !search.trim() ||
      (inv.invoice_number && inv.invoice_number.toLowerCase().includes(search.toLowerCase())) ||
      inv.customer_name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "ALL" || inv.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Calculate Metrics
  const totalBilled = invoices.reduce((acc, i) => acc + (parseFloat(i.total_amount) || 0), 0);
  const totalPaid = invoices.reduce((acc, i) => acc + (parseFloat(i.paid_amount) || 0), 0);
  const totalOutstanding = invoices.reduce((acc, i) => acc + (parseFloat(i.balance_amount) || 0), 0);

  return (
    <div className="stack" style={{ gap: 24 }}>
      {/* Top Financial Metrics */}
      <section className="metrics">
        <div className="metric-card">
          <div className="metric-header">
            <div className="metric-icon" style={{ background: "rgba(59, 73, 223, 0.15)", color: "var(--accent)" }}>
              <Receipt size={20} />
            </div>
            TOTAL INVOICED
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>₹{totalBilled.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong>
              <span>Cumulative Revenue</span>
            </div>
            <div className="metric-trend live">{invoices.length} Invoices Issued</div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <div className="metric-icon" style={{ background: "rgba(34, 197, 94, 0.15)", color: "var(--ok)" }}>
              <CheckCircle2 size={20} />
            </div>
            TOTAL COLLECTED
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>₹{totalPaid.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong>
              <span>Received Payments</span>
            </div>
            <div className="metric-trend ok">Bank & Cash Realized</div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <div className="metric-icon" style={{ background: "rgba(239, 68, 68, 0.15)", color: "var(--danger)" }}>
              <Clock size={20} />
            </div>
            OUTSTANDING AR
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>₹{totalOutstanding.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong>
              <span>Pending Receivables</span>
            </div>
            <div className="metric-trend live">Corporate Credit</div>
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

      {/* Search & Action Bar */}
      <div className="search-filter-bar">
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className={`button ${activeTab === "invoices" ? "" : "secondary"}`}
            onClick={() => setActiveTab("invoices")}
          >
            <Receipt size={16} /> Tax Invoices
          </button>
          <button
            className={`button ${activeTab === "generator" ? "" : "secondary"}`}
            onClick={() => setActiveTab("generator")}
          >
            <Plus size={16} /> Generate Invoice
          </button>
        </div>

        {activeTab === "invoices" && (
          <>
            <div className="search-input-wrapper" style={{ flex: 1, maxWidth: 400 }}>
              <Search size={16} className="search-icon" />
              <input
                type="text"
                placeholder="Search by invoice # or customer..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="filter-select-wrapper">
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="ALL">All Statuses</option>
                <option value="DRAFT">DRAFT</option>
                <option value="ISSUED">ISSUED</option>
                <option value="SENT">SENT</option>
                <option value="PARTIALLY_PAID">PARTIALLY PAID</option>
                <option value="PAID">PAID</option>
              </select>
            </div>
            <button className="button secondary" onClick={fetchInvoices}>
              <RefreshCw size={14} /> Refresh
            </button>
          </>
        )}
      </div>

      {activeTab === "invoices" ? (
        /* Shadcn UI Table for Billing & Invoices */
        <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Invoice #</TableHead>
                <TableHead>Billed Customer</TableHead>
                <TableHead>Legal Entity</TableHead>
                <TableHead>Issue Date</TableHead>
                <TableHead>Due Date</TableHead>
                <TableHead>Taxable Value</TableHead>
                <TableHead>GST (5%)</TableHead>
                <TableHead>Total Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead style={{ textAlign: "right" }}>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={10} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                    Loading tax invoices...
                  </TableCell>
                </TableRow>
              ) : filteredInvoices.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={10} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                    No tax invoices found.
                  </TableCell>
                </TableRow>
              ) : (
                filteredInvoices.map((inv) => {
                  const gstSum = (parseFloat(inv.cgst_amount) || 0) + (parseFloat(inv.sgst_amount) || 0);
                  return (
                    <TableRow key={inv.id}>
                      <TableCell>
                        <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--accent)", padding: "4px 8px", background: "rgba(59, 73, 223, 0.12)", borderRadius: 6 }}>
                          {inv.invoice_number || `DRAFT-#${inv.id}`}
                        </span>
                      </TableCell>

                      <TableCell>
                        <strong style={{ color: "#fff", fontSize: 14 }}>{inv.customer_name}</strong>
                      </TableCell>

                      <TableCell>
                        <span style={{ fontSize: 12, color: "var(--muted)" }}>{inv.legal_entity_name}</span>
                      </TableCell>

                      <TableCell>
                        <span style={{ fontSize: 13, color: "#cbd5e1" }}>{inv.issue_date || "Not Issued"}</span>
                      </TableCell>

                      <TableCell>
                        <span style={{ fontSize: 13, color: "#cbd5e1" }}>{inv.due_date || "N/A"}</span>
                      </TableCell>

                      <TableCell>
                        <span>₹{parseFloat(inv.taxable_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
                      </TableCell>

                      <TableCell>
                        <span style={{ color: "var(--muted)", fontSize: 13 }}>₹{gstSum.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
                      </TableCell>

                      <TableCell>
                        <strong style={{ color: "#fff", fontSize: 14 }}>₹{parseFloat(inv.total_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong>
                      </TableCell>

                      <TableCell>
                        <span className={`status ${inv.status === "PAID" ? "ok" : inv.status === "DRAFT" ? "warn" : "info"}`}>
                          {inv.status}
                        </span>
                      </TableCell>

                      <TableCell style={{ textAlign: "right" }}>
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
                          <button
                            className="button secondary"
                            style={{ padding: "6px 10px", fontSize: 12 }}
                            title="Preview PDF Tax Invoice"
                            onClick={() => handlePreviewPdf(inv.id, inv.invoice_number || "")}
                          >
                            <Eye size={13} /> PDF
                          </button>

                          <button
                            className="button secondary"
                            style={{ padding: "6px 10px", fontSize: 12 }}
                            title="Export Tally Prime XML"
                            onClick={() => handleExportTally(inv.id, inv.invoice_number || "")}
                          >
                            <Download size={13} /> Tally
                          </button>

                          {inv.status === "DRAFT" && (
                            <button
                              className="button"
                              style={{ padding: "6px 10px", fontSize: 12, background: "var(--ok)", color: "#000" }}
                              onClick={() => handleIssueInvoice(inv.id)}
                            >
                              Issue
                            </button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      ) : (
        /* Invoice Generator Form Panel */
        <div className="panel" style={{ padding: 24, maxWidth: 640 }}>
          <h3 style={{ margin: "0 0 16px", color: "#fff", display: "flex", alignItems: "center", gap: 8 }}>
            <FileText size={20} style={{ color: "var(--accent)" }} />
            Generate Corporate Tax Invoice
          </h3>
          <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 20 }}>
            Select your legal entity and input completed trip IDs to compile automated GST tax invoices based on corporate contract pricing packages.
          </p>

          {genError && (
            <div style={{ padding: 12, background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.25)", borderRadius: 6, color: "var(--danger)", fontSize: 13, marginBottom: 16 }}>
              {genError}
            </div>
          )}
          {genSuccess && (
            <div style={{ padding: 12, background: "rgba(34, 197, 94, 0.1)", border: "1px solid rgba(34, 197, 94, 0.25)", borderRadius: 6, color: "var(--ok)", fontSize: 13, marginBottom: 16 }}>
              {genSuccess}
            </div>
          )}

          <form onSubmit={handleGenerateInvoice} className="stack" style={{ gap: 16 }}>
            <div>
              <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>
                Legal Entity (Billing Provider) *
              </label>
              <select
                required
                style={{ width: "100%", padding: 12, borderRadius: 8, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                value={selectedEntityId}
                onChange={(e) => setSelectedEntityId(e.target.value)}
              >
                <option value="">Select Legal Entity...</option>
                {entities.map((ent) => (
                  <option key={ent.id} value={ent.id}>
                    {ent.legal_name} (GSTIN: {ent.gstin})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>
                Trip IDs (Comma-separated) *
              </label>
              <input
                type="text"
                required
                placeholder="e.g. 101, 102, 105"
                style={{ width: "100%", padding: 12, borderRadius: 8, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff", fontFamily: "monospace" }}
                value={tripIdsInput}
                onChange={(e) => setTripIdsInput(e.target.value)}
              />
            </div>

            <button type="submit" className="button" disabled={generating} style={{ marginTop: 8 }}>
              {generating ? "Generating Invoice..." : "Compile & Issue Invoice Draft"}
            </button>
          </form>
        </div>
      )}

      {/* PDF Tax Invoice Modal Preview */}
      {previewHtml && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", backdropFilter: "blur(10px)", display: "flex", flexDirection: "column", zIndex: 2000, padding: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h3 style={{ color: "#fff", margin: 0 }}>{previewTitle}</h3>
            <button
              className="button secondary"
              onClick={() => setPreviewHtml(null)}
              style={{ background: "rgba(255,255,255,0.1)", color: "#fff", border: 0 }}
            >
              <X size={18} /> Close Preview
            </button>
          </div>
          <iframe
            srcDoc={previewHtml}
            style={{ flex: 1, width: "100%", border: "0", borderRadius: 8, background: "#fff" }}
            title="PDF Preview"
          />
        </div>
      )}
    </div>
  );
}

export default BillingManager;
