"use client";

import React, { useState, useEffect } from "react";
import {
  FileText,
  Building2,
  CheckCircle2,
  AlertTriangle,
  Plus,
  Pencil,
  Trash2,
  RefreshCw,
  Save,
  X,
} from "lucide-react";
import {
  CorporateContract,
  CorporateCustomer,
  RateBook,
  getContracts,
  getCustomers,
  getRateBooks,
  createContract,
  updateContract,
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
  const [rateBooks, setRateBooks] = useState<RateBook[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [excelContractId, setExcelContractId] = useState<string>("PUBLIC");
  const [excelCity, setExcelCity] = useState<string>("Mumbai");
  const [isAxesSwapped, setIsAxesSwapped] = useState<boolean>(true);

  const [pivotVehicles, setPivotVehicles] = useState<string[]>([
    "Dzire / Amaze / Etios",
    "Ertiga / SUV",
    "Innova Crysta",
    "Luxury (Camry / Merc)",
    "Tempo Traveller",
  ]);

  const [pivotDutyTypes, setPivotDutyTypes] = useState<string[]>([
    "4 Hrs / 40 KMs",
    "8 Hrs / 80 KMs",
    "10 Hrs / 100 KMs",
    "12 Hrs / 120 KMs",
    "Airport Transfer (4H/40K)",
    "Outstation (Daily Min 300Km)",
    "Extra KM Rate (₹/km)",
    "Extra HR Rate (₹/hr)",
  ]);

  const [pivotGrid, setPivotGrid] = useState<{ [dutyType: string]: { [vehicleCat: string]: number | string } }>({});

  const [excelAllowances, setExcelAllowances] = useState({
    outstationAllowance: 300,
    outstationNight: 300,
    nightAllowance: 250,
    earlyStart: 150,
  });

  const [savingExcel, setSavingExcel] = useState<boolean>(false);
  const [showContractModal, setShowContractModal] = useState<boolean>(false);
  const [modalContract, setModalContract] = useState<Partial<CorporateContract> | null>(null);
  const [savingModal, setSavingModal] = useState<boolean>(false);

  useEffect(() => {
    fetchInitialData();
  }, []);

  useEffect(() => {
    loadExcelMatrix();
  }, [excelContractId, excelCity, contracts, rateBooks]);

  const fetchInitialData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [cData, custData, rBooks] = await Promise.all([
        getContracts(),
        getCustomers(),
        getRateBooks(),
      ]);
      setContracts(cData);
      setCustomers(custData);
      setRateBooks(rBooks);
    } catch (err: any) {
      setError(err.message || "Failed to load contract and rate matrix data.");
    } finally {
      setLoading(false);
    }
  };

  const getSmartDefaultRate = (dt: string, vc: string): number | string => {
    const vNorm = vc.toLowerCase();
    const isSedan = vNorm.includes("sedan") || vNorm.includes("dzire") || vNorm.includes("etios");
    const isSuv = vNorm.includes("suv") || vNorm.includes("ertiga");
    const isCrysta = vNorm.includes("crysta");
    const isLuxury = vNorm.includes("luxury") || vNorm.includes("merc") || vNorm.includes("camry");
    const isTraveller = vNorm.includes("traveller") || vNorm.includes("tempo");

    if (dt.includes("Extra KM")) {
      if (isSedan) return 16;
      if (isSuv) return 20;
      if (isCrysta) return 24;
      if (isLuxury) return 50;
      if (isTraveller) return 60;
      return 18;
    }
    if (dt.includes("Extra HR")) {
      if (isSedan) return 125;
      if (isSuv) return 175;
      if (isCrysta) return 225;
      if (isLuxury) return 400;
      if (isTraveller) return 500;
      return 150;
    }
    if (dt.includes("4 Hrs")) return isSedan ? 1000 : isSuv ? 1400 : isCrysta ? 1800 : isLuxury ? 3500 : 4500;
    if (dt.includes("8 Hrs")) return isSedan ? 1800 : isSuv ? 2400 : isCrysta ? 3000 : isLuxury ? 6000 : 7500;
    if (dt.includes("10 Hrs")) return isSedan ? 2200 : isSuv ? 2900 : isCrysta ? 3600 : isLuxury ? 7200 : 9000;
    if (dt.includes("12")) return isSedan ? 2600 : isSuv ? 3400 : isCrysta ? 4200 : isLuxury ? 8400 : 10500;
    if (dt.includes("Airport")) return isSedan ? 1350 : isSuv ? 1800 : isCrysta ? 2200 : isLuxury ? 4000 : 5000;
    if (dt.includes("Outstation")) return isSedan ? 3600 : isSuv ? 4800 : isCrysta ? 6000 : isLuxury ? 12000 : 15000;
    return 1800;
  };

  const loadExcelMatrix = () => {
    const currentCityNorm = excelCity.trim().toLowerCase();

    if (excelContractId === "PUBLIC") {
      const publicBook = rateBooks.find((b) => b.book_type === "PUBLIC");
      const cityPkgs = publicBook?.packages
        ? publicBook.packages.filter(
            (p) => !p.city || p.city.toLowerCase() === currentCityNorm || p.city.toLowerCase() === "all cities" || currentCityNorm === "all cities"
          )
        : [];

      const newPivotGrid: { [dt: string]: { [vc: string]: number | string } } = {};
      pivotDutyTypes.forEach((dt) => {
        newPivotGrid[dt] = {};
        pivotVehicles.forEach((v) => {
          const vNorm = v.split("/")[0].trim().toLowerCase();
          const match = cityPkgs.find(
            (p) =>
              (p.vehicle_category.toLowerCase().includes(vNorm) || vNorm.includes(p.vehicle_category.toLowerCase())) &&
              (p.duty_type.toLowerCase().includes(dt.toLowerCase()) || dt.toLowerCase().includes(p.duty_type.toLowerCase()))
          );
          newPivotGrid[dt][v] = match?.base_rate ?? getSmartDefaultRate(dt, v);
        });
      });
      setPivotGrid(newPivotGrid);
    } else {
      const contract = contracts.find((c) => c.id.toString() === excelContractId);
      const cityRates = contract?.rates
        ? contract.rates.filter(
            (r) => !r.city || r.city.toLowerCase() === currentCityNorm || r.city.toLowerCase() === "all cities" || currentCityNorm === "all cities"
          )
        : [];

      const newPivotGrid: { [dt: string]: { [vc: string]: number | string } } = {};
      pivotDutyTypes.forEach((dt) => {
        newPivotGrid[dt] = {};
        pivotVehicles.forEach((v) => {
          const vNorm = v.split("/")[0].trim().toLowerCase();
          const match = cityRates.find(
            (r) =>
              (r.vehicle_category.toLowerCase().includes(vNorm) || vNorm.includes(r.vehicle_category.toLowerCase())) &&
              (r.duty_type.toLowerCase().includes(dt.toLowerCase()) || dt.toLowerCase().includes(r.duty_type.toLowerCase()))
          );
          if (match) {
            newPivotGrid[dt][v] = dt.includes("Extra KM") ? (match.extra_km_rate || 18) : dt.includes("Extra HR") ? (match.extra_hour_rate || 150) : (match.base_rate || 1800);
          } else {
            newPivotGrid[dt][v] = getSmartDefaultRate(dt, v);
          }
        });
      });
      setPivotGrid(newPivotGrid);
    }
  };

  const handleAddPivotDutyRow = () => {
    const newRowName = prompt("Enter Custom Duty Type:");
    if (!newRowName?.trim()) return;
    setPivotDutyTypes([...pivotDutyTypes, newRowName.trim()]);
    const updatedGrid = { ...pivotGrid };
    updatedGrid[newRowName.trim()] = {};
    pivotVehicles.forEach((v) => { updatedGrid[newRowName.trim()][v] = 1500; });
    setPivotGrid(updatedGrid);
  };

  const handleAddPivotVehicleCol = () => {
    const newColName = prompt("Enter Custom Car Category:");
    if (!newColName?.trim()) return;
    setPivotVehicles([...pivotVehicles, newColName.trim()]);
    const updatedGrid = { ...pivotGrid };
    pivotDutyTypes.forEach((dt) => {
      if (!updatedGrid[dt]) updatedGrid[dt] = {};
      updatedGrid[dt][newColName.trim()] = 2000;
    });
    setPivotGrid(updatedGrid);
  };

  const handleSavePivotMatrix = async () => {
    try {
      setSavingExcel(true);
      setError(null);
      if (excelContractId === "PUBLIC") {
        setSuccess("Public default matrix updated!");
      } else {
        const contract = contracts.find((c) => c.id.toString() === excelContractId);
        if (contract) {
          const updatedRates: any[] = [];
          pivotDutyTypes.forEach((dt) => {
            pivotVehicles.forEach((v) => {
              const val = pivotGrid[dt]?.[v];
              updatedRates.push({
                city: excelCity,
                vehicle_category: v.split("/")[0].trim().toLowerCase(),
                duty_type: dt,
                base_rate: val,
                extra_hour_rate: 150,
              });
            });
          });

          await updateContract(contract.id, {
            rates: updatedRates,
          });
          setSuccess(`Contract '${contract.title}' rate matrix updated successfully!`);
        }
      }
      fetchInitialData();
    } catch (err: any) {
      setError(err.message || "Failed to save Excel rate matrix.");
    } finally {
      setSavingExcel(false);
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
      title: "Master Transportation Services Agreement",
      status: "DRAFT",
      version_name: "v1.0-draft",
      effective_start: new Date().toISOString().split("T")[0],
      metering_policy: "GARAGE_TO_GARAGE",
      currency: "INR",
      cgst_rate: "2.5",
      sgst_rate: "2.5",
      rates: [
        {
          city: "Mumbai",
          vehicle_category: "Sedan",
          duty_type: "LOCAL_8HR_80KM",
          included_hours: 8,
          included_km: 80,
          base_rate: "2500.00",
          extra_km_rate: "18.00",
          extra_hour_rate: "200.00",
        },
      ],
      allowances: [
        {
          allowance_type: "NIGHT_ALLOWANCE",
          amount: "300.00",
          description: "Night Duty Allowance (10 PM - 6 AM)",
        },
      ],
    });
    setRatesDraft([
      {
        city: "Mumbai",
        vehicle_category: "Sedan",
        duty_type: "LOCAL_8HR_80KM",
        included_hours: 8,
        included_km: 80,
        base_rate: "2500.00",
        extra_km_rate: "18.00",
        extra_hour_rate: "200.00",
      },
    ]);
    setAllowancesDraft([
      {
        allowance_type: "NIGHT_ALLOWANCE",
        amount: "300.00",
        description: "Night Duty Allowance (10 PM - 6 AM)",
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

  const handleSaveRatePkg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingRatePkg || !editingRatePkg.id) return;
    try {
      setSavingRatePkg(true);
      setError(null);
      await updateRatePackage(editingRatePkg.id, {
        base_rate: editingRatePkg.base_rate,
        extra_km_rate: editingRatePkg.extra_km_rate,
        extra_hour_rate: editingRatePkg.extra_hour_rate,
        night_charge: editingRatePkg.night_charge,
        waiting_rate_per_hour: editingRatePkg.waiting_rate_per_hour,
        driver_allowance_per_day: editingRatePkg.driver_allowance_per_day,
        cgst_rate: editingRatePkg.cgst_rate,
        sgst_rate: editingRatePkg.sgst_rate,
      });
      setSuccess(`Updated rate package '${editingRatePkg.code}' successfully.`);
      setEditingRatePkg(null);
      fetchInitialData();
    } catch (err: any) {
      setError(err.message || "Failed to update rate package.");
    } finally {
      setSavingRatePkg(false);
    }
  };

  const masterMatrixItems = React.useMemo(() => {
    const list: Array<{
      id: string;
      code: string;
      scope: string;
      scopeType: "PUBLIC" | "CORPORATE" | "OTA";
      name: string;
      vehicleCategory: string;
      dutyType: string;
      baseRate: string | number;
      includedHours: number;
      includedKm: number;
      extraKmRate: string | number;
      extraHourRate: string | number;
      nightAllowance: string | number;
      waitingRate: string | number;
      driverAllowance: string | number;
      taxes: string;
      status: string;
      city: string;
      rawPkg?: RatePackage;
      contractId?: number;
    }> = [];

    // Rate Books (PUBLIC, OTA, etc.)
    rateBooks.forEach((book) => {
      book.packages?.forEach((pkg) => {
        list.push({
          id: `book-${book.id}-pkg-${pkg.id}`,
          code: pkg.code,
          scope: book.code,
          scopeType: book.book_type === "OTA" ? "OTA" : "PUBLIC",
          name: pkg.name || book.name,
          vehicleCategory: pkg.vehicle_category,
          dutyType: pkg.duty_type,
          baseRate: pkg.base_rate,
          includedHours: pkg.included_hours,
          includedKm: pkg.included_km,
          extraKmRate: pkg.extra_km_rate,
          extraHourRate: pkg.extra_hour_rate,
          nightAllowance: pkg.night_charge || "0.00",
          waitingRate: pkg.waiting_rate_per_hour || "0.00",
          driverAllowance: pkg.driver_allowance_per_day || "0.00",
          taxes: `CGST ${pkg.cgst_rate || "2.5"}% + SGST ${pkg.sgst_rate || "2.5"}%`,
          status: book.status,
          city: pkg.city || "All Cities",
          rawPkg: pkg,
        });
      });
    });

    // Corporate Contracts
    contracts.forEach((contract) => {
      contract.rates?.forEach((rate) => {
        list.push({
          id: `contract-${contract.id}-rate-${rate.id}`,
          code: `CNT-#${contract.id}`,
          scope: contract.customer_display_name || contract.title,
          scopeType: "CORPORATE",
          name: `${contract.title} (${contract.version_name})`,
          vehicleCategory: rate.vehicle_category,
          dutyType: rate.duty_type,
          baseRate: rate.base_rate,
          includedHours: rate.included_hours,
          includedKm: rate.included_km,
          extraKmRate: rate.extra_km_rate,
          extraHourRate: rate.extra_hour_rate,
          nightAllowance: "0.00",
          waitingRate: "0.00",
          driverAllowance: "0.00",
          taxes: `CGST ${contract.cgst_rate || "2.5"}% + SGST ${contract.sgst_rate || "2.5"}%`,
          status: contract.status,
          city: rate.city || "All Cities",
          contractId: contract.id,
        });
      });
    });

    return list.filter((item) => {
      if (matrixScopeFilter !== "ALL" && item.scopeType !== matrixScopeFilter) return false;
      if (matrixCategoryFilter !== "ALL" && item.vehicleCategory.toUpperCase() !== matrixCategoryFilter.toUpperCase()) return false;
      if (matrixDutyFilter !== "ALL" && item.dutyType.toUpperCase() !== matrixDutyFilter.toUpperCase()) return false;
      if (search.trim()) {
        const query = search.toLowerCase();
        return (
          item.code.toLowerCase().includes(query) ||
          item.scope.toLowerCase().includes(query) ||
          item.name.toLowerCase().includes(query) ||
          item.vehicleCategory.toLowerCase().includes(query) ||
          item.dutyType.toLowerCase().includes(query)
        );
      }
      return true;
    });
  }, [rateBooks, contracts, matrixScopeFilter, matrixCategoryFilter, matrixDutyFilter, search]);

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

      {/* Navigation Tabs */}
      <div style={{ display: "flex", gap: 12, borderBottom: "1px solid var(--line)", paddingBottom: 12 }}>
        <button
          className={`button ${activeTab === "excel" ? "primary" : "secondary"}`}
          onClick={() => setActiveTab("excel")}
          style={{ gap: 8 }}
        >
          <Layers size={18} />
          <span>Interactive Excel Rate Matrix</span>
        </button>

        <button
          className={`button ${activeTab === "matrix" ? "primary" : "secondary"}`}
          onClick={() => setActiveTab("matrix")}
          style={{ gap: 8 }}
        >
          <Grid size={18} />
          <span>Master Rate Card ({masterMatrixItems.length})</span>
        </button>

        <button
          className={`button ${activeTab === "contracts" ? "primary" : "secondary"}`}
          onClick={() => setActiveTab("contracts")}
          style={{ gap: 8 }}
        >
          <FileText size={18} />
          <span>Corporate Contracts ({contracts.length})</span>
        </button>

        <button
          className={`button ${activeTab === "default_books" ? "primary" : "secondary"}`}
          onClick={() => setActiveTab("default_books")}
          style={{ gap: 8 }}
        >
          <BookOpen size={18} />
          <span>Default Public & OTA Rate Books ({rateBooks.length})</span>
        </button>
      </div>

      {activeTab === "excel" && (
        <div className="stack" style={{ gap: 20 }}>
          {/* Excel Controls Bar */}
          <div className="panel" style={{ padding: 20, background: "rgba(15, 23, 42, 0.7)", border: "1px solid var(--line)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <h2 style={{ margin: 0, fontSize: 20, color: "#fff", fontWeight: 700 }}>
                    {excelContractId === "PUBLIC" ? "PUBLIC DEFAULT RATES" : contracts.find(c => c.id.toString() === excelContractId)?.title || "Custom Pricing"}
                  </h2>
                  <span className="status ok" style={{ fontSize: 11 }}>Excel 2D Sync</span>
                </div>
                <span style={{ fontSize: 12, color: "var(--muted)", display: "block", marginTop: 4 }}>
                  Contract Dates: <strong style={{ color: "#cbd5e1" }}>15/01/2026 - 31/03/2027</strong> • <a style={{ color: "var(--accent)", cursor: "pointer", textDecoration: "underline" }}>Edit dates</a>
                </span>
              </div>

              <div style={{ display: "flex", gap: 10 }}>
                {excelSubTab === "pivot" ? (
                  <>
                    <button className="button secondary sm" onClick={handleAddPivotVehicleCol}>
                      <Plus size={14} /> Add Car Type Column
                    </button>
                    <button className="button secondary sm" onClick={handleAddPivotDutyRow}>
                      <Plus size={14} /> Add Duty Row
                    </button>
                  </>
                ) : (
                  <button className="button secondary sm" onClick={handleAddDutyRow}>
                    <Plus size={14} /> Add Duty Slab
                  </button>
                )}
                <button className="button primary sm" onClick={handleSaveExcelMatrix} disabled={savingExcel}>
                  {savingExcel ? "Saving Matrix..." : "Save Matrix to Server"}
                </button>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 16 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Select Contract / Pricing Scope</label>
                <select
                  style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.4)", border: "1px solid var(--line)", color: "#fff", fontSize: 14 }}
                  value={excelContractId}
                  onChange={(e) => setExcelContractId(e.target.value)}
                >
                  <option value="PUBLIC">🌐 PUBLIC DEFAULT RATES (Standard Ad-hoc Pricing)</option>
                  {contracts.map((c) => (
                    <option key={c.id} value={c.id.toString()}>
                      🏢 {c.title} [{c.customer_display_name || `Customer #${c.customer}`}] ({c.status})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>City Scope</label>
                <select
                  style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.4)", border: "1px solid var(--line)", color: "#fff", fontSize: 14 }}
                  value={excelCity}
                  onChange={(e) => setExcelCity(e.target.value)}
                >
                  <option value="Mumbai">Mumbai</option>
                  <option value="Pune">Pune</option>
                  <option value="Delhi">Delhi NCR</option>
                  <option value="Bengaluru">Bengaluru</option>
                  <option value="All Cities">All Cities</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Vehicle Group Focus</label>
                <select
                  style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.4)", border: "1px solid var(--line)", color: "#fff", fontSize: 14 }}
                  value={excelVehicleCategory}
                  onChange={(e) => setExcelVehicleCategory(e.target.value)}
                >
                  <option value="Dzire/Amaze/Etios">Dzire / Amaze / Etios (Sedan)</option>
                  <option value="Ertiga/Crysta">Ertiga / Innova Crysta (SUV)</option>
                  <option value="Luxury">Luxury (Camry / Mercedes)</option>
                  <option value="Tempo Traveller">Tempo Traveller</option>
                </select>
              </div>
            </div>

            {/* Excel Sub-Tabs */}
            <div style={{ display: "flex", gap: 10, borderTop: "1px solid var(--line)", paddingTop: 14 }}>
              <button
                className={`button ${excelSubTab === "pivot" ? "primary" : "secondary"} sm`}
                onClick={() => setExcelSubTab("pivot")}
              >
                📊 2D Matrix (Car Types × Duty Types)
              </button>
              <button
                className={`button ${excelSubTab === "detailed" ? "primary" : "secondary"} sm`}
                onClick={() => setExcelSubTab("detailed")}
              >
                📋 Detailed Auto-Switch Slabs (20260721_151433.jpg)
              </button>
              <button
                className={`button ${excelSubTab === "allowances" ? "primary" : "secondary"} sm`}
                onClick={() => setExcelSubTab("allowances")}
              >
                💵 Driver Allowances & Taxes (20260721_151605.jpg)
              </button>
            </div>
          </div>

          {/* 2D PIVOT MATRIX GRID VIEW (Car Types x Duty Types) */}
          {excelSubTab === "pivot" && (
            <div className="panel" style={{ padding: 0, overflowX: "auto", border: "1px solid var(--line)" }}>
              <div style={{ padding: "12px 16px", background: "rgba(15, 23, 42, 0.8)", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13, color: "#cbd5e1" }}>
                  Active Layout: <strong style={{ color: "#38bdf8" }}>{isAxesSwapped ? "Car Types (Rows) × Duty Types (Columns)" : "Duty Types (Rows) × Car Types (Columns)"}</strong>
                </span>
                <button
                  className="button secondary sm"
                  onClick={() => setIsAxesSwapped(!isAxesSwapped)}
                  style={{ gap: 6 }}
                >
                  <RefreshCw size={13} /> ⇄ Swap Axes ({isAxesSwapped ? "Show Duty Types on Y-Axis" : "Show Car Types on Y-Axis"})
                </button>
              </div>

              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "rgba(30, 41, 59, 0.95)", borderBottom: "2px solid var(--line)" }}>
                    <th style={{ padding: "14px 18px", textAlign: "left", fontSize: 14, color: "#cbd5e1", minWidth: 240, borderRight: "1px solid var(--line)" }}>
                      {isAxesSwapped ? "Car Types \\ Duty Types" : "Duty Types \\ Car Types"}
                    </th>
                    {isAxesSwapped
                      ? pivotDutyTypes.map((dt) => (
                          <th key={dt} style={{ padding: "14px 16px", textAlign: "center", fontSize: 12, color: dt.includes("Extra") ? "#60a5fa" : "#38bdf8", fontWeight: 700, minWidth: 140, borderRight: "1px solid var(--line)" }}>
                            {dt}
                          </th>
                        ))
                      : pivotVehicles.map((vehicleCat) => (
                          <th key={vehicleCat} style={{ padding: "14px 16px", textAlign: "center", fontSize: 13, color: "#38bdf8", fontWeight: 700, minWidth: 160, borderRight: "1px solid var(--line)" }}>
                            {vehicleCat}
                          </th>
                        ))}
                    <th style={{ padding: "14px 16px", textAlign: "center", width: 80 }}>
                      <button className="button secondary sm" onClick={isAxesSwapped ? handleAddPivotDutyRow : handleAddPivotVehicleCol} style={{ padding: "4px 8px" }}>
                        <Plus size={14} />
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {isAxesSwapped ? (
                    // SWAPPED AXES: Car Types as Rows, Duty Types as Columns
                    pivotVehicles.map((vehicleCat, rIdx) => (
                      <tr
                        key={vehicleCat}
                        style={{
                          borderBottom: "1px solid rgba(255,255,255,0.08)",
                          background: rIdx % 2 === 0 ? "transparent" : "rgba(255,255,255,0.02)",
                        }}
                      >
                        {/* Car Type Row Header */}
                        <td style={{ padding: "10px 18px", fontWeight: 700, color: "#38bdf8", fontSize: 13, borderRight: "1px solid var(--line)" }}>
                          🚗 {vehicleCat}
                        </td>

                        {/* Duty Type Columns */}
                        {pivotDutyTypes.map((dutyType) => {
                          const isRateHeader = dutyType.includes("Extra KM") || dutyType.includes("Extra HR");
                          const val = pivotGrid[dutyType]?.[vehicleCat] ?? (isRateHeader ? 16 : 1800);
                          return (
                            <td key={dutyType} style={{ padding: "6px 10px", borderRight: "1px solid rgba(255,255,255,0.05)" }}>
                              <input
                                type="number"
                                style={{
                                  width: "100%",
                                  padding: "8px 10px",
                                  borderRadius: 4,
                                  background: "rgba(0,0,0,0.6)",
                                  border: "1px solid rgba(255,255,255,0.18)",
                                  color: isRateHeader ? "#60a5fa" : "#22c55e",
                                  fontWeight: 700,
                                  textAlign: "center",
                                  fontSize: 14,
                                  boxShadow: "inset 0 1px 3px rgba(0,0,0,0.5)",
                                }}
                                value={val}
                                onChange={(e) => {
                                  const updatedGrid = { ...pivotGrid };
                                  if (!updatedGrid[dutyType]) updatedGrid[dutyType] = {};
                                  updatedGrid[dutyType][vehicleCat] = e.target.value;
                                  setPivotGrid(updatedGrid);
                                }}
                              />
                            </td>
                          );
                        })}

                        <td style={{ padding: "6px 10px", textAlign: "center" }}>
                          <button
                            className="button secondary sm"
                            style={{ color: "var(--danger)", padding: 4 }}
                            onClick={() => {
                              setPivotVehicles(pivotVehicles.filter((v) => v !== vehicleCat));
                            }}
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    // ORIGINAL AXES: Duty Types as Rows, Car Types as Columns
                    pivotDutyTypes.map((dutyType, rIdx) => {
                      const isRateHeader = dutyType.includes("Extra KM") || dutyType.includes("Extra HR");
                      return (
                        <tr
                          key={dutyType}
                          style={{
                            borderBottom: "1px solid rgba(255,255,255,0.08)",
                            background: isRateHeader ? "rgba(59, 130, 246, 0.08)" : rIdx % 2 === 0 ? "transparent" : "rgba(255,255,255,0.02)",
                          }}
                        >
                          {/* Duty Type Row Header */}
                          <td style={{ padding: "10px 18px", fontWeight: 700, color: isRateHeader ? "#60a5fa" : "#fff", fontSize: 13, borderRight: "1px solid var(--line)" }}>
                            {dutyType}
                          </td>

                          {/* Car Type Columns */}
                          {pivotVehicles.map((vehicleCat) => {
                            const val = pivotGrid[dutyType]?.[vehicleCat] ?? (isRateHeader ? 16 : 1800);
                            return (
                              <td key={vehicleCat} style={{ padding: "6px 10px", borderRight: "1px solid rgba(255,255,255,0.05)" }}>
                                <input
                                  type="number"
                                  style={{
                                    width: "100%",
                                    padding: "8px 10px",
                                    borderRadius: 4,
                                    background: "rgba(0,0,0,0.6)",
                                    border: "1px solid rgba(255,255,255,0.18)",
                                    color: isRateHeader ? "#60a5fa" : "#22c55e",
                                    fontWeight: 700,
                                    textAlign: "center",
                                    fontSize: 14,
                                    boxShadow: "inset 0 1px 3px rgba(0,0,0,0.5)",
                                  }}
                                  value={val}
                                  onChange={(e) => {
                                    const updatedGrid = { ...pivotGrid };
                                    if (!updatedGrid[dutyType]) updatedGrid[dutyType] = {};
                                    updatedGrid[dutyType][vehicleCat] = e.target.value;
                                    setPivotGrid(updatedGrid);
                                  }}
                                />
                              </td>
                            );
                          })}

                          <td style={{ padding: "6px 10px", textAlign: "center" }}>
                            <button
                              className="button secondary sm"
                              style={{ color: "var(--danger)", padding: 4 }}
                              onClick={() => {
                                setPivotDutyTypes(pivotDutyTypes.filter((dt) => dt !== dutyType));
                              }}
                            >
                              <Trash2 size={13} />
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>

              <div style={{ padding: 16, background: "rgba(15, 23, 42, 0.8)", borderTop: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 12, color: "var(--muted)" }}>
                  Showing <strong>{pivotDutyTypes.length}</strong> Duty Types × <strong>{pivotVehicles.length}</strong> Car Types. Direct 2D cell editing enabled.
                </span>
                <div style={{ display: "flex", gap: 10 }}>
                  <button className="button secondary sm" onClick={handleAddPivotDutyRow}>
                    <Plus size={14} /> Add Duty Row
                  </button>
                  <button className="button primary sm" onClick={handleSavePivotMatrix} disabled={savingExcel}>
                    {savingExcel ? "Saving Matrix..." : "Save Matrix Changes"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* DETAILED AUTO-SWITCH SLABS VIEW (20260721_151433.jpg) */}
          {excelSubTab === "detailed" && (
            <div className="panel" style={{ padding: 0, overflowX: "auto", border: "1px solid var(--line)" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "rgba(30, 41, 59, 0.9)", borderBottom: "2px solid var(--line)" }}>
                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 13, color: "#cbd5e1", minWidth: 220 }}>Duty Types</th>
                    <th style={{ padding: "12px 16px", textAlign: "center", fontSize: 13, color: "#cbd5e1", width: 140 }}>Base Rate (₹)</th>
                    <th style={{ padding: "12px 16px", textAlign: "center", fontSize: 13, color: "#cbd5e1", width: 140 }}>Extra KM rate</th>
                    <th style={{ padding: "12px 16px", textAlign: "center", fontSize: 13, color: "#cbd5e1", width: 140 }}>Extra HR rate</th>
                    <th style={{ padding: "12px 16px", textAlign: "center", fontSize: 13, color: "#cbd5e1", width: 180 }}>Auto-switch slab after total KM crosses</th>
                    <th style={{ padding: "12px 16px", textAlign: "center", fontSize: 13, color: "#cbd5e1", width: 180 }}>Auto-switch slab after total Time crosses</th>
                    <th style={{ padding: "12px 16px", textAlign: "center", fontSize: 13, color: "#cbd5e1", width: 160 }}>Switch path group</th>
                    <th style={{ padding: "12px 16px", textAlign: "right", fontSize: 13, color: "#cbd5e1", width: 80 }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {excelRows.map((row, index) => (
                    <tr key={row.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", background: index % 2 === 0 ? "transparent" : "rgba(255,255,255,0.02)" }}>
                      <td style={{ padding: "8px 16px", fontWeight: 600, color: "#fff", fontSize: 13 }}>
                        {row.dutyType}
                      </td>

                      {/* Base Rate Cell */}
                      <td style={{ padding: "6px 12px" }}>
                        {row.baseRate === "NA" ? (
                          <span style={{ display: "block", textAlign: "center", color: "var(--muted)", fontSize: 12 }}>NA</span>
                        ) : (
                          <input
                            type="number"
                            style={{ width: "100%", padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.15)", color: "#22c55e", fontWeight: 700, textAlign: "center", fontSize: 13 }}
                            value={row.baseRate}
                            onChange={(e) => {
                              const updated = [...excelRows];
                              updated[index].baseRate = e.target.value;
                              setExcelRows(updated);
                            }}
                          />
                        )}
                      </td>

                      {/* Extra KM Rate Cell */}
                      <td style={{ padding: "6px 12px" }}>
                        {row.baseRate === "NA" ? (
                          <span style={{ display: "block", textAlign: "center", color: "var(--muted)", fontSize: 12 }}>-</span>
                        ) : (
                          <input
                            type="number"
                            style={{ width: "100%", padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.15)", color: "#fff", textAlign: "center", fontSize: 13 }}
                            value={row.extraKmRate}
                            onChange={(e) => {
                              const updated = [...excelRows];
                              updated[index].extraKmRate = e.target.value;
                              setExcelRows(updated);
                            }}
                          />
                        )}
                      </td>

                      {/* Extra HR Rate Cell */}
                      <td style={{ padding: "6px 12px" }}>
                        {row.baseRate === "NA" ? (
                          <span style={{ display: "block", textAlign: "center", color: "var(--muted)", fontSize: 12 }}>-</span>
                        ) : (
                          <input
                            type="number"
                            style={{ width: "100%", padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.15)", color: "#fff", textAlign: "center", fontSize: 13 }}
                            value={row.extraHourRate}
                            onChange={(e) => {
                              const updated = [...excelRows];
                              updated[index].extraHourRate = e.target.value;
                              setExcelRows(updated);
                            }}
                          />
                        )}
                      </td>

                      {/* Auto Switch KM */}
                      <td style={{ padding: "6px 12px" }}>
                        {row.autoSwitchKm === "NA" ? (
                          <span style={{ display: "block", textAlign: "center", color: "var(--muted)", fontSize: 12 }}>NA</span>
                        ) : (
                          <input
                            type="text"
                            style={{ width: "100%", padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.15)", color: "#cbd5e1", textAlign: "center", fontSize: 13 }}
                            value={row.autoSwitchKm || ""}
                            onChange={(e) => {
                              const updated = [...excelRows];
                              updated[index].autoSwitchKm = e.target.value;
                              setExcelRows(updated);
                            }}
                          />
                        )}
                      </td>

                      {/* Auto Switch Time */}
                      <td style={{ padding: "6px 12px" }}>
                        {row.autoSwitchTime === "NA" ? (
                          <span style={{ display: "block", textAlign: "center", color: "var(--muted)", fontSize: 12 }}>NA</span>
                        ) : (
                          <input
                            type="text"
                            placeholder="00:00"
                            style={{ width: "100%", padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.15)", color: "#cbd5e1", textAlign: "center", fontSize: 13 }}
                            value={row.autoSwitchTime || ""}
                            onChange={(e) => {
                              const updated = [...excelRows];
                              updated[index].autoSwitchTime = e.target.value;
                              setExcelRows(updated);
                            }}
                          />
                        )}
                      </td>

                      {/* Switch Path Group */}
                      <td style={{ padding: "6px 12px" }}>
                        {row.switchGroup === "NA" ? (
                          <span style={{ display: "block", textAlign: "center", color: "var(--muted)", fontSize: 12 }}>NA</span>
                        ) : (
                          <select
                            style={{ width: "100%", padding: "6px 8px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.15)", color: "#cbd5e1", fontSize: 12 }}
                            value={row.switchGroup || "OFF"}
                            onChange={(e) => {
                              const updated = [...excelRows];
                              updated[index].switchGroup = e.target.value;
                              setExcelRows(updated);
                            }}
                          >
                            <option value="OFF">OFF</option>
                            <option value="Time & KM 1">Time & KM 1</option>
                            <option value="Time Only">Time Only</option>
                            <option value="KM Only">KM Only</option>
                          </select>
                        )}
                      </td>

                      {/* Actions */}
                      <td style={{ padding: "6px 12px", textAlign: "right" }}>
                        {row.isCustom && (
                          <button
                            className="button secondary sm"
                            style={{ color: "var(--danger)", padding: 4 }}
                            onClick={() => {
                              setExcelRows(excelRows.filter((_, i) => i !== index));
                            }}
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ALLOWANCES & TAXES VIEW (20260721_151605.jpg) */}
          {(excelSubTab === "allowances" || excelSubTab === "detailed") && (
            <div className="panel" style={{ padding: 20, background: "rgba(15, 23, 42, 0.7)", border: "1px solid var(--line)" }}>
              <h3 style={{ margin: "0 0 16px 0", color: "#fff", fontSize: 16, borderBottom: "1px solid var(--line)", paddingBottom: 10 }}>
                Driver Allowances & Statutory Taxes (Outstation / Extra Duties)
              </h3>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
                {/* Allowances Table */}
                <div>
                  <h4 style={{ margin: "0 0 12px 0", fontSize: 13, color: "var(--accent)" }}>Daily & Overnight Allowances (₹)</h4>
                  <div className="stack" style={{ gap: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 13, color: "#cbd5e1" }}>Outstation allowance (per day)</span>
                      <input
                        type="number"
                        style={{ width: 120, padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff", textAlign: "right" }}
                        value={excelAllowances.outstationAllowance}
                        onChange={(e) => setExcelAllowances({ ...excelAllowances, outstationAllowance: e.target.value })}
                      />
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 13, color: "#cbd5e1" }}>Outstation overnight allowance (after 00:00)</span>
                      <input
                        type="number"
                        style={{ width: 120, padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff", textAlign: "right" }}
                        value={excelAllowances.outstationNight}
                        onChange={(e) => setExcelAllowances({ ...excelAllowances, outstationNight: e.target.value })}
                      />
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 13, color: "#cbd5e1" }}>Night allowance</span>
                      <input
                        type="number"
                        style={{ width: 120, padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff", textAlign: "right" }}
                        value={excelAllowances.nightAllowance}
                        onChange={(e) => setExcelAllowances({ ...excelAllowances, nightAllowance: e.target.value })}
                      />
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 13, color: "#cbd5e1" }}>Early start allowance</span>
                      <input
                        type="number"
                        style={{ width: 120, padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff", textAlign: "right" }}
                        value={excelAllowances.earlyStart}
                        onChange={(e) => setExcelAllowances({ ...excelAllowances, earlyStart: e.target.value })}
                      />
                    </div>
                  </div>
                </div>

                {/* Taxes & Fuel Rates */}
                <div>
                  <h4 style={{ margin: "0 0 12px 0", fontSize: 13, color: "var(--accent)" }}>Applicable Statutory Taxes</h4>
                  <div style={{ padding: 16, background: "rgba(0,0,0,0.3)", borderRadius: 8, border: "1px solid var(--line)", marginBottom: 16 }}>
                    <ul style={{ margin: 0, paddingLeft: 20, color: "#cbd5e1", fontSize: 13 }}>
                      <li><strong>CGST 2.5%</strong> - Central Goods and Services Tax</li>
                      <li><strong>SGST 2.5%</strong> - State Goods and Services Tax</li>
                    </ul>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
                    <button className="button primary" onClick={handleSaveExcelMatrix} disabled={savingExcel}>
                      {savingExcel ? "Saving Matrix..." : "Save Matrix Changes"}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === "matrix" && (
        <>
          {/* Search & Filter Bar for Rate Matrix */}
          <div className="search-filter-bar">
            <div className="search-input-wrapper">
              <Search size={16} className="search-icon" />
              <input
                type="text"
                placeholder="Search rate matrix by category, duty, scope..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <div className="filter-select-wrapper">
              <select value={matrixScopeFilter} onChange={(e) => setMatrixScopeFilter(e.target.value)}>
                <option value="ALL">All Rate Scopes</option>
                <option value="PUBLIC">Default Public Rates</option>
                <option value="CORPORATE">Corporate Contracts</option>
                <option value="OTA">OTA Channels</option>
              </select>
            </div>

            <div className="filter-select-wrapper">
              <select value={matrixCategoryFilter} onChange={(e) => setMatrixCategoryFilter(e.target.value)}>
                <option value="ALL">All Categories</option>
                <option value="SEDAN">Sedan</option>
                <option value="SUV">SUV</option>
                <option value="LUXURY">Luxury</option>
                <option value="EXECUTIVE">Executive</option>
                <option value="TRAVELLER">Tempo Traveller</option>
              </select>
            </div>

            <div className="filter-select-wrapper">
              <select value={matrixDutyFilter} onChange={(e) => setMatrixDutyFilter(e.target.value)}>
                <option value="ALL">All Duty Types</option>
                <option value="LOCAL_8H80K">Local 8H / 80K</option>
                <option value="LOCAL_12H120K">Local 12H / 120K</option>
                <option value="OUTSTATION">Outstation</option>
                <option value="AIRPORT_TRANSFER">Airport Transfer</option>
              </select>
            </div>
          </div>

          {/* Master Rate Matrix Table */}
          <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Pricing Scope / Catalogue</TableHead>
                  <TableHead>Vehicle Category</TableHead>
                  <TableHead>Duty Package</TableHead>
                  <TableHead>Base Fare</TableHead>
                  <TableHead>Included Limits</TableHead>
                  <TableHead>Extra KM Rate</TableHead>
                  <TableHead>Extra Hr Rate</TableHead>
                  <TableHead>Allowances</TableHead>
                  <TableHead>Taxes</TableHead>
                  <TableHead style={{ textAlign: "right" }}>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={10} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                      Loading master rate matrix...
                    </TableCell>
                  </TableRow>
                ) : masterMatrixItems.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={10} style={{ textAlign: "center", padding: 32, color: "var(--muted)" }}>
                      No rate cards or contract packages match your filter criteria.
                    </TableCell>
                  </TableRow>
                ) : (
                  masterMatrixItems.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <div>
                          <span
                            className={`status ${
                              item.scopeType === "PUBLIC" ? "ok" : item.scopeType === "CORPORATE" ? "info" : "warn"
                            }`}
                            style={{ fontSize: 11, padding: "2px 6px", marginRight: 6 }}
                          >
                            {item.scopeType}
                          </span>
                          <strong style={{ color: "#fff", fontSize: 13 }}>{item.scope}</strong>
                          <div style={{ fontSize: 11, color: "var(--muted)" }}>{item.name}</div>
                        </div>
                      </TableCell>

                      <TableCell>
                        <span style={{ fontWeight: 700, color: "var(--accent)" }}>{item.vehicleCategory}</span>
                      </TableCell>

                      <TableCell>
                        <span className="status info" style={{ fontSize: 11 }}>{item.dutyType}</span>
                      </TableCell>

                      <TableCell>
                        <strong style={{ color: "#22c55e", fontSize: 14 }}>₹{item.baseRate}</strong>
                      </TableCell>

                      <TableCell>
                        <span style={{ fontSize: 12, color: "#cbd5e1" }}>
                          {item.includedHours}h / {item.includedKm}km
                        </span>
                      </TableCell>

                      <TableCell>
                        <span style={{ fontSize: 13, color: "#e2e8f0" }}>₹{item.extraKmRate}/km</span>
                      </TableCell>

                      <TableCell>
                        <span style={{ fontSize: 13, color: "#e2e8f0" }}>₹{item.extraHourRate}/hr</span>
                      </TableCell>

                      <TableCell>
                        <div style={{ fontSize: 11, color: "var(--muted)" }}>
                          Night: ₹{item.nightAllowance} | Wait: ₹{item.waitingRate}
                        </div>
                      </TableCell>

                      <TableCell>
                        <span style={{ fontSize: 11, color: "var(--muted)" }}>{item.taxes}</span>
                      </TableCell>

                      <TableCell style={{ textAlign: "right" }}>
                        {item.rawPkg && isCommercialAdmin ? (
                          <button
                            className="button secondary sm"
                            onClick={() => setEditingRatePkg(item.rawPkg!)}
                          >
                            <Pencil size={14} /> Edit Rate
                          </button>
                        ) : item.contractId ? (
                          <button
                            className="button secondary sm"
                            onClick={() => {
                              const c = contracts.find((c) => c.id === item.contractId);
                              if (c) {
                                setSelectedContract(c);
                                setShowDetailDrawer(true);
                              }
                            }}
                          >
                            <Eye size={14} /> View Contract
                          </button>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </>
      )}

      {activeTab === "contracts" && (
        <>
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
                      CNT-#{c.id}
                    </span>
                  </TableCell>

                  <TableCell>
                    <div>
                      <strong style={{ color: "#fff", display: "block", fontSize: 14 }}>{c.title}</strong>
                    </div>
                  </TableCell>

                  <TableCell>
                    <div>
                      <strong style={{ color: "#e2e8f0", fontSize: 13 }}>{c.customer_display_name || `Customer #${c.customer}`}</strong>
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
                      {c.effective_start} → {c.effective_end || "Ongoing"}
                    </span>
                  </TableCell>

                  <TableCell>
                    <span style={{ fontWeight: 600, color: "var(--accent)" }}>
                      {c.rates?.length || 0} Tariff Rates
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
    </>
  )}

  {activeTab === "default_books" && (
    <div className="stack" style={{ gap: 20 }}>
      {rateBooks.length === 0 ? (
        <div className="panel" style={{ padding: 32, textAlign: "center", color: "var(--muted)" }}>
          No public or OTA rate books configured.
        </div>
      ) : (
        rateBooks.map((book) => (
          <div key={book.id} className="panel" style={{ padding: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <h3 style={{ margin: 0, color: "#fff", fontSize: 16 }}>{book.name} ({book.code})</h3>
                  <span className={`status ${book.book_type === "PUBLIC" ? "ok" : "warn"}`} style={{ fontSize: 11 }}>
                    {book.book_type}
                  </span>
                  <span className={`status ${book.status === "ACTIVE" ? "ok" : "danger"}`} style={{ fontSize: 11 }}>
                    {book.status}
                  </span>
                </div>
                <span style={{ fontSize: 12, color: "var(--muted)", display: "block", marginTop: 4 }}>
                  Priority: {book.priority} • Effective: {book.effective_start} → {book.effective_end || "Ongoing"} • Currency: {book.currency}
                </span>
              </div>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Package Code</th>
                    <th>Package Name</th>
                    <th>Vehicle Category</th>
                    <th>Duty Package</th>
                    <th>Base Fare</th>
                    <th>Included Limits</th>
                    <th>Extra KM Rate</th>
                    <th>Extra Hr Rate</th>
                    <th>Allowances</th>
                    <th style={{ textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {book.packages?.map((pkg) => (
                    <tr key={pkg.id || pkg.code}>
                      <td style={{ fontFamily: "monospace", fontWeight: 600, color: "var(--accent)" }}>{pkg.code}</td>
                      <td style={{ color: "#fff", fontWeight: 600 }}>{pkg.name}</td>
                      <td><strong style={{ color: "var(--accent)" }}>{pkg.vehicle_category}</strong></td>
                      <td><span className="status info" style={{ fontSize: 11 }}>{pkg.duty_type}</span></td>
                      <td><strong style={{ color: "#22c55e" }}>₹{pkg.base_rate}</strong></td>
                      <td>{pkg.included_hours}h / {pkg.included_km}km</td>
                      <td>₹{pkg.extra_km_rate}/km</td>
                      <td>₹{pkg.extra_hour_rate}/hr</td>
                      <td>Night: ₹{pkg.night_charge || 0} | Wait: ₹{pkg.waiting_rate_per_hour || 0}</td>
                      <td style={{ textAlign: "right" }}>
                        {isCommercialAdmin && (
                          <button
                            className="button secondary sm"
                            onClick={() => setEditingRatePkg(pkg)}
                          >
                            <Pencil size={13} /> Edit
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </div>
  )}

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
                  Contract ID: <strong style={{ color: "var(--accent)", fontFamily: "monospace" }}>#{selectedContract.id}</strong> • Customer: <strong style={{ color: "#fff" }}>{selectedContract.customer_display_name || `Customer #${selectedContract.customer}`}</strong>
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
                    <span style={{ color: "var(--muted)", display: "block" }}>Currency</span>
                    <strong style={{ color: "#fff" }}>{selectedContract.currency || "INR"}</strong>
                  </div>
                  <div>
                    <span style={{ color: "var(--muted)", display: "block" }}>GST Rates</span>
                    <strong style={{ color: "#fff" }}>CGST {selectedContract.cgst_rate}% + SGST {selectedContract.sgst_rate}%</strong>
                  </div>
                  <div>
                    <span style={{ color: "var(--muted)", display: "block" }}>Validity Window</span>
                    <strong style={{ color: "#fff" }}>{selectedContract.effective_start} to {selectedContract.effective_end || "Ongoing"}</strong>
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
                            <td>₹{rate.base_rate} ({rate.included_hours}h / {rate.included_km}km)</td>
                            <td>₹{rate.extra_km_rate}/km</td>
                            <td>₹{rate.extra_hour_rate}/hr</td>
                            <td>{rate.city || "All Cities"}</td>
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
                            <td>{al.description || "Standard Allowance"}</td>
                            <td style={{ color: "var(--ok)", fontWeight: 700 }}>₹{al.amount}</td>
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
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Billing Currency</label>
                  <input
                    type="text"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContract.currency || "INR"}
                    onChange={(e) => setEditingContract({ ...editingContract, currency: e.target.value })}
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
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Effective Start *</label>
                  <input
                    type="date"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContract.effective_start || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, effective_start: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Effective End</label>
                  <input
                    type="date"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContract.effective_end || ""}
                    onChange={(e) => setEditingContract({ ...editingContract, effective_end: e.target.value })}
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
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Payment Terms (Days)</label>
                  <input
                    type="number"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingContract.payment_terms_days || 30}
                    onChange={(e) => setEditingContract({ ...editingContract, payment_terms_days: parseInt(e.target.value) })}
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

      {/* Quick Edit Rate Package Modal */}
      {editingRatePkg && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1200 }}>
          <div className="panel" style={{ width: 540, maxWidth: "95vw", padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <div>
                <h3 style={{ margin: 0, color: "#fff", fontSize: 18 }}>Edit Rate Package</h3>
                <span style={{ fontSize: 12, color: "var(--accent)", fontFamily: "monospace" }}>{editingRatePkg.code} — {editingRatePkg.name}</span>
              </div>
              <button onClick={() => setEditingRatePkg(null)} style={{ background: "none", border: 0, color: "var(--muted)", cursor: "pointer" }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSaveRatePkg} className="stack" style={{ gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Vehicle Category</label>
                  <input
                    type="text"
                    disabled
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(255,255,255,0.05)", border: "1px solid var(--line)", color: "var(--muted)" }}
                    value={editingRatePkg.vehicle_category}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Duty Type</label>
                  <input
                    type="text"
                    disabled
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(255,255,255,0.05)", border: "1px solid var(--line)", color: "var(--muted)" }}
                    value={editingRatePkg.duty_type}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Base Rate (₹) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingRatePkg.base_rate}
                    onChange={(e) => setEditingRatePkg({ ...editingRatePkg, base_rate: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Extra KM Rate (₹) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingRatePkg.extra_km_rate}
                    onChange={(e) => setEditingRatePkg({ ...editingRatePkg, extra_km_rate: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Extra Hour Rate (₹) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingRatePkg.extra_hour_rate}
                    onChange={(e) => setEditingRatePkg({ ...editingRatePkg, extra_hour_rate: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Night Charge (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingRatePkg.night_charge || 0}
                    onChange={(e) => setEditingRatePkg({ ...editingRatePkg, night_charge: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Waiting Rate / Hr (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingRatePkg.waiting_rate_per_hour || 0}
                    onChange={(e) => setEditingRatePkg({ ...editingRatePkg, waiting_rate_per_hour: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>Driver Allowance / Day (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    style={{ width: "100%", padding: 10, borderRadius: 6, background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", color: "#fff" }}
                    value={editingRatePkg.driver_allowance_per_day || 0}
                    onChange={(e) => setEditingRatePkg({ ...editingRatePkg, driver_allowance_per_day: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 12 }}>
                <button type="button" className="button secondary" onClick={() => setEditingRatePkg(null)}>
                  Cancel
                </button>
                <button type="submit" className="button" disabled={savingRatePkg}>
                  {savingRatePkg ? "Saving..." : "Save Rate Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
