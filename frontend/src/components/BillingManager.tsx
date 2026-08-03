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
import { getCustomers, CorporateCustomer } from "@/lib/api";
import CloseoutReviewManager from "./CloseoutReviewManager";
import InvoiceTripSelector from "./InvoiceTripSelector";
import {
  BillingInvoice,
  BillingLegalEntity,
  exportBillingInvoiceTallyXml,
  issueBillingInvoice,
  listBillingEntities,
  listBillingInvoices,
  submitBillingInvoiceReview,
  approveBillingInvoice,
  voidBillingInvoice,
  downloadBillingInvoiceDocument,
  downloadOfficialInvoicePdf,
  downloadDutySlipPdf,
  getReconciliationDashboard,
  ReconciliationDashboardData,
  PaymentReceipt,
  PaymentAllocation,
  CreditNote,
  DebitNote,
  listPaymentReceipts,
  createPaymentReceipt,
  reversePaymentReceipt,
  createPaymentAllocation,
  reversePaymentAllocation,
  listCreditNotes,
  createCreditNote,
  approveCreditNote,
  voidCreditNote,
  listDebitNotes,
  createDebitNote,
  approveDebitNote,
  voidDebitNote,
  getARAgingReport,
  getCustomerStatementReport,
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
  const [activeTab, setActiveTab] = useState<"invoices" | "closeouts" | "generator" | "payments" | "notes" | "reports" | "reconciliation">("invoices");
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

  // Payments Tab States
  const [receipts, setReceipts] = useState<PaymentReceipt[]>([]);
  const [receiptsLoading, setReceiptsLoading] = useState(false);
  const [selectedReceipt, setSelectedReceipt] = useState<PaymentReceipt | null>(null);
  const [showRecordReceiptModal, setShowRecordReceiptModal] = useState(false);
  const [receiptForm, setReceiptForm] = useState({
    legal_entity: "",
    customer: "",
    amount: "",
    currency: "INR",
    payment_method: "BANK_TRANSFER",
    reference_number: "",
  });
  const [showAllocateModal, setShowAllocateModal] = useState(false);
  const [allocationForm, setAllocationForm] = useState({
    invoice: "",
    allocated_amount: "",
    tds_amount: "0.00",
  });

  // Notes Tab States
  const [creditNotes, setCreditNotes] = useState<CreditNote[]>([]);
  const [debitNotes, setDebitNotes] = useState<DebitNote[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [selectedNote, setSelectedNote] = useState<{ type: "credit" | "debit"; data: any } | null>(null);
  const [showCreateNoteModal, setShowCreateNoteModal] = useState<{ show: boolean; type: "credit" | "debit" }>({ show: false, type: "credit" });
  const [noteForm, setNoteForm] = useState({
    invoice: "",
    reason: "",
    lines: [] as Array<{ invoice_line_id: number; quantity: string; unit_rate: string; description?: string; max_qty?: number; rate?: number }>,
  });

  // Reports Tab States
  const [reportsSubTab, setReportsSubTab] = useState<"aging" | "statement">("aging");
  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().split("T")[0]);
  const [agingReport, setAgingReport] = useState<any>(null);
  const [agingLoading, setAgingLoading] = useState(false);
  const [statementCustomer, setStatementCustomer] = useState("");
  const [statementStartDate, setStatementStartDate] = useState(new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split("T")[0]);
  const [statementEndDate, setStatementEndDate] = useState(new Date().toISOString().split("T")[0]);
  const [statementReport, setStatementReport] = useState<any>(null);
  const [statementLoading, setStatementLoading] = useState(false);

  // Filters
  const [search, setSearch] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const canManageBilling =
    !!user &&
    (user.role === "admin" ||
      user.role === "accountant" ||
      user.permissions?.includes("superuser"));

  const fetchReceipts = async () => {
    setReceiptsLoading(true);
    try {
      setReceipts(await listPaymentReceipts());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load payment receipts.");
    } finally {
      setReceiptsLoading(false);
    }
  };

  const fetchNotes = async () => {
    setNotesLoading(true);
    try {
      const cnList = await listCreditNotes();
      const dnList = await listDebitNotes();
      setCreditNotes(cnList);
      setDebitNotes(dnList);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load credit/debit notes.");
    } finally {
      setNotesLoading(false);
    }
  };

  const fetchAging = async () => {
    setAgingLoading(true);
    try {
      setAgingReport(await getARAgingReport(asOfDate));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load AR Aging report.");
    } finally {
      setAgingLoading(false);
    }
  };

  const fetchStatement = async () => {
    if (!statementCustomer) return;
    setStatementLoading(true);
    try {
      setStatementReport(await getCustomerStatementReport(Number(statementCustomer), statementStartDate, statementEndDate));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load Customer Statement.");
    } finally {
      setStatementLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "payments") {
      fetchReceipts();
    } else if (activeTab === "notes") {
      fetchNotes();
    } else if (activeTab === "reports") {
      if (reportsSubTab === "aging") {
        fetchAging();
      }
    }
  }, [activeTab, reportsSubTab, asOfDate]);

  const handleRecordReceiptSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const payload = {
        legal_entity: Number(receiptForm.legal_entity),
        customer: Number(receiptForm.customer),
        amount: receiptForm.amount,
        currency: receiptForm.currency,
        payment_method: receiptForm.payment_method,
        reference_number: receiptForm.reference_number,
      };
      await createPaymentReceipt(payload);
      setSuccess("Payment receipt recorded successfully.");
      setShowRecordReceiptModal(false);
      setReceiptForm({
        legal_entity: "",
        customer: "",
        amount: "",
        currency: "INR",
        payment_method: "BANK_TRANSFER",
        reference_number: "",
      });
      fetchReceipts();
      fetchInvoices();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record payment receipt.");
    }
  };

  const handleAllocateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReceipt) return;
    setError(null);
    try {
      const payload = {
        receipt: selectedReceipt.id,
        invoice: Number(allocationForm.invoice),
        allocated_amount: allocationForm.allocated_amount,
        tds_amount: allocationForm.tds_amount,
      };
      await createPaymentAllocation(payload);
      setSuccess("Payment allocated successfully.");
      setShowAllocateModal(false);
      setAllocationForm({
        invoice: "",
        allocated_amount: "",
        tds_amount: "0.00",
      });
      setSelectedReceipt(null);
      fetchReceipts();
      fetchInvoices();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to allocate payment.");
    }
  };

  const handleReverseReceipt = async (receiptId: number, reason: string) => {
    setError(null);
    try {
      await reversePaymentReceipt(receiptId, reason);
      setSuccess("Receipt reversed successfully.");
      setSelectedReceipt(null);
      fetchReceipts();
      fetchInvoices();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reverse receipt.");
    }
  };

  const handleReverseAllocation = async (allocationId: number) => {
    setError(null);
    try {
      await reversePaymentAllocation(allocationId);
      setSuccess("Allocation reversed successfully.");
      setSelectedReceipt(null);
      fetchReceipts();
      fetchInvoices();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reverse allocation.");
    }
  };

  const handleNoteInvoiceChange = (invoiceId: string) => {
    const inv = invoices.find(i => i.id === Number(invoiceId));
    if (!inv) return;
    const lines = inv.lines.map(line => ({
      invoice_line_id: line.id,
      quantity: "0",
      unit_rate: line.unit_rate,
      description: line.description,
      max_qty: Number(line.quantity),
      rate: Number(line.unit_rate),
    }));
    setNoteForm({
      invoice: invoiceId,
      reason: "",
      lines,
    });
  };

  const handleCreateNoteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const filteredLines = noteForm.lines
        .filter(l => Number(l.quantity) > 0)
        .map(l => ({
          invoice_line_id: l.invoice_line_id,
          quantity: l.quantity,
          unit_rate: l.unit_rate,
        }));
      if (filteredLines.length === 0) {
        throw new Error("Must specify quantity > 0 for at least one line item.");
      }
      const payload = {
        invoice: Number(noteForm.invoice),
        reason: noteForm.reason,
        lines: filteredLines,
      };
      if (showCreateNoteModal.type === "credit") {
        await createCreditNote(payload);
        setSuccess("Credit note draft created.");
      } else {
        await createDebitNote(payload);
        setSuccess("Debit note draft created.");
      }
      setShowCreateNoteModal({ show: false, type: "credit" });
      setNoteForm({ invoice: "", reason: "", lines: [] });
      fetchNotes();
      fetchInvoices();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create note.");
    }
  };

  const handleApproveNote = async (noteId: number, type: "credit" | "debit") => {
    setError(null);
    try {
      if (type === "credit") {
        await approveCreditNote(noteId);
        setSuccess("Credit note approved successfully.");
      } else {
        await approveDebitNote(noteId);
        setSuccess("Debit note approved successfully.");
      }
      setSelectedNote(null);
      fetchNotes();
      fetchInvoices();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve note.");
    }
  };

  const handleVoidNote = async (noteId: number, type: "credit" | "debit") => {
    setError(null);
    try {
      if (type === "credit") {
        await voidCreditNote(noteId);
        setSuccess("Credit note voided successfully.");
      } else {
        await voidDebitNote(noteId);
        setSuccess("Debit note voided successfully.");
      }
      setSelectedNote(null);
      fetchNotes();
      fetchInvoices();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to void note.");
    }
  };

  const [customers, setCustomers] = useState<CorporateCustomer[]>([]);

  const fetchCustomers = async () => {
    try {
      setCustomers(await getCustomers());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load customers.");
    }
  };

  useEffect(() => {
    fetchInvoices();
    fetchEntities();
    fetchCustomers();
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
            className={`button ${activeTab === "payments" ? "" : "secondary"}`}
            onClick={() => setActiveTab("payments")}
            disabled={authLoading || !canManageBilling}
            title={!canManageBilling ? "Admin or accountant access is required" : undefined}
          >
            <DollarSign size={16} /> Payments & Receipts
          </button>
          <button
            className={`button ${activeTab === "notes" ? "" : "secondary"}`}
            onClick={() => setActiveTab("notes")}
            disabled={authLoading || !canManageBilling}
            title={!canManageBilling ? "Admin or accountant access is required" : undefined}
          >
            <CreditCard size={16} /> Adjustments (CN/DN)
          </button>
          <button
            className={`button ${activeTab === "reports" ? "" : "secondary"}`}
            onClick={() => setActiveTab("reports")}
            disabled={authLoading || !canManageBilling}
            title={!canManageBilling ? "Admin or accountant access is required" : undefined}
          >
            <Layers size={16} /> Reports
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
      ) : activeTab === "payments" ? (
        <div className="stack" style={{ gap: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h2 style={{ margin: 0 }}>Payment Receipts & Allocations</h2>
              <p style={{ color: "var(--muted)", margin: "4px 0 0" }}>
                Record customer payments, check unapplied balances, and allocate funds to tax invoices.
              </p>
            </div>
            <button className="button" onClick={() => setShowRecordReceiptModal(true)}>
              <Plus size={16} /> Record Payment Receipt
            </button>
          </div>

          <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Receipt #</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Legal Entity</TableHead>
                  <TableHead>Receipt Date</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Unapplied Balance</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead style={{ textAlign: "right" }}>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {receiptsLoading ? (
                  <TableRow>
                    <TableCell colSpan={9} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                      Loading receipts...
                    </TableCell>
                  </TableRow>
                ) : receipts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                      No payment receipts found.
                    </TableCell>
                  </TableRow>
                ) : (
                  receipts.map((rec) => (
                    <TableRow key={rec.id}>
                      <TableCell>
                        <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--accent)", padding: "4px 8px", background: "rgba(59, 73, 223, 0.12)", borderRadius: 6 }}>
                          {rec.receipt_number}
                        </span>
                      </TableCell>
                      <TableCell><strong>{rec.customer_name}</strong></TableCell>
                      <TableCell>{rec.legal_entity_name}</TableCell>
                      <TableCell>{rec.receipt_date}</TableCell>
                      <TableCell>₹{parseFloat(rec.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</TableCell>
                      <TableCell>
                        <strong style={{ color: parseFloat(rec.unapplied_amount) > 0 ? "var(--warn)" : "var(--ok)" }}>
                          ₹{parseFloat(rec.unapplied_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                        </strong>
                      </TableCell>
                      <TableCell>{rec.payment_method.replace("_", " ")}</TableCell>
                      <TableCell>
                        <span className={`status ${rec.is_reversed ? "danger" : "ok"}`}>
                          {rec.is_reversed ? "REVERSED" : "ACTIVE"}
                        </span>
                      </TableCell>
                      <TableCell style={{ textAlign: "right" }}>
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
                          <button
                            className="button secondary"
                            style={{ padding: "6px 10px", fontSize: 12 }}
                            onClick={() => {
                              setSelectedReceipt(rec);
                              setAllocationForm(prev => ({ ...prev, allocated_amount: rec.unapplied_amount }));
                            }}
                          >
                            <Eye size={13} /> View & Manage
                          </button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      ) : activeTab === "notes" ? (
        <div className="stack" style={{ gap: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h2 style={{ margin: 0 }}>Credit & Debit Notes</h2>
              <p style={{ color: "var(--muted)", margin: "4px 0 0" }}>
                Issue credit notes for discounts/write-offs or debit notes to adjust billing amounts.
              </p>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="button" onClick={() => setShowCreateNoteModal({ show: true, type: "credit" })}>
                <Plus size={16} /> Create Credit Note
              </button>
              <button className="button secondary" onClick={() => setShowCreateNoteModal({ show: true, type: "debit" })}>
                <Plus size={16} /> Create Debit Note
              </button>
            </div>
          </div>

          <div className="panel" style={{ padding: 20 }}>
            <h3 style={{ margin: "0 0 16px", color: "#fff" }}>Credit Notes</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Note Number</TableHead>
                  <TableHead>Invoice #</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Total Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created At</TableHead>
                  <TableHead style={{ textAlign: "right" }}>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {notesLoading ? (
                  <TableRow>
                    <TableCell colSpan={8} style={{ textAlign: "center", padding: 16, color: "var(--muted)" }}>
                      Loading notes...
                    </TableCell>
                  </TableRow>
                ) : creditNotes.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} style={{ textAlign: "center", padding: 16, color: "var(--muted)" }}>
                      No credit notes recorded.
                    </TableCell>
                  </TableRow>
                ) : (
                  creditNotes.map((cn) => (
                    <TableRow key={cn.id}>
                      <TableCell>
                        <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--accent)", padding: "4px 8px", background: "rgba(59, 73, 223, 0.12)", borderRadius: 6 }}>
                          {cn.credit_note_number}
                        </span>
                      </TableCell>
                      <TableCell>{cn.invoice_number}</TableCell>
                      <TableCell><strong>{cn.legal_entity_name || "—"}</strong></TableCell>
                      <TableCell>{cn.reason}</TableCell>
                      <TableCell>₹{parseFloat(cn.total_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</TableCell>
                      <TableCell>
                        <span className={`status ${cn.status === "APPROVED" ? "ok" : cn.status === "VOID" ? "danger" : "warn"}`}>
                          {cn.status}
                        </span>
                      </TableCell>
                      <TableCell>{new Date(cn.created_at).toLocaleDateString()}</TableCell>
                      <TableCell style={{ textAlign: "right" }}>
                        <button
                          className="button secondary"
                          style={{ padding: "6px 10px", fontSize: 12 }}
                          onClick={() => setSelectedNote({ type: "credit", data: cn })}
                        >
                          <Eye size={13} /> View
                        </button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <div className="panel" style={{ padding: 20 }}>
            <h3 style={{ margin: "0 0 16px", color: "#fff" }}>Debit Notes</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Note Number</TableHead>
                  <TableHead>Invoice #</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Total Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created At</TableHead>
                  <TableHead style={{ textAlign: "right" }}>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {notesLoading ? (
                  <TableRow>
                    <TableCell colSpan={8} style={{ textAlign: "center", padding: 16, color: "var(--muted)" }}>
                      Loading notes...
                    </TableCell>
                  </TableRow>
                ) : debitNotes.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} style={{ textAlign: "center", padding: 16, color: "var(--muted)" }}>
                      No debit notes recorded.
                    </TableCell>
                  </TableRow>
                ) : (
                  debitNotes.map((dn) => (
                    <TableRow key={dn.id}>
                      <TableCell>
                        <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--accent)", padding: "4px 8px", background: "rgba(59, 73, 223, 0.12)", borderRadius: 6 }}>
                          {dn.debit_note_number}
                        </span>
                      </TableCell>
                      <TableCell>{dn.invoice_number}</TableCell>
                      <TableCell><strong>{dn.legal_entity_name || "—"}</strong></TableCell>
                      <TableCell>{dn.reason}</TableCell>
                      <TableCell>₹{parseFloat(dn.total_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</TableCell>
                      <TableCell>
                        <span className={`status ${dn.status === "APPROVED" ? "ok" : dn.status === "VOID" ? "danger" : "warn"}`}>
                          {dn.status}
                        </span>
                      </TableCell>
                      <TableCell>{new Date(dn.created_at).toLocaleDateString()}</TableCell>
                      <TableCell style={{ textAlign: "right" }}>
                        <button
                          className="button secondary"
                          style={{ padding: "6px 10px", fontSize: 12 }}
                          onClick={() => setSelectedNote({ type: "debit", data: dn })}
                        >
                          <Eye size={13} /> View
                        </button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      ) : activeTab === "reports" ? (
        <div className="stack" style={{ gap: 24 }}>
          <div style={{ display: "flex", gap: 8, borderBottom: "1px solid var(--line)", paddingBottom: 12 }}>
            <button
              className={`button ${reportsSubTab === "aging" ? "" : "secondary"}`}
              onClick={() => setReportsSubTab("aging")}
              style={{ padding: "8px 16px" }}
            >
              Accounts Receivable Aging
            </button>
            <button
              className={`button ${reportsSubTab === "statement" ? "" : "secondary"}`}
              onClick={() => {
                setReportsSubTab("statement");
                if (customers.length > 0 && !statementCustomer) {
                  setStatementCustomer(String(customers[0].id));
                }
              }}
              style={{ padding: "8px 16px" }}
            >
              Customer Statement Ledger
            </button>
          </div>

          {reportsSubTab === "aging" ? (
            <div className="stack" style={{ gap: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h3 style={{ margin: 0, color: "#fff" }}>Accounts Receivable (AR) Aging Report</h3>
                  <p style={{ color: "var(--muted)", margin: "4px 0 0", fontSize: 13 }}>
                    Historical outstanding customer invoice balances categorized by due dates.
                  </p>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span style={{ fontSize: 13, color: "var(--muted)" }}>As of date:</span>
                  <input
                    type="date"
                    value={asOfDate}
                    onChange={(e) => setAsOfDate(e.target.value)}
                    style={{ padding: 8, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 6, color: "#fff" }}
                  />
                  <button className="button secondary" onClick={fetchAging} style={{ padding: "8px 12px" }}>
                    <RefreshCw size={14} />
                  </button>
                </div>
              </div>

              {agingLoading ? (
                <div style={{ textAlign: "center", padding: 48, color: "var(--muted)" }}>
                  Generating AR Aging report...
                </div>
              ) : !agingReport ? (
                <div style={{ textAlign: "center", padding: 48, color: "var(--muted)" }}>
                  No aging report data.
                </div>
              ) : (
                <>
                  <div className="metrics compact" style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 12 }}>
                    {[
                      { label: "Current", val: agingReport.grand_totals.current, color: "var(--ok)" },
                      { label: "1 - 30 Days", val: agingReport.grand_totals["1_30"], color: "var(--warn)" },
                      { label: "31 - 60 Days", val: agingReport.grand_totals["31_60"], color: "var(--warn)" },
                      { label: "61 - 90 Days", val: agingReport.grand_totals["61_90"], color: "var(--danger)" },
                      { label: "90+ Days", val: agingReport.grand_totals.over_90, color: "var(--danger)" },
                      { label: "Unapplied Cash", val: agingReport.grand_totals.unapplied, color: "var(--muted)" },
                      { label: "Net Outstanding", val: agingReport.grand_totals.net_outstanding, color: "#fff", isBold: true },
                    ].map((bucket, i) => (
                      <div key={i} className="panel" style={{ padding: 12, textAlign: "center" }}>
                        <span style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase" }}>{bucket.label}</span>
                        <h4 style={{ margin: "6px 0 0", color: bucket.color, fontSize: 14, fontWeight: bucket.isBold ? 800 : 700 }}>
                          ₹{parseFloat(bucket.val).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                        </h4>
                      </div>
                    ))}
                  </div>

                  <div className="panel" style={{ padding: 20 }}>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Customer</TableHead>
                          <TableHead>Current</TableHead>
                          <TableHead>1-30</TableHead>
                          <TableHead>31-60</TableHead>
                          <TableHead>61-90</TableHead>
                          <TableHead>90+</TableHead>
                          <TableHead>Unapplied Receipts</TableHead>
                          <TableHead style={{ textAlign: "right" }}>Net Outstanding</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {agingReport.customers.map((c: any) => (
                          <TableRow key={c.customer_id}>
                            <TableCell><strong>{c.customer_name}</strong></TableCell>
                            <TableCell>₹{parseFloat(c.totals.current).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</TableCell>
                            <TableCell>₹{parseFloat(c.totals["1_30"]).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</TableCell>
                            <TableCell>₹{parseFloat(c.totals["31_60"]).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</TableCell>
                            <TableCell>₹{parseFloat(c.totals["61_90"]).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</TableCell>
                            <TableCell>₹{parseFloat(c.totals.over_90).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</TableCell>
                            <TableCell style={{ color: "var(--warn)" }}>-₹{parseFloat(c.totals.unapplied).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</TableCell>
                            <TableCell style={{ textAlign: "right" }}>
                              <strong style={{ color: parseFloat(c.totals.net_outstanding) > 0 ? "#fff" : "var(--ok)" }}>
                                ₹{parseFloat(c.totals.net_outstanding).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                              </strong>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="stack" style={{ gap: 20 }}>
              <div className="panel" style={{ padding: 20 }}>
                <h3 style={{ margin: "0 0 16px", color: "#fff" }}>Customer Statement Query</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr auto", gap: 12, alignItems: "end" }}>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Billed Customer</label>
                    <select
                      value={statementCustomer}
                      onChange={(e) => setStatementCustomer(e.target.value)}
                      style={{ width: "100%", padding: 10, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                    >
                      <option value="">Select a Customer</option>
                      {customers.map((c) => (
                        <option key={c.id} value={c.id}>{c.display_name} ({c.code})</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Start Date</label>
                    <input
                      type="date"
                      value={statementStartDate}
                      onChange={(e) => setStatementStartDate(e.target.value)}
                      style={{ width: "100%", padding: 9, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>End Date</label>
                    <input
                      type="date"
                      value={statementEndDate}
                      onChange={(e) => setStatementEndDate(e.target.value)}
                      style={{ width: "100%", padding: 9, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                    />
                  </div>
                  <button
                    className="button"
                    style={{ height: 40, padding: "0 24px" }}
                    onClick={fetchStatement}
                    disabled={!statementCustomer || statementLoading}
                  >
                    {statementLoading ? "Generating..." : "Query Statement"}
                  </button>
                </div>
              </div>

              {statementReport && (
                <div className="panel" style={{ padding: 24, display: "grid", gap: 20 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--line)", paddingBottom: 16 }}>
                    <div>
                      <h3 style={{ margin: 0, color: "#fff" }}>Customer Account Ledger Statement</h3>
                      <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: 13 }}>
                        {statementReport.customer_name} · Period: {statementReport.start_date} to {statementReport.end_date}
                      </p>
                    </div>
                    <div style={{ display: "flex", gap: 32, textAlign: "right" }}>
                      <div>
                        <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase" }}>Opening Balance</span>
                        <h4 style={{ margin: "4px 0 0", color: "#fff" }}>₹{parseFloat(statementReport.opening_balance).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</h4>
                      </div>
                      <div>
                        <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase" }}>Closing Balance</span>
                        <h4 style={{ margin: "4px 0 0", color: parseFloat(statementReport.closing_balance) > 0 ? "var(--warn)" : "var(--ok)" }}>
                          ₹{parseFloat(statementReport.closing_balance).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                        </h4>
                      </div>
                    </div>
                  </div>

                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Transaction Type</TableHead>
                        <TableHead>Reference #</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Debit (Due)</TableHead>
                        <TableHead>Credit (Received/CN)</TableHead>
                        <TableHead style={{ textAlign: "right" }}>Running Balance</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {statementReport.lines.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={7} style={{ textAlign: "center", padding: 16, color: "var(--muted)" }}>
                            No ledger entries found during this period.
                          </TableCell>
                        </TableRow>
                      ) : (
                        statementReport.lines.map((line: any, index: number) => (
                          <TableRow key={index}>
                            <TableCell>{line.date}</TableCell>
                            <TableCell>
                              <span className={`status ${line.type === "INVOICE" ? "warn" : line.type === "RECEIPT" ? "ok" : "info"}`}>
                                {line.type}
                              </span>
                            </TableCell>
                            <TableCell style={{ fontFamily: "monospace", fontSize: 12 }}>{line.reference}</TableCell>
                            <TableCell style={{ fontSize: 13, color: "#cbd5e1" }}>{line.description}</TableCell>
                            <TableCell style={{ color: parseFloat(line.debit) > 0 ? "#f87171" : "var(--muted)" }}>
                              {parseFloat(line.debit) > 0 ? `₹${parseFloat(line.debit).toLocaleString("en-IN", { minimumFractionDigits: 2 })}` : "—"}
                            </TableCell>
                            <TableCell style={{ color: parseFloat(line.credit) > 0 ? "#4ade80" : "var(--muted)" }}>
                              {parseFloat(line.credit) > 0 ? `₹${parseFloat(line.credit).toLocaleString("en-IN", { minimumFractionDigits: 2 })}` : "—"}
                            </TableCell>
                            <TableCell style={{ textAlign: "right", fontWeight: 600 }}>
                              ₹{parseFloat(line.balance).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>
          )}
        </div>
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

      {/* View & Manage Payment Receipt Overlay */}
      {selectedReceipt && (
        <div className="invoice-detail-overlay">
          <section className="panel invoice-detail-panel" style={{ maxWidth: 800 }}>
            <div className="invoice-detail-header">
              <div>
                <span className="eyebrow">{selectedReceipt.is_reversed ? "REVERSED" : "ACTIVE"}</span>
                <h2>Receipt {selectedReceipt.receipt_number}</h2>
                <p>{selectedReceipt.customer_name} · Recorded on {selectedReceipt.receipt_date}</p>
              </div>
              <button className="button secondary" onClick={() => setSelectedReceipt(null)}><X size={15} /> Close</button>
            </div>
            
            <div className="invoice-preview-grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
              <div><span>Total Amount</span><strong>₹{parseFloat(selectedReceipt.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong></div>
              <div><span>Unapplied Balance</span><strong style={{ color: "var(--warn)" }}>₹{parseFloat(selectedReceipt.unapplied_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong></div>
              <div><span>Payment Method</span><strong>{selectedReceipt.payment_method.replace("_", " ")}</strong></div>
              <div><span>Ref / Instrument</span><strong>{selectedReceipt.reference_number || "—"}</strong></div>
            </div>

            <div className="invoice-detail-lines" style={{ marginTop: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3>Allocations</h3>
                {!selectedReceipt.is_reversed && parseFloat(selectedReceipt.unapplied_amount) > 0 && (
                  <button className="button" style={{ padding: "6px 12px", fontSize: 13 }} onClick={() => setShowAllocateModal(true)}>
                    <Plus size={14} /> Allocate Funds
                  </button>
                )}
              </div>
              {selectedReceipt.allocations && selectedReceipt.allocations.length > 0 ? (
                selectedReceipt.allocations.map((alloc) => (
                  <div key={alloc.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: "1px solid var(--line)" }}>
                    <span>
                      <strong>Allocated to Invoice {alloc.invoice_number}</strong>
                      <small>TDS Amount: ₹{parseFloat(alloc.tds_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })} · Status: {alloc.is_reversed ? "Reversed" : "Active"}</small>
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <strong>₹{parseFloat(alloc.allocated_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong>
                      {!alloc.is_reversed && !selectedReceipt.is_reversed && (
                        <button
                          className="button secondary"
                          style={{ padding: "4px 8px", fontSize: 11, background: "rgba(239, 68, 68, 0.15)", color: "var(--danger)", border: "1px solid rgba(239, 68, 68, 0.2)" }}
                          onClick={() => handleReverseAllocation(alloc.id)}
                        >
                          Reverse
                        </button>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <p style={{ color: "var(--muted)", fontSize: 13 }}>No allocations made for this receipt.</p>
              )}
            </div>

            {!selectedReceipt.is_reversed && (
              <div className="invoice-detail-actions" style={{ borderTop: "1px solid var(--line)", paddingTop: 16 }}>
                <input
                  type="text"
                  placeholder="Enter reason to reverse this receipt..."
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                />
                <button
                  className="button secondary"
                  style={{ background: "rgba(239, 68, 68, 0.15)", color: "var(--danger)", border: "1px solid rgba(239, 68, 68, 0.2)" }}
                  disabled={!correctionReason.trim()}
                  onClick={() => handleReverseReceipt(selectedReceipt.id, correctionReason)}
                >
                  Reverse Receipt
                </button>
              </div>
            )}
          </section>
        </div>
      )}

      {/* Record Payment Receipt Modal */}
      {showRecordReceiptModal && (
        <div className="invoice-detail-overlay">
          <form className="panel invoice-detail-panel" style={{ maxWidth: 550 }} onSubmit={handleRecordReceiptSubmit}>
            <div className="invoice-detail-header">
              <h2>Record Payment Receipt</h2>
              <button type="button" className="button secondary" onClick={() => setShowRecordReceiptModal(false)}><X size={15} /> Cancel</button>
            </div>
            
            <div className="stack" style={{ gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Legal Entity</label>
                <select
                  required
                  value={receiptForm.legal_entity}
                  onChange={(e) => setReceiptForm(prev => ({ ...prev, legal_entity: e.target.value }))}
                  style={{ width: "100%", padding: 10, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                >
                  <option value="">Select Legal Entity</option>
                  {entities.map(ent => (
                    <option key={ent.id} value={ent.id}>{ent.legal_name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Billed Customer</label>
                <select
                  required
                  value={receiptForm.customer}
                  onChange={(e) => setReceiptForm(prev => ({ ...prev, customer: e.target.value }))}
                  style={{ width: "100%", padding: 10, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                >
                  <option value="">Select Customer</option>
                  {customers.map(cust => (
                    <option key={cust.id} value={cust.id}>{cust.display_name} ({cust.code})</option>
                  ))}
                </select>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Amount</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="0.00"
                    value={receiptForm.amount}
                    onChange={(e) => setReceiptForm(prev => ({ ...prev, amount: e.target.value }))}
                    style={{ width: "100%", padding: 9, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Currency</label>
                  <select
                    value={receiptForm.currency}
                    onChange={(e) => setReceiptForm(prev => ({ ...prev, currency: e.target.value }))}
                    style={{ width: "100%", padding: 10, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                  >
                    <option value="INR">INR</option>
                    <option value="USD">USD</option>
                  </select>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Payment Method</label>
                  <select
                    value={receiptForm.payment_method}
                    onChange={(e) => setReceiptForm(prev => ({ ...prev, payment_method: e.target.value }))}
                    style={{ width: "100%", padding: 10, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                  >
                    <option value="BANK_TRANSFER">Bank Transfer</option>
                    <option value="CASH">Cash</option>
                    <option value="CHEQUE">Cheque</option>
                    <option value="ONLINE">Online Portal</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Ref / Instrument Number</label>
                  <input
                    type="text"
                    placeholder="UTR / Check Reference"
                    value={receiptForm.reference_number}
                    onChange={(e) => setReceiptForm(prev => ({ ...prev, reference_number: e.target.value }))}
                    style={{ width: "100%", padding: 9, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                  />
                </div>
              </div>
            </div>

            <div className="invoice-detail-actions" style={{ borderTop: "1px solid var(--line)", paddingTop: 16, marginTop: 14 }}>
              <button type="submit" className="button" style={{ width: "100%" }}>Record Receipt</button>
            </div>
          </form>
        </div>
      )}

      {/* Allocate Payment Modal */}
      {showAllocateModal && selectedReceipt && (
        <div className="invoice-detail-overlay">
          <form className="panel invoice-detail-panel" style={{ maxWidth: 500 }} onSubmit={handleAllocateSubmit}>
            <div className="invoice-detail-header">
              <h2>Allocate Funds</h2>
              <button type="button" className="button secondary" onClick={() => setShowAllocateModal(false)}><X size={15} /> Cancel</button>
            </div>
            
            <div className="stack" style={{ gap: 14 }}>
              <div>
                <span className="eyebrow" style={{ display: "block", marginBottom: 6 }}>Allocating From Receipt</span>
                <strong>{selectedReceipt.receipt_number} ({selectedReceipt.customer_name})</strong>
                <p style={{ color: "var(--muted)", fontSize: 12, margin: "4px 0 0" }}>Unapplied balance: ₹{parseFloat(selectedReceipt.unapplied_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</p>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Tax Invoice</label>
                <select
                  required
                  value={allocationForm.invoice}
                  onChange={(e) => {
                    const invId = e.target.value;
                    const inv = invoices.find(i => i.id === Number(invId));
                    setAllocationForm(prev => ({
                      ...prev,
                      invoice: invId,
                      allocated_amount: inv ? String(Math.min(parseFloat(selectedReceipt.unapplied_amount), parseFloat(inv.balance_amount))) : ""
                    }));
                  }}
                  style={{ width: "100%", padding: 10, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                >
                  <option value="">Select Invoice</option>
                  {invoices
                    .filter(i => i.customer_name === selectedReceipt.customer_name && ["ISSUED", "SENT", "PARTIALLY_PAID"].includes(i.status))
                    .map(i => (
                      <option key={i.id} value={i.id}>{i.invoice_number || `Draft #${i.id}`} (Due: ₹{parseFloat(i.balance_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })})</option>
                    ))
                  }
                </select>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Allocation Amount</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={allocationForm.allocated_amount}
                    onChange={(e) => setAllocationForm(prev => ({ ...prev, allocated_amount: e.target.value }))}
                    style={{ width: "100%", padding: 9, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>TDS Withheld Amount</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={allocationForm.tds_amount}
                    onChange={(e) => setAllocationForm(prev => ({ ...prev, tds_amount: e.target.value }))}
                    style={{ width: "100%", padding: 9, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                  />
                </div>
              </div>
            </div>

            <div className="invoice-detail-actions" style={{ borderTop: "1px solid var(--line)", paddingTop: 16, marginTop: 14 }}>
              <button type="submit" className="button" style={{ width: "100%" }}>Allocate</button>
            </div>
          </form>
        </div>
      )}

      {/* Credit / Debit Note Details Overlay */}
      {selectedNote && (
        <div className="invoice-detail-overlay">
          <section className="panel invoice-detail-panel" style={{ maxWidth: 850 }}>
            <div className="invoice-detail-header">
              <div>
                <span className="eyebrow">{selectedNote.type.toUpperCase()} NOTE · {selectedNote.data.status}</span>
                <h2>{selectedNote.type === "credit" ? selectedNote.data.credit_note_number : selectedNote.data.debit_note_number}</h2>
                <p>Linked to Invoice {selectedNote.data.invoice_number || `#${selectedNote.data.invoice}`}</p>
              </div>
              <button className="button secondary" onClick={() => setSelectedNote(null)}><X size={15} /> Close</button>
            </div>

            <div className="invoice-preview-grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
              <div><span>Total Note Value</span><strong>₹{parseFloat(selectedNote.data.total_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong></div>
              <div><span>Taxable Amount</span><strong>₹{parseFloat(selectedNote.data.taxable_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong></div>
              <div><span>CGST / SGST</span><strong>₹{parseFloat(selectedNote.data.cgst_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })} / ₹{parseFloat(selectedNote.data.sgst_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong></div>
              <div><span>IGST Amount</span><strong>₹{parseFloat(selectedNote.data.igst_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong></div>
            </div>

            <div style={{ padding: 14, background: "rgba(255,255,255,0.03)", border: "1px solid var(--line)", borderRadius: 8 }}>
              <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase" }}>Reason for Issuance</span>
              <p style={{ margin: "4px 0 0", color: "#fff", fontSize: 14 }}>{selectedNote.data.reason}</p>
            </div>

            <div className="invoice-detail-lines">
              <h3>Itemized Lines</h3>
              {selectedNote.data.lines && selectedNote.data.lines.map((line: any) => (
                <div key={line.id}>
                  <span>
                    <strong>{line.description}</strong>
                    <small>Qty: {line.quantity} · Rate: ₹{parseFloat(line.unit_rate).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</small>
                  </span>
                  <div style={{ textAlign: "right" }}>
                    <strong>₹{parseFloat(line.line_total).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong>
                    <div style={{ fontSize: 11, color: "var(--muted)" }}>Taxes: CGST ₹{parseFloat(line.cgst_amount).toFixed(2)} | SGST ₹{parseFloat(line.sgst_amount).toFixed(2)}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="invoice-detail-actions" style={{ borderTop: "1px solid var(--line)", paddingTop: 16 }}>
              {selectedNote.data.status === "DRAFT" && (
                <button className="button" onClick={() => handleApproveNote(selectedNote.data.id, selectedNote.type)}>
                  Approve Note
                </button>
              )}
              {selectedNote.data.status === "APPROVED" && (
                <button
                  className="button secondary"
                  style={{ background: "rgba(239, 68, 68, 0.15)", color: "var(--danger)", border: "1px solid rgba(239, 68, 68, 0.2)" }}
                  onClick={() => handleVoidNote(selectedNote.data.id, selectedNote.type)}
                >
                  Void Note
                </button>
              )}
            </div>
          </section>
        </div>
      )}

      {/* Create Credit / Debit Note Modal */}
      {showCreateNoteModal.show && (
        <div className="invoice-detail-overlay">
          <form className="panel invoice-detail-panel" style={{ maxWidth: 650 }} onSubmit={handleCreateNoteSubmit}>
            <div className="invoice-detail-header">
              <h2>Create {showCreateNoteModal.type === "credit" ? "Credit" : "Debit"} Note</h2>
              <button type="button" className="button secondary" onClick={() => {
                setShowCreateNoteModal({ show: false, type: "credit" });
                setNoteForm({ invoice: "", reason: "", lines: [] });
              }}><X size={15} /> Cancel</button>
            </div>

            <div className="stack" style={{ gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Select Tax Invoice</label>
                <select
                  required
                  value={noteForm.invoice}
                  onChange={(e) => handleNoteInvoiceChange(e.target.value)}
                  style={{ width: "100%", padding: 10, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                >
                  <option value="">Select Invoice</option>
                  {invoices
                    .filter(i => ["ISSUED", "SENT", "PARTIALLY_PAID", "PAID"].includes(i.status))
                    .map(i => (
                      <option key={i.id} value={i.id}>{i.invoice_number || `Draft #${i.id}`} ({i.customer_name} · Total: ₹{parseFloat(i.total_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })})</option>
                    ))
                  }
                </select>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Reason for Adjustment</label>
                <input
                  type="text"
                  required
                  placeholder="Discount, correction, rate difference, etc..."
                  value={noteForm.reason}
                  onChange={(e) => setNoteForm(prev => ({ ...prev, reason: e.target.value }))}
                  style={{ width: "100%", padding: 9, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 7, color: "#fff" }}
                />
              </div>

              {noteForm.lines.length > 0 && (
                <div style={{ display: "grid", gap: 10 }}>
                  <label style={{ fontSize: 12, color: "var(--muted)", fontWeight: "bold" }}>Line Item Breakdown</label>
                  {noteForm.lines.map((line, idx) => (
                    <div key={line.invoice_line_id} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 10, alignItems: "center", paddingBottom: 10, borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: "bold" }}>{line.description}</div>
                        <div style={{ fontSize: 11, color: "var(--muted)" }}>Original Rate: ₹{line.rate} | Max Qty: {line.max_qty}</div>
                      </div>
                      <div>
                        <label style={{ fontSize: 10, color: "var(--muted)" }}>Qty to adjust</label>
                        <input
                          type="number"
                          step="1"
                          min="0"
                          max={line.max_qty}
                          value={line.quantity}
                          onChange={(e) => {
                            const val = e.target.value;
                            setNoteForm(prev => {
                              const updated = [...prev.lines];
                              updated[idx].quantity = val;
                              return { ...prev, lines: updated };
                            });
                          }}
                          style={{ width: "100%", padding: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 5, color: "#fff" }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: 10, color: "var(--muted)" }}>Rate</label>
                        <input
                          type="number"
                          step="0.01"
                          value={line.unit_rate}
                          onChange={(e) => {
                            const val = e.target.value;
                            setNoteForm(prev => {
                              const updated = [...prev.lines];
                              updated[idx].unit_rate = val;
                              return { ...prev, lines: updated };
                            });
                          }}
                          style={{ width: "100%", padding: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 5, color: "#fff" }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="invoice-detail-actions" style={{ borderTop: "1px solid var(--line)", paddingTop: 16, marginTop: 14 }}>
              <button type="submit" className="button" style={{ width: "100%" }}>Create Draft Note</button>
            </div>
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
