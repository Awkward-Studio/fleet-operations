"use client";

import React, { useState, useEffect } from "react";
import {
  CorporateCustomer,
  CustomerContact,
  getCustomers,
  createCustomer,
  updateCustomer,
  deleteCustomer,
  getCustomerContacts,
  createCustomerContact,
  updateCustomerContact,
  deleteCustomerContact,
  getContracts,
  CorporateContract,
} from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";

type TabType = "directory" | "detail";
type DetailTab = "overview" | "contacts" | "contracts" | "terms";

export default function CustomerManager() {
  const { user } = useAuth();
  const isCommercialAdmin =
    user?.role === "admin" ||
    user?.role === "commercial" ||
    user?.role === "accountant" ||
    user?.permissions?.includes("write_customers");

  const [customers, setCustomers] = useState<CorporateCustomer[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Search and Filters
  const [search, setSearch] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // Selection & Detail
  const [selectedCustomer, setSelectedCustomer] = useState<CorporateCustomer | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");
  const [customerContacts, setCustomerContacts] = useState<CustomerContact[]>([]);
  const [customerContracts, setCustomerContracts] = useState<CorporateContract[]>([]);

  // Modals
  const [showCustomerModal, setShowCustomerModal] = useState<boolean>(false);
  const [editingCustomer, setEditingCustomer] = useState<Partial<CorporateCustomer> | null>(null);
  const [showContactModal, setShowContactModal] = useState<boolean>(false);
  const [editingContact, setEditingContact] = useState<Partial<CustomerContact> | null>(null);

  useEffect(() => {
    fetchCustomers();
  }, [search, statusFilter]);

  useEffect(() => {
    if (selectedCustomer) {
      fetchCustomerDetails(selectedCustomer.id);
    }
  }, [selectedCustomer?.id]);

  const fetchCustomers = async () => {
    try {
      setLoading(true);
      setError(null);
      const params: any = {};
      if (search.trim()) params.search = search.trim();
      if (statusFilter !== "ALL") params.status = statusFilter;

      const data = await getCustomers(params);
      setCustomers(data);
    } catch (err: any) {
      setError(err.message || "Failed to load customers.");
    } finally {
      setLoading(false);
    }
  };

  const fetchCustomerDetails = async (customerId: number) => {
    try {
      const [contacts, contracts] = await Promise.all([
        getCustomerContacts(customerId),
        getContracts({ customer: customerId }),
      ]);
      setCustomerContacts(contacts);
      setCustomerContracts(contracts);
    } catch (err: any) {
      console.error("Error fetching customer details:", err);
    }
  };

  const handleSaveCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCustomer) return;

    try {
      setError(null);
      if (editingCustomer.id) {
        const updated = await updateCustomer(editingCustomer.id, editingCustomer);
        setCustomers((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
        if (selectedCustomer?.id === updated.id) {
          setSelectedCustomer(updated);
        }
        setSuccess(`Customer '${updated.display_name}' updated successfully.`);
      } else {
        const created = await createCustomer(editingCustomer);
        setCustomers((prev) => [created, ...prev]);
        setSuccess(`Customer '${created.display_name}' created successfully.`);
      }
      setShowCustomerModal(false);
      setEditingCustomer(null);
    } catch (err: any) {
      setError(err.message || "Failed to save customer.");
    }
  };

  const handleDeactivateCustomer = async (customer: CorporateCustomer) => {
    if (!confirm(`Are you sure you want to deactivate '${customer.display_name}'?`)) return;

    try {
      setError(null);
      const res = await deleteCustomer(customer.id);
      setSuccess(res.detail || "Customer deactivated.");
      fetchCustomers();
      if (selectedCustomer?.id === customer.id) {
        setSelectedCustomer({ ...customer, is_active: false, status: "INACTIVE" });
      }
    } catch (err: any) {
      setError(err.message || "Failed to deactivate customer.");
    }
  };

  const handleSaveContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingContact || !selectedCustomer) return;

    try {
      setError(null);
      if (editingContact.id) {
        await updateCustomerContact(editingContact.id, editingContact);
        setSuccess("Contact updated successfully.");
      } else {
        await createCustomerContact(selectedCustomer.id, editingContact);
        setSuccess("Contact created successfully.");
      }
      setShowContactModal(false);
      setEditingContact(null);
      fetchCustomerDetails(selectedCustomer.id);
    } catch (err: any) {
      setError(err.message || "Failed to save contact.");
    }
  };

  const handleDeleteContact = async (contactId: number) => {
    if (!confirm("Are you sure you want to delete this contact?")) return;

    try {
      setError(null);
      await deleteCustomerContact(contactId);
      setSuccess("Contact deleted.");
      if (selectedCustomer) fetchCustomerDetails(selectedCustomer.id);
    } catch (err: any) {
      setError(err.message || "Failed to delete contact.");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Action Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-900/60 p-6 rounded-2xl border border-slate-800 backdrop-blur-md">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Customer Management</h1>
          <p className="text-sm text-slate-400 mt-1">
            Maintain corporate accounts, billing profiles, contacts, and pricing contracts.
          </p>
        </div>
        {isCommercialAdmin && (
          <button
            onClick={() => {
              setEditingCustomer({
                code: "",
                legal_name: "",
                display_name: "",
                status: "ACTIVE",
                is_active: true,
                gstin: "",
                billing_address: "",
                billing_email: "",
                billing_phone: "",
                payment_terms_days: 30,
                po_required: false,
              });
              setShowCustomerModal(true);
            }}
            className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-xl transition shadow-lg shadow-indigo-600/20 flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            Add New Corporate
          </button>
        )}
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-sm flex justify-between items-center">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-200">×</button>
        </div>
      )}
      {success && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-sm flex justify-between items-center">
          <span>{success}</span>
          <button onClick={() => setSuccess(null)} className="text-emerald-400 hover:text-emerald-200">×</button>
        </div>
      )}

      {/* Main Grid: Directory + Detail View */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Searchable Directory List (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-slate-900/60 p-4 rounded-2xl border border-slate-800 space-y-3">
            <div className="relative">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by code, name, GSTIN..."
                className="w-full bg-slate-800/80 border border-slate-700/60 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition"
              />
              {search && (
                <button
                  onClick={() => setSearch("")}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-white text-xs"
                >
                  Clear
                </button>
              )}
            </div>
            <div className="flex gap-2">
              {["ALL", "ACTIVE", "INACTIVE", "SUSPENDED"].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                    statusFilter === st
                      ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/50"
                      : "bg-slate-800/50 text-slate-400 hover:bg-slate-800 hover:text-slate-300 border border-slate-800"
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          {/* Customer Cards List */}
          <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
            {loading ? (
              <div className="p-8 text-center text-slate-400 text-sm">Loading corporate customers...</div>
            ) : customers.length === 0 ? (
              <div className="p-8 text-center bg-slate-900/40 rounded-2xl border border-slate-800/60 text-slate-400 text-sm">
                No corporate customers found.
              </div>
            ) : (
              customers.map((c) => {
                const isSelected = selectedCustomer?.id === c.id;
                return (
                  <div
                    key={c.id}
                    onClick={() => setSelectedCustomer(c)}
                    className={`p-4 rounded-xl border transition cursor-pointer ${
                      isSelected
                        ? "bg-indigo-950/40 border-indigo-500/60 shadow-lg shadow-indigo-900/20"
                        : "bg-slate-900/50 border-slate-800 hover:border-slate-700 hover:bg-slate-800/40"
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-white text-base">{c.display_name}</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-800 text-slate-300 border border-slate-700">
                            {c.code}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-1 line-clamp-1">{c.legal_name}</p>
                      </div>
                      <span
                        className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${
                          c.status === "ACTIVE"
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                            : c.status === "INACTIVE"
                            ? "bg-slate-500/10 text-slate-400 border-slate-500/30"
                            : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                        }`}
                      >
                        {c.status}
                      </span>
                    </div>

                    <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                      <div>
                        <span>GSTIN: </span>
                        <span className="font-mono text-slate-300">{c.gstin || "N/A"}</span>
                      </div>
                      <div>
                        <span>Terms: </span>
                        <span className="text-slate-300">{c.payment_terms_days} days</span>
                      </div>
                    </div>

                    {c.active_contract_summary && (
                      <div className="mt-2 px-2.5 py-1.5 bg-indigo-900/30 border border-indigo-700/30 rounded-lg text-xs text-indigo-300 flex justify-between items-center">
                        <span>📄 {c.active_contract_summary.title}</span>
                        <span className="text-[10px] bg-indigo-950 px-1.5 py-0.5 rounded">
                          {c.active_contract_summary.version_name}
                        </span>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Customer Details View (7 cols) */}
        <div className="lg:col-span-7">
          {selectedCustomer ? (
            <div className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6 space-y-6">
              {/* Header inside detail */}
              <div className="flex justify-between items-start pb-4 border-b border-slate-800">
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="text-xl font-bold text-white">{selectedCustomer.display_name}</h2>
                    <span className="px-2.5 py-0.5 rounded-md text-xs font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
                      {selectedCustomer.code}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">{selectedCustomer.legal_name}</p>
                </div>
                {isCommercialAdmin && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        setEditingCustomer(selectedCustomer);
                        setShowCustomerModal(true);
                      }}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700 transition"
                    >
                      Edit Profile
                    </button>
                    {selectedCustomer.is_active && (
                      <button
                        onClick={() => handleDeactivateCustomer(selectedCustomer)}
                        className="px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-xs font-medium rounded-lg border border-rose-500/30 transition"
                      >
                        Deactivate
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Navigation Tabs */}
              <div className="flex gap-2 border-b border-slate-800/80 pb-2">
                {[
                  { id: "overview", label: "Overview" },
                  { id: "contacts", label: `Contacts (${customerContacts.length})` },
                  { id: "contracts", label: `Contracts (${customerContracts.length})` },
                  { id: "terms", label: "Commercial & Billing" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setDetailTab(tab.id as DetailTab)}
                    className={`px-4 py-2 rounded-xl text-xs font-medium transition ${
                      detailTab === tab.id
                        ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              {detailTab === "overview" && (
                <div className="space-y-4 text-sm text-slate-300">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-800">
                      <span className="text-xs text-slate-400 block mb-1">Status & Activity</span>
                      <span className="font-semibold text-white">{selectedCustomer.status}</span>
                      <span className="text-xs text-slate-400 block mt-1">
                        Active: {selectedCustomer.is_active ? "Yes" : "No"}
                      </span>
                    </div>
                    <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-800">
                      <span className="text-xs text-slate-400 block mb-1">GSTIN Number</span>
                      <span className="font-mono font-medium text-white">{selectedCustomer.gstin || "Not provided"}</span>
                    </div>
                  </div>

                  <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-800 space-y-2">
                    <span className="text-xs text-slate-400 block">Default Booking Contact</span>
                    <p className="font-medium text-white">{selectedCustomer.booking_contact_name || "N/A"}</p>
                    <p className="text-xs text-slate-400">{selectedCustomer.booking_contact_email} {selectedCustomer.booking_contact_phone && `• ${selectedCustomer.booking_contact_phone}`}</p>
                  </div>

                  {selectedCustomer.notes && (
                    <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-800">
                      <span className="text-xs text-slate-400 block mb-1">Account Notes</span>
                      <p className="text-xs text-slate-300 whitespace-pre-wrap">{selectedCustomer.notes}</p>
                    </div>
                  )}
                </div>
              )}

              {detailTab === "contacts" && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-sm font-semibold text-white">Customer Contacts</h3>
                    {isCommercialAdmin && (
                      <button
                        onClick={() => {
                          setEditingContact({
                            name: "",
                            contact_type: "PRIMARY",
                            phone: "",
                            email: "",
                            is_primary: customerContacts.length === 0,
                          });
                          setShowContactModal(true);
                        }}
                        className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg transition"
                      >
                        + Add Contact
                      </button>
                    )}
                  </div>

                  {customerContacts.length === 0 ? (
                    <p className="text-xs text-slate-400 py-4 text-center">No contacts added for this customer yet.</p>
                  ) : (
                    <div className="space-y-3">
                      {customerContacts.map((ct) => (
                        <div
                          key={ct.id}
                          className="p-3.5 bg-slate-800/40 rounded-xl border border-slate-800 flex justify-between items-center"
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-white text-sm">{ct.name}</span>
                              {ct.is_primary && (
                                <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] rounded font-semibold">
                                  Primary
                                </span>
                              )}
                              <span className="px-2 py-0.5 bg-slate-700 text-slate-300 text-[10px] rounded font-medium">
                                {ct.contact_type}
                              </span>
                            </div>
                            <div className="text-xs text-slate-400 mt-1 space-x-3">
                              {ct.email && <span>📧 {ct.email}</span>}
                              {ct.phone && <span>📞 {ct.phone}</span>}
                            </div>
                          </div>
                          {isCommercialAdmin && (
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => {
                                  setEditingContact(ct);
                                  setShowContactModal(true);
                                }}
                                className="text-xs text-indigo-400 hover:text-indigo-300"
                              >
                                Edit
                              </button>
                              <button
                                onClick={() => handleDeleteContact(ct.id)}
                                className="text-xs text-rose-400 hover:text-rose-300"
                              >
                                Delete
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {detailTab === "contracts" && (
                <div className="space-y-4">
                  <h3 className="text-sm font-semibold text-white">Commercial Rate Contracts</h3>
                  {customerContracts.length === 0 ? (
                    <p className="text-xs text-slate-400 py-4 text-center">No active or draft contracts created yet.</p>
                  ) : (
                    <div className="space-y-3">
                      {customerContracts.map((ctr) => (
                        <div key={ctr.id} className="p-4 bg-slate-800/40 rounded-xl border border-slate-800 space-y-2">
                          <div className="flex justify-between items-center">
                            <div>
                              <span className="font-semibold text-white text-sm">{ctr.title}</span>
                              <span className="ml-2 text-xs text-slate-400">({ctr.version_name})</span>
                            </div>
                            <span
                              className={`px-2 py-0.5 rounded text-xs font-semibold ${
                                ctr.status === "ACTIVE"
                                  ? "bg-emerald-500/20 text-emerald-300"
                                  : "bg-slate-700 text-slate-300"
                              }`}
                            >
                              {ctr.status}
                            </span>
                          </div>
                          <div className="text-xs text-slate-400 flex gap-4">
                            <span>Start: {ctr.effective_start}</span>
                            <span>End: {ctr.effective_end || "Ongoing"}</span>
                            <span>Taxes: CGST {ctr.cgst_rate}% + SGST {ctr.sgst_rate}%</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {detailTab === "terms" && (
                <div className="space-y-4 text-sm text-slate-300">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-800">
                      <span className="text-xs text-slate-400 block mb-1">Payment Credit Terms</span>
                      <span className="font-bold text-white text-base">{selectedCustomer.payment_terms_days} Days</span>
                    </div>
                    <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-800">
                      <span className="text-xs text-slate-400 block mb-1">Purchase Order Required</span>
                      <span className="font-bold text-white text-base">
                        {selectedCustomer.po_required ? "Yes (Mandatory PO)" : "No (Optional PO)"}
                      </span>
                    </div>
                  </div>

                  <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-800 space-y-2">
                    <span className="text-xs text-slate-400 block">Billing Identity & Address</span>
                    <p className="text-xs font-medium text-white">{selectedCustomer.billing_email || "No billing email"}</p>
                    <p className="text-xs text-slate-300 whitespace-pre-wrap">{selectedCustomer.billing_address || "No billing address configured."}</p>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-slate-900/40 rounded-2xl border border-slate-800 p-12 text-center text-slate-400 text-sm">
              Select a customer from the left directory to view full details and management controls.
            </div>
          )}
        </div>
      </div>

      {/* Customer Create/Edit Modal */}
      {showCustomerModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 space-y-6 shadow-2xl">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <h3 className="text-lg font-bold text-white">
                {editingCustomer?.id ? "Edit Customer Profile" : "Create New Corporate Customer"}
              </h3>
              <button onClick={() => setShowCustomerModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleSaveCustomer} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-slate-300 block mb-1">Customer Code *</label>
                  <input
                    type="text"
                    required
                    value={editingCustomer?.code || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, code: e.target.value })}
                    placeholder="e.g. ACME01"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-300 block mb-1">Status</label>
                  <select
                    value={editingCustomer?.status || "ACTIVE"}
                    onChange={(e: any) => setEditingCustomer({ ...editingCustomer, status: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="ACTIVE">ACTIVE</option>
                    <option value="INACTIVE">INACTIVE</option>
                    <option value="SUSPENDED">SUSPENDED</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-slate-300 block mb-1">Display Name *</label>
                  <input
                    type="text"
                    required
                    value={editingCustomer?.display_name || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, display_name: e.target.value })}
                    placeholder="e.g. ACME Corp"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-300 block mb-1">Legal Registered Name *</label>
                  <input
                    type="text"
                    required
                    value={editingCustomer?.legal_name || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, legal_name: e.target.value })}
                    placeholder="e.g. ACME Logistics Pvt Ltd"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-slate-300 block mb-1">GSTIN Number</label>
                  <input
                    type="text"
                    value={editingCustomer?.gstin || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, gstin: e.target.value })}
                    placeholder="27AAAAA0000A1Z5"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-300 block mb-1">Payment Credit Terms (Days)</label>
                  <input
                    type="number"
                    value={editingCustomer?.payment_terms_days || 30}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, payment_terms_days: parseInt(e.target.value) || 0 })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-slate-300 block mb-1">Billing Email</label>
                  <input
                    type="email"
                    value={editingCustomer?.billing_email || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, billing_email: e.target.value })}
                    placeholder="accounts@acme.com"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-300 block mb-1">Billing Phone</label>
                  <input
                    type="text"
                    value={editingCustomer?.billing_phone || ""}
                    onChange={(e) => setEditingCustomer({ ...editingCustomer, billing_phone: e.target.value })}
                    placeholder="+91 9876543210"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-300 block mb-1">Billing Address</label>
                <textarea
                  rows={2}
                  value={editingCustomer?.billing_address || ""}
                  onChange={(e) => setEditingCustomer({ ...editingCustomer, billing_address: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="po_required"
                  checked={editingCustomer?.po_required || false}
                  onChange={(e) => setEditingCustomer({ ...editingCustomer, po_required: e.target.checked })}
                  className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500"
                />
                <label htmlFor="po_required" className="text-xs text-slate-300 font-medium">
                  Mandatory Purchase Order (PO) required for bookings
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowCustomerModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 text-xs font-semibold rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/30"
                >
                  Save Customer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Contact Modal */}
      {showContactModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white">
                {editingContact?.id ? "Edit Contact" : "Add New Contact"}
              </h3>
              <button onClick={() => setShowContactModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleSaveContact} className="space-y-4 text-xs">
              <div>
                <label className="text-slate-300 block mb-1">Contact Name *</label>
                <input
                  type="text"
                  required
                  value={editingContact?.name || ""}
                  onChange={(e) => setEditingContact({ ...editingContact, name: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-white"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 block mb-1">Contact Type</label>
                  <select
                    value={editingContact?.contact_type || "PRIMARY"}
                    onChange={(e) => setEditingContact({ ...editingContact, contact_type: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  >
                    <option value="PRIMARY">PRIMARY</option>
                    <option value="BILLING">BILLING</option>
                    <option value="DISPATCH">DISPATCH</option>
                    <option value="COMMERCIAL">COMMERCIAL</option>
                    <option value="EMERGENCY">EMERGENCY</option>
                    <option value="OTHER">OTHER</option>
                  </select>
                </div>
                <div>
                  <label className="text-slate-300 block mb-1">Phone</label>
                  <input
                    type="text"
                    value={editingContact?.phone || ""}
                    onChange={(e) => setEditingContact({ ...editingContact, phone: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-300 block mb-1">Email</label>
                <input
                  type="email"
                  value={editingContact?.email || ""}
                  onChange={(e) => setEditingContact({ ...editingContact, email: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-white"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="is_primary"
                  checked={editingContact?.is_primary || false}
                  onChange={(e) => setEditingContact({ ...editingContact, is_primary: e.target.checked })}
                  className="rounded border-slate-700 text-indigo-600"
                />
                <label htmlFor="is_primary" className="text-slate-300 font-medium">Set as primary contact</label>
              </div>

              <div className="flex justify-end gap-2 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowContactModal(false)}
                  className="px-3 py-1.5 bg-slate-800 text-slate-300 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg"
                >
                  Save Contact
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
