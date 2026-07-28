"use client";

import { useEffect, useState } from "react";
import { Download, Receipt } from "lucide-react";
import { getPortalInvoices, PortalInvoice } from "@/lib/rentalsApi";
import { requestBlob } from "@/lib/api";

export default function PortalInvoicesPage() {
  const [invoices, setInvoices] = useState<PortalInvoice[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    void getPortalInvoices().then(setInvoices).catch((e) => setError(e.message));
  }, []);

  async function download(invoice: PortalInvoice) {
    const blob = await requestBlob(`/rentals/portal/invoices/${invoice.id}/download/?type=${invoice.type}`);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${invoice.invoice_number}.pdf`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return <div className="stack" style={{ gap: 20 }}>
    <div><h2>Invoices</h2><p style={{ color: "var(--muted)" }}>Issued fleet and chauffeur documents for your company.</p></div>
    {error && <div className="error">{error}</div>}
    <div className="panel invoice-trip-table">
      <div className="invoice-trip-row header"><span /><span>Invoice</span><span>Source</span><span>Issue / due</span><span>Status</span><span>Balance</span></div>
      {invoices.map((invoice) => <div className="invoice-trip-row" key={`${invoice.type}-${invoice.id}`}>
        <Receipt size={16} />
        <span><strong>{invoice.invoice_number}</strong><small>PO {invoice.po_number || "—"}</small></span>
        <span><strong>{invoice.type_display}</strong></span>
        <span><strong>{invoice.issue_date}</strong><small>Due {invoice.due_date}</small></span>
        <span className="status info">{invoice.status}</span>
        <span><strong>₹{invoice.balance_amount.toLocaleString("en-IN")}</strong><button className="button secondary" onClick={() => download(invoice)}><Download size={13} /> PDF</button></span>
      </div>)}
    </div>
  </div>;
}
