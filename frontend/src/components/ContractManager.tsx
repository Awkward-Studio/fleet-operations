"use client";

import React, { useState, useEffect } from "react";
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
        base_rate: "2500.00",
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

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-900/60 p-6 rounded-2xl border border-slate-800 backdrop-blur-md">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Corporate Contract & Rate Card Management</h1>
          <p className="text-sm text-slate-400 mt-1">
            Configure versioned rate cards, duty packages, allowances, tax rates, and metering policies.
          </p>
        </div>
        {isCommercialAdmin && (
          <button
            onClick={handleOpenCreateModal}
            className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-xl transition shadow-lg shadow-indigo-600/20 flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            Create New Contract
          </button>
        )}
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-sm flex justify-between items-center">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-200">✕</button>
        </div>
      )}
      {success && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-sm flex justify-between items-center">
          <span>{success}</span>
          <button onClick={() => setSuccess(null)} className="text-emerald-400 hover:text-emerald-200">✕</button>
        </div>
      )}

      {/* Main Grid: Contracts List + Rate Matrix Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Contracts List (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Filters */}
          <div className="bg-slate-900/60 p-4 rounded-2xl border border-slate-800 space-y-3">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search contract title or customer..."
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
            <div className="grid grid-cols-2 gap-2">
              <select
                value={selectedCustomerFilter}
                onChange={(e) => setSelectedCustomerFilter(e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-white"
              >
                <option value="ALL">All Customers</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>{c.display_name}</option>
                ))}
              </select>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-white"
              >
                <option value="ALL">All Statuses</option>
                <option value="DRAFT">DRAFT</option>
                <option value="ACTIVE">ACTIVE</option>
                <option value="EXPIRED">EXPIRED</option>
                <option value="ARCHIVED">ARCHIVED</option>
              </select>
            </div>
          </div>

          {/* List Cards */}
          <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
            {loading ? (
              <div className="p-8 text-center text-slate-400 text-sm">Loading contracts...</div>
            ) : contracts.length === 0 ? (
              <div className="p-8 text-center bg-slate-900/40 rounded-2xl border border-slate-800 text-slate-400 text-sm">
                No corporate contracts found.
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
                    className={`p-4 rounded-xl border transition cursor-pointer ${
                      isSelected
                        ? "bg-indigo-950/40 border-indigo-500/60 shadow-lg shadow-indigo-900/20"
                        : "bg-slate-900/50 border-slate-800 hover:border-slate-700 hover:bg-slate-800/40"
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-white text-base">{c.title}</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-800 text-slate-300 border border-slate-700">
                            {c.version_name}
                          </span>
                        </div>
                        <p className="text-xs text-indigo-400 mt-1 font-medium">{c.customer_display_name}</p>
                      </div>
                      <span
                        className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${
                          c.status === "ACTIVE"
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                            : c.status === "DRAFT"
                            ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                            : "bg-slate-500/10 text-slate-400 border-slate-500/30"
                        }`}
                      >
                        {c.status}
                      </span>
                    </div>

                    <div className="mt-3 pt-3 border-t border-slate-800/80 flex justify-between items-center text-xs text-slate-400">
                      <span>Rates: <strong className="text-white">{c.rates?.length || 0} rows</strong></span>
                      <span>CGST {c.cgst_rate}% + SGST {c.sgst_rate}%</span>
                      <span>Policy: <strong className="text-slate-300">{c.metering_policy}</strong></span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Rate Card Matrix & Validation Detail (7 cols) */}
        <div className="lg:col-span-7">
          {selectedContract ? (
            <div className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6 space-y-6">
              {/* Detail Header */}
              <div className="flex justify-between items-start pb-4 border-b border-slate-800">
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="text-xl font-bold text-white">{selectedContract.title}</h2>
                    <span className="px-2 py-0.5 rounded text-xs font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
                      {selectedContract.version_name}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">Customer: <span className="text-white font-medium">{selectedContract.customer_display_name}</span></p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleValidateContract(selectedContract)}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700 transition"
                  >
                    Check Validation
                  </button>
                  {isCommercialAdmin && (
                    <>
                      {selectedContract.status === "DRAFT" && (
                        <button
                          onClick={() => handleActivateContract(selectedContract)}
                          className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg shadow-md shadow-emerald-600/30 transition"
                        >
                          Activate
                        </button>
                      )}
                      <button
                        onClick={() => handleOpenEditModal(selectedContract)}
                        className="px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 text-xs font-medium rounded-lg border border-indigo-500/30 transition"
                      >
                        Edit Matrix
                      </button>
                      <button
                        onClick={() => handleCopyContract(selectedContract)}
                        className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg border border-slate-700 transition"
                      >
                        Copy
                      </button>
                      <button
                        onClick={() => handleDeleteContract(selectedContract.id)}
                        className="px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-xs font-medium rounded-lg border border-rose-500/30 transition"
                      >
                        Delete
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Validation Banner if checked */}
              {validationResult && (
                <div
                  className={`p-4 rounded-xl border text-xs space-y-1 ${
                    validationResult.is_valid
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                      : "bg-rose-500/10 border-rose-500/30 text-rose-300"
                  }`}
                >
                  <p className="font-bold">
                    {validationResult.is_valid ? "✓ Contract is valid and ready for activation." : "❌ Contract validation failed:"}
                  </p>
                  {validationResult.errors.map((err, i) => (
                    <p key={i}>• {err}</p>
                  ))}
                  {validationResult.warnings.map((warn, i) => (
                    <p key={i} className="text-amber-300">• Warning: {warn}</p>
                  ))}
                </div>
              )}

              {/* Rate Card Matrix Table */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-white">Rate Card Matrix</h3>
                {selectedContract.rates && selectedContract.rates.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-800/80 text-slate-400 border-b border-slate-800">
                          <th className="p-2.5 font-medium">City</th>
                          <th className="p-2.5 font-medium">Category</th>
                          <th className="p-2.5 font-medium">Duty Type</th>
                          <th className="p-2.5 font-medium">Included</th>
                          <th className="p-2.5 font-medium">Base Fare</th>
                          <th className="p-2.5 font-medium">Extra Hr / Km</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {selectedContract.rates.map((r, i) => (
                          <tr key={i} className="hover:bg-slate-800/30">
                            <td className="p-2.5 text-white font-medium capitalize">{r.city}</td>
                            <td className="p-2.5 text-slate-300 capitalize">{r.vehicle_category}</td>
                            <td className="p-2.5 text-indigo-400 font-mono">{r.duty_type}</td>
                            <td className="p-2.5 text-slate-300">{r.included_hours}h / {r.included_km}km</td>
                            <td className="p-2.5 text-emerald-400 font-semibold">₹{r.base_rate}</td>
                            <td className="p-2.5 text-slate-300">₹{r.extra_hour_rate}/h • ₹{r.extra_km_rate}/km</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 py-3">No rate rows configured for this contract yet.</p>
                )}
              </div>

              {/* Contract Allowances */}
              <div className="space-y-3 pt-3 border-t border-slate-800">
                <h3 className="text-sm font-semibold text-white">Configured Allowances</h3>
                {selectedContract.allowances && selectedContract.allowances.length > 0 ? (
                  <div className="grid grid-cols-2 gap-3">
                    {selectedContract.allowances.map((a, i) => (
                      <div key={i} className="p-3 bg-slate-800/40 rounded-xl border border-slate-800 flex justify-between items-center">
                        <div>
                          <span className="text-xs font-medium text-white block">{a.allowance_type}</span>
                          <span className="text-[11px] text-slate-400">{a.description}</span>
                        </div>
                        <span className="text-xs font-bold text-emerald-400">₹{a.amount}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">No extra allowances specified.</p>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-slate-900/40 rounded-2xl border border-slate-800 p-12 text-center text-slate-400 text-sm">
              Select a contract from the left list to view rate card details, validation status, and matrix rules.
            </div>
          )}
        </div>
      </div>

      {/* Contract Editor Modal with Rate Matrix & Allowances */}
      {showContractModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto p-6 space-y-6 shadow-2xl">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <h3 className="text-lg font-bold text-white">
                {editingContract?.id ? "Edit Contract & Rate Card Matrix" : "Create New Corporate Contract"}
              </h3>
              <button onClick={() => setShowContractModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleSaveContract} className="space-y-6">
              {/* Header Fields */}
              <div className="grid grid-cols-3 gap-4 text-xs">
                <div>
                  <label className="text-slate-300 block mb-1">Corporate Customer *</label>
                  <select
                    required
                    value={editingContract?.customer || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, customer: parseInt(e.target.value) })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  >
                    {customers.map((c) => (
                      <option key={c.id} value={c.id}>{c.display_name} ({c.code})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-slate-300 block mb-1">Contract Title *</label>
                  <input
                    type="text"
                    required
                    value={editingContract?.title || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, title: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>

                <div>
                  <label className="text-slate-300 block mb-1">Version Identifier *</label>
                  <input
                    type="text"
                    required
                    value={editingContract?.version_name || "v1.0"}
                    onChange={(e) => setEditingContract({ ...editingContract, version_name: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-white font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-4 gap-4 text-xs">
                <div>
                  <label className="text-slate-300 block mb-1">Effective Start *</label>
                  <input
                    type="date"
                    required
                    value={editingContract?.effective_start || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, effective_start: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 block mb-1">Effective End (Optional)</label>
                  <input
                    type="date"
                    value={editingContract?.effective_end || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, effective_end: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 block mb-1">CGST Rate (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editingContract?.cgst_rate || "2.50"}
                    onChange={(e) => setEditingContract({ ...editingContract, cgst_rate: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 block mb-1">SGST Rate (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editingContract?.sgst_rate || "2.50"}
                    onChange={(e) => setEditingContract({ ...editingContract, sgst_rate: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>
              </div>

              {/* Rate Card Matrix Section */}
              <div className="space-y-3 pt-3 border-t border-slate-800">
                <div className="flex justify-between items-center">
                  <h4 className="text-sm font-bold text-white">Rate Card Matrix Rows</h4>
                  <button
                    type="button"
                    onClick={handleAddRateRow}
                    className="px-3 py-1 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/50 text-xs font-semibold rounded-lg"
                  >
                    + Add Rate Row
                  </button>
                </div>

                <div className="space-y-2">
                  {ratesDraft.map((rate, index) => (
                    <div key={index} className="p-3 bg-slate-800/50 rounded-xl border border-slate-700/60 grid grid-cols-12 gap-2 text-xs items-center">
                      <div className="col-span-2">
                        <input
                          type="text"
                          placeholder="City (e.g. mumbai)"
                          value={rate.city}
                          onChange={(e) => {
                            const updated = [...ratesDraft];
                            updated[index].city = e.target.value;
                            setRatesDraft(updated);
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-white capitalize"
                        />
                      </div>
                      <div className="col-span-2">
                        <input
                          type="text"
                          placeholder="Category (e.g. sedan)"
                          value={rate.vehicle_category}
                          onChange={(e) => {
                            const updated = [...ratesDraft];
                            updated[index].vehicle_category = e.target.value;
                            setRatesDraft(updated);
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-white capitalize"
                        />
                      </div>
                      <div className="col-span-3">
                        <select
                          value={rate.duty_type}
                          onChange={(e) => {
                            const updated = [...ratesDraft];
                            updated[index].duty_type = e.target.value;
                            setRatesDraft(updated);
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-white text-[11px]"
                        >
                          <option value="LOCAL_8HR_80KM">LOCAL_8HR_80KM</option>
                          <option value="LOCAL_12HR_120KM">LOCAL_12HR_120KM</option>
                          <option value="OUTSTATION">OUTSTATION</option>
                          <option value="AIRPORT_TRANSFER">AIRPORT_TRANSFER</option>
                          <option value="ONE_WAY">ONE_WAY</option>
                          <option value="FULL_DAY">FULL_DAY</option>
                        </select>
                      </div>
                      <div className="col-span-2">
                        <input
                          type="number"
                          placeholder="Base ₹"
                          value={rate.base_rate}
                          onChange={(e) => {
                            const updated = [...ratesDraft];
                            updated[index].base_rate = e.target.value;
                            setRatesDraft(updated);
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-emerald-400 font-semibold"
                        />
                      </div>
                      <div className="col-span-2 flex gap-1">
                        <input
                          type="number"
                          placeholder="Ex/h ₹"
                          value={rate.extra_hour_rate}
                          onChange={(e) => {
                            const updated = [...ratesDraft];
                            updated[index].extra_hour_rate = e.target.value;
                            setRatesDraft(updated);
                          }}
                          className="w-1/2 bg-slate-900 border border-slate-700 rounded-lg px-1.5 py-1 text-white"
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
                          className="w-1/2 bg-slate-900 border border-slate-700 rounded-lg px-1.5 py-1 text-white"
                        />
                      </div>
                      <div className="col-span-1 text-right">
                        <button
                          type="button"
                          onClick={() => handleRemoveRateRow(index)}
                          className="text-rose-400 hover:text-rose-300 font-bold px-2 py-1"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Allowances Section */}
              <div className="space-y-3 pt-3 border-t border-slate-800">
                <div className="flex justify-between items-center">
                  <h4 className="text-sm font-bold text-white">Contract Allowances</h4>
                  <button
                    type="button"
                    onClick={handleAddAllowanceRow}
                    className="px-3 py-1 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/50 text-xs font-semibold rounded-lg"
                  >
                    + Add Allowance
                  </button>
                </div>

                <div className="space-y-2">
                  {allowancesDraft.map((allowance, index) => (
                    <div key={index} className="p-3 bg-slate-800/50 rounded-xl border border-slate-700/60 grid grid-cols-12 gap-2 text-xs items-center">
                      <div className="col-span-5">
                        <select
                          value={allowance.allowance_type}
                          onChange={(e) => {
                            const updated = [...allowancesDraft];
                            updated[index].allowance_type = e.target.value;
                            setAllowancesDraft(updated);
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-white"
                        >
                          <option value="OVERTIME_PER_HOUR">OVERTIME_PER_HOUR</option>
                          <option value="OUTSTATION_PER_DAY">OUTSTATION_PER_DAY</option>
                          <option value="OVERNIGHT_DRIVER_ALLOWANCE">OVERNIGHT_DRIVER_ALLOWANCE</option>
                          <option value="SUNDAY_ALLOWANCE">SUNDAY_ALLOWANCE</option>
                          <option value="EARLY_START_ALLOWANCE">EARLY_START_ALLOWANCE</option>
                          <option value="NIGHT_ALLOWANCE">NIGHT_ALLOWANCE</option>
                          <option value="EXTRA_DUTY_ALLOWANCE">EXTRA_DUTY_ALLOWANCE</option>
                        </select>
                      </div>
                      <div className="col-span-3">
                        <input
                          type="number"
                          placeholder="Amount ₹"
                          value={allowance.amount}
                          onChange={(e) => {
                            const updated = [...allowancesDraft];
                            updated[index].amount = e.target.value;
                            setAllowancesDraft(updated);
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-emerald-400 font-semibold"
                        />
                      </div>
                      <div className="col-span-3">
                        <input
                          type="text"
                          placeholder="Description"
                          value={allowance.description || ""}
                          onChange={(e) => {
                            const updated = [...allowancesDraft];
                            updated[index].description = e.target.value;
                            setAllowancesDraft(updated);
                          }}
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-white"
                        />
                      </div>
                      <div className="col-span-1 text-right">
                        <button
                          type="button"
                          onClick={() => handleRemoveAllowanceRow(index)}
                          className="text-rose-400 hover:text-rose-300 font-bold px-2 py-1"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Submit Buttons */}
              <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowContractModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 text-xs font-semibold rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/30"
                >
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
