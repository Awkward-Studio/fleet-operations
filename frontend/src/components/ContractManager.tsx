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
  FileCheck
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

  // Selection
  const [selectedContract, setSelectedContract] = useState<CorporateContract | null>(null);
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
      if (contractList.length > 0 && !selectedContract) {
        setSelectedContract(contractList[0]);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load contracts.");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreateModal = () => {
    setEditingContract({
      customer: customers[0]?.id || 0,
      title: "Master Corporate Rate Card 2026",
      version_name: "v1.0",
      effective_start: new Date().toISOString().split("T")[0],
      status: "DRAFT",
      currency: "INR",
      cgst_rate: "2.50",
      sgst_rate: "2.50",
      metering_policy: "GARAGE_TO_GARAGE",
      payment_terms_days: 30,
    });
    setRatesDraft([
      {
        city: "mumbai",
        vehicle_category: "sedan",
        duty_type: "LOCAL_8HR_80KM",
        included_hours: 8,
        included_km: 80,
        base_rate: "2400.00",
        extra_hour_rate: "200.00",
        extra_km_rate: "18.00",
      },
      {
        city: "mumbai",
        vehicle_category: "sedan",
        duty_type: "LOCAL_12HR_120KM",
        included_hours: 12,
        included_km: 120,
        base_rate: "3500.00",
        extra_hour_rate: "200.00",
        extra_km_rate: "18.00",
      },
    ]);
    setAllowancesDraft([
      {
        allowance_type: "OVERTIME_PER_HOUR",
        amount: "150.00",
        description: "Overtime charge per hour",
      },
      {
        allowance_type: "OVERNIGHT_DRIVER_ALLOWANCE",
        amount: "300.00",
        description: "Night halt allowance",
      },
    ]);
    setShowContractModal(true);
  };

  const handleOpenEditModal = (contract: CorporateContract) => {
    setEditingContract(contract);
    setRatesDraft(contract.rates || []);
    setAllowancesDraft(contract.allowances || []);
    setShowContractModal(true);
  };

  const handleAddRateRow = () => {
    setRatesDraft((prev) => [
      ...prev,
      {
        city: "mumbai",
        vehicle_category: "sedan",
        duty_type: "LOCAL_8HR_80KM",
        included_hours: 8,
        included_km: 80,
        base_rate: "2000.00",
        extra_hour_rate: "150.00",
        extra_km_rate: "15.00",
      },
    ]);
  };

  const handleRemoveRateRow = (index: number) => {
    setRatesDraft((prev) => prev.filter((_, i) => i !== index));
  };

  const handleAddAllowanceRow = () => {
    setAllowancesDraft((prev) => [
      ...prev,
      {
        allowance_type: "OUTSTATION_PER_DAY",
        amount: "400.00",
        description: "Daily outstation allowance",
      },
    ]);
  };

  const handleRemoveAllowanceRow = (index: number) => {
    setAllowancesDraft((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSaveContract = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingContract) return;

    try {
      setError(null);
      const payload: Partial<CorporateContract> = {
        ...editingContract,
        rates: ratesDraft,
        allowances: allowancesDraft,
      };

      if (editingContract.id) {
        const updated = await updateContract(editingContract.id, payload);
        setSuccess(`Contract '${updated.title}' updated successfully.`);
      } else {
        const created = await createContract(payload);
        setSuccess(`Contract '${created.title}' created successfully.`);
      }
      setShowContractModal(false);
      setEditingContract(null);
      fetchInitialData();
    } catch (err: any) {
      setError(err.message || "Failed to save contract.");
    }
  };

  const handleActivateContract = async (contract: CorporateContract) => {
    try {
      setError(null);
      const updated = await activateContract(contract.id);
      setSuccess(`Contract '${updated.title}' is now ACTIVE.`);
      fetchInitialData();
      if (selectedContract?.id === contract.id) setSelectedContract(updated);
    } catch (err: any) {
      setError(err.message || "Failed to activate contract.");
    }
  };

  const handleValidateContract = async (contract: CorporateContract) => {
    try {
      setError(null);
      const res = await validateContract(contract.id);
      setValidationResult(res);
    } catch (err: any) {
      setError(err.message || "Failed to validate contract.");
    }
  };

  const handleCopyContract = async (contract: CorporateContract) => {
    try {
      setError(null);
      const newContract = await copyContract(contract.id);
      setSuccess(`Copied contract into new draft '${newContract.title}'.`);
      fetchInitialData();
    } catch (err: any) {
      setError(err.message || "Failed to copy contract.");
    }
  };

  const handleDeleteContract = async (contractId: number) => {
    if (!confirm("Are you sure you want to delete this contract?")) return;
    try {
      setError(null);
      await deleteContract(contractId);
      setSuccess("Contract deleted.");
      fetchInitialData();
      if (selectedContract?.id === contractId) setSelectedContract(null);
    } catch (err: any) {
      setError(err.message || "Failed to delete contract.");
    }
  };

  const activeContractsCount = contracts.filter((c) => c.status === "ACTIVE").length;
  const draftContractsCount = contracts.filter((c) => c.status === "DRAFT").length;
  const totalRatesCount = contracts.reduce((acc, c) => acc + (c.rates?.length || 0), 0);

  return (
    <div className="stack" style={{ gap: 24 }}>
      {/* Top Metrics Cards matching Console Design System */}
      <section className="metrics">
        <div className="metric">
          <div className="metric-header">
            <div style={{ background: "rgba(59, 73, 223, 0.15)", padding: 8, borderRadius: "50%", color: "var(--accent)" }}>
              <FileText size={16} />
            </div>
            TOTAL CONTRACTS
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{contracts.length}</strong>
              <span>Versioned Cards</span>
            </div>
            <div className="metric-trend up">
              <CheckCircle2 size={12} /> {activeContractsCount} Active
            </div>
          </div>
        </div>

        <div className="metric">
          <div className="metric-header">
            <div style={{ background: "rgba(34, 197, 94, 0.15)", padding: 8, borderRadius: "50%", color: "var(--ok)" }}>
              <CheckCircle2 size={16} />
            </div>
            ACTIVE RATE CARDS
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{activeContractsCount}</strong>
              <span>Live Pricing</span>
            </div>
            <div className="metric-trend live">Ready</div>
          </div>
        </div>

        <div className="metric">
          <div className="metric-header">
            <div style={{ background: "rgba(234, 179, 8, 0.15)", padding: 8, borderRadius: "50%", color: "var(--warn)" }}>
              <Clock size={16} />
            </div>
            DRAFT CONTRACTS
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{draftContractsCount}</strong>
              <span>Pending Review</span>
            </div>
            <div className="metric-trend down">Drafts</div>
          </div>
        </div>

        <div className="metric">
          <div className="metric-header">
            <div style={{ background: "rgba(139, 92, 246, 0.15)", padding: 8, borderRadius: "50%", color: "#8b5cf6" }}>
              <Percent size={16} />
            </div>
            MATRIX RATES
          </div>
          <div className="metric-content">
            <div className="metric-value">
              <strong>{totalRatesCount}</strong>
              <span>Duty Package Rows</span>
            </div>
            <div className="metric-trend live">Configured</div>
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

      {/* Main Grid: Contracts List + Rate Matrix Detail */}
      <section className="grid">
        {/* Left Column: Contracts List & Search */}
        <div className="stack">
          {/* Search Filter Bar */}
          <div className="search-filter-bar">
            <div className="search-input-wrapper">
              <Search size={16} className="search-icon" />
              <input
                type="text"
                placeholder="Search title or customer..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="filter-select-wrapper">
              <select value={selectedCustomerFilter} onChange={(e) => setSelectedCustomerFilter(e.target.value)}>
                <option value="ALL">All Customers</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>{c.display_name}</option>
                ))}
              </select>
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="ALL">All Statuses</option>
                <option value="DRAFT">DRAFT</option>
                <option value="ACTIVE">ACTIVE</option>
                <option value="EXPIRED">EXPIRED</option>
                <option value="ARCHIVED">ARCHIVED</option>
              </select>
            </div>
            {isCommercialAdmin && (
              <button className="button" style={{ whiteSpace: "nowrap" }} onClick={handleOpenCreateModal}>
                <Plus size={16} /> New Contract
              </button>
            )}
          </div>

          {/* List Cards */}
          <div className="stack" style={{ maxHeight: 620, overflowY: "auto", paddingRight: 4 }}>
            {loading ? (
              <div style={{ padding: 32, textAlign: "center", color: "var(--muted)", fontSize: 14 }}>
                Loading corporate contracts...
              </div>
            ) : contracts.length === 0 ? (
              <div className="availability-item" style={{ textAlign: "center", color: "var(--muted)", padding: 32 }}>
                No rate contracts found.
              </div>
            ) : (
              contracts.map((c) => {
                const isSelected = selectedContract?.id === c.id;
                return (
                  <div
                    key={c.id}
                    onClick={() => {
                      setSelectedContract(c);
                      setValidationResult(null);
                    }}
                    style={{
                      background: isSelected ? "var(--sidebar-active)" : "var(--panel)",
                      border: `1px solid ${isSelected ? "var(--accent)" : "var(--line)"}`,
                      borderRadius: 12,
                      padding: 16,
                      cursor: "pointer",
                      transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                      boxShadow: isSelected ? "0 4px 20px var(--accent-glow)" : "var(--card-shadow)"
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <strong style={{ color: "#fff", fontSize: 15 }}>{c.title}</strong>
                          <span style={{ fontSize: 11, fontFamily: "monospace", padding: "2px 6px", background: "rgba(255, 255, 255, 0.08)", borderRadius: 4, color: "var(--muted)" }}>
                            {c.version_name}
                          </span>
                        </div>
                        <span style={{ fontSize: 12, color: "#5c6cfa", display: "block", marginTop: 4, fontWeight: 500 }}>
                          🏢 {c.customer_display_name}
                        </span>
                      </div>
                      <span className={`status ${c.status === "ACTIVE" ? "ok" : c.status === "DRAFT" ? "warn" : "neutral"}`}>
                        {c.status}
                      </span>
                    </div>

                    <div style={{ display: "flex", justifyContent: "space-between", marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--line)", fontSize: 12, color: "var(--muted)" }}>
                      <span>Package Rows: <strong style={{ color: "#fff" }}>{c.rates?.length || 0}</strong></span>
                      <span>CGST {c.cgst_rate}% + SGST {c.sgst_rate}%</span>
                      <span>Policy: <strong style={{ color: "#a5b4fc" }}>{c.metering_policy}</strong></span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Rate Card Matrix Detail View */}
        <div>
          {selectedContract ? (
            <div className="section">
              <div className="section-header" style={{ padding: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <h2 style={{ fontSize: 20, margin: 0, color: "#fff" }}>{selectedContract.title}</h2>
                      <span style={{ background: "rgba(59, 73, 223, 0.2)", border: "1px solid var(--accent)", color: "#a5b4fc", padding: "2px 8px", borderRadius: 6, fontSize: 11, fontFamily: "monospace" }}>
                        {selectedContract.version_name}
                      </span>
                    </div>
                    <span style={{ fontSize: 13, color: "var(--muted)", marginTop: 4, display: "block" }}>
                      Account: <strong style={{ color: "#fff" }}>{selectedContract.customer_display_name}</strong> • Policy: <span style={{ color: "var(--accent)" }}>{selectedContract.metering_policy}</span>
                    </span>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      className="button secondary"
                      style={{ padding: "6px 12px", fontSize: 12 }}
                      onClick={() => handleValidateContract(selectedContract)}
                    >
                      <ShieldCheck size={14} /> Validate
                    </button>
                    {isCommercialAdmin && (
                      <>
                        {selectedContract.status === "DRAFT" && (
                          <button
                            className="button"
                            style={{ padding: "6px 12px", fontSize: 12, background: "var(--ok)" }}
                            onClick={() => handleActivateContract(selectedContract)}
                          >
                            <CheckCircle2 size={14} /> Activate
                          </button>
                        )}
                        <button
                          className="button secondary"
                          style={{ padding: "6px 12px", fontSize: 12 }}
                          onClick={() => handleOpenEditModal(selectedContract)}
                        >
                          <Pencil size={14} /> Edit Matrix
                        </button>
                        <button
                          className="button secondary"
                          style={{ padding: "6px 12px", fontSize: 12 }}
                          onClick={() => handleCopyContract(selectedContract)}
                        >
                          <Copy size={14} /> Copy
                        </button>
                        <button
                          className="button secondary"
                          style={{ padding: "6px 12px", fontSize: 12, color: "var(--danger)" }}
                          onClick={() => handleDeleteContract(selectedContract.id)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>

              <div className="section-body" style={{ padding: 20 }}>
                {/* Validation Summary Box */}
                {validationResult && (
                  <div
                    style={{
                      padding: 16,
                      borderRadius: 8,
                      fontSize: 13,
                      marginBottom: 16,
                      background: validationResult.is_valid ? "rgba(34, 197, 94, 0.1)" : "rgba(239, 68, 68, 0.1)",
                      border: `1px solid ${validationResult.is_valid ? "rgba(34, 197, 94, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
                      color: validationResult.is_valid ? "var(--ok)" : "var(--danger)"
                    }}
                  >
                    <strong style={{ display: "block", marginBottom: 4 }}>
                      {validationResult.is_valid ? "✓ Contract rate card is valid and ready for activation." : "❌ Validation issues found:"}
                    </strong>
                    {validationResult.errors.map((err, i) => (
                      <div key={i} style={{ marginTop: 2 }}>• {err}</div>
                    ))}
                    {validationResult.warnings.map((warn, i) => (
                      <div key={i} style={{ marginTop: 2, color: "var(--warn)" }}>• Warning: {warn}</div>
                    ))}
                  </div>
                )}

                {/* Rate Card Matrix Table */}
                <div className="stack" style={{ gap: 12 }}>
                  <strong style={{ color: "#fff", fontSize: 14 }}>Configured Rate Card Matrix</strong>
                  {selectedContract.rates && selectedContract.rates.length > 0 ? (
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>City</th>
                            <th>Category</th>
                            <th>Duty Type</th>
                            <th>Included</th>
                            <th>Base Fare</th>
                            <th>Extra Hr / Km</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedContract.rates.map((r, i) => (
                            <tr key={i}>
                              <td><strong style={{ color: "#fff", textTransform: "capitalize" }}>{r.city}</strong></td>
                              <td style={{ textTransform: "capitalize" }}>{r.vehicle_category}</td>
                              <td><span className="status neutral">{r.duty_type}</span></td>
                              <td>{r.included_hours}h / {r.included_km}km</td>
                              <td><strong style={{ color: "var(--ok)" }}>₹{r.base_rate}</strong></td>
                              <td>₹{r.extra_hour_rate}/h • ₹{r.extra_km_rate}/km</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="availability-item" style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                      No rate card package rows configured.
                    </div>
                  )}
                </div>

                {/* Allowances Section */}
                <div className="stack" style={{ gap: 12, marginTop: 20, paddingTop: 20, borderTop: "1px solid var(--line)" }}>
                  <strong style={{ color: "#fff", fontSize: 14 }}>Contract Allowances & Drivers Extras</strong>
                  {selectedContract.allowances && selectedContract.allowances.length > 0 ? (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                      {selectedContract.allowances.map((a, i) => (
                        <div key={i} className="availability-item" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <div>
                            <strong style={{ fontSize: 13 }}>{a.allowance_type}</strong>
                            <span style={{ fontSize: 11, color: "var(--muted)" }}>{a.description}</span>
                          </div>
                          <strong style={{ color: "var(--ok)", fontSize: 14 }}>₹{a.amount}</strong>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span style={{ color: "var(--muted)", fontSize: 13 }}>No extra driver or operational allowances specified.</span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="section" style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>
              Select a rate contract from the left list to view its matrix packages, tax rules, and allowances.
            </div>
          )}
        </div>
      </section>

      {/* Contract Editor Modal */}
      {showContractModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", backdropFilter: "blur(8px)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div style={{ background: "var(--panel-strong)", border: "1px solid var(--line)", borderRadius: 16, width: "100%", maxWidth: 840, maxHeight: "90vh", overflowY: "auto", boxShadow: "0 20px 50px rgba(0,0,0,0.6)" }}>
            <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: 18, color: "#fff" }}>
                {editingContract?.id ? "Edit Contract & Rate Card Matrix" : "Create New Corporate Contract"}
              </h3>
              <button onClick={() => setShowContractModal(false)} style={{ background: "none", border: 0, color: "var(--muted)", cursor: "pointer", fontSize: 18 }}>✕</button>
            </div>

            <form onSubmit={handleSaveContract} style={{ padding: 24 }} className="stack">
              {/* Header Fields */}
              <div className="form-grid">
                <div className="field">
                  <label>Corporate Account *</label>
                  <select
                    required
                    value={editingContract?.customer || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, customer: parseInt(e.target.value) })}
                  >
                    {customers.map((c) => (
                      <option key={c.id} value={c.id}>{c.display_name} ({c.code})</option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Contract Title *</label>
                  <input
                    type="text"
                    required
                    value={editingContract?.title || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, title: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-grid">
                <div className="field">
                  <label>Version Identifier *</label>
                  <input
                    type="text"
                    required
                    value={editingContract?.version_name || "v1.0"}
                    onChange={(e) => setEditingContract({ ...editingContract, version_name: e.target.value })}
                    style={{ fontFamily: "monospace" }}
                  />
                </div>
                <div className="field">
                  <label>Metering Policy</label>
                  <select
                    value={editingContract?.metering_policy || "GARAGE_TO_GARAGE"}
                    onChange={(e) => setEditingContract({ ...editingContract, metering_policy: e.target.value })}
                  >
                    <option value="GARAGE_TO_GARAGE">GARAGE_TO_GARAGE</option>
                    <option value="PICKUP_TO_DROP">PICKUP_TO_DROP</option>
                    <option value="FIXED_PACKAGE">FIXED_PACKAGE</option>
                    <option value="OUTSTATION_DAILY_MINIMUM">OUTSTATION_DAILY_MINIMUM</option>
                  </select>
                </div>
              </div>

              <div className="form-grid">
                <div className="field">
                  <label>Effective Start Date *</label>
                  <input
                    type="date"
                    required
                    value={editingContract?.effective_start || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, effective_start: e.target.value })}
                  />
                </div>
                <div className="field">
                  <label>Effective End Date</label>
                  <input
                    type="date"
                    value={editingContract?.effective_end || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, effective_end: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-grid">
                <div className="field">
                  <label>CGST Rate (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editingContract?.cgst_rate || "2.50"}
                    onChange={(e) => setEditingContract({ ...editingContract, cgst_rate: e.target.value })}
                  />
                </div>
                <div className="field">
                  <label>SGST Rate (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editingContract?.sgst_rate || "2.50"}
                    onChange={(e) => setEditingContract({ ...editingContract, sgst_rate: e.target.value })}
                  />
                </div>
              </div>

              {/* Matrix Rows */}
              <div className="stack" style={{ gap: 12, marginTop: 12, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ color: "#fff", fontSize: 14 }}>Rate Card Matrix Rows</strong>
                  <button type="button" className="button secondary" style={{ padding: "4px 10px", fontSize: 12 }} onClick={handleAddRateRow}>
                    <Plus size={14} /> Add Row
                  </button>
                </div>

                <div className="stack" style={{ gap: 8 }}>
                  {ratesDraft.map((rate, index) => (
                    <div key={index} className="availability-item" style={{ display: "grid", gridTemplateColumns: "1.2fr 1.2fr 2fr 1.2fr 1fr 1fr 30px", gap: 8, padding: 10, alignItems: "center" }}>
                      <input
                        type="text"
                        placeholder="City"
                        value={rate.city}
                        onChange={(e) => {
                          const updated = [...ratesDraft];
                          updated[index].city = e.target.value;
                          setRatesDraft(updated);
                        }}
                        style={{ padding: "6px 8px", fontSize: 12, textTransform: "capitalize" }}
                      />
                      <input
                        type="text"
                        placeholder="Category"
                        value={rate.vehicle_category}
                        onChange={(e) => {
                          const updated = [...ratesDraft];
                          updated[index].vehicle_category = e.target.value;
                          setRatesDraft(updated);
                        }}
                        style={{ padding: "6px 8px", fontSize: 12, textTransform: "capitalize" }}
                      />
                      <select
                        value={rate.duty_type}
                        onChange={(e) => {
                          const updated = [...ratesDraft];
                          updated[index].duty_type = e.target.value;
                          setRatesDraft(updated);
                        }}
                        style={{ padding: "6px 8px", fontSize: 12 }}
                      >
                        <option value="LOCAL_8HR_80KM">LOCAL_8HR_80KM</option>
                        <option value="LOCAL_12HR_120KM">LOCAL_12HR_120KM</option>
                        <option value="OUTSTATION">OUTSTATION</option>
                        <option value="AIRPORT_TRANSFER">AIRPORT_TRANSFER</option>
                        <option value="ONE_WAY">ONE_WAY</option>
                        <option value="FULL_DAY">FULL_DAY</option>
                      </select>
                      <input
                        type="number"
                        placeholder="Base ₹"
                        value={rate.base_rate}
                        onChange={(e) => {
                          const updated = [...ratesDraft];
                          updated[index].base_rate = e.target.value;
                          setRatesDraft(updated);
                        }}
                        style={{ padding: "6px 8px", fontSize: 12, color: "var(--ok)", fontWeight: 700 }}
                      />
                      <input
                        type="number"
                        placeholder="Ex/h ₹"
                        value={rate.extra_hour_rate}
                        onChange={(e) => {
                          const updated = [...ratesDraft];
                          updated[index].extra_hour_rate = e.target.value;
                          setRatesDraft(updated);
                        }}
                        style={{ padding: "6px 8px", fontSize: 12 }}
                      />
                      <input
                        type="number"
                        placeholder="Ex/km ₹"
                        value={rate.extra_km_rate}
                        onChange={(e) => {
                          const updated = [...ratesDraft];
                          updated[index].extra_km_rate = e.target.value;
                          setRatesDraft(updated);
                        }}
                        style={{ padding: "6px 8px", fontSize: 12 }}
                      />
                      <button
                        type="button"
                        onClick={() => handleRemoveRateRow(index)}
                        style={{ background: "none", border: 0, color: "var(--danger)", cursor: "pointer", fontWeight: 700 }}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Allowances Rows */}
              <div className="stack" style={{ gap: 12, marginTop: 12, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ color: "#fff", fontSize: 14 }}>Contract Allowances</strong>
                  <button type="button" className="button secondary" style={{ padding: "4px 10px", fontSize: 12 }} onClick={handleAddAllowanceRow}>
                    <Plus size={14} /> Add Allowance
                  </button>
                </div>

                <div className="stack" style={{ gap: 8 }}>
                  {allowancesDraft.map((allowance, index) => (
                    <div key={index} className="availability-item" style={{ display: "grid", gridTemplateColumns: "2.5fr 1.5fr 3fr 30px", gap: 8, padding: 10, alignItems: "center" }}>
                      <select
                        value={allowance.allowance_type}
                        onChange={(e) => {
                          const updated = [...allowancesDraft];
                          updated[index].allowance_type = e.target.value;
                          setAllowancesDraft(updated);
                        }}
                        style={{ padding: "6px 8px", fontSize: 12 }}
                      >
                        <option value="OVERTIME_PER_HOUR">OVERTIME_PER_HOUR</option>
                        <option value="OUTSTATION_PER_DAY">OUTSTATION_PER_DAY</option>
                        <option value="OVERNIGHT_DRIVER_ALLOWANCE">OVERNIGHT_DRIVER_ALLOWANCE</option>
                        <option value="SUNDAY_ALLOWANCE">SUNDAY_ALLOWANCE</option>
                        <option value="EARLY_START_ALLOWANCE">EARLY_START_ALLOWANCE</option>
                        <option value="NIGHT_ALLOWANCE">NIGHT_ALLOWANCE</option>
                        <option value="EXTRA_DUTY_ALLOWANCE">EXTRA_DUTY_ALLOWANCE</option>
                      </select>
                      <input
                        type="number"
                        placeholder="Amount ₹"
                        value={allowance.amount}
                        onChange={(e) => {
                          const updated = [...allowancesDraft];
                          updated[index].amount = e.target.value;
                          setAllowancesDraft(updated);
                        }}
                        style={{ padding: "6px 8px", fontSize: 12, color: "var(--ok)", fontWeight: 700 }}
                      />
                      <input
                        type="text"
                        placeholder="Description"
                        value={allowance.description || ""}
                        onChange={(e) => {
                          const updated = [...allowancesDraft];
                          updated[index].description = e.target.value;
                          setAllowancesDraft(updated);
                        }}
                        style={{ padding: "6px 8px", fontSize: 12 }}
                      />
                      <button
                        type="button"
                        onClick={() => handleRemoveAllowanceRow(index)}
                        style={{ background: "none", border: 0, color: "var(--danger)", cursor: "pointer", fontWeight: 700 }}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
                <button type="button" className="button secondary" onClick={() => setShowContractModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="button">
                  Save Contract & Matrix
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
