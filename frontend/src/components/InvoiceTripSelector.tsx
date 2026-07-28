"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, ChevronLeft, ChevronRight, RefreshCw, Search } from "lucide-react";
import {
  BillableTrip,
  BillingInvoice,
  BillingLegalEntity,
  generateInvoiceDraft,
  listBillableTrips,
  previewInvoiceGrouping,
} from "@/lib/billingApi";

function money(value?: string | null) {
  return `₹${Number(value || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
}

function keyOf(trip: BillableTrip) {
  return JSON.stringify(trip.grouping_key);
}

export default function InvoiceTripSelector({
  entities,
  entitiesLoading,
  onCreated,
}: {
  entities: BillingLegalEntity[];
  entitiesLoading: boolean;
  onCreated: (invoice: BillingInvoice) => Promise<void> | void;
}) {
  const [trips, setTrips] = useState<BillableTrip[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [entityId, setEntityId] = useState("");
  const [search, setSearch] = useState("");
  const [channel, setChannel] = useState("");
  const [page, setPage] = useState(1);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [previousPage, setPreviousPage] = useState<number | null>(null);
  const [count, setCount] = useState(0);
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof previewInvoiceGrouping>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(targetPage = page) {
    setLoading(true);
    setError(null);
    try {
      const data = await listBillableTrips({
        search,
        booking_type: channel,
        page: targetPage,
        page_size: 20,
      });
      setTrips(data.results);
      setCount(data.count);
      setPage(data.page);
      setNextPage(data.next_page);
      setPreviousPage(data.previous_page);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load billing-ready trips.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void load(1), 250);
    return () => window.clearTimeout(timer);
  }, [search, channel]);

  useEffect(() => {
    if (!selected.length) {
      setPreview(null);
      return;
    }
    void previewInvoiceGrouping(selected)
      .then(setPreview)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to preview grouping."));
  }, [selected]);

  const selectedTrips = useMemo(
    () => selected.map((id) => trips.find((trip) => trip.id === id)).filter(Boolean) as BillableTrip[],
    [selected, trips],
  );
  const selectedKey = selectedTrips[0] ? keyOf(selectedTrips[0]) : null;

  function toggle(trip: BillableTrip) {
    if (selected.includes(trip.id)) {
      setSelected(selected.filter((id) => id !== trip.id));
      return;
    }
    if (selectedKey && keyOf(trip) !== selectedKey) return;
    setSelected([...selected, trip.id]);
  }

  async function createDraft() {
    if (!entityId || !selected.length || preview?.groups.length !== 1 || !preview.groups[0].eligible) return;
    setBusy(true);
    setError(null);
    try {
      const invoice = await generateInvoiceDraft({
        legal_entity_id: Number(entityId),
        trip_ids: selected,
      });
      setSelected([]);
      setPreview(null);
      await onCreated(invoice);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create invoice draft.");
    } finally {
      setBusy(false);
    }
  }

  const group = preview?.groups.length === 1 ? preview.groups[0] : null;

  return (
    <div className="invoice-selector">
      {error && <div className="closeout-alert danger">{error}</div>}
      <div className="panel invoice-selector-toolbar">
        <div className="search-input-wrapper">
          <Search size={15} className="search-icon" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Customer, route, PO or bill-to" />
        </div>
        <select value={channel} onChange={(e) => setChannel(e.target.value)}>
          <option value="">All booking channels</option>
          <option value="CORPORATE">Corporate</option>
          <option value="ADHOC">Ad-hoc</option>
          <option value="OTA">OTA</option>
        </select>
        <button className="button secondary" onClick={() => load()}><RefreshCw size={14} /> Refresh</button>
        <span>{count} billing-ready trips</span>
      </div>

      <div className="panel invoice-trip-table">
        <div className="invoice-trip-row header">
          <span />
          <span>Trip / customer</span>
          <span>Package & actuals</span>
          <span>PO / grouping</span>
          <span>Quote → final</span>
          <span>Total</span>
        </div>
        {loading ? <p>Loading billing-ready trips…</p> : trips.map((trip) => {
          const compatible = !selectedKey || keyOf(trip) === selectedKey || selected.includes(trip.id);
          return (
            <button
              type="button"
              className={`invoice-trip-row ${selected.includes(trip.id) ? "selected" : ""} ${!compatible ? "incompatible" : ""}`}
              key={trip.id}
              disabled={!compatible}
              onClick={() => toggle(trip)}
              title={!compatible ? "Bill-to, channel, currency, PO, and billing cycle must match" : undefined}
            >
              <span className="invoice-check">{selected.includes(trip.id) && <Check size={14} />}</span>
              <span><strong>Trip #{trip.id} · {trip.customer_name}</strong><small>{trip.pickup_city} → {trip.drop_city}</small></span>
              <span><strong>{trip.pricing_snapshot?.package?.name || trip.duty_type || "Package"}</strong><small>{trip.closeout_summary?.actual_km || "0"} km · {trip.closeout_summary?.actual_hours || "0"} hr · {trip.closeout_summary?.approved_extra_count || 0} extras</small></span>
              <span><strong>{trip.po_number || "No PO"}</strong><small>{trip.grouping_key.booking_channel} · {trip.grouping_key.billing_cycle}</small></span>
              <span><strong>{money(trip.quoted_total_amount)} → {money(trip.amount_summary.total_amount)}</strong><small>{trip.closeout_summary?.variance_percent || "0"}% variance</small></span>
              <span><strong>{money(trip.amount_summary.total_amount)}</strong><small>Tax {money(trip.amount_summary.tax_amount)}</small></span>
            </button>
          );
        })}
        {!loading && !trips.length && <p>No billing-ready trips match these filters.</p>}
        <div className="invoice-pagination">
          <button className="button secondary" disabled={!previousPage} onClick={() => previousPage && load(previousPage)}><ChevronLeft size={14} /> Previous</button>
          <span>Page {page}</span>
          <button className="button secondary" disabled={!nextPage} onClick={() => nextPage && load(nextPage)}>Next <ChevronRight size={14} /></button>
        </div>
      </div>

      <section className="panel invoice-preview-card">
        <div>
          <h3>Server invoice preview</h3>
          <p>{selected.length ? `${selected.length} compatible trip(s) selected` : "Select one trip to establish the compatible billing group."}</p>
        </div>
        {preview && preview.groups.length > 1 && (
          <div className="closeout-alert danger"><AlertTriangle size={14} /> Selection contains incompatible billing groups.</div>
        )}
        {group && <>
          <div className="invoice-preview-grid">
            <div><span>Bill to</span><strong>{group.bill_to_name}</strong><small>{group.bill_to_snapshot.gstin || "No GSTIN"}</small></div>
            <div><span>Taxable</span><strong>{money(group.estimated_taxable_amount)}</strong></div>
            <div><span>Tax</span><strong>{money(group.estimated_tax_amount)}</strong></div>
            <div><span>Invoice total</span><strong>{money(group.estimated_total_amount)}</strong></div>
          </div>
          {group.blockers.map((item) => <p className="closeout-alert danger" key={`${item.trip_id}-${item.code}`}>Trip #{item.trip_id}: {item.message}</p>)}
        </>}
        <div className="invoice-preview-actions">
          <select value={entityId} onChange={(e) => setEntityId(e.target.value)} disabled={entitiesLoading}>
            <option value="">Select issuing legal entity</option>
            {entities.map((entity) => <option key={entity.id} value={entity.id}>{entity.legal_name} · {entity.gstin}</option>)}
          </select>
          <button className="button" disabled={busy || !entityId || !group?.eligible} onClick={createDraft}>
            {busy ? "Creating…" : "Create matching draft"}
          </button>
        </div>
      </section>
    </div>
  );
}
