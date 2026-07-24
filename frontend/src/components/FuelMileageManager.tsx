"use client";

import React, { useState, useEffect } from "react";
import {
  Fuel,
  Search,
  Plus,
  Pencil,
  Eye,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RotateCcw,
  Gauge,
  DollarSign,
  Droplet,
  FileText,
  Calendar,
  X,
  FileCheck,
  Building,
  ArrowRightLeft,
  Wrench,
  Loader2
} from "lucide-react";
import {
  FuelTransaction,
  Vehicle,
  Driver,
  UploadedAsset,
  getFuelTransactions,
  createFuelTransaction,
  approveFuelTransaction,
  rejectFuelTransaction,
  reverseFuelTransaction,
  correctFuelTransaction,
  resolveAnomaly,
  getVehicleMileage,
  getVehicles,
  getDrivers,
  updateVehicle
} from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell
} from "@/components/ui/table";
import { DocumentUpload } from "@/components/DocumentUpload";

type ActiveTab = "dashboard" | "transactions" | "anomalies" | "vehicles";

export default function FuelMileageManager() {
  const { user } = useAuth();
  const isCommercialAdmin =
    user?.role === "admin" ||
    user?.role === "commercial" ||
    user?.role === "accountant";

  // Data state
  const [transactions, setTransactions] = useState<FuelTransaction[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Selection & UI state
  const [activeTab, setActiveTab] = useState<ActiveTab>("dashboard");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [selectedTx, setSelectedTx] = useState<FuelTransaction | null>(null);
  const [txMileageMetrics, setTxMileageMetrics] = useState<any>(null);

  // Modals
  const [showLogModal, setShowLogModal] = useState<boolean>(false);
  const [showCorrectModal, setShowCorrectModal] = useState<boolean>(false);
  const [showResolveModal, setShowResolveModal] = useState<boolean>(false);
  const [showConfigModal, setShowConfigModal] = useState<boolean>(false);

  // Form states
  const [newTx, setNewTx] = useState<Partial<FuelTransaction>>({
    vehicle: 0,
    driver: null,
    vendor: "",
    invoice_number: "",
    transaction_datetime: new Date().toISOString().substring(0, 16),
    odometer_km: 0,
    quantity: "",
    unit_price: "",
    tax_amount: "0.00",
    total_amount: "",
    is_full_fill: true,
    notes: "",
    source: "console"
  });
  const [correctTxData, setCorrectTxData] = useState<Partial<FuelTransaction> | null>(null);
  const [resolveNotes, setResolveNotes] = useState<string>("");
  const [selectedVehicleForConfig, setSelectedVehicleForConfig] = useState<Vehicle | null>(null);
  const [vehicleConfig, setVehicleConfig] = useState({
    fuel_type: "PETROL",
    fuel_unit: "LITRES",
    tank_capacity: "",
    expected_mileage_min: "",
    expected_mileage_max: "",
    baseline_mileage: ""
  });

  // Attachments
  const [receiptAsset, setReceiptAsset] = useState<UploadedAsset | null>(null);
  const [odometerAsset, setOdometerAsset] = useState<UploadedAsset | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [txsData, vehiclesData, driversData] = await Promise.all([
        getFuelTransactions(),
        getVehicles(),
        getDrivers()
      ]);
      setTransactions(txsData);
      setVehicles(vehiclesData);
      setDrivers(driversData);
    } catch (err: any) {
      setError(err.message || "Failed to load fuel data.");
    } finally {
      setLoading(false);
    }
  };

  const handleFetchMileage = async (vId: number) => {
    try {
      const data = await getVehicleMileage(vId);
      setTxMileageMetrics(data);
    } catch (err) {
      console.error("Failed to load vehicle mileage details", err);
    }
  };

  const handleOpenLogModal = () => {
    setReceiptAsset(null);
    setOdometerAsset(null);
    setNewTx({
      vehicle: vehicles[0]?.id || 0,
      driver: drivers[0]?.id || null,
      vendor: "",
      invoice_number: "",
      transaction_datetime: new Date().toISOString().substring(0, 16),
      odometer_km: vehicles[0]?.odometer_km || 0,
      quantity: "",
      unit_price: "",
      tax_amount: "0.00",
      total_amount: "",
      is_full_fill: true,
      notes: "",
      source: "console"
    });
    setShowLogModal(true);
  };

  const handleSaveTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setError(null);
      const payload = {
        ...newTx,
        receipt_asset: receiptAsset ? receiptAsset.id : null,
        odometer_asset: odometerAsset ? odometerAsset.id : null
      } as any;
      await createFuelTransaction(payload);
      setSuccess("Fuel transaction logged successfully.");
      setShowLogModal(false);
      fetchData();
    } catch (err: any) {
      setError(err.message || "Failed to submit fuel transaction.");
    }
  };

  const handleOpenCorrectModal = (tx: FuelTransaction) => {
    setReceiptAsset(tx.receipt_asset || null);
    setOdometerAsset(tx.odometer_asset || null);
    setCorrectTxData({
      id: tx.id,
      vehicle: tx.vehicle,
      driver: tx.driver,
      vendor: tx.vendor,
      invoice_number: tx.invoice_number,
      transaction_datetime: tx.transaction_datetime ? tx.transaction_datetime.substring(0, 16) : "",
      odometer_km: tx.odometer_km,
      quantity: tx.quantity.toString(),
      unit_price: tx.unit_price.toString(),
      tax_amount: tx.tax_amount.toString(),
      total_amount: tx.total_amount.toString(),
      is_full_fill: tx.is_full_fill,
      notes: tx.notes || ""
    });
    setShowCorrectModal(true);
  };

  const handleCorrectTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!correctTxData || !correctTxData.id) return;
    try {
      setError(null);
      const payload = {
        ...correctTxData,
        receipt_asset: receiptAsset ? receiptAsset.id : null,
        odometer_asset: odometerAsset ? odometerAsset.id : null
      } as any;
      await correctFuelTransaction(correctTxData.id, payload);
      setSuccess("Correction submitted. Old transaction is marked corrected, and new linked replacement is created.");
      setShowCorrectModal(false);
      setCorrectTxData(null);
      fetchData();
    } catch (err: any) {
      setError(err.message || "Failed to submit correction.");
    }
  };

  const handleApprove = async (txId: number) => {
    if (!confirm("Are you sure you want to approve this fuel transaction? This will create an accounting entry.")) return;
    try {
      setError(null);
      await approveFuelTransaction(txId);
      setSuccess("Transaction approved and posted to general ledger.");
      fetchData();
    } catch (err: any) {
      setError(err.message || "Failed to approve transaction.");
    }
  };

  const handleReject = async (txId: number) => {
    if (!confirm("Are you sure you want to reject this fuel transaction?")) return;
    try {
      setError(null);
      await rejectFuelTransaction(txId);
      setSuccess("Transaction rejected.");
      fetchData();
    } catch (err: any) {
      setError(err.message || "Failed to reject transaction.");
    }
  };

  const handleReverse = async (txId: number) => {
    if (!confirm("Are you sure you want to REVERSE this transaction? This will post a reversing entry in the ledger.")) return;
    try {
      setError(null);
      await reverseFuelTransaction(txId);
      setSuccess("Transaction reversed. Accrued expenses are voided.");
      fetchData();
    } catch (err: any) {
      setError(err.message || "Failed to reverse transaction.");
    }
  };

  const handleOpenResolveAnomaly = (tx: FuelTransaction) => {
    setSelectedTx(tx);
    setResolveNotes("");
    setShowResolveModal(true);
  };

  const handleResolveAnomalySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTx) return;
    try {
      setError(null);
      await resolveAnomaly(selectedTx.id, { anomaly_review_notes: resolveNotes });
      setSuccess("Anomaly flagged state resolved with review notes.");
      setShowResolveModal(false);
      setSelectedTx(null);
      fetchData();
    } catch (err: any) {
      setError(err.message || "Failed to resolve anomaly.");
    }
  };

  const handleOpenConfigModal = (v: Vehicle) => {
    setSelectedVehicleForConfig(v);
    setVehicleConfig({
      fuel_type: v.fuel_type || "PETROL",
      fuel_unit: v.fuel_unit || "LITRES",
      tank_capacity: v.tank_capacity ? v.tank_capacity.toString() : "",
      expected_mileage_min: v.expected_mileage_min ? v.expected_mileage_min.toString() : "",
      expected_mileage_max: v.expected_mileage_max ? v.expected_mileage_max.toString() : "",
      baseline_mileage: v.baseline_mileage ? v.baseline_mileage.toString() : ""
    });
    setShowConfigModal(true);
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedVehicleForConfig) return;
    try {
      setError(null);
      const payload: any = {
        fuel_type: vehicleConfig.fuel_type,
        fuel_unit: vehicleConfig.fuel_unit,
        tank_capacity: vehicleConfig.tank_capacity ? parseFloat(vehicleConfig.tank_capacity) : null,
        expected_mileage_min: vehicleConfig.expected_mileage_min ? parseFloat(vehicleConfig.expected_mileage_min) : null,
        expected_mileage_max: vehicleConfig.expected_mileage_max ? parseFloat(vehicleConfig.expected_mileage_max) : null,
        baseline_mileage: vehicleConfig.baseline_mileage ? parseFloat(vehicleConfig.baseline_mileage) : null
      };
      await updateVehicle(selectedVehicleForConfig.id, payload);
      setSuccess(`Fuel configuration for vehicle ${selectedVehicleForConfig.registration_number} updated.`);
      setShowConfigModal(false);
      setSelectedVehicleForConfig(null);
      fetchData();
    } catch (err: any) {
      setError(err.message || "Failed to update configuration.");
    }
  };

  // Auto calculate total in new/correct forms
  const updateNewTxTotal = (qty: string, price: string, tax: string) => {
    const q = parseFloat(qty) || 0;
    const p = parseFloat(price) || 0;
    const t = parseFloat(tax) || 0;
    setNewTx(prev => ({
      ...prev,
      quantity: qty,
      unit_price: price,
      tax_amount: tax,
      total_amount: (q * p + t).toFixed(2)
    }));
  };

  const updateCorrectTxTotal = (qty: string, price: string, tax: string) => {
    const q = parseFloat(qty) || 0;
    const p = parseFloat(price) || 0;
    const t = parseFloat(tax) || 0;
    setCorrectTxData(prev => prev ? ({
      ...prev,
      quantity: qty,
      unit_price: price,
      tax_amount: tax,
      total_amount: (q * p + t).toFixed(2)
    }) : null);
  };

  // Stats / calculations
  const approvedTxs = transactions.filter(t => t.status === "approved");
  const totalFuelCost = approvedTxs.reduce((sum, t) => sum + parseFloat(t.total_amount as string), 0);
  const totalLitres = approvedTxs.reduce((sum, t) => sum + parseFloat(t.quantity as string), 0);
  const activeAnomaliesCount = transactions.filter(t => t.has_anomaly).length;

  const filteredTxs = transactions.filter(t => {
    const matchesSearch = t.vehicle_details?.registration_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.vendor.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.invoice_number.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "ALL" ? true : t.status === statusFilter.toLowerCase();
    return matchesSearch && matchesStatus;
  });

  const anomalousTxs = transactions.filter(t => t.has_anomaly);

  return (
    <div className="stack" style={{ gap: 24 }}>
      {/* Tab Select Bar */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--line)", background: "rgba(0,0,0,0.2)", borderRadius: 8, padding: 4 }}>
        {(["dashboard", "transactions", "anomalies", "vehicles"] as ActiveTab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => {
              setActiveTab(tab);
              setSelectedTx(null);
            }}
            style={{
              flex: 1,
              padding: "10px 16px",
              background: activeTab === tab ? "var(--accent)" : "none",
              border: 0,
              borderRadius: 6,
              color: "#fff",
              fontWeight: activeTab === tab ? 600 : 400,
              fontSize: 13,
              cursor: "pointer",
              textTransform: "capitalize",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              transition: "all 0.2s ease"
            }}
          >
            {tab === "dashboard" && <Gauge size={16} />}
            {tab === "transactions" && <Fuel size={16} />}
            {tab === "anomalies" && <AlertTriangle size={16} />}
            {tab === "vehicles" && <Wrench size={16} />}
            {tab === "anomalies" && activeAnomaliesCount > 0 ? (
              <span style={{ fontSize: 11, background: "var(--danger)", color: "#fff", padding: "1px 6px", borderRadius: 10, fontWeight: 700 }}>
                {activeAnomaliesCount}
              </span>
            ) : null}
            {tab}
          </button>
        ))}
      </div>

      {/* Notifications */}
      {error && (
        <div style={{ padding: "12px 16px", background: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: 8, color: "var(--danger)", fontSize: 13, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}><XCircle size={16} />{error}</span>
          <button onClick={() => setError(null)} style={{ background: "none", border: 0, color: "inherit", cursor: "pointer", fontSize: 16 }}>✕</button>
        </div>
      )}
      {success && (
        <div style={{ padding: "12px 16px", background: "rgba(34, 197, 94, 0.15)", border: "1px solid rgba(34, 197, 94, 0.3)", borderRadius: 8, color: "var(--ok)", fontSize: 13, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}><CheckCircle size={16} />{success}</span>
          <button onClick={() => setSuccess(null)} style={{ background: "none", border: 0, color: "inherit", cursor: "pointer", fontSize: 16 }}>✕</button>
        </div>
      )}

      {/* TAB CONTENT: DASHBOARD */}
      {activeTab === "dashboard" && (
        <div className="stack" style={{ gap: 24 }}>
          {/* Top Metrics Cards */}
          <section className="metrics">
            <div className="metric-card">
              <div className="metric-header">
                <div className="metric-icon" style={{ background: "rgba(59, 73, 223, 0.15)", color: "var(--accent)" }}>
                  <DollarSign size={20} />
                </div>
                TOTAL FUEL COST
              </div>
              <div className="metric-content">
                <div className="metric-value">
                  <strong>₹{totalFuelCost.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</strong>
                  <span>Approved Purchases</span>
                </div>
                <div className="metric-trend live">Live Audited</div>
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-header">
                <div className="metric-icon" style={{ background: "rgba(34, 197, 94, 0.15)", color: "var(--ok)" }}>
                  <Droplet size={20} />
                </div>
                FUEL CONSUMED
              </div>
              <div className="metric-content">
                <div className="metric-value">
                  <strong>{totalLitres.toLocaleString("en-IN", { maximumFractionDigits: 1 })}</strong>
                  <span>Litres Filled</span>
                </div>
                <div className="metric-trend ok">Active</div>
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-header">
                <div className="metric-icon" style={{ background: "rgba(234, 179, 8, 0.15)", color: "var(--warn)" }}>
                  <AlertTriangle size={20} />
                </div>
                ACTIVE ANOMALIES
              </div>
              <div className="metric-content">
                <div className="metric-value">
                  <strong>{activeAnomaliesCount}</strong>
                  <span>Flagged Fills</span>
                </div>
                <div className="metric-trend danger">Requires Review</div>
              </div>
            </div>
          </section>

          {/* Quick Info & Action */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0, color: "#fff" }}>Recent Fueling Operations</h3>
            {isCommercialAdmin && (
              <button className="button" onClick={handleOpenLogModal}>
                <Plus size={16} /> Log Fuel Purchase
              </button>
            )}
          </div>

          <div className="panel" style={{ padding: 0 }}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date & Time</TableHead>
                  <TableHead>Vehicle</TableHead>
                  <TableHead>Driver</TableHead>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Odo (km)</TableHead>
                  <TableHead>Qty (L)</TableHead>
                  <TableHead>Total Amount</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={8} style={{ textAlign: "center", padding: 24, color: "var(--muted)" }}>
                      Loading dashboard stats...
                    </TableCell>
                  </TableRow>
                ) : transactions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} style={{ textAlign: "center", padding: 24, color: "var(--muted)" }}>
                      No transactions recorded yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  transactions.slice(0, 5).map((t) => (
                    <TableRow key={t.id}>
                      <TableCell>{new Date(t.transaction_datetime).toLocaleString()}</TableCell>
                      <TableCell>
                        <strong style={{ color: "#fff" }}>{t.vehicle_details?.registration_number}</strong>
                      </TableCell>
                      <TableCell>{t.driver_details?.name || "N/A"}</TableCell>
                      <TableCell>{t.vendor}</TableCell>
                      <TableCell>{t.odometer_km.toLocaleString()}</TableCell>
                      <TableCell>{parseFloat(t.quantity as string).toFixed(2)}</TableCell>
                      <TableCell>₹{parseFloat(t.total_amount as string).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</TableCell>
                      <TableCell>
                        <span className={`status ${t.status === "approved" ? "ok" : t.status === "submitted" ? "warn" : "danger"}`}>
                          {t.status}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* TAB CONTENT: TRANSACTIONS LOG */}
      {activeTab === "transactions" && (
        <div className="stack" style={{ gap: 20 }}>
          {/* Filters Bar */}
          <div className="search-filter-bar">
            <div className="search-input-wrapper">
              <Search size={16} className="search-icon" />
              <input
                type="text"
                placeholder="Search by vehicle, vendor, invoice..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <div className="filter-select-wrapper">
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="ALL">All Statuses</option>
                <option value="SUBMITTED">Submitted</option>
                <option value="APPROVED">Approved</option>
                <option value="REJECTED">Rejected</option>
                <option value="REVERSED">Reversed</option>
                <option value="CORRECTED">Corrected</option>
              </select>
            </div>
            {isCommercialAdmin && (
              <button className="button" style={{ whiteSpace: "nowrap" }} onClick={handleOpenLogModal}>
                <Plus size={16} /> Log Fuel Purchase
              </button>
            )}
          </div>

          <div className="panel" style={{ padding: 0 }}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Vehicle</TableHead>
                  <TableHead>Odo (km)</TableHead>
                  <TableHead>Invoice</TableHead>
                  <TableHead>Quantity</TableHead>
                  <TableHead>Rate</TableHead>
                  <TableHead>Total Cost</TableHead>
                  <TableHead>Evidence</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead style={{ textAlign: "right" }}>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={10} style={{ textAlign: "center", padding: 24 }}>
                      Loading transactions...
                    </TableCell>
                  </TableRow>
                ) : filteredTxs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={10} style={{ textAlign: "center", padding: 24, color: "var(--muted)" }}>
                      No transactions match your search filter.
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredTxs.map((t) => (
                    <TableRow
                      key={t.id}
                      style={{
                        background: t.has_anomaly ? "rgba(239, 68, 68, 0.05)" : "transparent"
                      }}
                    >
                      <TableCell>{new Date(t.transaction_datetime).toLocaleDateString()}</TableCell>
                      <TableCell>
                        <div>
                          <strong style={{ color: "#fff" }}>{t.vehicle_details?.registration_number}</strong>
                          <span style={{ fontSize: 11, color: "var(--muted)", display: "block" }}>
                            {t.is_full_fill ? "Full Fill" : "Partial Fill"}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>{t.odometer_km.toLocaleString()}</TableCell>
                      <TableCell>
                        <div>
                          <span style={{ color: "#cbd5e1" }}>{t.invoice_number}</span>
                          <span style={{ fontSize: 11, color: "var(--muted)", display: "block" }}>{t.vendor}</span>
                        </div>
                      </TableCell>
                      <TableCell>{parseFloat(t.quantity as string).toFixed(2)} L</TableCell>
                      <TableCell>₹{parseFloat(t.unit_price as string).toFixed(2)}</TableCell>
                      <TableCell>
                        <div>
                          <strong>₹{parseFloat(t.total_amount as string).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong>
                          {parseFloat(t.tax_amount as string) > 0 && (
                            <span style={{ fontSize: 11, color: "var(--muted)", display: "block" }}>
                              Tax: ₹{parseFloat(t.tax_amount as string).toFixed(2)}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div style={{ display: "flex", gap: 6 }}>
                          {t.receipt_asset ? (
                            <a
                              href={t.receipt_asset.href}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                fontSize: 11,
                                background: "rgba(59, 73, 223, 0.15)",
                                color: "var(--accent)",
                                padding: "2px 6px",
                                borderRadius: 4,
                                textDecoration: "none"
                              }}
                            >
                              Receipt
                            </a>
                          ) : (
                            <span style={{ fontSize: 11, color: "var(--muted)" }}>No Receipt</span>
                          )}
                          {t.odometer_asset && (
                            <a
                              href={t.odometer_asset.href}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                fontSize: 11,
                                background: "rgba(34, 197, 94, 0.15)",
                                color: "var(--ok)",
                                padding: "2px 6px",
                                borderRadius: 4,
                                textDecoration: "none"
                              }}
                            >
                              Odo
                            </a>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          <span className={`status ${t.status === "approved" ? "ok" : t.status === "submitted" ? "warn" : "danger"}`}>
                            {t.status}
                          </span>
                          {t.has_anomaly && (
                            <span style={{ fontSize: 10, background: "var(--danger)", color: "#fff", padding: "1px 4px", borderRadius: 4, textAlign: "center", fontWeight: "bold" }}>
                              ANOMALY
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell style={{ textAlign: "right" }}>
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
                          <button
                            className="button secondary"
                            style={{ padding: 6 }}
                            onClick={() => {
                              setSelectedTx(t);
                              handleFetchMileage(t.vehicle);
                            }}
                          >
                            <Eye size={14} />
                          </button>
                          {isCommercialAdmin && t.status === "submitted" && (
                            <>
                              <button
                                className="button ok"
                                style={{ padding: "6px 12px", background: "var(--ok)", fontSize: 12 }}
                                onClick={() => handleApprove(t.id)}
                              >
                                Approve
                              </button>
                              <button
                                className="button danger"
                                style={{ padding: "6px 12px", background: "var(--danger)", fontSize: 12 }}
                                onClick={() => handleReject(t.id)}
                              >
                                Reject
                              </button>
                            </>
                          )}
                          {isCommercialAdmin && t.status === "approved" && (
                            <button
                              className="button secondary"
                              style={{ padding: "6px 12px", color: "var(--warn)", borderColor: "var(--warn)" }}
                              onClick={() => handleReverse(t.id)}
                            >
                              Reverse
                            </button>
                          )}
                          {isCommercialAdmin && (t.status === "submitted" || t.status === "approved") && (
                            <button
                              className="button secondary"
                              style={{ padding: "6px 12px" }}
                              onClick={() => handleOpenCorrectModal(t)}
                            >
                              Correct
                            </button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* TAB CONTENT: ANOMALIES QUEUE */}
      {activeTab === "anomalies" && (
        <div className="stack" style={{ gap: 20 }}>
          <h3 style={{ margin: 0, color: "#fff" }}>Flagged Exceptions & Anomalies</h3>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: 14 }}>
            Review fuel submissions flagged by automatic audits. Resolve false positives or request driver corrections.
          </p>

          <div className="panel" style={{ padding: 0 }}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Vehicle</TableHead>
                  <TableHead>Driver</TableHead>
                  <TableHead>Odo (km)</TableHead>
                  <TableHead>Vendor & Invoice</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Flagged Rules</TableHead>
                  <TableHead style={{ textAlign: "right" }}>Review Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={7} style={{ textAlign: "center", padding: 24 }}>
                      Loading anomalies...
                    </TableCell>
                  </TableRow>
                ) : anomalousTxs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                      <CheckCircle size={24} style={{ color: "var(--ok)", margin: "0 auto 10px", display: "block" }} />
                      No active anomalies detected! All logs are clean.
                    </TableCell>
                  </TableRow>
                ) : (
                  anomalousTxs.map((t) => (
                    <TableRow key={t.id} style={{ background: "rgba(239, 68, 68, 0.04)" }}>
                      <TableCell>
                        <strong style={{ color: "#fff" }}>{t.vehicle_details?.registration_number}</strong>
                      </TableCell>
                      <TableCell>{t.driver_details?.name || "N/A"}</TableCell>
                      <TableCell>{t.odometer_km.toLocaleString()}</TableCell>
                      <TableCell>
                        <div>
                          <strong>{t.vendor}</strong>
                          <span style={{ fontSize: 11, color: "var(--muted)", display: "block" }}>Inv: {t.invoice_number}</span>
                        </div>
                      </TableCell>
                      <TableCell>₹{parseFloat(t.total_amount as string).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</TableCell>
                      <TableCell>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                          {t.anomaly_flags?.map((flag) => (
                            <span
                              key={flag}
                              style={{
                                fontSize: 11,
                                background: "rgba(239, 68, 68, 0.15)",
                                color: "var(--danger)",
                                padding: "2px 8px",
                                borderRadius: 6,
                                fontWeight: 700,
                                textTransform: "capitalize"
                              }}
                            >
                              {flag.replace("_", " ")}
                            </span>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell style={{ textAlign: "right" }}>
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                          <button
                            className="button secondary"
                            style={{ padding: "6px 12px" }}
                            onClick={() => handleOpenResolveAnomaly(t)}
                          >
                            Resolve / False Positive
                          </button>
                          <button
                            className="button secondary"
                            style={{ padding: "6px 12px" }}
                            onClick={() => handleOpenCorrectModal(t)}
                          >
                            Correct
                          </button>
                          {t.status === "submitted" && (
                            <button
                              className="button danger"
                              style={{ padding: "6px 12px", background: "var(--danger)" }}
                              onClick={() => handleReject(t.id)}
                            >
                              Reject
                            </button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* TAB CONTENT: VEHICLE CONFIGURATIONS */}
      {activeTab === "vehicles" && (
        <div className="stack" style={{ gap: 20 }}>
          <h3 style={{ margin: 0, color: "#fff" }}>Fuel Policies & Configuration</h3>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: 14 }}>
            Configure specific fuel capacities and expected fuel economy benchmarks per vehicle to automate anomaly detection checks.
          </p>

          <div className="panel" style={{ padding: 0 }}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Vehicle Reg</TableHead>
                  <TableHead>Make & Model</TableHead>
                  <TableHead>Odometer (km)</TableHead>
                  <TableHead>Fuel Type</TableHead>
                  <TableHead>Tank Capacity</TableHead>
                  <TableHead>Expected Mileage (min - max)</TableHead>
                  <TableHead>Baseline Mileage</TableHead>
                  <TableHead style={{ textAlign: "right" }}>Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={8} style={{ textAlign: "center", padding: 24 }}>
                      Loading vehicles...
                    </TableCell>
                  </TableRow>
                ) : vehicles.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} style={{ textAlign: "center", padding: 24, color: "var(--muted)" }}>
                      No vehicles found.
                    </TableCell>
                  </TableRow>
                ) : (
                  vehicles.map((v) => (
                    <TableRow key={v.id}>
                      <TableCell>
                        <strong style={{ color: "#fff" }}>{v.registration_number}</strong>
                      </TableCell>
                      <TableCell>{v.make} {v.model}</TableCell>
                      <TableCell>{v.odometer_km.toLocaleString()} km</TableCell>
                      <TableCell>
                        <span style={{ fontSize: 12, padding: "2px 6px", background: "rgba(255,255,255,0.06)", borderRadius: 4 }}>
                          {v.fuel_type || "Not Set"}
                        </span>
                      </TableCell>
                      <TableCell>{v.tank_capacity ? `${parseFloat(v.tank_capacity as string)} ${v.fuel_unit || 'L'}` : "Not Configured"}</TableCell>
                      <TableCell>
                        {v.expected_mileage_min ? (
                          <span>{parseFloat(v.expected_mileage_min as string)} - {parseFloat(v.expected_mileage_max as string)} km/L</span>
                        ) : (
                          <span style={{ color: "var(--muted)" }}>No bounds</span>
                        )}
                      </TableCell>
                      <TableCell>{v.baseline_mileage ? `${parseFloat(v.baseline_mileage as string)} km/L` : "Not Configured"}</TableCell>
                      <TableCell style={{ textAlign: "right" }}>
                        {isCommercialAdmin && (
                          <button
                            className="button secondary"
                            style={{ padding: "6px 12px" }}
                            onClick={() => handleOpenConfigModal(v)}
                          >
                            Configure
                          </button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* DETAIL MODAL */}
      {selectedTx && !showResolveModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0, 0, 0, 0.75)", backdropFilter: "blur(8px)", display: "flex", justifyContent: "center", alignItems: "center", zIndex: 1000 }}>
          <div className="panel" style={{ width: 600, maxWidth: "90vw", padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
              <div>
                <h3 style={{ margin: 0, color: "#fff" }}>Fuel Purchase Details</h3>
                <span style={{ fontSize: 12, color: "var(--muted)" }}>ID: #{selectedTx.id}</span>
              </div>
              <button onClick={() => { setSelectedTx(null); setTxMileageMetrics(null); }} style={{ background: "none", border: 0, color: "var(--muted)", cursor: "pointer" }}><X size={20} /></button>
            </div>

            <div className="stack" style={{ gap: 16, fontSize: 13 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div>
                  <span style={{ color: "var(--muted)" }}>Vehicle</span>
                  <strong style={{ display: "block", color: "#fff" }}>{selectedTx.vehicle_details?.registration_number}</strong>
                </div>
                <div>
                  <span style={{ color: "var(--muted)" }}>Driver</span>
                  <strong style={{ display: "block", color: "#fff" }}>{selectedTx.driver_details?.name || "N/A"}</strong>
                </div>
                <div>
                  <span style={{ color: "var(--muted)" }}>Vendor</span>
                  <span style={{ display: "block", color: "#fff" }}>{selectedTx.vendor}</span>
                </div>
                <div>
                  <span style={{ color: "var(--muted)" }}>Invoice / Ref</span>
                  <span style={{ display: "block", color: "#fff" }}>{selectedTx.invoice_number || "N/A"}</span>
                </div>
                <div>
                  <span style={{ color: "var(--muted)" }}>Odometer</span>
                  <span style={{ display: "block", color: "#fff" }}>{selectedTx.odometer_km.toLocaleString()} km</span>
                </div>
                <div>
                  <span style={{ color: "var(--muted)" }}>Quantity filled</span>
                  <span style={{ display: "block", color: "#fff" }}>{parseFloat(selectedTx.quantity as string).toFixed(2)} L ({selectedTx.is_full_fill ? "Full Fill" : "Partial Fill"})</span>
                </div>
                <div>
                  <span style={{ color: "var(--muted)" }}>Unit Price</span>
                  <span style={{ display: "block", color: "#fff" }}>₹{parseFloat(selectedTx.unit_price as string).toFixed(2)}</span>
                </div>
                <div>
                  <span style={{ color: "var(--muted)" }}>Total Amount</span>
                  <strong style={{ display: "block", color: "#fff" }}>₹{parseFloat(selectedTx.total_amount as string).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong>
                </div>
              </div>

              {/* Mileage analysis details if available */}
              {txMileageMetrics && txMileageMetrics[selectedTx.id] && (
                <div style={{ padding: 12, background: "rgba(59, 73, 223, 0.08)", border: "1px solid rgba(59, 73, 223, 0.15)", borderRadius: 6, marginTop: 8 }}>
                  <h4 style={{ margin: "0 0 8px 0", fontSize: 13, color: "var(--accent)" }}>Audit Mileage Calculations</h4>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div>
                      <span style={{ color: "var(--muted)", fontSize: 12 }}>Distance Delta</span>
                      <strong style={{ display: "block" }}>{txMileageMetrics[selectedTx.id].delta_distance ? `${txMileageMetrics[selectedTx.id].delta_distance} km` : "N/A"}</strong>
                    </div>
                    <div>
                      <span style={{ color: "var(--muted)", fontSize: 12 }}>Computed Mileage</span>
                      <strong style={{ display: "block", color: "var(--ok)" }}>
                        {txMileageMetrics[selectedTx.id].mileage ? `${parseFloat(txMileageMetrics[selectedTx.id].mileage).toFixed(2)} km/L` : "N/A"}
                        <span style={{ fontSize: 10, fontWeight: "normal", color: "var(--muted)", marginLeft: 6 }}>
                          ({txMileageMetrics[selectedTx.id].is_authoritative ? "Authoritative" : "Estimate"})
                        </span>
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: "var(--muted)", fontSize: 12 }}>Cost per km</span>
                      <strong style={{ display: "block" }}>{txMileageMetrics[selectedTx.id].cost_per_km ? `₹${parseFloat(txMileageMetrics[selectedTx.id].cost_per_km).toFixed(2)}/km` : "N/A"}</strong>
                    </div>
                    <div>
                      <span style={{ color: "var(--muted)", fontSize: 12 }}>Consumption rate</span>
                      <strong style={{ display: "block" }}>{txMileageMetrics[selectedTx.id].consumption_rate ? `${parseFloat(txMileageMetrics[selectedTx.id].consumption_rate).toFixed(2)} L/100km` : "N/A"}</strong>
                    </div>
                  </div>
                  <div style={{ marginTop: 8, fontSize: 11, color: "var(--muted)" }}>
                    <strong>Math:</strong> {txMileageMetrics[selectedTx.id].calculation_notes}
                  </div>
                </div>
              )}

              {/* Anomaly notes */}
              {selectedTx.has_anomaly && (
                <div style={{ padding: 12, background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.15)", borderRadius: 6 }}>
                  <span style={{ color: "var(--danger)", fontWeight: 700, display: "block", marginBottom: 4 }}>Anomaly Flag Explanation</span>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
                    {selectedTx.anomaly_flags?.map(f => (
                      <span key={f} style={{ fontSize: 10, padding: "1px 6px", background: "rgba(239, 68, 68, 0.15)", color: "var(--danger)", borderRadius: 4, fontWeight: "bold" }}>
                        {f}
                      </span>
                    ))}
                  </div>
                  {selectedTx.anomaly_review_notes && (
                    <span style={{ fontSize: 12, color: "var(--muted)" }}>
                      <strong>Review Notes:</strong> {selectedTx.anomaly_review_notes}
                    </span>
                  )}
                </div>
              )}

              {/* Correction links */}
              {selectedTx.is_correction && (
                <div style={{ padding: 10, background: "rgba(255, 255, 255, 0.06)", borderRadius: 6, fontSize: 12 }}>
                  <span style={{ color: "var(--muted)" }}>This is a corrected replacement from:</span>
                  <strong style={{ display: "block" }}>Transaction ID #{selectedTx.corrected_from_transaction}</strong>
                </div>
              )}
              {selectedTx.corrected_by_transaction && (
                <div style={{ padding: 10, background: "rgba(255, 255, 255, 0.06)", borderRadius: 6, fontSize: 12 }}>
                  <span style={{ color: "var(--muted)" }}>This transaction has been superseded by Correction:</span>
                  <strong style={{ display: "block" }}>Transaction ID #{selectedTx.corrected_by_transaction}</strong>
                </div>
              )}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 24 }}>
              <button className="button secondary" onClick={() => { setSelectedTx(null); setTxMileageMetrics(null); }}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CREATE TRANSACTION MODAL */}
      {showLogModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1100 }}>
          <div className="panel" style={{ width: 560, maxWidth: "90vw", maxHeight: "90vh", overflowY: "auto", padding: 24 }}>
            <h3 style={{ margin: "0 0 20px", color: "#fff" }}>Log Vehicle Fuel Purchase</h3>
            <form onSubmit={handleSaveTransaction} className="stack" style={{ gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Vehicle *</label>
                  <select
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newTx.vehicle || 0}
                    onChange={(e) => {
                      const vId = parseInt(e.target.value);
                      const matched = vehicles.find(v => v.id === vId);
                      setNewTx(prev => ({
                        ...prev,
                        vehicle: vId,
                        odometer_km: matched ? matched.odometer_km : 0
                      }));
                    }}
                  >
                    <option value={0}>Select Vehicle</option>
                    {vehicles.map(v => (
                      <option key={v.id} value={v.id}>{v.registration_number} ({v.make})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Driver (Optional)</label>
                  <select
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newTx.driver || ""}
                    onChange={(e) => setNewTx({ ...newTx, driver: e.target.value ? parseInt(e.target.value) : null })}
                  >
                    <option value="">Select Driver</option>
                    {drivers.map(d => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Vendor *</label>
                  <input
                    type="text"
                    required
                    placeholder="Shell / HP Petrol Pump"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newTx.vendor || ""}
                    onChange={(e) => setNewTx({ ...newTx, vendor: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Invoice / Reference Number *</label>
                  <input
                    type="text"
                    required
                    placeholder="INV-12345"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newTx.invoice_number || ""}
                    onChange={(e) => setNewTx({ ...newTx, invoice_number: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Odometer Reading (km) *</label>
                  <input
                    type="number"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newTx.odometer_km || ""}
                    onChange={(e) => setNewTx({ ...newTx, odometer_km: parseInt(e.target.value) || 0 })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Transaction Date & Time *</label>
                  <input
                    type="datetime-local"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newTx.transaction_datetime || ""}
                    onChange={(e) => setNewTx({ ...newTx, transaction_datetime: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Quantity (Litres) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="25.50"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newTx.quantity || ""}
                    onChange={(e) => updateNewTxTotal(e.target.value, newTx.unit_price as string, newTx.tax_amount as string)}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Price per Litre (₹) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="96.50"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newTx.unit_price || ""}
                    onChange={(e) => updateNewTxTotal(newTx.quantity as string, e.target.value, newTx.tax_amount as string)}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Tax Amount (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={newTx.tax_amount || ""}
                    onChange={(e) => updateNewTxTotal(newTx.quantity as string, newTx.unit_price as string, e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Total Amount Charged (₹) *</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(59, 73, 223, 0.1)", border: "1px solid var(--accent)", color: "#fff", fontWeight: 700 }}
                  value={newTx.total_amount || ""}
                  onChange={(e) => setNewTx({ ...newTx, total_amount: e.target.value })}
                />
              </div>

              <div style={{ display: "flex", gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Fuel Invoice Receipt File</label>
                  <DocumentUpload
                    value={receiptAsset}
                    onChange={(asset) => setReceiptAsset(asset)}
                    placeholder="Upload invoice receipt (Image/PDF)"
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Odometer Verification Photo</label>
                  <DocumentUpload
                    value={odometerAsset}
                    onChange={(asset) => setOdometerAsset(asset)}
                    placeholder="Upload dashboard photo (Image)"
                  />
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  type="checkbox"
                  id="new_is_full"
                  checked={newTx.is_full_fill || false}
                  onChange={(e) => setNewTx({ ...newTx, is_full_fill: e.target.checked })}
                />
                <label htmlFor="new_is_full" style={{ fontSize: 13, color: "#fff", cursor: "pointer" }}>
                  This was a tank full fueling (Full fill)
                </label>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Operational Notes</label>
                <textarea
                  style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff", minHeight: 60 }}
                  value={newTx.notes || ""}
                  onChange={(e) => setNewTx({ ...newTx, notes: e.target.value })}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
                <button type="button" className="button secondary" onClick={() => setShowLogModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="button">
                  Submit Log
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CORRECT TRANSACTION MODAL */}
      {showCorrectModal && correctTxData && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1100 }}>
          <div className="panel" style={{ width: 560, maxWidth: "90vw", maxHeight: "90vh", overflowY: "auto", padding: 24 }}>
            <h3 style={{ margin: "0 0 20px", color: "#fff" }}>Correct Fuel Transaction (supersede ID #{correctTxData.id})</h3>
            <form onSubmit={handleCorrectTransaction} className="stack" style={{ gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Vehicle *</label>
                  <select
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={correctTxData.vehicle || 0}
                    onChange={(e) => setCorrectTxData({ ...correctTxData, vehicle: parseInt(e.target.value) })}
                  >
                    {vehicles.map(v => (
                      <option key={v.id} value={v.id}>{v.registration_number}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Driver</label>
                  <select
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={correctTxData.driver || ""}
                    onChange={(e) => setCorrectTxData({ ...correctTxData, driver: e.target.value ? parseInt(e.target.value) : null })}
                  >
                    <option value="">Select Driver</option>
                    {drivers.map(d => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Vendor *</label>
                  <input
                    type="text"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={correctTxData.vendor || ""}
                    onChange={(e) => setCorrectTxData({ ...correctTxData, vendor: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Invoice / Reference Number *</label>
                  <input
                    type="text"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={correctTxData.invoice_number || ""}
                    onChange={(e) => setCorrectTxData({ ...correctTxData, invoice_number: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Odometer Reading (km) *</label>
                  <input
                    type="number"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={correctTxData.odometer_km || ""}
                    onChange={(e) => setCorrectTxData({ ...correctTxData, odometer_km: parseInt(e.target.value) || 0 })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Transaction Date & Time *</label>
                  <input
                    type="datetime-local"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={correctTxData.transaction_datetime || ""}
                    onChange={(e) => setCorrectTxData({ ...correctTxData, transaction_datetime: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Quantity (Litres) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={correctTxData.quantity || ""}
                    onChange={(e) => updateCorrectTxTotal(e.target.value, correctTxData.unit_price as string, correctTxData.tax_amount as string)}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Price per Litre (₹) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={correctTxData.unit_price || ""}
                    onChange={(e) => updateCorrectTxTotal(correctTxData.quantity as string, e.target.value, correctTxData.tax_amount as string)}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Tax Amount (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={correctTxData.tax_amount || ""}
                    onChange={(e) => updateCorrectTxTotal(correctTxData.quantity as string, correctTxData.unit_price as string, e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Total Amount Charged (₹) *</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(59, 73, 223, 0.15)", border: "1px solid var(--accent)", color: "#fff", fontWeight: 700 }}
                  value={correctTxData.total_amount || ""}
                  onChange={(e) => setCorrectTxData({ ...correctTxData, total_amount: e.target.value })}
                />
              </div>

              <div style={{ display: "flex", gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Fuel Invoice Receipt File</label>
                  <DocumentUpload
                    value={receiptAsset}
                    onChange={(asset) => setReceiptAsset(asset)}
                    placeholder="Upload invoice receipt (Image/PDF)"
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Odometer Verification Photo</label>
                  <DocumentUpload
                    value={odometerAsset}
                    onChange={(asset) => setOdometerAsset(asset)}
                    placeholder="Upload dashboard photo (Image)"
                  />
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  type="checkbox"
                  id="correct_is_full"
                  checked={correctTxData.is_full_fill || false}
                  onChange={(e) => setCorrectTxData({ ...correctTxData, is_full_fill: e.target.checked })}
                />
                <label htmlFor="correct_is_full" style={{ fontSize: 13, color: "#fff", cursor: "pointer" }}>
                  This was a tank full fueling (Full fill)
                </label>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Notes / Reason for Correction *</label>
                <textarea
                  required
                  placeholder="Specify what details were entered wrong in the original submission."
                  style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff", minHeight: 60 }}
                  value={correctTxData.notes || ""}
                  onChange={(e) => setCorrectTxData({ ...correctTxData, notes: e.target.value })}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
                <button type="button" className="button secondary" onClick={() => setShowCorrectModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="button">
                  Submit Correction
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* RESOLVE ANOMALY MODAL */}
      {showResolveModal && selectedTx && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1100 }}>
          <div className="panel" style={{ width: 480, padding: 24 }}>
            <h3 style={{ margin: "0 0 10px", color: "#fff" }}>Resolve Odometer/Fuel Anomaly</h3>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>Vehicle: {selectedTx.vehicle_details?.registration_number} • Date: {new Date(selectedTx.transaction_datetime).toLocaleDateString()}</span>
            <div style={{ margin: "14px 0", padding: 10, background: "rgba(234, 179, 8, 0.1)", border: "1px solid rgba(234, 179, 8, 0.2)", borderRadius: 6, fontSize: 12, color: "#fef08a" }}>
              <strong>Flagged triggers:</strong> {selectedTx.anomaly_flags?.join(", ")}
            </div>

            <form onSubmit={handleResolveAnomalySubmit} className="stack" style={{ gap: 16 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Review Resolution Notes *</label>
                <textarea
                  required
                  placeholder="Explain why this anomaly is a false positive (e.g. verified receipt/odometer photos manually, vehicle configuration update, etc.)"
                  style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff", minHeight: 100 }}
                  value={resolveNotes}
                  onChange={(e) => setResolveNotes(e.target.value)}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                <button type="button" className="button secondary" onClick={() => { setShowResolveModal(false); setSelectedTx(null); }}>
                  Cancel
                </button>
                <button type="submit" className="button">
                  Resolve anomaly flag
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* VEHICLE CONFIGURATION MODAL */}
      {showConfigModal && selectedVehicleForConfig && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1100 }}>
          <div className="panel" style={{ width: 500, padding: 24 }}>
            <h3 style={{ margin: "0 0 14px", color: "#fff" }}>Configure Vehicle Fuel Parameters</h3>
            <span style={{ fontSize: 13, color: "var(--muted)", display: "block", marginBottom: 16 }}>
              Setup benchmarks for <strong style={{ color: "var(--accent)" }}>{selectedVehicleForConfig.registration_number}</strong> ({selectedVehicleForConfig.make} {selectedVehicleForConfig.model})
            </span>

            <form onSubmit={handleSaveConfig} className="stack" style={{ gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Fuel Type</label>
                  <select
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={vehicleConfig.fuel_type}
                    onChange={(e) => setVehicleConfig({ ...vehicleConfig, fuel_type: e.target.value })}
                  >
                    <option value="PETROL">Petrol</option>
                    <option value="DIESEL">Diesel</option>
                    <option value="CNG">CNG</option>
                    <option value="ELECTRIC">Electric (EV)</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Fuel Unit</label>
                  <select
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={vehicleConfig.fuel_unit}
                    onChange={(e) => setVehicleConfig({ ...vehicleConfig, fuel_unit: e.target.value })}
                  >
                    <option value="LITRES">Litres (L)</option>
                    <option value="KG">Kilograms (Kg)</option>
                    <option value="KWH">Kilowatt-hours (kWh)</option>
                  </select>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Tank Capacity (Units)</label>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="e.g. 45"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={vehicleConfig.tank_capacity}
                    onChange={(e) => setVehicleConfig({ ...vehicleConfig, tank_capacity: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Baseline Mileage (km/Unit)</label>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="e.g. 14.5"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={vehicleConfig.baseline_mileage}
                    onChange={(e) => setVehicleConfig({ ...vehicleConfig, baseline_mileage: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Min Expected Mileage (km/L)</label>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="e.g. 10"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={vehicleConfig.expected_mileage_min}
                    onChange={(e) => setVehicleConfig({ ...vehicleConfig, expected_mileage_min: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Max Expected Mileage (km/L)</label>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="e.g. 18"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={vehicleConfig.expected_mileage_max}
                    onChange={(e) => setVehicleConfig({ ...vehicleConfig, expected_mileage_max: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
                <button type="button" className="button secondary" onClick={() => { setShowConfigModal(false); setSelectedVehicleForConfig(null); }}>
                  Cancel
                </button>
                <button type="submit" className="button">
                  Save Config
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
