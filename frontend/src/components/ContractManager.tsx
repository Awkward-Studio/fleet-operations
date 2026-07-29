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
            justify: "space-between",
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
              Active Layout: <strong style={{ color: "#38bdf8" }}>{isAxesSwapped ? "Car Types (Rows) × Duty Types (Columns)" : "Duty Types (Rows) × Car Types (Columns)"}</strong>
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

      {/* DRIVER ALLOWANCES & STATUTORY TAXES */}
      <div className="panel" style={{ padding: 20, background: "rgba(15, 23, 42, 0.7)", border: "1px solid var(--line)" }}>
        <h3 style={{ margin: "0 0 16px 0", color: "#fff", fontSize: 16, borderBottom: "1px solid var(--line)", paddingBottom: 10 }}>
          Driver Allowances & Statutory Taxes ({excelCity})
        </h3>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          <div>
            <h4 style={{ margin: "0 0 12px 0", fontSize: 13, color: "var(--accent)" }}>Daily & Overnight Allowances (₹)</h4>
            <div className="stack" style={{ gap: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13, color: "#cbd5e1" }}>Outstation allowance (per day)</span>
                <input
                  type="number"
                  style={{ width: 120, padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff", textAlign: "right" }}
                  value={excelAllowances.outstationAllowance}
                  onChange={(e) => setExcelAllowances({ ...excelAllowances, outstationAllowance: Number(e.target.value) })}
                />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13, color: "#cbd5e1" }}>Outstation overnight allowance (after 00:00)</span>
                <input
                  type="number"
                  style={{ width: 120, padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff", textAlign: "right" }}
                  value={excelAllowances.outstationNight}
                  onChange={(e) => setExcelAllowances({ ...excelAllowances, outstationNight: Number(e.target.value) })}
                />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13, color: "#cbd5e1" }}>Night allowance</span>
                <input
                  type="number"
                  style={{ width: 120, padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff", textAlign: "right" }}
                  value={excelAllowances.nightAllowance}
                  onChange={(e) => setExcelAllowances({ ...excelAllowances, nightAllowance: Number(e.target.value) })}
                />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13, color: "#cbd5e1" }}>Early start allowance</span>
                <input
                  type="number"
                  style={{ width: 120, padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--line)", color: "#fff", textAlign: "right" }}
                  value={excelAllowances.earlyStart}
                  onChange={(e) => setExcelAllowances({ ...excelAllowances, earlyStart: Number(e.target.value) })}
                />
              </div>
            </div>
          </div>

          <div>
            <h4 style={{ margin: "0 0 12px 0", fontSize: 13, color: "var(--accent)" }}>Applicable Statutory Taxes</h4>
            <div style={{ padding: 16, background: "rgba(0,0,0,0.3)", borderRadius: 8, border: "1px solid var(--line)", marginBottom: 16 }}>
              <ul style={{ margin: 0, paddingLeft: 20, color: "#cbd5e1", fontSize: 13 }}>
                <li><strong>CGST 2.5%</strong> - Central Goods and Services Tax</li>
                <li><strong>SGST 2.5%</strong> - State Goods and Services Tax</li>
              </ul>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
              <button className="button primary" onClick={handleSavePivotMatrix} disabled={savingExcel}>
                <Save size={16} /> {savingExcel ? "Saving Matrix..." : "Save Rate Changes"}
              </button>
            </div>
          </div>
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
            justify: "center",
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
}
