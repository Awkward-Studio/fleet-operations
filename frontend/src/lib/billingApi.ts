import { request, requestBlob, requestText } from "./api";

export type BillingLegalEntity = {
  id: number;
  legal_name: string;
  trade_name?: string;
  pan?: string;
  gstin?: string;
  state_code?: string;
  registered_address?: string;
  billing_email?: string;
  billing_phone?: string;
  bank_name?: string;
  bank_account_number?: string;
  ifsc_code?: string;
  bank_branch?: string;
  invoice_notes?: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
};

export type BillingTripSource = {
  id: number;
  booking_type: string;
  customer_display_name_snapshot: string;
  pickup_city: string;
  drop_city: string;
  status: string;
  pricing_amount_status: string;
};

export type BillableTrip = BillingTripSource & {
  customer_name: string;
  pickup_at: string;
  quoted_total_amount?: string;
  po_number?: string;
  duty_type?: string;
  pricing_snapshot?: {
    package?: { name?: string; code?: string };
    [key: string]: unknown;
  };
  billing_eligibility: {
    eligible: boolean;
    bill_to_key: string;
    estimated_taxable_amount: string;
    blockers: Array<{ code: string; message: string }>;
  };
  grouping_key: {
    bill_to_key: string;
    booking_channel: string;
    currency: string;
    po_number: string;
    billing_cycle: string;
  };
  amount_summary: {
    source: string;
    taxable_amount: string;
    tax_amount: string;
    total_amount: string;
  };
  closeout_summary: {
    id: number;
    status: string;
    actual_km: string;
    actual_hours: string;
    final_total_amount: string | null;
    variance_amount: string | null;
    variance_percent: string | null;
    approved_extra_count: number;
  } | null;
  bill_to_snapshot: {
    type: string;
    key: string;
    name: string;
    address: string;
    gstin: string;
    email: string;
    phone: string;
  };
};

export type BillableTripPage = {
  count: number;
  page: number;
  page_size: number;
  next_page: number | null;
  previous_page: number | null;
  summary: {
    eligible_trip_count: number;
    estimated_taxable_amount: string;
    estimated_tax_amount: string;
    estimated_total_amount: string;
  };
  results: BillableTrip[];
};

export type InvoiceGroupingPreview = {
  groups: Array<{
    grouping_key: BillableTrip["grouping_key"];
    bill_to_key: string;
    bill_to_name: string;
    bill_to_snapshot: Omit<BillableTrip["bill_to_snapshot"], "key">;
    booking_channel: string;
    currency: string;
    po_number: string;
    billing_cycle: string;
    trip_ids: number[];
    eligible: boolean;
    blockers: Array<{ trip_id: number; code: string; message: string }>;
    estimated_taxable_amount: string;
    estimated_tax_amount: string;
    estimated_total_amount: string;
  }>;
};

export type BillingCloseout = {
  id: number;
  trip: number;
  status:
    | "INCOMPLETE"
    | "EXCEPTION_REVIEW"
    | "SUBMITTED"
    | "REOPENED"
    | "APPROVED"
    | "BILLING_READY";
  status_display: string;
  billing_ready: boolean;
  actual_km: string;
  actual_hours: string;
  start_odometer_km: string;
  end_odometer_km: string;
  actual_pickup_at: string | null;
  actual_drop_at: string | null;
  waiting_minutes: number;
  metering_policy: string;
  source_snapshot: Record<string, unknown>;
  evidence_snapshot: Record<string, unknown>;
  milestone_snapshot: Record<string, unknown>;
  quantity_provenance: Record<string, unknown>;
  blockers: Array<{ code?: string; message?: string } | string>;
  final_charge_snapshot: {
    components?: Record<string, string>;
    approved_manual_charges?: BillingTripCharge[];
    [key: string]: unknown;
  };
  final_taxable_amount: string | null;
  final_tax_amount: string | null;
  final_total_amount: string | null;
  quote_variance_amount: string | null;
  quote_variance_percent: string | null;
  trip_details: {
    id: number;
    customer_name: string;
    customer_display_name_snapshot?: string;
    pickup_city: string;
    drop_city: string;
    booking_type?: string;
    duty_type?: string;
    quoted_taxable_amount?: string;
    quoted_tax_amount?: string;
    quoted_total_amount?: string;
    pricing_snapshot?: Record<string, unknown>;
  };
  extra_charges: BillingTripCharge[];
  audit_events: BillingCloseoutAudit[];
};

