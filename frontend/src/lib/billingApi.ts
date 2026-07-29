import { request, requestBlob, requestText } from "./api";

export type BillingLegalEntity = {
  id: number;
  legal_name: string;
  trade_name: string;
  gstin: string;
  state_code: string;
  is_active: boolean;
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

