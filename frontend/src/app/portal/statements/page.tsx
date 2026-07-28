"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/AuthContext";
import { getPortalStatement, PortalStatement } from "@/lib/rentalsApi";

export default function PortalStatementsPage() {
  const { user } = useAuth();
  const [statement, setStatement] = useState<PortalStatement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const companyId = user?.active_memberships?.[0]?.company_id;
  useEffect(() => {
    if (companyId) void getPortalStatement(companyId).then(setStatement).catch((e) => setError(e.message));
  }, [companyId]);
  return <div className="stack" style={{ gap: 20 }}>
    <div><h2>Account statement</h2><p style={{ color: "var(--muted)" }}>Invoices, receipts and the accounting balance for your company.</p></div>
    {error && <div className="error">{error}</div>}
    {statement && <>
      <div className="metrics">
        <div className="metric-card"><span>OPENING BALANCE</span><strong>₹{statement.opening_balance.toLocaleString("en-IN")}</strong></div>
        <div className="metric-card"><span>CLOSING BALANCE</span><strong>₹{statement.closing_balance.toLocaleString("en-IN")}</strong></div>
      </div>
      <div className="panel invoice-trip-table">
        <div className="invoice-trip-row header"><span /><span>Date / reference</span><span>Description</span><span>Debit</span><span>Credit</span><span>Balance</span></div>
        {statement.entries.map((entry, index) => <div className="invoice-trip-row" key={`${entry.reference}-${index}`}>
          <span />
          <span><strong>{entry.reference}</strong><small>{entry.date}</small></span>
          <span>{entry.description}</span>
          <span>₹{entry.debit.toLocaleString("en-IN")}</span>
          <span>₹{entry.credit.toLocaleString("en-IN")}</span>
          <span><strong>₹{entry.balance.toLocaleString("en-IN")}</strong></span>
        </div>)}
      </div>
    </>}
  </div>;
}