export type BillingTripCharge = {
  id: number;
  category: string;
  category_display: string;
  amount: string;
  description: string;
  receipt_attachment_url: string;
  is_approved: boolean;
  created_by: number | null;
  approved_by: number | null;
};

export type BillingCloseoutAudit = {
  id: number;
  action: string;
  reason: string;
  actor_name: string;
  from_status: string;
  to_status: string;
  created_at: string;
};

export type CloseoutReconciliationReport = {
  generated_at: string;
  coverage: {
    completed_trips: number;
    with_closeout: number;
    missing_closeout: number;
    reconciles: boolean;
  };
  issue_counts: Record<
    "missing_closeout" | "stale_review" | "large_variance" | "zero_fare" | "reopened_invoiced",
    number
  >;
};

export type BillingInvoiceLine = {
  id: number;
  description: string;
  sac_hsn_code: string;
  quantity: string;
  unit_rate: string;
  taxable_value: string;
  cgst_amount: string;
  sgst_amount: string;
  igst_amount: string;
  line_total: string;
  source_type: string;
  source_id: string;
  calculation_version: string;
};

export type BillingInvoice = {
  id: number;
  invoice_number: string | null;
  legal_entity_name: string;
  customer_name: string | null;
  status:
    | "DRAFT"
    | "REVIEW"
    | "APPROVED"
    | "ISSUED"
    | "SENT"
    | "PARTIALLY_PAID"
    | "PAID"
    | "VOID"
    | "CREDITED";
  subtotal: string;
  taxable_amount: string;
  cgst_amount: string;
  sgst_amount: string;
  igst_amount: string;
  total_amount: string;
  paid_amount: string;
  balance_amount: string;
  issue_date: string | null;
  due_date: string | null;
  lines: BillingInvoiceLine[];
  source_trips?: BillingTripSource[];
  submitted_by?: number | null;
  submitted_at?: string | null;
  approved_by?: number | null;
  approved_at?: string | null;
  audit_events: Array<{
    id: number;
    action: string;
    actor_name: string;
    from_status: string;
    to_status: string;
    reason: string;
    created_at: string;
  }>;
};

export type OTAProfitabilityRow = {
  trip: {
    id: number;
    route: string;
    pickup_at: string | null;
    status: string;
    customer_name: string;
    vehicle: string;
    driver: string;
  };
  external: {
    provider_code: string;
    provider_name: string;
    provider_booking_id: string;
    partner_reference_number: string;
    provider_trip_id: string;
  };
  waterfall: {
    currency: string;
    gross_fare: string;
    fare_tax: string;
    commission_amount: string;
    commission_tax: string;
    withholding_amount: string;
    cancellation_amount: string;
    net_expected: string;
    formula: string;
  };
  settlement: {
    batch_id: number | null;
    batch_reference: string;
    payout_date: string | null;
    classification: string;
    status: string;
    expected_amount: string;
    received_amount: string;
    variance_amount: string;
  };
  profitability: {
    revenue_basis: string;
    fleet_revenue: string;
    approved_expenses: string;
    approved_closeout_charges: string;
    approved_costs: string;
    contribution_margin: string;
    margin_incomplete: boolean;
    incomplete_reasons: string[];
  };
  journals: {
    booking_journal: string;
    settlement_journal: string;
  };
};

export type OTAProfitabilityReport = {
  summary: {
    trip_count: number;
    exception_count: number;
    incomplete_margin_count: number;
    gross_fare: string;
    net_expected: string;
    received_amount: string;
    approved_costs: string;
    contribution_margin: string;
  };
  results: OTAProfitabilityRow[];
};

type ApiList<T> = T[] | { results: T[] };

function unwrapList<T>(value: ApiList<T>): T[] {
  return Array.isArray(value) ? value : value.results;
}

export async function listBillingInvoices(): Promise<BillingInvoice[]> {
  return unwrapList(await request<ApiList<BillingInvoice>>("/billing/invoices/"));
}

export async function listBillingEntities(): Promise<BillingLegalEntity[]> {
  return unwrapList(await request<ApiList<BillingLegalEntity>>("/billing/entities/"));
}

