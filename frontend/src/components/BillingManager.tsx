"use client";

import React, { useState, useEffect } from "react";
import {
  Receipt,
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
  ClipboardCheck,
} from "lucide-react";
import { useAuth } from "@/lib/AuthContext";
import CloseoutReviewManager from "./CloseoutReviewManager";
import InvoiceTripSelector from "./InvoiceTripSelector";
import {
  BillingInvoice,
  BillingLegalEntity,
  exportBillingInvoiceTallyXml,
  issueBillingInvoice,
  listBillingEntities,
  listBillingInvoices,
  previewBillingInvoice,
  submitBillingInvoiceReview,
  approveBillingInvoice,
  voidBillingInvoice,
  downloadBillingInvoiceDocument,
  downloadOfficialInvoicePdf,
  downloadDutySlipPdf,
  getReconciliationDashboard,
  ReconciliationDashboardData,
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
  const [activeTab, setActiveTab] = useState<"invoices" | "closeouts" | "generator" | "reconciliation">("invoices");
  const [invoices, setInvoices] = useState<BillingInvoice[]>([]);
  const [entities, setEntities] = useState<BillingLegalEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [entitiesLoading, setEntitiesLoading] = useState(true);
  const [activeMutationId, setActiveMutationId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState<string>("");
  const [selectedInvoice, setSelectedInvoice] = useState<BillingInvoice | null>(null);
  const [correctionReason, setCorrectionReason] = useState("");
  const [recoData, setRecoData] = useState<ReconciliationDashboardData | null>(null);
  const [recoLoading, setRecoLoading] = useState(false);

  // Filters
  const [search, setSearch] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

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

  const fetchReco = async () => {
    setRecoLoading(true);
    setError(null);
    try {
      setRecoData(await getReconciliationDashboard());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load reconciliation dashboard.");
    } finally {
      setRecoLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "reconciliation") {
      fetchReco();
    }
  }, [activeTab]);

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

  const handleDownloadDocument = async (invoiceId: number, invNum: string) => {
    try {
      const blob = await downloadBillingInvoiceDocument(invoiceId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${invNum || `invoice-${invoiceId}`}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to download invoice PDF.");
    }
  };

  const handleDownloadOfficialPdf = async (invoiceId: number, invNum: string) => {
    try {
      const blob = await downloadOfficialInvoicePdf(invoiceId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `tax-invoice-${invNum || invoiceId}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to download official Tax Invoice PDF.");
    }
  };

  const handleDownloadDutySlip = async (invoiceId: number, invNum: string) => {
    try {
      const blob = await downloadDutySlipPdf(invoiceId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `duty-slip-${invNum || invoiceId}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to download Duty Slip Annexure PDF.");
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

  const handleLifecycle = async (
    invoiceId: number,
    label: string,
    action: () => Promise<BillingInvoice>,
  ) => {
    setActiveMutationId(invoiceId);
    setError(null);
    try {
      const updated = await action();
      setSuccess(label);
      setSelectedInvoice(updated);
      setCorrectionReason("");
      await fetchInvoices();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invoice lifecycle action failed.");
    } finally {
      setActiveMutationId(null);
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
            className={`button ${activeTab === "closeouts" ? "" : "secondary"}`}
            onClick={() => setActiveTab("closeouts")}
          >
            <ClipboardCheck size={16} /> Trip Closeouts
          </button>
          <button
            className={`button ${activeTab === "generator" ? "" : "secondary"}`}
            onClick={() => setActiveTab("generator")}
            disabled={authLoading || !canManageBilling}
            title={!canManageBilling ? "Admin or accountant access is required" : undefined}
          >
            <Plus size={16} /> Generate Invoice
          </button>
          <button
            className={`button ${activeTab === "reconciliation" ? "" : "secondary"}`}
            onClick={() => setActiveTab("reconciliation")}
            disabled={authLoading || !canManageBilling}
            title={!canManageBilling ? "Admin or accountant access is required" : undefined}
          >
            <AlertTriangle size={16} /> Reconciliation
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

      {activeTab === "closeouts" ? (
        <CloseoutReviewManager />
      ) : activeTab === "reconciliation" ? (
        <ReconciliationDashboardView data={recoData} loading={recoLoading} onRefresh={fetchReco} />
      ) : activeTab === "invoices" ? (
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
                          <button
                            className="button secondary"
                            style={{ padding: "6px 10px", fontSize: 12 }}
                            title="Download official Tax Invoice PDF"
                            onClick={() => handleDownloadOfficialPdf(inv.id, inv.invoice_number || "")}
                          >
                            <Download size={13} /> Tax Invoice
                          </button>
                          <button
                            className="button secondary"
                            style={{ padding: "6px 10px", fontSize: 12 }}
                            title="Download Duty Slip Annexure PDF"
                            onClick={() => handleDownloadDutySlip(inv.id, inv.invoice_number || "")}
                          >
                            <ClipboardCheck size={13} /> Duty Slip
                          </button>
                          <button
                            className="button secondary"
                            style={{ padding: "6px 10px", fontSize: 12 }}
                            onClick={() => handleDownloadDocument(inv.id, inv.invoice_number || "")}
                          >
                            <Download size={13} /> Archive PDF
                          </button>
                          <button
                            className="button secondary"
                            style={{ padding: "6px 10px", fontSize: 12 }}
                            onClick={() => setSelectedInvoice(inv)}
                          >
                            <FileCheck size={13} /> Review
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

                          {inv.status === "APPROVED" && (
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
        <InvoiceTripSelector
          entities={entities}
          entitiesLoading={entitiesLoading}
          onCreated={async (invoice) => {
            setSuccess(`Invoice draft #${invoice.id} created successfully.`);
            setActiveTab("invoices");
            await fetchInvoices();
          }}
        />
      )}

      {selectedInvoice && (
        <div className="invoice-detail-overlay">
          <section className="panel invoice-detail-panel">
            <div className="invoice-detail-header">
              <div>
                <span className="eyebrow">{selectedInvoice.status}</span>
                <h2>{selectedInvoice.invoice_number || `Draft #${selectedInvoice.id}`}</h2>
                <p>{selectedInvoice.customer_name} · Due {selectedInvoice.due_date || "not set"}</p>
              </div>
              <button className="button secondary" onClick={() => setSelectedInvoice(null)}><X size={15} /> Close</button>
            </div>
            <div className="invoice-preview-grid">
              <div><span>Taxable</span><strong>₹{selectedInvoice.taxable_amount}</strong></div>
              <div><span>CGST / SGST / IGST</span><strong>₹{selectedInvoice.cgst_amount} / ₹{selectedInvoice.sgst_amount} / ₹{selectedInvoice.igst_amount}</strong></div>
              <div><span>Total</span><strong>₹{selectedInvoice.total_amount}</strong></div>
              <div><span>Balance</span><strong>₹{selectedInvoice.balance_amount}</strong></div>
            </div>
            <div className="invoice-detail-lines">
              <h3>Source lines</h3>
              {selectedInvoice.lines.map((line) => (
                <div key={line.id}>
                  <span><strong>{line.description}</strong><small>{line.source_type} #{line.source_id} · {line.calculation_version}</small></span>
                  <strong>₹{line.line_total}</strong>
                </div>
              ))}
            </div>
            <div className="invoice-detail-lines">
              <h3>Approval history</h3>
              {(selectedInvoice.audit_events || []).map((event) => (
                <div key={event.id}>
                  <span><strong>{event.action}</strong><small>{event.actor_name} · {event.from_status} → {event.to_status}</small></span>
                  <small>{event.reason}</small>
                </div>
              ))}
              {!selectedInvoice.audit_events?.length && <p>No lifecycle actions recorded.</p>}
            </div>
            <div className="invoice-detail-actions">
              <input value={correctionReason} onChange={(e) => setCorrectionReason(e.target.value)} placeholder="Correction reason required to void" />
              {selectedInvoice.status === "DRAFT" && <button className="button" disabled={activeMutationId === selectedInvoice.id} onClick={() => handleLifecycle(selectedInvoice.id, "Invoice submitted for review.", () => submitBillingInvoiceReview(selectedInvoice.id))}>Submit review</button>}
              {selectedInvoice.status === "REVIEW" && <button className="button" disabled={activeMutationId === selectedInvoice.id} onClick={() => handleLifecycle(selectedInvoice.id, "Invoice approved.", () => approveBillingInvoice(selectedInvoice.id))}>Approve</button>}
              {selectedInvoice.status === "APPROVED" && <button className="button" disabled={activeMutationId === selectedInvoice.id} onClick={() => handleLifecycle(selectedInvoice.id, "Invoice issued.", () => issueBillingInvoice(selectedInvoice.id))}>Issue</button>}
              {["DRAFT", "REVIEW", "APPROVED", "ISSUED", "SENT"].includes(selectedInvoice.status) && <button className="button secondary" disabled={!correctionReason.trim() || activeMutationId === selectedInvoice.id} onClick={() => handleLifecycle(selectedInvoice.id, "Invoice voided for correction.", () => voidBillingInvoice(selectedInvoice.id, correctionReason))}>Void / correct</button>}
            </div>
          </section>
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


function ReconciliationDashboardView({
  data,
  loading,
  onRefresh,
}: {
  data: ReconciliationDashboardData | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 48, color: "var(--muted)" }}>
        <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 12px" }} />
        Analyzing financial subledgers and general ledger balances...
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ textAlign: "center", padding: 48, color: "var(--muted)" }}>
        No reconciliation data available.
        <button className="button" onClick={onRefresh} style={{ marginTop: 12 }}>
          Load Dashboard
        </button>
      </div>
    );
  }

  const exceptionCategories = [
    {
      title: "Trips Missing Closeout",
      description: "Completed trips that have no closeout record or are not in BILLING_READY status.",
      items: data.trips_missing_closeout,
      renderHeaders: () => (
        <>
          <TableHead>Trip ID</TableHead>
          <TableHead>Customer</TableHead>
          <TableHead>Pickup Time</TableHead>
          <TableHead>Quoted Amount</TableHead>
          <TableHead>Exception Description</TableHead>
        </>
      ),
      renderRow: (item: any) => (
        <TableRow key={item.trip_id}>
          <TableCell>#{item.trip_id}</TableCell>
          <TableCell>{item.customer_name}</TableCell>
          <TableCell>{item.pickup_at ? new Date(item.pickup_at).toLocaleString() : "—"}</TableCell>
          <TableCell>₹{item.amount}</TableCell>
          <TableCell style={{ color: "var(--danger)" }}>{item.description}</TableCell>
        </TableRow>
      ),
    },
    {
      title: "Closeouts Not Invoiced",
      description: "Billing-ready closeouts that are not linked to any invoice.",
      items: data.closeouts_not_invoiced,
      renderHeaders: () => (
        <>
          <TableHead>Closeout ID</TableHead>
          <TableHead>Trip ID</TableHead>
          <TableHead>Customer</TableHead>
          <TableHead>Final Amount</TableHead>
          <TableHead>Exception Description</TableHead>
        </>
      ),
      renderRow: (item: any) => (
        <TableRow key={item.closeout_id}>
          <TableCell>#{item.closeout_id}</TableCell>
          <TableCell>#{item.trip_id}</TableCell>
          <TableCell>{item.customer_name}</TableCell>
          <TableCell>₹{item.final_total_amount}</TableCell>
          <TableCell style={{ color: "var(--warning)" }}>{item.description}</TableCell>
        </TableRow>
      ),
    },
    {
      title: "Invoices Missing GL Journal Entries",
      description: "Issued or paid invoices that have no corresponding journal entry in the GL.",
      items: data.invoices_missing_journals,
      renderHeaders: () => (
        <>
          <TableHead>Invoice ID</TableHead>
          <TableHead>Invoice #</TableHead>
          <TableHead>Customer</TableHead>
          <TableHead>Invoice Total</TableHead>
          <TableHead>Exception Description</TableHead>
        </>
      ),
      renderRow: (item: any) => (
        <TableRow key={item.invoice_id}>
          <TableCell>#{item.invoice_id}</TableCell>
          <TableCell>{item.invoice_number || `DRAFT-#${item.invoice_id}`}</TableCell>
          <TableCell>{item.customer_name}</TableCell>
          <TableCell>₹{item.total_amount}</TableCell>
          <TableCell style={{ color: "var(--danger)" }}>{item.description}</TableCell>
        </TableRow>
      ),
    },
    {
      title: "Invoice vs Journal Amount Mismatches",
      description: "Invoices where the subledger total does not match the sum of debits in the GL journal entry.",
      items: data.invoices_journal_amount_mismatches,
      renderHeaders: () => (
        <>
          <TableHead>Invoice #</TableHead>
          <TableHead>Journal entry</TableHead>
          <TableHead>Invoice Amount</TableHead>
          <TableHead>Journal Amount</TableHead>
          <TableHead>Exception Description</TableHead>
        </>
      ),
      renderRow: (item: any) => (
        <TableRow key={item.invoice_id}>
          <TableCell>{item.invoice_number}</TableCell>
          <TableCell>{item.journal_entry_number}</TableCell>
          <TableCell>₹{item.invoice_amount}</TableCell>
          <TableCell>₹{item.journal_amount}</TableCell>
          <TableCell style={{ color: "var(--danger)" }}>{item.description}</TableCell>
        </TableRow>
      ),
    },
    {
      title: "Receipts Missing GL Journal Entries",
      description: "Payment receipts that have no matching GL journal record.",
      items: data.receipts_missing_journals,
      renderHeaders: () => (
        <>
          <TableHead>Receipt ID</TableHead>
          <TableHead>Receipt #</TableHead>
          <TableHead>Customer</TableHead>
          <TableHead>Receipt Amount</TableHead>
          <TableHead>Exception Description</TableHead>
        </>
      ),
      renderRow: (item: any) => (
        <TableRow key={item.receipt_id}>
          <TableCell>#{item.receipt_id}</TableCell>
          <TableCell>{item.receipt_number}</TableCell>
          <TableCell>{item.customer_name}</TableCell>
          <TableCell>₹{item.amount}</TableCell>
          <TableCell style={{ color: "var(--danger)" }}>{item.description}</TableCell>
        </TableRow>
      ),
    },
    {
      title: "Receipt vs Journal Amount Mismatches",
      description: "Receipts where the cash amount does not match the sum of debits in the GL journal entry.",
      items: data.receipts_journal_amount_mismatches,
      renderHeaders: () => (
        <>
          <TableHead>Receipt #</TableHead>
          <TableHead>Journal entry</TableHead>
          <TableHead>Receipt Amount</TableHead>
          <TableHead>Journal Amount</TableHead>
          <TableHead>Exception Description</TableHead>
        </>
      ),
      renderRow: (item: any) => (
        <TableRow key={item.receipt_id}>
          <TableCell>{item.receipt_number}</TableCell>
          <TableCell>{item.journal_entry_number}</TableCell>
          <TableCell>₹{item.receipt_amount}</TableCell>
          <TableCell>₹{item.journal_amount}</TableCell>
          <TableCell style={{ color: "var(--danger)" }}>{item.description}</TableCell>
        </TableRow>
      ),
    },
    {
      title: "TDS Allocations Missing GL Journals",
      description: "TDS allocations that lack corresponding journal postings in the GL.",
      items: data.allocations_missing_journals,
      renderHeaders: () => (
        <>
          <TableHead>Allocation ID</TableHead>
          <TableHead>Receipt #</TableHead>
          <TableHead>Invoice #</TableHead>
          <TableHead>TDS Amount</TableHead>
          <TableHead>Exception Description</TableHead>
        </>
      ),
      renderRow: (item: any) => (
        <TableRow key={item.allocation_id}>
          <TableCell>#{item.allocation_id}</TableCell>
          <TableCell>{item.receipt_number}</TableCell>
          <TableCell>{item.invoice_number}</TableCell>
          <TableCell>₹{item.tds_amount}</TableCell>
          <TableCell style={{ color: "var(--danger)" }}>{item.description}</TableCell>
        </TableRow>
      ),
    },
    {
      title: "Unbalanced GL Journal Entries",
      description: "Journal entries where total debits do not equal total credits.",
      items: data.unbalanced_journals,
      renderHeaders: () => (
        <>
          <TableHead>Journal Entry #</TableHead>
          <TableHead>Total Debits</TableHead>
          <TableHead>Total Credits</TableHead>
          <TableHead>Exception Description</TableHead>
        </>
      ),
      renderRow: (item: any) => (
        <TableRow key={item.journal_entry_number}>
          <TableCell>{item.journal_entry_number}</TableCell>
          <TableCell>₹{item.debit_total}</TableCell>
          <TableCell>₹{item.credit_total}</TableCell>
          <TableCell style={{ color: "var(--danger)" }}>{item.description}</TableCell>
        </TableRow>
      ),
    },
  ];

  const totalExceptions = exceptionCategories.reduce((acc, cat) => acc + cat.items.length, 0);

  return (
    <div className="stack" style={{ gap: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0 }}>Subledger to GL Reconciliation</h2>
          <p style={{ color: "var(--muted)", margin: "4px 0 0" }}>
            Real-time validation matching operational source events, subledgers, and general ledger journal entries.
          </p>
        </div>
        <button className="button" onClick={onRefresh}>
          <RefreshCw size={14} style={{ marginRight: 8 }} /> Re-run Audit
        </button>
      </div>

      <div style={{ padding: 16, background: totalExceptions === 0 ? "rgba(34, 197, 94, 0.1)" : "rgba(239, 68, 68, 0.1)", border: `1px solid ${totalExceptions === 0 ? "rgba(34, 197, 94, 0.25)" : "rgba(239, 68, 68, 0.25)"}`, borderRadius: 8 }}>
        <h4 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8, color: totalExceptions === 0 ? "var(--ok)" : "var(--danger)" }}>
          {totalExceptions === 0 ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          {totalExceptions === 0 ? "Ledger Reconciled: Zero Unexplained Differences" : `${totalExceptions} Reconciliation Exceptions Detected`}
        </h4>
        <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--muted)" }}>
          {totalExceptions === 0 
            ? "All source records match subledger totals and have balanced double-entry journal postings in the general ledger."
            : "Review and resolve the mismatch items below to ensure proper financial statement accuracy."}
        </p>
      </div>

      {exceptionCategories.map((cat, idx) => {
        if (cat.items.length === 0) return null;
        return (
          <div className="panel" key={idx} style={{ padding: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 16, color: "#fff" }}>{cat.title}</h3>
                <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--muted)" }}>{cat.description}</p>
              </div>
              <span style={{ background: "rgba(239, 68, 68, 0.15)", color: "var(--danger)", padding: "4px 10px", borderRadius: 12, fontSize: 12, fontWeight: "bold" }}>
                {cat.items.length} Mismatches
              </span>
            </div>
            <Table>
              <TableHeader>
                <TableRow>{cat.renderHeaders()}</TableRow>
              </TableHeader>
              <TableBody>
                {cat.items.map((item: any) => cat.renderRow(item))}
              </TableBody>
            </Table>
          </div>
        );
      })}
    </div>
  );
}


export default BillingManager;
