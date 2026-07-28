import { request, requestText } from "./api";

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

export function previewBillingInvoice(invoiceId: number): Promise<string> {
  return requestText(`/billing/invoices/${invoiceId}/html_preview/`);
}

export function exportBillingInvoiceTallyXml(invoiceId: number): Promise<string> {
  return requestText(`/billing/invoices/${invoiceId}/tally_xml/`);
}
