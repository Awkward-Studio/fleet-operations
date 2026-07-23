"use client";

import React, { useState, useEffect } from "react";
import {
  FileText,
  Building2,
  CheckCircle2,
  AlertTriangle,
  Search,
  Plus,
  Pencil,
  Trash2,
  Copy,
  ShieldCheck,
  Percent,
  Clock,
  Car,
  MapPin,
  HelpCircle,
  FileCheck,
  Eye,
  X,
} from "lucide-react";
import {
  CorporateContract,
  ContractRate,
  ContractAllowance,
  CorporateCustomer,
  getContracts,
  getCustomers,
  createContract,
  updateContract,
  activateContract,
  validateContract,
  copyContract,
  deleteContract,
} from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";

export default function ContractManager() {
  const { user } = useAuth();
  const isCommercialAdmin =
    user?.role === "admin" ||
    user?.role === "commercial" ||
    user?.role === "accountant" ||
    user?.permissions?.includes("write_contracts");

  const [contracts, setContracts] = useState<CorporateContract[]>([]);
  const [customers, setCustomers] = useState<CorporateCustomer[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState<string>("");
  const [selectedCustomerFilter, setSelectedCustomerFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // Selection & Detail Drawer
  const [selectedContract, setSelectedContract] = useState<CorporateContract | null>(null);
  const [showDetailDrawer, setShowDetailDrawer] = useState<boolean>(false);
  const [validationResult, setValidationResult] = useState<{
    is_valid: boolean;
    errors: string[];
    warnings: string[];
    rates_count: number;
  } | null>(null);

  // Modals
  const [showContractModal, setShowContractModal] = useState<boolean>(false);
  const [editingContract, setEditingContract] = useState<Partial<CorporateContract> | null>(null);

  // Rate Matrix Draft State
  const [ratesDraft, setRatesDraft] = useState<ContractRate[]>([]);
  const [allowancesDraft, setAllowancesDraft] = useState<ContractAllowance[]>([]);

  useEffect(() => {
    fetchInitialData();
  }, [search, selectedCustomerFilter, statusFilter]);

  const fetchInitialData = async () => {
    try {
      setLoading(true);
      setError(null);
      const params: any = {};
      if (search.trim()) params.search = search.trim();
      if (selectedCustomerFilter !== "ALL") params.customer = parseInt(selectedCustomerFilter);
      if (statusFilter !== "ALL") params.status = statusFilter;

      const [contractList, customerList] = await Promise.all([
        getContracts(params),
        getCustomers(),
      ]);
      setContracts(contractList);
      setCustomers(customerList);
    } catch (err: any) {
      setError(err.message || "Failed to load contracts.");
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async (contractId: number) => {
    try {
      setError(null);
      const res = await validateContract(contractId);
      setValidationResult(res);
    } catch (err: any) {
      setError(err.message || "Contract validation failed.");
    }
  };

  const handleActivate = async (contractId: number) => {
    try {
      setError(null);
      const res = await activateContract(contractId);
      setSuccess(`Contract version ${res.version_name} activated successfully.`);
      fetchInitialData();
      if (selectedContract?.id === contractId) {
        setSelectedContract(res);
      }
    } catch (err: any) {
      setError(err.message || "Activation failed.");
    }
  };

  const handleDuplicate = async (contractId: number) => {
    try {
      setError(null);
      const created = await copyContract(contractId);
      setSuccess(`Created draft version '${created.version_name}' from contract ID #${contractId}.`);
      fetchInitialData();
      setSelectedContract(created);
      setShowDetailDrawer(true);
    } catch (err: any) {
      setError(err.message || "Failed to duplicate contract.");
    }
  };

  const handleDelete = async (contract: CorporateContract) => {
    if (!confirm(`Are you sure you want to delete contract '${contract.title}'?`)) return;
    try {
      setError(null);
      await deleteContract(contract.id);
      setSuccess(`Contract '${contract.title}' deleted.`);
      if (selectedContract?.id === contract.id) {
        setSelectedContract(null);
        setShowDetailDrawer(false);
      }
      fetchInitialData();
    } catch (err: any) {
      setError(err.message || "Failed to delete contract.");
    }
  };

  const openNewContractModal = () => {
    setEditingContract({
      contract_code: `CNT-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`,
      title: "Master Transportation Services Agreement",
      status: "DRAFT",
      version_name: "v1.0-draft",
      start_date: new Date().toISOString().split("T")[0],
      metering_policy: "GARAGE_TO_GARAGE",
      grace_period_minutes: 15,
      night_shift_start: "22:00:00",
      night_shift_end: "06:00:00",
      is_active: true,
      rates: [
        {
          vehicle_category: "Sedan",
          duty_type: "LOCAL_8HR_80KM",
          base_hours: 8,
          base_km: 80,
          base_rate: "2500.00",
          extra_km_rate: "18.00",
          extra_hour_rate: "200.00",
          night_allowance_rate: "300.00",
          outstation_driver_allowance_per_day: "500.00",
        },
      ],
      allowances: [
        {
          allowance_type: "NIGHT_ALLOWANCE",
          name: "Night Duty Allowance (10 PM - 6 AM)",
          amount: "300.00",
          charging_unit: "PER_NIGHT",
          is_mandatory: false,
        },
      ],
    });
    setRatesDraft([
      {
        vehicle_category: "Sedan",
        duty_type: "LOCAL_8HR_80KM",
        base_hours: 8,
        base_km: 80,
        base_rate: "2500.00",
        extra_km_rate: "18.00",
        extra_hour_rate: "200.00",
        night_allowance_rate: "300.00",
        outstation_driver_allowance_per_day: "500.00",
      },
    ]);
    setAllowancesDraft([
      {
        allowance_type: "NIGHT_ALLOWANCE",
        name: "Night Duty Allowance (10 PM - 6 AM)",
        amount: "300.00",
        charging_unit: "PER_NIGHT",
        is_mandatory: false,
      },
    ]);
    setShowContractModal(true);
  };

  const openEditContractModal = (contract: CorporateContract) => {
    setEditingContract(contract);
    setRatesDraft(contract.rates || []);
    setAllowancesDraft(contract.allowances || []);
    setShowContractModal(true);
  };

  const handleSaveContract = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingContract || !editingContract.customer) {
      setError("Please select a valid corporate customer.");
      return;
    }
    try {
      setError(null);
      const payload = {
        ...editingContract,
        rates: ratesDraft,
        allowances: allowancesDraft,
      };

      if (editingContract.id) {
        const updated = await updateContract(editingContract.id, payload);
        setSuccess(`Contract '${updated.title}' updated.`);
        if (selectedContract?.id === updated.id) {
          setSelectedContract(updated);
        }
      } else {
        const created = await createContract(payload);
        setSuccess(`Contract '${created.title}' created as DRAFT.`);
        setSelectedContract(created);
        setShowDetailDrawer(true);
      }
      setShowContractModal(false);
      setEditingContract(null);
      fetchInitialData();
    } catch (err: any) {
      setError(err.message || "Failed to save contract.");
    }
  };

  // Metrics
  const totalContracts = contracts.length;
  const activeContracts = contracts.filter((c) => c.status === "ACTIVE").length;
  const draftContracts = contracts.filter((c) => c.status === "DRAFT").length;

  return (
    <div className="stack" style={{ gap: 24 }}>
      {/* Top Metrics Cards */}
      <section className="metrics">
        <div className="metric-card">
          <div className="metric-header">
            <div className="metric-icon" style={{ background: "rgba(59, 73, 223, 0.15)", color: "var(--accent)" }}>
              <FileText size={20} />
            </div>
            TOTAL CONTRACTS
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{totalContracts}</strong>
              <span>Corporate Agreements</span>
            </div>
            <div className="metric-trend live">Commercial Rate Sheets</div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <div className="metric-icon" style={{ background: "rgba(34, 197, 94, 0.15)", color: "var(--ok)" }}>
              <CheckCircle2 size={20} />
            </div>
            ACTIVE AGREEMENTS
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{activeContracts}</strong>
              <span>Live Pricing Enforced</span>
            </div>
            <div className="metric-trend ok">Billing Enabled</div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <div className="metric-icon" style={{ background: "rgba(234, 179, 8, 0.15)", color: "var(--warn)" }}>
              <AlertTriangle size={20} />
            </div>
            DRAFT / PENDING
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{draftContracts}</strong>
              <span>Pending Activation</span>
            </div>
            <div className="metric-trend live">Validation Needed</div>
          </div>
        </div>
      </section>

      {/* Notifications */}
      {error && (
        <div style={{ padding: "12px 16px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.25)", borderRadius: 8, color: "var(--danger)", fontSize: 13, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{error}</span>
          <button onClick={() => setError(null)} style={{ background: "none", border: 0, color: "inherit", cursor: "pointer" }}>✕</button>
        </div>
      )}
      {success && (
        <div style={{ padding: "12px 16px", background: "rgba(34, 197, 94, 0.1)", border: "1px solid rgba(34, 197, 94, 0.25)", borderRadius: 8, color: "var(--ok)", fontSize: 13, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{success}</span>
          <button onClick={() => setSuccess(null)} style={{ background: "none", border: 0, color: "inherit", cursor: "pointer" }}>✕</button>
        </div>
      )}

      {/* Search & Filter Bar */}
      <div className="search-filter-bar">
        <div className="search-input-wrapper">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search by contract code, title, version..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="filter-select-wrapper">
          <select value={selectedCustomerFilter} onChange={(e) => setSelectedCustomerFilter(e.target.value)}>
            <option value="ALL">All Customers</option>
            {customers.map((cust) => (
              <option key={cust.id} value={cust.id}>
                {cust.display_name} ({cust.code})
              </option>
            ))}
          </select>
        </div>
        <div className="filter-select-wrapper">
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="ALL">All Statuses</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="DRAFT">DRAFT</option>
            <option value="EXPIRED">EXPIRED</option>
            <option value="TERMINATED">TERMINATED</option>
          </select>
        </div>
        {isCommercialAdmin && (
          <button className="button" style={{ whiteSpace: "nowrap" }} onClick={openNewContractModal}>
            <Plus size={16} /> Create Contract
          </button>
        )}
      </div>

      {/* Shadcn UI Table for Corporate Contracts */}
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Contract Code</TableHead>
              <TableHead>Agreement Title</TableHead>
              <TableHead>Corporate Customer</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Validity Period</TableHead>
              <TableHead>Rate Packages</TableHead>
              <TableHead>Metering Policy</TableHead>
              <TableHead style={{ textAlign: "right" }}>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={9} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                  Loading commercial contracts...
                </TableCell>
              </TableRow>
            ) : contracts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                  No corporate contracts match your filter criteria.
                </TableCell>
              </TableRow>
            ) : (
              contracts.map((c) => (
                <TableRow
                  key={c.id}
                  onClick={() => {
                    setSelectedContract(c);
                    setShowDetailDrawer(true);
                  }}
                  style={{
                    background: selectedContract?.id === c.id ? "rgba(59, 73, 223, 0.08)" : "transparent",
                  }}
                >
                  <TableCell>
                    <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--accent)", padding: "4px 8px", background: "rgba(59, 73, 223, 0.12)", borderRadius: 6 }}>
                      {c.contract_code}
                    </span>
                  </TableCell>

                  <TableCell>
                    <div>
                      <strong style={{ color: "#fff", display: "block", fontSize: 14 }}>{c.title}</strong>
                    </div>
                  </TableCell>

                  <TableCell>
                    <div>
                      <strong style={{ color: "#e2e8f0", fontSize: 13 }}>{c.customer_name}</strong>
                      <span style={{ fontSize: 11, color: "var(--muted)", display: "block" }}>{c.customer_code}</span>
                    </div>
                  </TableCell>

                  <TableCell>
                    <span style={{ fontSize: 12, padding: "2px 6px", background: "rgba(255,255,255,0.08)", borderRadius: 4, color: "#cbd5e1", fontFamily: "monospace" }}>
                      {c.version_name}
                    </span>
                  </TableCell>

                  <TableCell>
                    <span className={`status ${c.status === "ACTIVE" ? "ok" : c.status === "DRAFT" ? "warn" : "danger"}`}>
                      {c.status}
                    </span>
                  </TableCell>

                  <TableCell>
                    <span style={{ fontSize: 12, color: "#cbd5e1" }}>
                      {c.start_date} → {c.end_date || "Ongoing"}
                    </span>
                  </TableCell>

                  <TableCell>
                    <span style={{ fontWeight: 600, color: "var(--accent)" }}>
                      {c.rates_count} Tariff Rates
                    </span>
                  </TableCell>

                  <TableCell>
                    <span style={{ fontSize: 11, padding: "3px 8px", background: "rgba(255,255,255,0.05)", borderRadius: 4, color: "var(--muted)" }}>
                      {c.metering_policy}
                    </span>
                  </TableCell>

                  <TableCell style={{ textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
                      <button
                        className="button secondary"
                        style={{ padding: "6px 12px", fontSize: 12 }}
                        onClick={() => {
                          setSelectedContract(c);
                          setShowDetailDrawer(true);
                        }}
                      >
                        <Eye size={14} /> Details
                      </button>

                      {isCommercialAdmin && (
                        <>
                          {c.status === "DRAFT" && (
                            <button
                              className="button"
                              style={{ padding: "6px 10px", fontSize: 12, background: "var(--ok)", color: "#000" }}
                              onClick={() => handleActivate(c.id)}
                            >
                              Activate
                            </button>
                          )}
                          <button
                            className="button secondary"
                            style={{ padding: "6px 10px", fontSize: 12 }}
                            title="Duplicate as new draft version"
                            onClick={() => handleDuplicate(c.id)}
                          >
                            <Copy size={13} />
                          </button>
                          <button
                            className="button secondary"
                            style={{ padding: "6px 10px", fontSize: 12 }}
                            onClick={() => openEditContractModal(c)}
                          >
                            <Pencil size={13} />
                          </button>
                          <button
                            className="button secondary"
                            style={{ padding: "6px 10px", fontSize: 12, color: "var(--danger)" }}
                            onClick={() => handleDelete(c)}
                          >
                            <Trash2 size={13} />
                          </button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Contract Detail Drawer */}
      {showDetailDrawer && selectedContract && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0, 0, 0, 0.75)", backdropFilter: "blur(8px)", display: "flex", justifyContent: "flex-end", zIndex: 1000 }}>
          <div style={{ width: 720, maxWidth: "100%", background: "var(--panel-strong)", height: "100%", display: "flex", flexDirection: "column", borderLeft: "1px solid var(--line)", boxShadow: "-10px 0 30px rgba(0,0,0,0.5)" }}>
            {/* Header */}
            <div style={{ padding: 24, borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "flex-start", background: "rgba(15, 23, 42, 0.8)" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#fff" }}>{selectedContract.title}</h2>
                  <span className={`status ${selectedContract.status === "ACTIVE" ? "ok" : "warn"}`}>
                    {selectedContract.status}
                  </span>
                </div>
                <span style={{ fontSize: 13, color: "var(--muted)", display: "block", marginTop: 4 }}>
                  Code: <strong style={{ color: "var(--accent)", fontFamily: "monospace" }}>{selectedContract.contract_code}</strong> • Customer: <strong style={{ color: "#fff" }}>{selectedContract.customer_name}</strong>
                </span>
              </div>
              <button
                onClick={() => setShowDetailDrawer(false)}
                style={{ background: "none", border: 0, color: "var(--muted)", cursor: "pointer", padding: 6 }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Content Body */}
            <div style={{ flex: 1, overflowY: "auto", padding: 24 }} className="stack">
              {/* Actions Bar */}
              <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                <button className="button secondary" onClick={() => handleValidate(selectedContract.id)}>
                  <ShieldCheck size={14} /> Validate Contract
                </button>
                {selectedContract.status === "DRAFT" && isCommercialAdmin && (
                  <button className="button" style={{ background: "var(--ok)", color: "#000" }} onClick={() => handleActivate(selectedContract.id)}>
                    <CheckCircle2 size={14} /> Activate Contract
                  </button>
                )}
                {isCommercialAdmin && (
                  <button className="button secondary" onClick={() => handleDuplicate(selectedContract.id)}>
                    <Copy size={14} /> Duplicate Version
                  </button>
                )}
              </div>

              {/* Validation Result Box */}
              {validationResult && (
                <div className="panel" style={{ padding: 16, borderColor: validationResult.is_valid ? "var(--ok)" : "var(--warn)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, color: validationResult.is_valid ? "var(--ok)" : "var(--warn)", fontWeight: 600 }}>
                    {validationResult.is_valid ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
                    <span>{validationResult.is_valid ? "Contract is valid & ready for execution!" : "Validation Warnings Found"}</span>
                  </div>
                  {validationResult.errors.length > 0 && (
                    <ul style={{ margin: "8px 0 0", paddingLeft: 20, color: "var(--danger)", fontSize: 13 }}>
                      {validationResult.errors.map((err, i) => <li key={i}>{err}</li>)}
                    </ul>
                  )}
                  {validationResult.warnings.length > 0 && (
                    <ul style={{ margin: "8px 0 0", paddingLeft: 20, color: "var(--warn)", fontSize: 13 }}>
                      {validationResult.warnings.map((warn, i) => <li key={i}>{warn}</li>)}
                    </ul>
                  )}
                </div>
              )}

              {/* General Metadata */}
              <div className="panel" style={{ padding: 18 }}>
                <h4 style={{ margin: "0 0 14px", fontSize: 14, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                  Contract Terms & Policy Parameters
                </h4>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, fontSize: 13 }}>
                  <div>
                    <span style={{ color: "var(--muted)", display: "block" }}>Metering Policy</span>
                    <strong style={{ color: "#fff" }}>{selectedContract.metering_policy}</strong>
                  </div>
                  <div>
                    <span style={{ color: "var(--muted)", display: "block" }}>Grace Period</span>
                    <strong style={{ color: "#fff" }}>{selectedContract.grace_period_minutes} Minutes</strong>
                  </div>
                  <div>
                    <span style={{ color: "var(--muted)", display: "block" }}>Night Shift Window</span>
                    <strong style={{ color: "#fff" }}>{selectedContract.night_shift_start} - {selectedContract.night_shift_end}</strong>
                  </div>
                  <div>
                    <span style={{ color: "var(--muted)", display: "block" }}>Validity Window</span>
                    <strong style={{ color: "#fff" }}>{selectedContract.start_date} to {selectedContract.end_date || "Ongoing"}</strong>
                  </div>
                </div>
              </div>

              {/* Rate Matrix Table */}
              <div className="panel" style={{ padding: 18 }}>
                <h4 style={{ margin: "0 0 14px", fontSize: 14, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                  Vehicle Package Rates Matrix ({selectedContract.rates?.length || 0})
                </h4>
                <div className="table-wrap">
                  <table style={{ minWidth: 600 }}>
                    <thead>
                      <tr>
                        <th>Category</th>
                        <th>Duty Package</th>
                        <th>Base Package</th>
                        <th>Extra KM</th>
                        <th>Extra Hour</th>
                        <th>Night Allowance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedContract.rates && selectedContract.rates.length > 0 ? (
                        selectedContract.rates.map((rate, i) => (
                          <tr key={i}>
                            <td style={{ fontWeight: 600, color: "#fff" }}>{rate.vehicle_category}</td>
                            <td><span className="status info">{rate.duty_type}</span></td>
                            <td>₹{rate.base_rate} ({rate.base_hours}h / {rate.base_km}km)</td>
                            <td>₹{rate.extra_km_rate}/km</td>
                            <td>₹{rate.extra_hour_rate}/hr</td>
                            <td>₹{rate.night_allowance_rate}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} style={{ textAlign: "center", color: "var(--muted)", padding: 16 }}>
                            No rate packages defined for this contract.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Allowances Table */}
              <div className="panel" style={{ padding: 18 }}>
                <h4 style={{ margin: "0 0 14px", fontSize: 14, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                  Commercial Driver & Outstation Allowances
                </h4>
                <div className="table-wrap">
                  <table style={{ minWidth: 500 }}>
                    <thead>
                      <tr>
                        <th>Allowance Type</th>
                        <th>Description</th>
                        <th>Amount</th>
                        <th>Unit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedContract.allowances && selectedContract.allowances.length > 0 ? (
                        selectedContract.allowances.map((al, i) => (
                          <tr key={i}>
                            <td style={{ fontWeight: 600, color: "#fff" }}>{al.allowance_type}</td>
                            <td>{al.name}</td>
                            <td style={{ color: "var(--ok)", fontWeight: 700 }}>₹{al.amount}</td>
                            <td>{al.charging_unit}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={4} style={{ textAlign: "center", color: "var(--muted)", padding: 16 }}>
                            No special allowances defined.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Contract Create/Edit Modal */}
      {showContractModal && editingContract && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1100 }}>
          <div className="panel" style={{ width: 640, maxWidth: "95vw", maxHeight: "90vh", overflowY: "auto", padding: 24 }}>
            <h3 style={{ margin: "0 0 20px", color: "#fff" }}>
              {editingContract.id ? "Edit Contract Agreement" : "New Contract Agreement"}
            </h3>
            <form onSubmit={handleSaveContract} className="stack" style={{ gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Corporate Customer *</label>
                  <select
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContract.customer || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, customer: parseInt(e.target.value) })}
                  >
                    <option value="">Select Customer...</option>
                    {customers.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.display_name} ({c.code})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Contract Code *</label>
                  <input
                    type="text"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContract.contract_code || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, contract_code: e.target.value })}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Agreement Title *</label>
                <input
                  type="text"
                  required
                  style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                  value={editingContract.title || ""}
                  onChange={(e) => setEditingContract({ ...editingContract, title: e.target.value })}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Version Name</label>
                  <input
                    type="text"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContract.version_name || "v1.0-draft"}
                    onChange={(e) => setEditingContract({ ...editingContract, version_name: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Start Date *</label>
                  <input
                    type="date"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContract.start_date || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, start_date: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>End Date</label>
                  <input
                    type="date"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContract.end_date || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, end_date: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Metering Policy</label>
                  <select
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContract.metering_policy || "GARAGE_TO_GARAGE"}
                    onChange={(e) => setEditingContract({ ...editingContract, metering_policy: e.target.value as any })}
                  >
                    <option value="GARAGE_TO_GARAGE">Garage to Garage</option>
                    <option value="PICKUP_TO_DROP">Pickup to Drop</option>
                    <option value="FIXED_PACKAGE">Fixed Package</option>
                    <option value="OUTSTATION_DAILY_MINIMUM">Outstation Daily Minimum</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Grace Period (Mins)</label>
                  <input
                    type="number"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContract.grace_period_minutes || 15}
                    onChange={(e) => setEditingContract({ ...editingContract, grace_period_minutes: parseInt(e.target.value) })}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 12 }}>
                <button type="button" className="button secondary" onClick={() => setShowContractModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="button">
                  Save Contract
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