export function createBillingEntity(payload: Partial<BillingLegalEntity>): Promise<BillingLegalEntity> {
  return request<BillingLegalEntity>("/billing/entities/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listBillableTrips(params: {
  search?: string;
  booking_type?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<BillableTripPage> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  return request<BillableTripPage>(`/billing/invoices/eligible_trips/?${query}`);
}

export function previewInvoiceGrouping(tripIds: number[]): Promise<InvoiceGroupingPreview> {
  return request<InvoiceGroupingPreview>("/billing/invoices/grouping_preview/", {
    method: "POST",
    body: JSON.stringify({ trip_ids: tripIds }),
  });
}

export async function listBillingCloseouts(status?: string): Promise<BillingCloseout[]> {
  const query = status && status !== "ALL" ? `?status=${encodeURIComponent(status)}` : "";
  return unwrapList(await request<ApiList<BillingCloseout>>(`/billing/closeouts/${query}`));
}

export function getCloseoutReconciliationReport(): Promise<CloseoutReconciliationReport> {
  return request<CloseoutReconciliationReport>("/billing/closeouts/reconciliation/");
}

function closeoutAction(
  closeoutId: number,
  action: string,
  payload: Record<string, unknown> = {},
): Promise<BillingCloseout> {
  return request<BillingCloseout>(`/billing/closeouts/${closeoutId}/${action}/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export const submitBillingCloseout = (id: number) => closeoutAction(id, "submit");
export const approveBillingCloseout = (id: number) => closeoutAction(id, "approve");
export const markCloseoutBillingReady = (id: number) => closeoutAction(id, "mark_billing_ready");
export const returnBillingCloseout = (id: number, reason: string) =>
  closeoutAction(id, "return", { reason });
export const reopenBillingCloseout = (id: number, reason: string) =>
  closeoutAction(id, "reopen", { reason });
export const addBillingCloseoutCharge = (
  id: number,
  payload: Pick<BillingTripCharge, "category" | "amount" | "description" | "receipt_attachment_url">,
) => closeoutAction(id, "add_charge", payload);
export const approveBillingCloseoutCharge = (id: number, chargeId: number) =>
  closeoutAction(id, "approve_charge", { charge_id: chargeId });

export function generateInvoiceDraft(payload: {
  legal_entity_id: number;
  trip_ids: number[];
}): Promise<BillingInvoice> {
  return request<BillingInvoice>("/billing/invoices/generate_draft/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function issueBillingInvoice(invoiceId: number): Promise<BillingInvoice> {
  return request<BillingInvoice>(`/billing/invoices/${invoiceId}/issue/`, {
    method: "POST",
  });
}

function invoiceAction(
  invoiceId: number,
  action: string,
  payload: Record<string, unknown> = {},
): Promise<BillingInvoice> {
  return request<BillingInvoice>(`/billing/invoices/${invoiceId}/${action}/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export const submitBillingInvoiceReview = (id: number) => invoiceAction(id, "submit_review");
export const approveBillingInvoice = (id: number) => invoiceAction(id, "approve");
export const voidBillingInvoice = (id: number, reason: string) =>
  invoiceAction(id, "void", { reason });

export function previewBillingInvoice(invoiceId: number): Promise<string> {
  return requestText(`/billing/invoices/${invoiceId}/html_preview/`);
}

export function exportBillingInvoiceTallyXml(invoiceId: number): Promise<string> {
  return requestText(`/billing/invoices/${invoiceId}/tally_xml/`);
}

export function downloadBillingInvoiceDocument(invoiceId: number): Promise<Blob> {
  return requestBlob(`/billing/invoices/${invoiceId}/document/`);
}

export function downloadOfficialInvoicePdf(invoiceId: number): Promise<Blob> {
  return requestBlob(`/billing/invoices/${invoiceId}/official-pdf/`);
}

export function downloadDutySlipPdf(invoiceId: number): Promise<Blob> {
  return requestBlob(`/billing/invoices/${invoiceId}/duty-slip-pdf/`);
}


export type ReconciliationDashboardData = {
  trips_missing_closeout: Array<{
    trip_id: number;
    customer_name: string;
    pickup_at: string | null;
    amount: string;
    description: string;
  }>;
  closeouts_not_invoiced: Array<{
    closeout_id: number;
    trip_id: number;
    customer_name: string;
    final_total_amount: string;
    description: string;
  }>;
  invoices_missing_journals: Array<{
    invoice_id: number;
    invoice_number: string;
    customer_name: string;
    total_amount: string;
    description: string;
  }>;
  invoices_journal_amount_mismatches: Array<{
    invoice_id: number;
    invoice_number: string;
    journal_entry_number: string;
    invoice_amount: string;
    journal_amount: string;
    description: string;
  }>;
  receipts_missing_journals: Array<{
    receipt_id: number;
    receipt_number: string;
    customer_name: string;
    amount: string;
    description: string;
  }>;
  receipts_journal_amount_mismatches: Array<{
    receipt_id: number;
    receipt_number: string;
    journal_entry_number: string;
    receipt_amount: string;
    journal_amount: string;
    description: string;
  }>;
  allocations_missing_journals: Array<{
    allocation_id: number;
    receipt_number: string;
    invoice_number: string;
    tds_amount: string;
    description: string;
  }>;
  unbalanced_journals: Array<{
    journal_entry_number: string;
    debit_total: string;
    credit_total: string;
    description: string;
  }>;
};

export function getReconciliationDashboard(): Promise<ReconciliationDashboardData> {
  return request<ReconciliationDashboardData>("/billing/invoices/reconciliation-dashboard/");
}

export function getOTAProfitabilityReport(params: {
  counterparty?: string;
  status?: string;
} = {}): Promise<OTAProfitabilityReport> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) query.set(key, value);
  });
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<OTAProfitabilityReport>(`/billing/ota-settlements/profitability/${suffix}`);
}


