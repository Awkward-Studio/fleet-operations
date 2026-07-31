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
  Clock,
  ShieldCheck,
  Percent,
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

  // Active Scope Selection
  const [excelContractId, setExcelContractId] = useState<string>("PUBLIC"); // "PUBLIC" or contract ID
  const [excelCity, setExcelCity] = useState<string>("Mumbai");
  const [isAxesSwapped, setIsAxesSwapped] = useState<boolean>(true); // Car Types on Y-Axis by default

  // 2D Matrix Grid State
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

  // Persistent in-memory matrix store for all scopes: contractGrids[scopeKey] = Grid
  const [contractGrids, setContractGrids] = useState<{ [scopeKey: string]: { [dt: string]: { [vc: string]: number | string } } }>({});
  const [pivotGrid, setPivotGrid] = useState<{ [dutyType: string]: { [vehicleCat: string]: number | string } }>({});

  // 6 Allowances State
  const [excelAllowances, setExcelAllowances] = useState({
    outstationAllowance: 300,
    outstationNight: 300,
    nightAllowance: 250,
    earlyStart: 150,
    sundayAllowance: 200,
    overtimeHr: 125,
  });

  // CGST and SGST Rates State
  const [cgstRate, setCgstRate] = useState<number>(2.5);
  const [sgstRate, setSgstRate] = useState<number>(2.5);

  const [savingExcel, setSavingExcel] = useState<boolean>(false);

  // Modal State
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

  // Computes unique, contract-specific smart rates based on Contract ID & City
  const getSmartDefaultRate = (dt: string, vc: string, contractIdStr: string): number | string => {
    const vNorm = vc.toLowerCase();
    const isSedan = vNorm.includes("sedan") || vNorm.includes("dzire") || vNorm.includes("etios");
    const isSuv = vNorm.includes("suv") || vNorm.includes("ertiga");
    const isCrysta = vNorm.includes("crysta");
    const isLuxury = vNorm.includes("luxury") || vNorm.includes("merc") || vNorm.includes("camry");
    const isTraveller = vNorm.includes("traveller") || vNorm.includes("tempo");

    // Base Public Standard Rate
    let base = 1800;
    if (dt.includes("Extra KM")) {
      base = isSedan ? 16 : isSuv ? 20 : isCrysta ? 24 : isLuxury ? 50 : 60;
    } else if (dt.includes("Extra HR")) {
      base = isSedan ? 125 : isSuv ? 175 : isCrysta ? 225 : isLuxury ? 400 : 500;
    } else if (dt.includes("4 Hrs")) {
      base = isSedan ? 1000 : isSuv ? 1400 : isCrysta ? 1800 : isLuxury ? 3500 : 4500;
    } else if (dt.includes("8 Hrs")) {
      base = isSedan ? 1800 : isSuv ? 2400 : isCrysta ? 3000 : isLuxury ? 6000 : 7500;
    } else if (dt.includes("10 Hrs")) {
      base = isSedan ? 2200 : isSuv ? 2900 : isCrysta ? 3600 : isLuxury ? 7200 : 9000;
    } else if (dt.includes("12")) {
      base = isSedan ? 2600 : isSuv ? 3400 : isCrysta ? 4200 : isLuxury ? 8400 : 10500;
    } else if (dt.includes("Airport")) {
      base = isSedan ? 1350 : isSuv ? 1800 : isCrysta ? 2200 : isLuxury ? 4000 : 5000;
    } else if (dt.includes("Outstation")) {
      base = isSedan ? 3600 : isSuv ? 4800 : isCrysta ? 6000 : isLuxury ? 12000 : 15000;
    }

    // Apply contract-specific corporate discount/multiplier if not PUBLIC
    if (contractIdStr !== "PUBLIC") {
      const cId = parseInt(contractIdStr, 10) || 1;
      // Unique multiplier per contract (e.g. 0.88 for Contract 1, 0.92 for Contract 2, 0.85 for Contract 3, etc.)
      const multiplier = 1 - (((cId * 3) % 15) + 5) / 100;
      return Math.round(base * multiplier);
    }

    return base;
  };

  const mapGridDutyTypeToBackend = (dt: string): string => {
    if (dt.includes("4 Hrs")) return "LOCAL_4HR_40KM";
    if (dt.includes("8 Hrs")) return "LOCAL_8HR_80KM";
    if (dt.includes("10 Hrs")) return "LOCAL_10HR_100KM";
    if (dt.includes("12 Hrs")) return "LOCAL_12HR_120KM";
    if (dt.includes("Airport")) return "AIRPORT_TRANSFER";
    if (dt.includes("Outstation")) return "OUTSTATION";
    return "CUSTOM";
  };

  const getDutyTypeDetails = (dt: string): { hours: number; km: number } => {
    if (dt.includes("4 Hrs")) return { hours: 4, km: 40 };
    if (dt.includes("8 Hrs")) return { hours: 8, km: 80 };
    if (dt.includes("10 Hrs")) return { hours: 10, km: 100 };
    if (dt.includes("12 Hrs")) return { hours: 12, km: 120 };
    if (dt.includes("Airport")) return { hours: 4, km: 40 };
    if (dt.includes("Outstation")) return { hours: 24, km: 300 };
    return { hours: 0, km: 0 };
  };

  const loadExcelMatrix = () => {
    const scopeKey = `${excelContractId}_${excelCity}`;
    const currentCityNorm = excelCity.trim().toLowerCase();

    // 1. If we have active unsaved or saved edits in memory for this exact contract/city scope, use them!
    if (contractGrids[scopeKey]) {
      setPivotGrid(contractGrids[scopeKey]);
      return;
    }

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
          if (dt.includes("Extra KM")) {
            const match = cityPkgs.find((p) => p.vehicle_category.toLowerCase() === vNorm);
            newPivotGrid[dt][v] = match?.extra_km_rate ?? getSmartDefaultRate(dt, v, "PUBLIC");
          } else if (dt.includes("Extra HR")) {
            const match = cityPkgs.find((p) => p.vehicle_category.toLowerCase() === vNorm);
            newPivotGrid[dt][v] = match?.extra_hour_rate ?? getSmartDefaultRate(dt, v, "PUBLIC");
          } else {
            const code = mapGridDutyTypeToBackend(dt);
            const match = cityPkgs.find(
              (p) => p.vehicle_category.toLowerCase() === vNorm && p.duty_type === code
            );
            newPivotGrid[dt][v] = match?.base_rate ?? getSmartDefaultRate(dt, v, "PUBLIC");
          }
        });
      });
      setPivotGrid(newPivotGrid);
      setCgstRate(2.5);
      setSgstRate(2.5);
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
          if (dt.includes("Extra KM")) {
            const match = cityRates.find((r) => r.vehicle_category.toLowerCase() === vNorm);
            newPivotGrid[dt][v] = match?.extra_km_rate ?? getSmartDefaultRate(dt, v, excelContractId);
          } else if (dt.includes("Extra HR")) {
            const match = cityRates.find((r) => r.vehicle_category.toLowerCase() === vNorm);
            newPivotGrid[dt][v] = match?.extra_hour_rate ?? getSmartDefaultRate(dt, v, excelContractId);
          } else {
            const code = mapGridDutyTypeToBackend(dt);
            const match = cityRates.find(
              (r) => r.vehicle_category.toLowerCase() === vNorm && r.duty_type === code
            );
            newPivotGrid[dt][v] = match?.base_rate ?? getSmartDefaultRate(dt, v, excelContractId);
          }
        });
      });
      setPivotGrid(newPivotGrid);

      if (contract) {
        setCgstRate(Number(contract.cgst_rate ?? 2.5));
        setSgstRate(Number(contract.sgst_rate ?? 2.5));

        // Load contract specific allowances if defined
        if (contract.allowances && contract.allowances.length > 0) {
          const outstation = contract.allowances.find((a) => a.allowance_type.toUpperCase().includes("OUTSTATION_PER_DAY"))?.amount ?? 300;
          const outstationNight = contract.allowances.find((a) => a.allowance_type.toUpperCase().includes("OVERNIGHT_DRIVER_ALLOWANCE"))?.amount ?? 300;
          const night = contract.allowances.find((a) => a.allowance_type.toUpperCase().includes("NIGHT_ALLOWANCE"))?.amount ?? 250;
          const early = contract.allowances.find((a) => a.allowance_type.toUpperCase().includes("EARLY_START_ALLOWANCE"))?.amount ?? 150;
          const sunday = contract.allowances.find((a) => a.allowance_type.toUpperCase().includes("SUNDAY_ALLOWANCE"))?.amount ?? 200;
          const overtime = contract.allowances.find((a) => a.allowance_type.toUpperCase().includes("OVERTIME_PER_HOUR"))?.amount ?? 125;
          
          setExcelAllowances({
            outstationAllowance: Number(outstation),
            outstationNight: Number(outstationNight),
            nightAllowance: Number(night),
            earlyStart: Number(early),
            sundayAllowance: Number(sunday),
            overtimeHr: Number(overtime),
          });
        } else {
          setExcelAllowances({
            outstationAllowance: 300,
            outstationNight: 300,
            nightAllowance: 250,
            earlyStart: 150,
            sundayAllowance: 200,
            overtimeHr: 125,
          });
        }
      }
    }
  };


  const handleCellChange = (dutyType: string, vehicleCat: string, val: string) => {
    const updatedGrid = { ...pivotGrid };
    if (!updatedGrid[dutyType]) updatedGrid[dutyType] = {};
    updatedGrid[dutyType][vehicleCat] = val;
    setPivotGrid(updatedGrid);

    // Save cell change into persistent contract grid store
    const scopeKey = `${excelContractId}_${excelCity}`;
    setContractGrids({
      ...contractGrids,
      [scopeKey]: updatedGrid,
    });
  };

  const handleAddPivotDutyRow = () => {
    const newRowName = prompt("Enter Custom Duty Type (e.g. 6 Hrs / 60 KMs or Outstation 250Km):");
    if (!newRowName?.trim()) return;
    const name = newRowName.trim();
    setPivotDutyTypes([...pivotDutyTypes, name]);
    const updatedGrid = { ...pivotGrid };
    updatedGrid[name] = {};
    pivotVehicles.forEach((v) => {
      updatedGrid[name][v] = 1500;
    });
    setPivotGrid(updatedGrid);
    setContractGrids({ ...contractGrids, [`${excelContractId}_${excelCity}`]: updatedGrid });
  };

  const handleAddPivotVehicleCol = () => {
    const newColName = prompt("Enter Custom Car / Vehicle Category Name:");
    if (!newColName?.trim()) return;
    const name = newColName.trim();
    setPivotVehicles([...pivotVehicles, name]);
    const updatedGrid = { ...pivotGrid };
    pivotDutyTypes.forEach((dt) => {
      if (!updatedGrid[dt]) updatedGrid[dt] = {};
      updatedGrid[dt][name] = dt.includes("Extra KM") ? 18 : dt.includes("Extra HR") ? 150 : 2000;
    });
    setPivotGrid(updatedGrid);
    setContractGrids({ ...contractGrids, [`${excelContractId}_${excelCity}`]: updatedGrid });
  };

  const handleSavePivotMatrix = async () => {
    try {
      setSavingExcel(true);
      setError(null);
      if (excelContractId === "PUBLIC") {
        const publicBook = rateBooks.find((b) => b.book_type === "PUBLIC");
        if (publicBook) {
          const { updateRatePackage, createRatePackage } = await import("@/lib/api");
          // For each vehicle category
          for (const v of pivotVehicles) {
            const vNorm = v.split("/")[0].trim().toLowerCase();
            const extraKmVal = Number(pivotGrid["Extra KM Rate (₹/km)"]?.[v]) || 0;
            const extraHrVal = Number(pivotGrid["Extra HR Rate (₹/hr)"]?.[v]) || 0;

            for (const dt of pivotDutyTypes) {
              if (dt.includes("Extra KM") || dt.includes("Extra HR")) continue;
              const val = pivotGrid[dt]?.[v];
              if (val !== undefined && val !== "") {
                const code = mapGridDutyTypeToBackend(dt);
                const pkg = publicBook.packages?.find(
                  (p) => p.vehicle_category.toLowerCase() === vNorm && p.duty_type === code
                );
                const details = getDutyTypeDetails(dt);
                const payload = {
                  rate_book: publicBook.id,
                  code: `PKG-PUBLIC-${excelCity.toUpperCase()}-${vNorm.toUpperCase()}-${code}`,
                  vehicle_category: vNorm,
                  duty_type: code,
                  base_rate: val,
                  extra_hour_rate: extraHrVal,
                  extra_km_rate: extraKmVal,
                  included_hours: details.hours,
                  included_km: details.km,
                  name: `${excelCity.charAt(0).toUpperCase() + excelCity.slice(1)} - ${v} (${code})`,
                  city: excelCity.trim().toLowerCase(),
                  cgst_rate: cgstRate,
                  sgst_rate: sgstRate,
                };
                if (pkg && pkg.id) {
                  await updateRatePackage(pkg.id, payload);
                } else {
                  await createRatePackage(payload);
                }
              }
            }
          }
          setSuccess("Public default 2D rate matrix updated successfully!");
        }
      } else {
        const contract = contracts.find((c) => c.id.toString() === excelContractId);
        if (contract) {
          const updatedRates: any[] = [];
          pivotVehicles.forEach((v) => {
            const vNorm = v.split("/")[0].trim().toLowerCase();
            const extraKmVal = Number(pivotGrid["Extra KM Rate (₹/km)"]?.[v]) || 0;
            const extraHrVal = Number(pivotGrid["Extra HR Rate (₹/hr)"]?.[v]) || 0;

            pivotDutyTypes.forEach((dt) => {
              if (dt.includes("Extra KM") || dt.includes("Extra HR")) return;
              const val = pivotGrid[dt]?.[v];
              if (val !== undefined && val !== "") {
                const code = mapGridDutyTypeToBackend(dt);
                const details = getDutyTypeDetails(dt);
                updatedRates.push({
                  city: excelCity.trim().toLowerCase(),
                  vehicle_category: vNorm,
                  duty_type: code,
                  base_rate: val,
                  extra_hour_rate: extraHrVal,
                  extra_km_rate: extraKmVal,
                  included_hours: details.hours,
                  included_km: details.km,
                  outstation_daily_min_km: dt.includes("Outstation") ? 300 : undefined,
                });
              }
            });
          });

          const updatedAllowances = [
            { allowance_type: "OUTSTATION_PER_DAY", amount: excelAllowances.outstationAllowance },
            { allowance_type: "OVERNIGHT_DRIVER_ALLOWANCE", amount: excelAllowances.outstationNight },
            { allowance_type: "NIGHT_ALLOWANCE", amount: excelAllowances.nightAllowance },
            { allowance_type: "EARLY_START_ALLOWANCE", amount: excelAllowances.earlyStart },
            { allowance_type: "SUNDAY_ALLOWANCE", amount: excelAllowances.sundayAllowance },
            { allowance_type: "OVERTIME_PER_HOUR", amount: excelAllowances.overtimeHr },
          ];

          await updateContract(contract.id, {
            rates: updatedRates,
            allowances: updatedAllowances,
            cgst_rate: cgstRate,
            sgst_rate: sgstRate,
          });
          setSuccess(`Contract '${contract.title}' rate card, allowances, and taxes updated successfully for ${excelCity}!`);
        }
      }
      fetchInitialData();
    } catch (err: any) {
      setError(err.message || "Failed to save rate matrix changes.");
    } finally {
      setSavingExcel(false);
    }
  };


  const handleSaveContractModal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modalContract) return;
    try {
      setSavingModal(true);
      setError(null);
      if (modalContract.id) {
        await updateContract(modalContract.id, modalContract);
        setSuccess(`Contract '${modalContract.title}' updated successfully!`);
      } else {
        const created = await createContract(modalContract);
        setSuccess(`Contract '${created.title}' created successfully!`);
        setExcelContractId(created.id.toString());
      }
      setShowContractModal(false);
      setModalContract(null);
      fetchInitialData();
    } catch (err: any) {
      setError(err.message || "Failed to save contract.");
    } finally {
      setSavingModal(false);
    }
  };

  const currentContract = contracts.find((c) => c.id.toString() === excelContractId);

  return (
    <div className="stack" style={{ gap: 20 }}>
      {/* SUCCESS / ERROR ALERTS */}
      {error && (
        <div className="banner danger" style={{ borderRadius: 8, padding: "12px 16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
          <button className="button secondary sm" onClick={() => setError(null)}>
            <X size={14} />
          </button>
        </div>
      )}
      {success && (
        <div className="banner ok" style={{ borderRadius: 8, padding: "12px 16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <CheckCircle2 size={18} />
            <span>{success}</span>
          </div>
          <button className="button secondary sm" onClick={() => setSuccess(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* PAGE TITLE & ACTION BAR */}
      <div className="panel" style={{ padding: "20px 24px", background: "linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%)", border: "1px solid var(--line)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <FileText size={24} style={{ color: "var(--accent)" }} />
              <h1 style={{ margin: 0, fontSize: 22, color: "#fff", fontWeight: 700 }}>
                Corporate Contracts & Rate Matrix
              </h1>
            </div>
            <p style={{ margin: "4px 0 0 0", fontSize: 13, color: "var(--muted)" }}>
              Select any contract and city scope below to inspect, edit, or customize the 2D Excel rate card.
            </p>
          </div>

          <div style={{ display: "flex", gap: 12 }}>
            {isCommercialAdmin && (
              <button
                className="button secondary"
                onClick={() => {
                  setModalContract({
                    title: "",
                    customer: customers[0]?.id || 1,
                    status: "ACTIVE",
                    effective_start: new Date().toISOString().split("T")[0],
                    effective_end: "2027-03-31",
                  });
                  setShowContractModal(true);
                }}
                style={{ gap: 8 }}
              >
                <Plus size={16} /> New Contract
              </button>
            )}
            <button
              className="button primary"
              onClick={handleSavePivotMatrix}
              disabled={savingExcel}
              style={{ gap: 8 }}
            >
              <Save size={16} /> {savingExcel ? "Saving Matrix..." : "Save Rate Changes"}
            </button>
          </div>
        </div>

        {/* SELECTORS BAR (Contract & City) */}
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginTop: 20, paddingTop: 20, borderTop: "1px solid rgba(255,255,255,0.1)" }}>
          <div>
            <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6, fontWeight: 600 }}>
              🏢 SELECT CORPORATE CONTRACT / PRICING SCOPE
            </label>
            <select
              style={{
                width: "100%",
                padding: "12px 16px",
                borderRadius: 8,
                background: "rgba(0,0,0,0.5)",
                border: "1px solid var(--accent)",
                color: "#fff",
                fontSize: 15,
                fontWeight: 600,
              }}
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
            <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6, fontWeight: 600 }}>
              🌆 CITY SCOPE
            </label>
            <select
              style={{
                width: "100%",
                padding: "12px 16px",
                borderRadius: 8,
                background: "rgba(0,0,0,0.5)",
                border: "1px solid var(--line)",
                color: "#fff",
                fontSize: 15,
                fontWeight: 600,
              }}
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
        </div>
      </div>

      {/* ACTIVE CONTRACT HEADER CARD */}
      {excelContractId !== "PUBLIC" && currentContract && (
        <div
          className="panel"
          style={{
            padding: 18,
            background: "rgba(30, 41, 59, 0.7)",
            border: "1px solid rgba(56, 189, 248, 0.3)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <Building2 size={24} style={{ color: "#38bdf8" }} />
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h3 style={{ margin: 0, fontSize: 17, color: "#fff", fontWeight: 700 }}>
                  {currentContract.title}
                </h3>
                <span className="status ok" style={{ fontSize: 11 }}>
                  {currentContract.status}
                </span>
              </div>
              <span style={{ fontSize: 12, color: "var(--muted)", display: "block", marginTop: 2 }}>
                Customer: <strong style={{ color: "#cbd5e1" }}>{currentContract.customer_display_name || `#${currentContract.customer}`}</strong> • Validity:{" "}
                <strong style={{ color: "#cbd5e1" }}>
                  {currentContract.effective_start} to {currentContract.effective_end || "Ongoing"}
                </strong>
              </span>
            </div>
          </div>

          <button
            className="button secondary sm"
            onClick={() => {
              setModalContract(currentContract);
              setShowContractModal(true);
            }}
            style={{ gap: 6 }}
          >
            <Pencil size={14} /> Edit Contract Details
          </button>
        </div>
      )}

      {/* 2D PIVOT EXCEL RATE MATRIX */}
      <div className="panel" style={{ padding: 0, overflowX: "auto", border: "1px solid var(--line)" }}>
        {/* MATRIX HEADER CONTROLS */}
        <div style={{ padding: "14px 18px", background: "rgba(15, 23, 42, 0.9)", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <span style={{ fontSize: 14, color: "#fff", fontWeight: 700 }}>
              📊 Interactive 2D Rate Card Matrix
            </span>
            <span style={{ fontSize: 12, color: "var(--muted)", display: "block", marginTop: 2 }}>
              Active Scope: <strong style={{ color: "#38bdf8" }}>{excelContractId === "PUBLIC" ? "Public Default" : currentContract?.title || `Contract #${excelContractId}`} ({excelCity})</strong> • Layout: <strong style={{ color: "#a7f3d0" }}>{isAxesSwapped ? "Car Types (Rows) × Duty Types (Columns)" : "Duty Types (Rows) × Car Types (Columns)"}</strong>
            </span>
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <button
              className="button secondary sm"
              onClick={() => setIsAxesSwapped(!isAxesSwapped)}
              style={{ gap: 6 }}
            >
              <RefreshCw size={14} /> ⇄ Swap Axes ({isAxesSwapped ? "Show Duty Types on Y-Axis" : "Show Car Types on Y-Axis"})
            </button>
            <button
              className="button secondary sm"
              onClick={isAxesSwapped ? handleAddPivotDutyRow : handleAddPivotVehicleCol}
              style={{ gap: 6 }}
            >
              <Plus size={14} /> {isAxesSwapped ? "Add Duty Column" : "Add Car Column"}
            </button>
            <button
              className="button secondary sm"
              onClick={isAxesSwapped ? handleAddPivotVehicleCol : handleAddPivotDutyRow}
              style={{ gap: 6 }}
            >
              <Plus size={14} /> {isAxesSwapped ? "Add Car Row" : "Add Duty Row"}
            </button>
          </div>
        </div>

        {/* 2D SPREADSHEET TABLE */}
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
              <th style={{ padding: "14px 16px", textAlign: "center", width: 80 }}>Action</th>
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
                  <td style={{ padding: "10px 18px", fontWeight: 700, color: "#38bdf8", fontSize: 13, borderRight: "1px solid var(--line)" }}>
                    🚗 {vehicleCat}
                  </td>

                  {pivotDutyTypes.map((dutyType) => {
                    const isRateHeader = dutyType.includes("Extra KM") || dutyType.includes("Extra HR");
                    const val = pivotGrid[dutyType]?.[vehicleCat] ?? getSmartDefaultRate(dutyType, vehicleCat, excelContractId);
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
                          onChange={(e) => handleCellChange(dutyType, vehicleCat, e.target.value)}
                        />
                      </td>
                    );
                  })}

                  <td style={{ padding: "6px 10px", textAlign: "center" }}>
                    <button
                      className="button secondary sm"
                      style={{ color: "var(--danger)", padding: 4 }}
                      onClick={() => setPivotVehicles(pivotVehicles.filter((v) => v !== vehicleCat))}
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
                    <td style={{ padding: "10px 18px", fontWeight: 700, color: isRateHeader ? "#60a5fa" : "#fff", fontSize: 13, borderRight: "1px solid var(--line)" }}>
                      {dutyType}
                    </td>

                    {pivotVehicles.map((vehicleCat) => {
                      const val = pivotGrid[dutyType]?.[vehicleCat] ?? getSmartDefaultRate(dutyType, vehicleCat, excelContractId);
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
                            onChange={(e) => handleCellChange(dutyType, vehicleCat, e.target.value)}
                          />
                        </td>
                      );
                    })}

                    <td style={{ padding: "6px 10px", textAlign: "center" }}>
                      <button
                        className="button secondary sm"
                        style={{ color: "var(--danger)", padding: 4 }}
                        onClick={() => setPivotDutyTypes(pivotDutyTypes.filter((dt) => dt !== dutyType))}
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
      </div>

      {/* DRIVER ALLOWANCES & STATUTORY TAXES (3-COLUMN GRID LAYOUT) */}
      <div className="panel" style={{ padding: 22, background: "rgba(15, 23, 42, 0.75)", border: "1px solid var(--line)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, borderBottom: "1px solid var(--line)", paddingBottom: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Clock size={18} style={{ color: "var(--accent)" }} />
            <h3 style={{ margin: 0, color: "#fff", fontSize: 16, fontWeight: 700 }}>
              Driver Allowances & Special Duty Slabs ({excelCity})
            </h3>
          </div>
          <span style={{ fontSize: 12, color: "var(--muted)" }}>
            Applies to contract: <strong style={{ color: "#38bdf8" }}>{excelContractId === "PUBLIC" ? "Public Default" : currentContract?.title || `Contract #${excelContractId}`}</strong>
          </span>
        </div>

        {/* 3-COLUMN INPUT CARDS */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 20 }}>
          {/* Card 1 */}
          <div style={{ padding: 14, borderRadius: 8, background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <label style={{ fontSize: 12, color: "#cbd5e1", fontWeight: 600, display: "block", marginBottom: 6 }}>
              🏞️ Outstation Daily Allowance (₹/day)
            </label>
            <input
              type="number"
              style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.6)", border: "1px solid var(--line)", color: "#22c55e", fontWeight: 700, fontSize: 15 }}
              value={excelAllowances.outstationAllowance}
              onChange={(e) => setExcelAllowances({ ...excelAllowances, outstationAllowance: Number(e.target.value) })}
            />
          </div>

          {/* Card 2 */}
          <div style={{ padding: 14, borderRadius: 8, background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <label style={{ fontSize: 12, color: "#cbd5e1", fontWeight: 600, display: "block", marginBottom: 6 }}>
              🌙 Outstation Night Allowance (₹ after 00:00)
            </label>
            <input
              type="number"
              style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.6)", border: "1px solid var(--line)", color: "#22c55e", fontWeight: 700, fontSize: 15 }}
              value={excelAllowances.outstationNight}
              onChange={(e) => setExcelAllowances({ ...excelAllowances, outstationNight: Number(e.target.value) })}
            />
          </div>

          {/* Card 3 */}
          <div style={{ padding: 14, borderRadius: 8, background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <label style={{ fontSize: 12, color: "#cbd5e1", fontWeight: 600, display: "block", marginBottom: 6 }}>
              🌌 City Night Charge (₹ 22:00 - 06:00)
            </label>
            <input
              type="number"
              style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.6)", border: "1px solid var(--line)", color: "#22c55e", fontWeight: 700, fontSize: 15 }}
              value={excelAllowances.nightAllowance}
              onChange={(e) => setExcelAllowances({ ...excelAllowances, nightAllowance: Number(e.target.value) })}
            />
          </div>

          {/* Card 4 */}
          <div style={{ padding: 14, borderRadius: 8, background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <label style={{ fontSize: 12, color: "#cbd5e1", fontWeight: 600, display: "block", marginBottom: 6 }}>
              🌅 Early Start Allowance (₹ before 06:00)
            </label>
            <input
              type="number"
              style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.6)", border: "1px solid var(--line)", color: "#22c55e", fontWeight: 700, fontSize: 15 }}
              value={excelAllowances.earlyStart}
              onChange={(e) => setExcelAllowances({ ...excelAllowances, earlyStart: Number(e.target.value) })}
            />
          </div>

          {/* Card 5 */}
          <div style={{ padding: 14, borderRadius: 8, background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <label style={{ fontSize: 12, color: "#cbd5e1", fontWeight: 600, display: "block", marginBottom: 6 }}>
              🎉 Sunday / Holiday Duty Charge (₹)
            </label>
            <input
              type="number"
              style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.6)", border: "1px solid var(--line)", color: "#22c55e", fontWeight: 700, fontSize: 15 }}
              value={excelAllowances.sundayAllowance}
              onChange={(e) => setExcelAllowances({ ...excelAllowances, sundayAllowance: Number(e.target.value) })}
            />
          </div>

          {/* Card 6 */}
          <div style={{ padding: 14, borderRadius: 8, background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <label style={{ fontSize: 12, color: "#cbd5e1", fontWeight: 600, display: "block", marginBottom: 6 }}>
              ⏱️ Driver Overtime Rate (₹/hr)
            </label>
            <input
              type="number"
              style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.6)", border: "1px solid var(--line)", color: "#22c55e", fontWeight: 700, fontSize: 15 }}
              value={excelAllowances.overtimeHr}
              onChange={(e) => setExcelAllowances({ ...excelAllowances, overtimeHr: Number(e.target.value) })}
            />
          </div>
        </div>

        {/* BOTTOM TAXES & SAVE STRIP */}
        <div style={{ padding: "14px 18px", borderRadius: 8, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>

            <div>
            
            </div>
          </div>

          <button className="button primary" onClick={handleSavePivotMatrix} disabled={savingExcel} style={{ gap: 8 }}>
            <Save size={16} /> {savingExcel ? "Saving Matrix..." : "Save Rate & Allowance Changes"}
          </button>
        </div>
      </div>

      {/* GST and TAXES SECTION */}
      <div className="panel" style={{ padding: 22, background: "rgba(15, 23, 42, 0.75)", border: "1px solid var(--line)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, borderBottom: "1px solid var(--line)", paddingBottom: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Percent size={18} style={{ color: "var(--accent)" }} />
            <h3 style={{ margin: 0, color: "#fff", fontSize: 16, fontWeight: 700 }}>
              GST and TAXES
            </h3>
          </div>
          <span style={{ fontSize: 12, color: "var(--muted)" }}>
            Tax configurations for: <strong style={{ color: "#38bdf8" }}>{excelContractId === "PUBLIC" ? "Public Default" : currentContract?.title || `Contract #${excelContractId}`}</strong>
          </span>
        </div>

        {/* GST Rate Inputs */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 20 }}>
          {/* CGST Input */}
          <div style={{ padding: 14, borderRadius: 8, background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <label style={{ fontSize: 12, color: "#cbd5e1", fontWeight: 600, display: "block", marginBottom: 6 }}>
              🏛️ Central GST (CGST) Rate (%)
            </label>
            <input
              type="number"
              min={0}
              max={100}
              step={0.01}
              style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.6)", border: "1px solid var(--line)", color: "#38bdf8", fontWeight: 700, fontSize: 15 }}
              value={cgstRate}
              onChange={(e) => setCgstRate(Number(e.target.value))}
            />
          </div>

          {/* SGST Input */}
          <div style={{ padding: 14, borderRadius: 8, background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <label style={{ fontSize: 12, color: "#cbd5e1", fontWeight: 600, display: "block", marginBottom: 6 }}>
              🏛️ State GST (SGST) Rate (%)
            </label>
            <input
              type="number"
              min={0}
              max={100}
              step={0.01}
              style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.6)", border: "1px solid var(--line)", color: "#38bdf8", fontWeight: 700, fontSize: 15 }}
              value={sgstRate}
              onChange={(e) => setSgstRate(Number(e.target.value))}
            />
          </div>

          {/* Combined GST Display */}
          <div style={{ padding: 14, borderRadius: 8, background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.08)", display: "flex", flexDirection: "column", justifyContent: "center" }}>
            <label style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600, display: "block", marginBottom: 6 }}>
              📊 Combined Total GST Rate (%)
            </label>
            <span style={{ fontSize: 20, color: "#22c55e", fontWeight: 800 }}>
              {(cgstRate + sgstRate).toFixed(2)}%
            </span>
          </div>
        </div>

        {/* BOTTOM SAVE STRIP */}
        <div style={{ padding: "14px 18px", borderRadius: 8, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <ShieldCheck size={20} style={{ color: "#38bdf8" }} />
            <div>
              <span style={{ fontSize: 13, color: "#fff", fontWeight: 700, display: "block" }}>Statutory GST Billing Breakdown</span>
              <span style={{ fontSize: 12, color: "var(--muted)" }}>
                CGST {cgstRate.toFixed(2)}% + SGST {sgstRate.toFixed(2)}% (Total {(cgstRate + sgstRate).toFixed(2)}% GST Applicable on Invoice Gross Amount)
              </span>
            </div>
          </div>

          <button className="button primary" onClick={handleSavePivotMatrix} disabled={savingExcel} style={{ gap: 8 }}>
            <Save size={16} /> {savingExcel ? "Saving Matrix..." : "Save Rate, Allowance & Tax Changes"}
          </button>
        </div>
      </div>

      {/* CREATE / EDIT CONTRACT MODAL */}
      {showContractModal && modalContract && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
          }}
        >
          <div className="panel" style={{ width: 520, padding: 24, background: "rgba(15, 23, 42, 0.95)", border: "1px solid var(--accent)", borderRadius: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <h3 style={{ margin: 0, fontSize: 18, color: "#fff", fontWeight: 700 }}>
                {modalContract.id ? "Edit Corporate Contract" : "Create New Corporate Contract"}
              </h3>
              <button className="button secondary sm" onClick={() => setShowContractModal(false)}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleSaveContractModal} className="stack" style={{ gap: 16 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Contract Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. CIPLA Corporate Mobility 2026"
                  style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff" }}
                  value={modalContract.title || ""}
                  onChange={(e) => setModalContract({ ...modalContract, title: e.target.value })}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Corporate Customer</label>
                <select
                  style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff" }}
                  value={modalContract.customer || ""}
                  onChange={(e) => setModalContract({ ...modalContract, customer: Number(e.target.value) })}
                >
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.display_name} ({c.code})
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Effective Start Date</label>
                  <input
                    type="date"
                    required
                    style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff" }}
                    value={modalContract.effective_start || ""}
                    onChange={(e) => setModalContract({ ...modalContract, effective_start: e.target.value })}
                  />
                </div>

                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Effective End Date</label>
                  <input
                    type="date"
                    style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff" }}
                    value={modalContract.effective_end || ""}
                    onChange={(e) => setModalContract({ ...modalContract, effective_end: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>CGST Rate (%)</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={0.01}
                    style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff" }}
                    value={modalContract.cgst_rate ?? 2.50}
                    onChange={(e) => setModalContract({ ...modalContract, cgst_rate: Number(e.target.value) })}
                  />
                </div>

                <div>
                  <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>SGST Rate (%)</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={0.01}
                    style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff" }}
                    value={modalContract.sgst_rate ?? 2.50}
                    onChange={(e) => setModalContract({ ...modalContract, sgst_rate: Number(e.target.value) })}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 6 }}>Contract Status</label>
                <select
                  style={{ width: "100%", padding: "10px 12px", borderRadius: 6, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff" }}
                  value={modalContract.status || "ACTIVE"}
                  onChange={(e) => setModalContract({ ...modalContract, status: e.target.value as any })}
                >
                  <option value="ACTIVE">ACTIVE</option>
                  <option value="DRAFT">DRAFT</option>
                  <option value="SUPERSEDED">SUPERSEDED</option>
                  <option value="EXPIRED">EXPIRED</option>
                </select>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 12 }}>
                <button type="button" className="button secondary" onClick={() => setShowContractModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="button primary" disabled={savingModal}>
                  {savingModal ? "Saving Contract..." : "Save Contract"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
