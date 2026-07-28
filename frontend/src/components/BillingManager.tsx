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
  BillingInvoice,
  BillingLegalEntity,
  exportBillingInvoiceTallyXml,
  generateInvoiceDraft,
  issueBillingInvoice,
  listBillingEntities,
  listBillingInvoices,
  previewBillingInvoice,
} from "@/lib/billingApi";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";

export function BillingManager() {
  const { user, loading: authLoading } = useAuth();
  const [activeTab, setActiveTab] = useState<"invoices" | "generator">("invoices");
  const [invoices, setInvoices] = useState<BillingInvoice[]>([]);
  const [entities, setEntities] = useState<BillingLegalEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [entitiesLoading, setEntitiesLoading] = useState(true);
  const [activeMutationId, setActiveMutationId] = useState<number | null>(null);
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
  const canManageBilling =
    !!user &&
    (user.role === "admin" ||
      user.role === "accountant" ||
      user.permissions?.includes("superuser"));

  useEffect(() => {
    fetchInvoices();
    fetchEntities();
  }, []);

  const fetchInvoices = async () => {
    setLoading(true);
    setError(null);
    try {
      setInvoices(await listBillingInvoices());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load billing invoices.");
    } finally {
      setLoading(false);
    }
  };

  const fetchEntities = async () => {
    setEntitiesLoading(true);
    try {
      setEntities(await listBillingEntities());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load legal entities.");
    } finally {
      setEntitiesLoading(false);
    }
  };

  const handlePreviewPdf = async (invoiceId: number, invNum: string) => {
    try {
      const html = await previewBillingInvoice(invoiceId);
      setPreviewHtml(html);
      setPreviewTitle(`Tax Invoice #${invNum || invoiceId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to render invoice preview.");
    }
  };

  const handleExportTally = async (invoiceId: number, invNum: string) => {
    try {
      const xml = await exportBillingInvoiceTallyXml(invoiceId);
      const url = URL.createObjectURL(new Blob([xml], { type: "application/xml" }));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${invNum || `invoice-${invoiceId}`}.xml`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to export Tally XML.");
    }
  };

  const handleIssueInvoice = async (invoiceId: number) => {
    setActiveMutationId(invoiceId);
    setError(null);
    try {
      await issueBillingInvoice(invoiceId);
      setSuccess("Invoice issued successfully!");
      await fetchInvoices();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to issue invoice");
    } finally {
      setActiveMutationId(null);
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
    if (!canManageBilling) {
      setGenError("Your account does not have permission to create invoices.");
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
      const data = await generateInvoiceDraft({
        legal_entity_id: parseInt(selectedEntityId, 10),
        trip_ids: rawIds,
      });
      setGenSuccess(`Invoice draft ${data.invoice_number || "#" + data.id} created with ${data.lines?.length || 0} line items.`);
      setTripIdsInput("");
      await fetchInvoices();
    } catch (err) {
      setGenError(err instanceof Error ? err.message : "Network error generating invoice.");
    } finally {
      setGenerating(false);
    }
  };

  // Filter logic
  const filteredInvoices = invoices.filter((inv) => {
    const matchesSearch =
      !search.trim() ||
      (inv.invoice_number && inv.invoice_number.toLowerCase().includes(search.toLowerCase())) ||
      (inv.customer_name || "").toLowerCase().includes(search.toLowerCase());
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
          <div style={{ display: "flex", gap: 8 }}>
            <button className="button secondary" onClick={() => { fetchInvoices(); fetchEntities(); }} style={{ padding: "4px 8px" }}>Retry</button>
            <button onClick={() => setError(null)} style={{ background: "none", border: 0, color: "inherit", cursor: "pointer" }}>✕</button>
          </div>
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
            disabled={authLoading || !canManageBilling}
            title={!canManageBilling ? "Admin or accountant access is required" : undefined}
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
                    {invoices.length === 0
                      ? "No invoices have been created yet."
                      : "No invoices match the current search and status filters."}
                  </TableCell>
                </TableRow>
              ) : (
                filteredInvoices.map((inv) => {
                  const gstSum =
                    (parseFloat(inv.cgst_amount) || 0) +
                    (parseFloat(inv.sgst_amount) || 0) +
                    (parseFloat(inv.igst_amount) || 0);
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
                            title={inv.status === "DRAFT" ? "Preview draft invoice" : "Preview issued tax invoice"}
                            onClick={() => handlePreviewPdf(inv.id, inv.invoice_number || "")}
                          >
                            <Eye size={13} /> {inv.status === "DRAFT" ? "Draft Preview" : "Invoice"}
                          </button>

                          {inv.status !== "DRAFT" && (
                            <button
                              className="button secondary"
                              style={{ padding: "6px 10px", fontSize: 12 }}
                              title="Download issued invoice as Tally Prime XML"
                              onClick={() => handleExportTally(inv.id, inv.invoice_number || "")}
                            >
                              <Download size={13} /> Tally
                            </button>
                          )}

                          {inv.status === "DRAFT" && (
                            <button
                              className="button"
                              style={{ padding: "6px 10px", fontSize: 12, background: "var(--ok)", color: "#000" }}
                              onClick={() => handleIssueInvoice(inv.id)}
                              disabled={!canManageBilling || activeMutationId === inv.id}
                              title={!canManageBilling ? "Admin or accountant access is required" : undefined}
                            >
                              {activeMutationId === inv.id ? "Issuing..." : "Issue"}
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
                disabled={entitiesLoading || !canManageBilling}
              >
                <option value="">
                  {entitiesLoading ? "Loading legal entities..." : entities.length === 0 ? "No active legal entity configured" : "Select Legal Entity..."}
                </option>
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

            {!authLoading && !canManageBilling && (
              <div style={{ color: "var(--danger)", fontSize: 13 }}>
                Admin or accountant access is required for financial mutations.
              </div>
            )}
            {!entitiesLoading && entities.length === 0 && (
              <div style={{ color: "var(--danger)", fontSize: 13 }}>
                Configure an active legal entity before generating invoices.
              </div>
            )}
            <button
              type="submit"
              className="button"
              disabled={generating || entitiesLoading || entities.length === 0 || !canManageBilling}
              style={{ marginTop: 8 }}
            >
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