// --- New Payment Receipts & Allocations APIs ---

export type PaymentReceipt = {
  id: number;
  receipt_number: string;
  legal_entity: number;
  legal_entity_name: string;
  receipt_date: string;
  customer: number;
  customer_name: string;
  amount: string;
  unapplied_amount: string;
  currency: string;
  payment_method: string;
  reference_number: string;
  is_reversed: boolean;
  reversal_reason: string;
  created_by: number | null;
  created_at: string;
  journal_entry_id?: number | null;
  journal_entry_number?: string | null;
  allocations?: PaymentAllocation[];
};

export type PaymentAllocation = {
  id: number;
  receipt: number;
  receipt_number?: string;
  invoice: number;
  invoice_number?: string;
  allocated_amount: string;
  tds_amount: string;
  is_reversed: boolean;
  created_at: string;
  journal_entry_id?: number | null;
  journal_entry_number?: string | null;
};

export async function listPaymentReceipts(): Promise<PaymentReceipt[]> {
  return unwrapList(await request<ApiList<PaymentReceipt>>("/billing/receipts/"));
}

export function createPaymentReceipt(payload: {
  legal_entity: number;
  customer: number;
  amount: string | number;
  currency?: string;
  payment_method?: string;
  reference_number?: string;
}): Promise<PaymentReceipt> {
  return request<PaymentReceipt>("/billing/receipts/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function reversePaymentReceipt(id: number, reason: string): Promise<PaymentReceipt> {
  return request<PaymentReceipt>(`/billing/receipts/${id}/reverse/`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function createPaymentAllocation(payload: {
  receipt: number;
  invoice: number;
  allocated_amount: string | number;
  tds_amount?: string | number;
}): Promise<PaymentAllocation> {
  return request<PaymentAllocation>("/billing/allocations/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function reversePaymentAllocation(id: number): Promise<PaymentAllocation> {
  return request<PaymentAllocation>(`/billing/allocations/${id}/reverse/`, {
    method: "POST",
  });
}


// --- New Credit Notes & Debit Notes APIs ---

export type CreditNoteLine = {
  id: number;
  credit_note: number;
  invoice_line: number | null;
  description: string;
  quantity: string;
  unit_rate: string;
  taxable_value: string;
  cgst_rate: string;
  cgst_amount: string;
  sgst_rate: string;
  sgst_amount: string;
  igst_rate: string;
  igst_amount: string;
  line_total: string;
};

export type CreditNote = {
  id: number;
  credit_note_number: string;
  invoice: number;
  invoice_number?: string;
  legal_entity: number;
  legal_entity_name?: string;
  reason: string;
  status: "DRAFT" | "APPROVED" | "VOID";
  total_amount: string;
  taxable_amount: string;
  cgst_amount: string;
  sgst_amount: string;
  igst_amount: string;
  created_by: number | null;
  created_at: string;
  approved_by: number | null;
  approved_at: string | null;
  lines?: CreditNoteLine[];
  journal_entry_id?: number | null;
  journal_entry_number?: string | null;
};

export type DebitNoteLine = {
  id: number;
  debit_note: number;
  invoice_line: number | null;
  description: string;
  quantity: string;
  unit_rate: string;
  taxable_value: string;
  cgst_rate: string;
  cgst_amount: string;
  sgst_rate: string;
  sgst_amount: string;
  igst_rate: string;
  igst_amount: string;
  line_total: string;
};

export type DebitNote = {
  id: number;
  debit_note_number: string;
  invoice: number;
  invoice_number?: string;
  legal_entity: number;
  legal_entity_name?: string;
  reason: string;
  status: "DRAFT" | "APPROVED" | "VOID";
  total_amount: string;
  taxable_amount: string;
  cgst_amount: string;
  sgst_amount: string;
  igst_amount: string;
  created_by: number | null;
  created_at: string;
  approved_by: number | null;
  approved_at: string | null;
  lines?: DebitNoteLine[];
  journal_entry_id?: number | null;
  journal_entry_number?: string | null;
};

export async function listCreditNotes(): Promise<CreditNote[]> {
  return unwrapList(await request<ApiList<CreditNote>>("/billing/credit-notes/"));
}

export function createCreditNote(payload: {
  invoice: number;
  reason: string;
  lines: Array<{
    invoice_line_id: number;
    quantity: number | string;
    unit_rate: number | string;
  }>;
}): Promise<CreditNote> {
  return request<CreditNote>("/billing/credit-notes/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function approveCreditNote(id: number): Promise<CreditNote> {
  return request<CreditNote>(`/billing/credit-notes/${id}/approve/`, {
    method: "POST",
  });
}

export function voidCreditNote(id: number): Promise<CreditNote> {
  return request<CreditNote>(`/billing/credit-notes/${id}/void/`, {
    method: "POST",
  });
}

export async function listDebitNotes(): Promise<DebitNote[]> {
  return unwrapList(await request<ApiList<DebitNote>>("/billing/debit-notes/"));
}

export function createDebitNote(payload: {
  invoice: number;
  reason: string;
  lines: Array<{
    invoice_line_id: number;
    quantity: number | string;
    unit_rate: number | string;
  }>;
}): Promise<DebitNote> {
  return request<DebitNote>("/billing/debit-notes/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function approveDebitNote(id: number): Promise<DebitNote> {
  return request<DebitNote>(`/billing/debit-notes/${id}/approve/`, {
    method: "POST",
  });
}

export function voidDebitNote(id: number): Promise<DebitNote> {
  return request<DebitNote>(`/billing/debit-notes/${id}/void/`, {
    method: "POST",
  });
}


// --- New Reports & Statements APIs ---

export type ARAgingCustomer = {
  customer_id: number;
  customer_name: string;
  invoices: Array<{
    invoice_id: number;
    invoice_number: string;
    issue_date: string;
    due_date: string;
    days_overdue: number;
    original_amount: string;
    outstanding_balance: string;
    bucket: string;
  }>;
  unapplied_receipts: Array<{
    receipt_id: number;
    receipt_number: string;
    receipt_date: string;
    amount: string;
    unapplied_amount: string;
  }>;
  totals: {
    current: string;
    "1_30": string;
    "31_60": string;
    "61_90": string;
    over_90: string;
    unapplied: string;
    net_outstanding: string;
  };
};

export type ARAgingReport = {
  as_of_date: string;
  customers: ARAgingCustomer[];
  grand_totals: {
    current: string;
    "1_30": string;
    "31_60": string;
    "61_90": string;
    over_90: string;
    unapplied: string;
    net_outstanding: string;
  };
};

export type CustomerStatementLine = {
  date: string;
  type: string;
  reference: string;
  description: string;
  debit: string;
  credit: string;
  balance: string;
};

export type CustomerStatementReport = {
  customer_id: number;
  customer_name: string;
  start_date: string;
  end_date: string;
  opening_balance: string;
  closing_balance: string;
  lines: CustomerStatementLine[];
};

export function getARAgingReport(asOfDate?: string): Promise<ARAgingReport> {
  const query = asOfDate ? `?as_of_date=${asOfDate}` : "";
  return request<ARAgingReport>(`/billing/invoices/aging/${query}`);
}

export function getCustomerStatementReport(
  customerId: number,
  startDate: string,
  endDate: string,
): Promise<CustomerStatementReport> {
  return request<CustomerStatementReport>(
    `/billing/invoices/statement/?customer=${customerId}&start_date=${startDate}&end_date=${endDate}`,
  );
}

