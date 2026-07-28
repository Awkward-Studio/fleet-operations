"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  History,
  Plus,
  RefreshCw,
  RotateCcw,
} from "lucide-react";
import {
  BillingCloseout,
  CloseoutReconciliationReport,
  addBillingCloseoutCharge,
  approveBillingCloseout,
  approveBillingCloseoutCharge,
  getCloseoutReconciliationReport,
  listBillingCloseouts,
  markCloseoutBillingReady,
  reopenBillingCloseout,
  returnBillingCloseout,
  submitBillingCloseout,
} from "@/lib/billingApi";

const statuses = [
  "ALL",
  "INCOMPLETE",
  "EXCEPTION_REVIEW",
  "SUBMITTED",
  "REOPENED",
  "APPROVED",
  "BILLING_READY",
];

function money(value?: string | null) {
  return `₹${Number(value || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
}

function dateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString("en-IN") : "Not captured";
}

function blockerText(blocker: BillingCloseout["blockers"][number]) {
  return typeof blocker === "string"
    ? blocker
    : `${blocker.code ? `${blocker.code}: ` : ""}${blocker.message || "Unresolved blocker"}`;
}

export default function CloseoutReviewManager({ initialTripId }: { initialTripId?: number }) {
  const searchParams = useSearchParams();
  const linkedTripId = initialTripId ?? (Number(searchParams.get("trip") || 0) || undefined);
  const [closeouts, setCloseouts] = useState<BillingCloseout[]>([]);
  const [report, setReport] = useState<CloseoutReconciliationReport | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [search, setSearch] = useState(linkedTripId ? String(linkedTripId) : "");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [charge, setCharge] = useState({
    category: "TOLL",
    amount: "",
    description: "",
    receipt_attachment_url: "",
  });

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [rows, reconciliation] = await Promise.all([
        listBillingCloseouts(statusFilter),
        getCloseoutReconciliationReport(),
      ]);
      setCloseouts(rows);
      setReport(reconciliation);
      setSelectedId((current) => {
        if (current && rows.some((item) => item.id === current)) return current;
        return rows.find((item) => item.trip === linkedTripId)?.id ?? rows[0]?.id ?? null;
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load closeouts.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [statusFilter]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return closeouts;
    return closeouts.filter((item) => {
      const trip = item.trip_details;
      return [
        item.trip,
        trip?.customer_name,
        trip?.customer_display_name_snapshot,
        trip?.pickup_city,
        trip?.drop_city,
        trip?.booking_type,
      ].some((value) => String(value || "").toLowerCase().includes(needle));
    });
  }, [closeouts, search]);

  const selected = closeouts.find((item) => item.id === selectedId) || null;

  async function mutate(label: string, operation: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await operation();
      setMessage(label);
      setReason("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Closeout action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function addCharge(event: React.FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await mutate("Charge added for independent approval.", () =>
      addBillingCloseoutCharge(selected.id, charge),
    );
    setCharge({ category: "TOLL", amount: "", description: "", receipt_attachment_url: "" });
  }

  const components = selected?.final_charge_snapshot?.components || {};

  return (
    <div className="closeout-workspace">
      <div className="closeout-toolbar">
        <div>
          <h2>Trip closeout review</h2>
          <p>Reconcile operational evidence into the final, invoiceable trip charge.</p>
        </div>
        <button className="button secondary" onClick={load} disabled={loading}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {error && <div className="closeout-alert danger">{error}</div>}
      {message && <div className="closeout-alert success">{message}</div>}

      {report && (
        <section className="closeout-report-strip">
          <div><span>Completed trips</span><strong>{report.coverage.completed_trips}</strong></div>
          <div><span>Missing closeout</span><strong>{report.issue_counts.missing_closeout}</strong></div>
          <div><span>Stale review</span><strong>{report.issue_counts.stale_review}</strong></div>
          <div><span>Large variance</span><strong>{report.issue_counts.large_variance}</strong></div>
          <div><span>Zero fare</span><strong>{report.issue_counts.zero_fare}</strong></div>
          <div className={report.coverage.reconciles ? "reconciled" : "unreconciled"}>
            <span>Coverage control</span><strong>{report.coverage.reconciles ? "Reconciled" : "Mismatch"}</strong>
          </div>
        </section>
      )}

      <div className="closeout-layout">
        <aside className="closeout-queue panel">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Trip, customer, city or channel"
          />
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            {statuses.map((status) => <option key={status}>{status}</option>)}
          </select>
          <div className="closeout-queue-list">
            {loading ? <p>Loading closeouts…</p> : filtered.map((item) => (
              <button
                key={item.id}
                className={item.id === selectedId ? "selected" : ""}
                onClick={() => setSelectedId(item.id)}
              >
                <span><strong>Trip #{item.trip}</strong> · {item.trip_details?.customer_name}</span>
                <small>{item.trip_details?.pickup_city} → {item.trip_details?.drop_city}</small>
                <span className={`status ${item.blockers?.length ? "warn" : item.billing_ready ? "ok" : "info"}`}>
                  {item.status_display || item.status}
                </span>
              </button>
            ))}
            {!loading && filtered.length === 0 && <p>No closeouts match these filters.</p>}
          </div>
        </aside>

        <main className="closeout-detail">
          {!selected ? <div className="panel">Select a closeout to review.</div> : (
            <>
              <section className="panel closeout-hero">
                <div>
                  <span className="eyebrow">{selected.trip_details.booking_type || "TRIP"} · {selected.trip_details.duty_type || "PACKAGE"}</span>
                  <h3>Trip #{selected.trip}: {selected.trip_details.pickup_city} → {selected.trip_details.drop_city}</h3>
                  <p>{selected.trip_details.customer_name} · {selected.metering_policy || "Metering policy unavailable"}</p>
                </div>
                <div className="closeout-total">
                  <span>Final total</span>
                  <strong>{money(selected.final_total_amount)}</strong>
                  <small>{money(selected.quote_variance_amount)} ({selected.quote_variance_percent || "0"}%) vs quote</small>
                </div>
              </section>

              {selected.blockers?.length > 0 && (
                <section className="panel closeout-blockers">
                  <h4><AlertTriangle size={16} /> Blocking exceptions</h4>
                  {selected.blockers.map((item, index) => <p key={index}>{blockerText(item)}</p>)}
                </section>
              )}

              <section className="closeout-comparison">
                <div className="panel">
                  <h4>Quote</h4>
                  <dl>
                    <div><dt>Taxable</dt><dd>{money(selected.trip_details.quoted_taxable_amount)}</dd></div>
                    <div><dt>Tax</dt><dd>{money(selected.trip_details.quoted_tax_amount)}</dd></div>
                    <div><dt>Total</dt><dd>{money(selected.trip_details.quoted_total_amount)}</dd></div>
                  </dl>
                </div>
                <ArrowRight className="closeout-arrow" />
                <div className="panel">
                  <h4>Actual and final</h4>
                  <dl>
                    <div><dt>Usage</dt><dd>{selected.actual_km} km · {selected.actual_hours} hr</dd></div>
                    <div><dt>Taxable</dt><dd>{money(selected.final_taxable_amount)}</dd></div>
                    <div><dt>Tax</dt><dd>{money(selected.final_tax_amount)}</dd></div>
                    <div><dt>Total</dt><dd>{money(selected.final_total_amount)}</dd></div>
                  </dl>
                </div>
              </section>

              <section className="closeout-grid">
                <div className="panel">
                  <h4><ClipboardCheck size={16} /> Metering evidence</h4>
                  <dl>
                    <div><dt>Start odometer</dt><dd>{selected.start_odometer_km} km</dd></div>
                    <div><dt>End odometer</dt><dd>{selected.end_odometer_km} km</dd></div>
                    <div><dt>Actual pickup</dt><dd>{dateTime(selected.actual_pickup_at)}</dd></div>
                    <div><dt>Actual drop</dt><dd>{dateTime(selected.actual_drop_at)}</dd></div>
                    <div><dt>Waiting</dt><dd>{selected.waiting_minutes} min</dd></div>
                    <div><dt>Evidence files</dt><dd>{Object.keys(selected.evidence_snapshot || {}).length}</dd></div>
                  </dl>
                </div>
                <div className="panel">
                  <h4>Calculated components</h4>
                  <dl>
                    {Object.entries(components).map(([name, value]) => (
                      <div key={name}><dt>{name.replaceAll("_", " ")}</dt><dd>{money(value)}</dd></div>
                    ))}
                    {Object.keys(components).length === 0 && <p>Submit the closeout to calculate components.</p>}
                  </dl>
                </div>
              </section>

              <section className="panel">
                <h4>Supported manual charges</h4>
                <div className="closeout-charges">
                  {selected.extra_charges.map((item) => (
                    <div key={item.id}>
                      <span><strong>{item.category_display}</strong> · {item.description || "No description"}</span>
                      <span>{money(item.amount)} {item.receipt_attachment_url && <a href={item.receipt_attachment_url}>Evidence</a>}</span>
                      {item.is_approved ? <span className="status ok">Approved</span> : (
                        <button className="button secondary" disabled={busy} onClick={() => mutate(
                          "Charge approved and totals recalculated.",
                          () => approveBillingCloseoutCharge(selected.id, item.id),
                        )}>Approve charge</button>
                      )}
                    </div>
                  ))}
                </div>
                {["INCOMPLETE", "REOPENED", "EXCEPTION_REVIEW"].includes(selected.status) && (
                  <form className="closeout-charge-form" onSubmit={addCharge}>
                    <select value={charge.category} onChange={(e) => setCharge({ ...charge, category: e.target.value })}>
                      {["TOLL", "PARKING", "STATE_TAX", "PERMIT", "OTHER", "DISCOUNT"].map((value) => <option key={value}>{value}</option>)}
                    </select>
                    <input required type="number" min="0" step="0.01" placeholder="Amount" value={charge.amount} onChange={(e) => setCharge({ ...charge, amount: e.target.value })} />
                    <input required placeholder="Description" value={charge.description} onChange={(e) => setCharge({ ...charge, description: e.target.value })} />
                    <input placeholder="Receipt/evidence URL" value={charge.receipt_attachment_url} onChange={(e) => setCharge({ ...charge, receipt_attachment_url: e.target.value })} />
                    <button className="button" disabled={busy}><Plus size={14} /> Add</button>
                  </form>
                )}
              </section>

              <section className="panel">
                <h4><History size={16} /> Approval history</h4>
                <div className="closeout-history">
                  {selected.audit_events.map((event) => (
                    <div key={event.id}>
                      <CheckCircle2 size={14} />
                      <span><strong>{event.action}</strong> by {event.actor_name || "system"}<small>{event.from_status} → {event.to_status} · {dateTime(event.created_at)}{event.reason ? ` · ${event.reason}` : ""}</small></span>
                    </div>
                  ))}
                  {selected.audit_events.length === 0 && <p>No approval actions recorded yet.</p>}
                </div>
              </section>

              <section className="panel closeout-actions">
                <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Required reason for return or reopen" />
                {["INCOMPLETE", "REOPENED", "EXCEPTION_REVIEW"].includes(selected.status) && (
                  <button className="button" disabled={busy} onClick={() => mutate("Closeout submitted.", () => submitBillingCloseout(selected.id))}>Submit</button>
                )}
                {selected.status === "SUBMITTED" && <>
                  <button className="button secondary" disabled={busy || !reason.trim()} onClick={() => mutate("Closeout returned.", () => returnBillingCloseout(selected.id, reason))}>Return</button>
                  <button className="button" disabled={busy} onClick={() => mutate("Closeout approved.", () => approveBillingCloseout(selected.id))}>Approve</button>
                </>}
                {selected.status === "APPROVED" && (
                  <button className="button" disabled={busy} onClick={() => mutate("Trip is billing-ready.", () => markCloseoutBillingReady(selected.id))}>Mark billing-ready</button>
                )}
                {["APPROVED", "BILLING_READY"].includes(selected.status) && (
                  <button className="button secondary" disabled={busy || !reason.trim()} onClick={() => mutate("Closeout reopened.", () => reopenBillingCloseout(selected.id, reason))}><RotateCcw size={14} /> Reopen</button>
                )}
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
