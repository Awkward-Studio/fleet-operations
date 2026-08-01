"use client";

import { useEffect, useMemo, useState } from "react";
import type React from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleDollarSign,
  FileText,
  Link2,
  RefreshCw,
  Search,
  TrendingUp,
} from "lucide-react";
import {
  getOTAProfitabilityReport,
  OTAProfitabilityReport,
  OTAProfitabilityRow,
} from "@/lib/billingApi";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const statusOptions = ["", "PENDING", "SETTLED", "EXCEPTION", "CANCELLED"];

function money(value: string) {
  return `₹${value}`;
}

function label(value: string) {
  return value ? value.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()) : "";
}

function statusClass(value: string) {
  if (value === "EXACT" || value === "SETTLED") return "ok";
  if (value === "MISSING" || value === "DUPLICATE" || value === "CANCELLED" || value === "EXCEPTION") return "danger";
  if (value === "SHORT" || value === "EXCESS" || value === "PENDING") return "warn";
  return "info";
}

export default function OtaSettlementManager() {
  const [report, setReport] = useState<OTAProfitabilityReport | null>(null);
  const [selected, setSelected] = useState<OTAProfitabilityRow | null>(null);
  const [counterparty, setCounterparty] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await getOTAProfitabilityReport({ counterparty, status });
      setReport(data);
      setSelected((current) => {
        if (!current) return data.results[0] ?? null;
        return data.results.find((row) => row.trip.id === current.trip.id) ?? data.results[0] ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load OTA settlement report.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [counterparty, status]);

  const filteredRows = useMemo(() => {
    const rows = report?.results ?? [];
    const needle = search.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) =>
      [
        row.trip.route,
        row.trip.customer_name,
        row.external.provider_code,
        row.external.provider_booking_id,
        row.external.partner_reference_number,
        row.settlement.batch_reference,
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [report, search]);

  return (
    <section className="grid">
      <div className="panel">
        <div className="panel-header">
          <div>
            <h3>OTA settlement and margin</h3>
            <p>Provider statements, settlement exceptions, and trip contribution.</p>
          </div>
          <button className="button secondary" onClick={load} disabled={loading}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        {error ? <div className="notice danger">{error}</div> : null}

        <div className="metrics compact">
          <Metric label="OTA trips" value={String(report?.summary.trip_count ?? 0)} icon={<FileText size={18} />} />
          <Metric label="Expected net" value={money(report?.summary.net_expected ?? "0.00")} icon={<CircleDollarSign size={18} />} />
          <Metric label="Received" value={money(report?.summary.received_amount ?? "0.00")} icon={<CheckCircle2 size={18} />} />
          <Metric label="Margin" value={money(report?.summary.contribution_margin ?? "0.00")} icon={<TrendingUp size={18} />} />
          <Metric label="Exceptions" value={String(report?.summary.exception_count ?? 0)} icon={<AlertTriangle size={18} />} />
        </div>

        <div className="search-filter-bar" style={{ marginTop: 16 }}>
          <div className="search-input-wrapper">
            <Search className="search-icon" size={16} />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search booking, batch, route, provider..." />
          </div>
          <select value={counterparty} onChange={(event) => setCounterparty(event.target.value)} aria-label="Filter provider">
            <option value="">All providers</option>
            <option value="MMT">MMT</option>
          </select>
          <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter settlement status">
            {statusOptions.map((option) => (
              <option key={option || "ALL"} value={option}>{option ? label(option) : "All statuses"}</option>
            ))}
          </select>
        </div>

        <div className="table-wrap" style={{ marginTop: 16 }}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Trip</TableHead>
                <TableHead>Provider refs</TableHead>
                <TableHead>Gross to net</TableHead>
                <TableHead>Settlement</TableHead>
                <TableHead>Margin</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={5}>Loading OTA settlement report...</TableCell></TableRow>
              ) : filteredRows.length === 0 ? (
                <TableRow><TableCell colSpan={5}>No OTA settlement rows match the filters.</TableCell></TableRow>
              ) : filteredRows.map((row) => (
                <TableRow
                  key={`${row.external.provider_code}-${row.external.provider_booking_id}`}
                  onClick={() => setSelected(row)}
                  style={{ cursor: "pointer" }}
                >
                  <TableCell>
                    <strong>Trip #{row.trip.id}</strong>
                    <small>{row.trip.route}</small>
                  </TableCell>
                  <TableCell>
                    <strong>{row.external.provider_code} {row.external.provider_booking_id}</strong>
                    <small>{row.external.partner_reference_number || "No partner ref"}</small>
                  </TableCell>
                  <TableCell>
                    <strong>{money(row.waterfall.net_expected)}</strong>
                    <small>{money(row.waterfall.gross_fare)} gross</small>
                  </TableCell>
                  <TableCell>
                    <span className={`status ${statusClass(row.settlement.classification)}`}>{label(row.settlement.classification)}</span>
                    <small>{row.settlement.batch_reference || "Not settled"}</small>
                  </TableCell>
                  <TableCell>
                    <strong style={{ color: row.profitability.contribution_margin.startsWith("-") ? "var(--danger)" : "var(--ok)" }}>
                      {money(row.profitability.contribution_margin)}
                    </strong>
                    {row.profitability.margin_incomplete ? <small style={{ color: "var(--warn)" }}>Incomplete cost review</small> : <small>Approved costs only</small>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      <OtaTracePanel row={selected} />
    </section>
  );
}

function OtaTracePanel({ row }: { row: OTAProfitabilityRow | null }) {
  if (!row) {
    return (
      <div className="panel">
        <div className="panel-header"><h3>Trip trace</h3></div>
        <div className="notice">Select an OTA trip to view settlement and profitability trace.</div>
      </div>
    );
  }

  const waterfall = [
    ["Gross fare", row.waterfall.gross_fare],
    ["Commission", `-${row.waterfall.commission_amount}`],
    ["Commission GST", `-${row.waterfall.commission_tax}`],
    ["Withholding", `-${row.waterfall.withholding_amount}`],
    ["Cancellation", `-${row.waterfall.cancellation_amount}`],
    ["Expected net", row.waterfall.net_expected],
  ];

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <h3>Trip #{row.trip.id} trace</h3>
          <p>{row.external.provider_name} booking {row.external.provider_booking_id}</p>
        </div>
        <span className={`status ${statusClass(row.settlement.classification)}`}>{label(row.settlement.classification)}</span>
      </div>

      <div className="detail-grid">
        <TraceItem label="Route" value={row.trip.route} />
        <TraceItem label="Provider trip" value={row.external.provider_trip_id || "Not supplied"} />
        <TraceItem label="Partner ref" value={row.external.partner_reference_number || "Not supplied"} />
        <TraceItem label="Payout batch" value={row.settlement.batch_reference || "Not settled"} />
      </div>

      <div className="waterfall">
        {waterfall.map(([name, value], index) => (
          <div className="waterfall-row" key={name}>
            <span>{name}</span>
            <strong>{money(value)}</strong>
            {index < waterfall.length - 1 ? <ArrowRight size={14} /> : null}
          </div>
        ))}
      </div>

      <div className="detail-grid">
        <TraceItem label="Received" value={money(row.settlement.received_amount)} />
        <TraceItem label="Variance" value={money(row.settlement.variance_amount)} />
        <TraceItem label="Approved costs" value={money(row.profitability.approved_costs)} />
        <TraceItem label="Contribution" value={money(row.profitability.contribution_margin)} />
      </div>

      {row.profitability.margin_incomplete ? (
        <div className="notice warn">
          <AlertTriangle size={15} />
          Margin excludes unapproved costs: {row.profitability.incomplete_reasons.map(label).join(", ")}
        </div>
      ) : null}

      <div className="trace-links">
        <span><Link2 size={14} /> Booking journal: {row.journals.booking_journal || "Not posted"}</span>
        <span><Link2 size={14} /> Settlement journal: {row.journals.settlement_journal || "Not posted"}</span>
      </div>
    </div>
  );
}

function TraceItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="trace-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="metric">
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}
