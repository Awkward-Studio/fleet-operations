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
  status: "DRAFT" | "SUBMITTED" | "APPROVED" | "REJECTED";
  billing_ready: boolean;
  actual_km: string;
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

export async function listBillingCloseouts(): Promise<BillingCloseout[]> {
  return unwrapList(await request<ApiList<BillingCloseout>>("/billing/closeouts/"));
}

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
