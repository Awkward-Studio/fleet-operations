"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  AlertTriangle,
  CalendarClock,
  Car,
  ClipboardCheck,
  LayoutDashboard,
  MapPinned,
  Plus,
  RefreshCw,
  Route,
  ShieldCheck,
  UserCheck,
  Users,
  Wifi,
  Search,
  Filter,
  Camera,
  Loader2,
  CheckCircle2,
  X,
  Bell,
  Sidebar as SidebarIcon,
  ChevronDown,
  MoreVertical,
  Fuel,
  Gauge,
  MapPin,
  ChevronRight,
  Ban,
  Clock,
  CheckCircle,
  Navigation,
  XCircle,
  Pencil,
  Trash2,
  UserPlus,
  KeyRound,
  Building2,
  FileText,
  Receipt,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState, useRef } from "react";
import { useAuth } from "@/lib/AuthContext";
import { AuthGuard } from "@/components/AuthGuard";
import dynamic from "next/dynamic";
import CustomerManager from "./CustomerManager";
import ContractManager from "./ContractManager";
import BillingManager from "./BillingManager";
import FuelMileageManager from "./FuelMileageManager";

const MapComponent = dynamic(() => import("./MapComponent"), { ssr: false });

import {
  Availability,
  Driver,
  Summary,
  Trip,
  Vehicle,
  assignTrip,
  createTrip,
  deleteTrip,
  createVehicle,
  updateVehicle,
  deleteVehicle,
  createDriver,
  updateDriver,
  deleteDriver,
  getAvailability,
  getDrivers,
  getSummary,
  getTrips,
  getVehicles,
  transitionTrip,
  UploadedAsset,
  CorporateCustomer,
  PricingQuote,
  getCustomers,
  getPricingQuote
} from "@/lib/api";
import { DocumentUpload } from "@/components/DocumentUpload";

type Role = "admin" | "dispatcher" | "accountant";
export type ConsoleSection = "dashboard" | "trips" | "create-trip" | "customers" | "contracts" | "billing" | "fuel" | "vehicles" | "drivers" | "tracking" | "availability" | "compliance" | "ota" | "rentals";

const navItems = [
  { href: "/", section: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/trips", section: "trips", label: "Trips", icon: Route },
  { href: "/rentals", section: "rentals", label: "Rentals", icon: KeyRound },
  { href: "/create-trip", section: "create-trip", label: "Create Trip", icon: Plus },
  { href: "/customers", section: "customers", label: "Customers", icon: Building2 },
  { href: "/contracts", section: "contracts", label: "Contracts", icon: FileText },
  { href: "/billing", section: "billing", label: "Fleet Billing", icon: Receipt },
  { href: "/fuel", section: "fuel", label: "Fuel & Mileage", icon: Fuel },
  { href: "/vehicles", section: "vehicles", label: "Vehicles", icon: Car },
  { href: "/drivers", section: "drivers", label: "Drivers", icon: Users },
  { href: "/tracking", section: "tracking", label: "Tracking", icon: MapPinned },
  { href: "/availability", section: "availability", label: "Availability", icon: CalendarClock },
  { href: "/compliance", section: "compliance", label: "Compliance", icon: ShieldCheck },
  { href: "/ota", section: "ota", label: "OTA Bidding", icon: Wifi }
] as const;

const tripTransitions = ["en_route_pickup", "active", "completed", "cancelled"];

export function FleetConsole({ section }: { section: ConsoleSection }) {
  const { user, logout } = useAuth();
  const [profileOpen, setProfileOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const [role, setRole] = useState<Role>("dispatcher");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [availability, setAvailability] = useState<Availability[]>([]);
  const [selectedTrip, setSelectedTrip] = useState<number | null>(null);
  const [selectedVehicle, setSelectedVehicle] = useState<number | null>(null);
  const [selectedDriver, setSelectedDriver] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Search & Filter States
  const [vehicleSearch, setVehicleSearch] = useState("");
  const [vehicleStatusFilter, setVehicleStatusFilter] = useState("all");

  const [driverSearch, setDriverSearch] = useState("");
  const [driverStatusFilter, setDriverStatusFilter] = useState("all");

  const [tripSearch, setTripSearch] = useState("");
  const [tripStatusFilter, setTripStatusFilter] = useState("all");

  // Advanced Trips Filters
  const [tripCityFilter, setTripCityFilter] = useState("all");
  const [tripDriverFilter, setTripDriverFilter] = useState("all");
  const [tripVehicleFilter, setTripVehicleFilter] = useState("all");
  const [tripOtaFilter, setTripOtaFilter] = useState("all");
  const [tripSortFilter, setTripSortFilter] = useState("latest");

  // Add & Edit Vehicle modal state
  const [isAddingVehicle, setIsAddingVehicle] = useState(false);
  const [editingVehicle, setEditingVehicle] = useState<Vehicle | null>(null);

  // Add & Edit Driver modal state
  const [isAddingDriver, setIsAddingDriver] = useState(false);
  const [editingDriver, setEditingDriver] = useState<Driver | null>(null);

  const unassignedTrips = useMemo(() => trips.filter((trip) => trip.status === "requested"), [trips]);
  const activeTrips = useMemo(
    () => trips.filter((trip) => ["assigned", "en_route_pickup", "active"].includes(trip.status)),
    [trips]
  );
  const availableDrivers = useMemo(
    () => drivers.filter((driver) => ["available", "assigned"].includes(driver.status)),
    [drivers]
  );
  const assignableVehicles = useMemo(
    () => vehicles.filter((vehicle) => vehicle.status === "idle" && vehicle.is_compliant),
    [vehicles]
  );
  const complianceVehicles = useMemo(
    () => vehicles.filter((vehicle) => vehicle.compliance_blockers.length > 0),
    [vehicles]
  );

  // Dynamic filter lists for Trips Kanban Board
  const tripCities = useMemo(() => {
    const citiesSet = new Set<string>();
    trips.forEach((t) => {
      if (t.pickup_city) citiesSet.add(t.pickup_city);
      if (t.drop_city) citiesSet.add(t.drop_city);
    });
    return Array.from(citiesSet).sort();
  }, [trips]);

  const tripDrivers = useMemo(() => {
    const driversSet = new Set<string>();
    trips.forEach((t) => {
      if (t.driver?.name) driversSet.add(t.driver.name);
    });
    return Array.from(driversSet).sort();
  }, [trips]);

  const tripVehicles = useMemo(() => {
    const vehiclesSet = new Set<string>();
    trips.forEach((t) => {
      if (t.vehicle?.registration_number) vehiclesSet.add(t.vehicle.registration_number);
    });
    return Array.from(vehiclesSet).sort();
  }, [trips]);

  const tripOtaSources = useMemo(() => {
    const otaSet = new Set<string>();
    trips.forEach((t) => {
      if (t.ota_source) otaSet.add(t.ota_source);
    });
    return Array.from(otaSet).sort();
  }, [trips]);

  // Filter lists based on Search & Filter parameters
  const filteredVehicles = useMemo(() => {
    return vehicles.filter((v) => {
      const matchesSearch =
        vehicleSearch === "" ||
        v.registration_number.toLowerCase().includes(vehicleSearch.toLowerCase()) ||
        v.make.toLowerCase().includes(vehicleSearch.toLowerCase()) ||
        v.model.toLowerCase().includes(vehicleSearch.toLowerCase()) ||
        v.current_city.toLowerCase().includes(vehicleSearch.toLowerCase());
      const matchesStatus =
        vehicleStatusFilter === "all" || v.status === vehicleStatusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [vehicles, vehicleSearch, vehicleStatusFilter]);

  const filteredDrivers = useMemo(() => {
    return drivers.filter((d) => {
      const matchesSearch =
        driverSearch === "" ||
        d.name.toLowerCase().includes(driverSearch.toLowerCase()) ||
        d.phone.toLowerCase().includes(driverSearch.toLowerCase()) ||
        d.license_number.toLowerCase().includes(driverSearch.toLowerCase()) ||
        d.home_base.toLowerCase().includes(driverSearch.toLowerCase());
      const matchesStatus =
        driverStatusFilter === "all" || d.status === driverStatusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [drivers, driverSearch, driverStatusFilter]);

  const filteredTrips = useMemo(() => {
    let result = trips.filter((t) => {
      const matchesSearch =
        tripSearch === "" ||
        t.customer_name.toLowerCase().includes(tripSearch.toLowerCase()) ||
        t.pickup_city.toLowerCase().includes(tripSearch.toLowerCase()) ||
        t.drop_city.toLowerCase().includes(tripSearch.toLowerCase()) ||
        (t.ota_source && t.ota_source.toLowerCase().includes(tripSearch.toLowerCase())) ||
        (t.driver?.name && t.driver.name.toLowerCase().includes(tripSearch.toLowerCase())) ||
        (t.vehicle?.registration_number && t.vehicle.registration_number.toLowerCase().includes(tripSearch.toLowerCase()));

      const matchesStatus =
        tripStatusFilter === "all" || t.status === tripStatusFilter;

      const matchesCity =
        tripCityFilter === "all" ||
        t.pickup_city === tripCityFilter ||
        t.drop_city === tripCityFilter;

      const matchesDriver =
        tripDriverFilter === "all" ||
        (t.driver && t.driver.name === tripDriverFilter);

      const matchesVehicle =
        tripVehicleFilter === "all" ||
        (t.vehicle && t.vehicle.registration_number === tripVehicleFilter);

      const matchesOta =
        tripOtaFilter === "all" ||
        t.ota_source === tripOtaFilter;

      return matchesSearch && matchesStatus && matchesCity && matchesDriver && matchesVehicle && matchesOta;
    });

    // Apply Sorting
    return [...result].sort((a, b) => {
      if (tripSortFilter === "earliest") {
        return new Date(a.pickup_at).getTime() - new Date(b.pickup_at).getTime();
      } else if (tripSortFilter === "fare_desc") {
        return parseFloat(b.fare_amount || "0") - parseFloat(a.fare_amount || "0");
      } else if (tripSortFilter === "distance_desc") {
        return parseFloat((b.distance_km || 0).toString()) - parseFloat((a.distance_km || 0).toString());
      } else {
        // default: latest
        return new Date(b.pickup_at).getTime() - new Date(a.pickup_at).getTime();
      }
    });
  }, [trips, tripSearch, tripStatusFilter, tripCityFilter, tripDriverFilter, tripVehicleFilter, tripOtaFilter, tripSortFilter]);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, vehicleData, driverData, tripData, availabilityData] = await Promise.all([
        getSummary(),
        getVehicles(),
        getDrivers(),
        getTrips(),
        getAvailability()
      ]);
      setSummary(summaryData);
      setVehicles(vehicleData);
      setDrivers(driverData);
      setTrips(tripData);
      setAvailability(availabilityData);
      setSelectedTrip(tripData.find((trip) => trip.status === "requested")?.id ?? null);
      setSelectedVehicle(vehicleData.find((vehicle) => vehicle.status === "idle" && vehicle.is_compliant)?.id ?? null);
      setSelectedDriver(driverData.find((driver) => driver.status === "available")?.id ?? null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load fleet data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleCreateTrip(payload: any, onSuccess: () => void) {
    try {
      await createTrip(payload);
      onSuccess();
      await loadData();
      setSuccessMsg("Trip created successfully!");
      setTimeout(() => setSuccessMsg(null), 4000);
      router.push("/trips");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create trip.");
    }
  }

  async function handleCreateVehicleSubmit(payload: Parameters<typeof createVehicle>[0]) {
    try {
      await createVehicle(payload);
      setIsAddingVehicle(false);
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create vehicle.");
    }
  }

  async function handleUpdateVehicleSubmit(id: number, payload: Parameters<typeof updateVehicle>[1]) {
    try {
      await updateVehicle(id, payload);
      setEditingVehicle(null);
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update vehicle.");
    }
  }

  async function handleDeleteVehicle(id: number) {
    if (!confirm("Are you sure you want to delete this vehicle?")) return;
    try {
      await deleteVehicle(id);
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete vehicle.");
    }
  }

  async function handleCreateDriverSubmit(payload: Parameters<typeof createDriver>[0]) {
    try {
      await createDriver(payload);
      setIsAddingDriver(false);
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create driver.");
    }
  }

  async function handleUpdateDriverSubmit(id: number, payload: Parameters<typeof updateDriver>[1]) {
    try {
      await updateDriver(id, payload);
      setEditingDriver(null);
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update driver.");
    }
  }

  async function handleDeleteDriver(id: number) {
    if (!confirm("Are you sure you want to delete this driver?")) return;
    try {
      await deleteDriver(id);
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete driver.");
    }
  }

  async function handleAssignTrip() {
    if (!selectedTrip || !selectedVehicle || !selectedDriver) {
      setError("Select a trip, vehicle, and driver before assigning.");
      return;
    }

    try {
      await assignTrip(selectedTrip, selectedVehicle, selectedDriver);
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to assign trip.");
    }
  }

  async function handleTransition(tripId: number, status: string) {
    try {
      await transitionTrip(tripId, status);
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update trip status.");
    }
  }

  async function handleDeleteTrip(tripId: number) {
    if (!confirm("Are you sure you want to delete this trip?")) return;
    try {
      await deleteTrip(tripId);
      await loadData();
      setSuccessMsg("Trip deleted successfully!");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete trip.");
    }
  }

  return (
    <AuthGuard>
      <div className="console-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">
            <Route size={20} />
          </span>
          <div>
            <strong>Index Fleet</strong>
            <span>Operations Console</span>
          </div>
        </div>
        <nav className="sidebar-nav" aria-label="Fleet console navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link className={active ? "active" : ""} href={item.href} key={item.href}>
                <Icon size={17} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div style={{ marginTop: "auto", position: "relative" }}>
          <div 
            onClick={() => setProfileOpen(!profileOpen)}
            style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: 12, border: "1px solid var(--line)", cursor: "pointer" }}
          >
            <div style={{ width: 32, height: 32, borderRadius: "50%", background: "linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%)", display: "flex", alignItems: "center", fontSize: 13, fontWeight: "bold", color: "#fff", justifyContent: "center" }}>
              {(user?.first_name?.[0] || user?.username?.[0] || "U").toUpperCase()}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <strong style={{ display: "block", fontSize: 13, color: "#fff", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {user?.first_name ? `${user.first_name} ${user.last_name}` : user?.username}
              </strong>
              <span style={{ display: "block", fontSize: 11, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {user?.email}
              </span>
            </div>
            <ChevronDown size={14} style={{ color: "var(--muted)" }} />
          </div>
          
          {profileOpen && (
            <div style={{
              position: "absolute",
              bottom: "100%",
              left: 0,
              right: 0,
              marginBottom: 8,
              background: "var(--panel-strong)",
              border: "1px solid var(--line)",
              borderRadius: 8,
              padding: 4,
              boxShadow: "0 -4px 15px rgba(0,0,0,0.3)",
              zIndex: 1000
            }}>
              <button 
                onClick={() => {
                  setProfileOpen(false);
                  logout();
                }}
                style={{
                  width: "100%",
                  textAlign: "left",
                  background: "transparent",
                  border: 0,
                  color: "var(--danger)",
                  padding: "10px 12px",
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: "pointer",
                  borderRadius: 6,
                  display: "flex",
                  alignItems: "center",
                  gap: 8
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = "rgba(239, 68, 68, 0.08)"}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            {section === "dashboard" ? (
              <>
                <h1>Welcome back, {user?.first_name || user?.username || "Guest"} 👋</h1>
                <p>Here's what's happening with your fleet today.</p>
              </>
            ) : (
              <>
                <h1>{pageTitle(section)}</h1>
                <p>{pageSubtitle(section)}</p>
              </>
            )}
          </div>
          <div className="topbar-actions" style={{ gap: 20 }}>
            <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
              <Search size={16} style={{ position: "absolute", left: 12, color: "var(--muted)" }} />
              <input 
                type="text" 
                placeholder="Search anything..." 
                style={{ 
                  background: "rgba(255,255,255,0.05)", 
                  border: "1px solid var(--line)", 
                  borderRadius: 8, 
                  padding: "8px 12px 8px 36px", 
                  color: "#fff",
                  fontSize: 13,
                  width: 240,
                  outline: "none"
                }} 
              />
              <div style={{ position: "absolute", right: 8, display: "flex", gap: 4 }}>
                <kbd style={{ background: "rgba(255,255,255,0.1)", color: "var(--muted)", padding: "2px 6px", borderRadius: 4, fontSize: 10, fontFamily: "monospace" }}>⌘</kbd>
                <kbd style={{ background: "rgba(255,255,255,0.1)", color: "var(--muted)", padding: "2px 6px", borderRadius: 4, fontSize: 10, fontFamily: "monospace" }}>K</kbd>
              </div>
            </div>
            
            <button style={{ background: "transparent", border: 0, color: "var(--muted)", cursor: "pointer", position: "relative" }}>
              <Bell size={18} />
              <span style={{ position: "absolute", top: -2, right: -2, width: 8, height: 8, background: "var(--danger)", borderRadius: "50%", border: "2px solid var(--background)" }}></span>
            </button>

            <div className="role-select" style={{ background: "transparent", border: 0, gap: 12 }}>
              <UserCheck size={18} style={{ color: "var(--muted)" }} />
              <select value={role} onChange={(event) => setRole(event.target.value as Role)} aria-label="Dashboard role" style={{ background: "rgba(255,255,255,0.05)", border: "1px solid var(--line)", borderRadius: 6, padding: "6px 10px" }}>
                <option value="dispatcher">Dispatcher</option>
                <option value="admin">Admin</option>
                <option value="accountant">Accountant</option>
              </select>
            </div>
          </div>
        </header>

        <main className="main">
          {error ? <div className="error">{error}</div> : null}
          {successMsg && (
            <div style={{
              position: "fixed", bottom: 24, right: 24, background: "var(--ok)", color: "#fff", 
              padding: "14px 20px", borderRadius: 8, boxShadow: "var(--card-shadow)", zIndex: 9999,
              display: "flex", alignItems: "center", gap: 10, fontWeight: 500, fontSize: 14,
              animation: "fadeInUp 0.3s ease-out"
            }}>
              <CheckCircle2 size={20} />
              {successMsg}
            </div>
          )}
          {loading ? <div className="notice">Loading fleet data from Django API...</div> : null}

          {section === "customers" ? <CustomerManager /> : null}
          {section === "contracts" ? <ContractManager /> : null}
          {section === "billing" ? <BillingManager /> : null}
          {section === "fuel" ? <FuelMileageManager /> : null}

          {section === "dashboard" ? (
            <DashboardView
              summary={summary}
              activeTrips={activeTrips}
              vehicles={vehicles}
              availability={availability}
              complianceVehicles={complianceVehicles}
            />
          ) : null}

          {section === "trips" ? (
            <>
              <section className="metrics" style={{ marginBottom: 24, gridTemplateColumns: "repeat(5, minmax(0, 1fr))" }}>
                <Metric 
                  icon={<Car size={16} />} 
                  label="TOTAL TRIPS" 
                  value={summary?.trips.today ?? trips.length} 
                  total="This month" 
                  trend="18.2%" 
                  trendUp={true} 
                  color="#3b82f6" 
                />
                <Metric 
                  icon={<Navigation size={16} />} 
                  label="EN ROUTE PICKUP" 
                  value={trips.filter((t) => t.status === "en_route_pickup").length} 
                  total="In progress" 
                  trend="Live"
                  trendUp={true}
                  color="#8b5cf6" 
                />
                <Metric 
                  icon={<RefreshCw size={16} />} 
                  label="ACTIVE" 
                  value={trips.filter((t) => t.status === "active").length} 
                  total="On going" 
                  trend="Live" 
                  trendUp={true} 
                  color="#3b82f6" 
                />
                <Metric 
                  icon={<CheckCircle size={16} />} 
                  label="COMPLETED" 
                  value={trips.filter((t) => t.status === "completed").length} 
                  total="This month" 
                  trend="25.6%" 
                  trendUp={true} 
                  color="#10b981" 
                />
                <Metric 
                  icon={<Ban size={16} />} 
                  label="CANCELLED" 
                  value={trips.filter((t) => t.status === "cancelled").length} 
                  total="This month" 
                  trend="12.5%" 
                  trendUp={false} 
                  color="#ef4444" 
                />
              </section>
              <div className="search-filter-bar" style={{ background: "transparent", border: 0, boxShadow: "none", padding: 0, marginBottom: 24, gap: 12 }}>
                <div className="search-input-wrapper">
                  <Search size={18} className="search-icon" />
                  <input
                    type="text"
                    placeholder="Search by customer, trip, vehicle, driver, city..."
                    value={tripSearch}
                    onChange={(e) => setTripSearch(e.target.value)}
                  />
                </div>
                
                <div className="filter-select-wrapper">
                  <Filter size={14} style={{ color: "var(--muted)" }} />
                  <select
                    value={tripCityFilter}
                    onChange={(e) => setTripCityFilter(e.target.value)}
                    aria-label="Filter by City"
                  >
                    <option value="all">All Cities</option>
                    {tripCities.map((city) => (
                      <option key={city} value={city}>{city}</option>
                    ))}
                  </select>
                </div>

                <div className="filter-select-wrapper">
                  <select
                    value={tripDriverFilter}
                    onChange={(e) => setTripDriverFilter(e.target.value)}
                    aria-label="Filter by Driver"
                  >
                    <option value="all">All Drivers</option>
                    {tripDrivers.map((driver) => (
                      <option key={driver} value={driver}>{driver}</option>
                    ))}
                  </select>
                </div>

                <div className="filter-select-wrapper">
                  <select
                    value={tripVehicleFilter}
                    onChange={(e) => setTripVehicleFilter(e.target.value)}
                    aria-label="Filter by Vehicle"
                  >
                    <option value="all">All Vehicles</option>
                    {tripVehicles.map((reg) => (
                      <option key={reg} value={reg}>{reg}</option>
                    ))}
                  </select>
                </div>

                <div className="filter-select-wrapper">
                  <select
                    value={tripOtaFilter}
                    onChange={(e) => setTripOtaFilter(e.target.value)}
                    aria-label="Filter by OTA Source"
                  >
                    <option value="all">All Trips</option>
                    {tripOtaSources.map((ota) => (
                      <option key={ota} value={ota}>{ota}</option>
                    ))}
                  </select>
                </div>

                <div className="filter-select-wrapper">
                  <select
                    value={tripSortFilter}
                    onChange={(e) => setTripSortFilter(e.target.value)}
                    aria-label="Sort Order"
                  >
                    <option value="latest">Sort: Latest</option>
                    <option value="earliest">Sort: Earliest</option>
                    <option value="fare_desc">Sort: Fare (High to Low)</option>
                    <option value="distance_desc">Sort: Distance (High to Low)</option>
                  </select>
                </div>
              </div>
              <TripsView
                role={role}
                trips={filteredTrips}
                onTransition={handleTransition}
                setError={setError}
                unassignedTrips={unassignedTrips}
                assignableVehicles={assignableVehicles}
                availableDrivers={availableDrivers}
                selectedTrip={selectedTrip}
                selectedVehicle={selectedVehicle}
                selectedDriver={selectedDriver}
                onTripChange={setSelectedTrip}
                onVehicleChange={setSelectedVehicle}
                onDriverChange={setSelectedDriver}
                onAssign={handleAssignTrip}
                onDelete={handleDeleteTrip}
              />
            </>
          ) : null}

          {section === "create-trip" ? (
            <CreateTripView
              role={role}
              onCreateTrip={handleCreateTrip}
            />
          ) : null}

          {section === "vehicles" ? (
            <>
              <div className="search-filter-bar">
                <div className="search-input-wrapper">
                  <Search size={18} className="search-icon" />
                  <input
                    type="text"
                    placeholder="Search by registration number, make, model or current city..."
                    value={vehicleSearch}
                    onChange={(e) => setVehicleSearch(e.target.value)}
                  />
                </div>
                <div className="filter-select-wrapper">
                  <Filter size={16} style={{ marginRight: 4, color: "var(--muted)" }} />
                  <select
                    value={vehicleStatusFilter}
                    onChange={(e) => setVehicleStatusFilter(e.target.value)}
                  >
                    <option value="all">All Statuses</option>
                    <option value="idle">Idle</option>
                    <option value="en_route_pickup">En route to pickup</option>
                    <option value="active_trip">Active trip</option>
                    <option value="maintenance">Maintenance</option>
                    <option value="offline">Offline</option>
                  </select>
                </div>
              </div>
              <VehiclesView
                vehicles={filteredVehicles}
                availability={availability}
                trips={trips}
                onAddClick={() => setIsAddingVehicle(true)}
                onEditClick={(v) => setEditingVehicle(v)}
                onDeleteClick={handleDeleteVehicle}
              />
            </>
          ) : null}

          {section === "drivers" ? (
            <>
              <div className="search-filter-bar">
                <div className="search-input-wrapper">
                  <Search size={18} className="search-icon" />
                  <input
                    type="text"
                    placeholder="Search by name, phone, license, base city..."
                    value={driverSearch}
                    onChange={(e) => setDriverSearch(e.target.value)}
                  />
                </div>
                <div className="filter-select-wrapper">
                  <Filter size={16} style={{ marginRight: 4, color: "var(--muted)" }} />
                  <select
                    value={driverStatusFilter}
                    onChange={(e) => setDriverStatusFilter(e.target.value)}
                  >
                    <option value="all">All Statuses</option>
                    <option value="available">Available</option>
                    <option value="assigned">Assigned</option>
                    <option value="on_trip">On trip</option>
                    <option value="off_duty">Off duty</option>
                    <option value="suspended">Suspended</option>
                  </select>
                </div>
              </div>
              <DriversView 
                drivers={filteredDrivers} 
                trips={trips} 
                onAddClick={() => setIsAddingDriver(true)}
                onEditClick={(d) => setEditingDriver(d)}
                onDeleteClick={handleDeleteDriver}
              />
            </>
          ) : null}

          {section === "tracking" ? <TrackingView vehicles={vehicles} activeTrips={activeTrips} availability={availability} /> : null}
          {section === "availability" ? <AvailabilityView availability={availability} vehicles={vehicles} /> : null}
          {section === "compliance" ? <ComplianceView vehicles={vehicles} /> : null}
          {section === "ota" ? <OtaView availability={availability} vehicles={vehicles} unassignedTrips={unassignedTrips} /> : null}
        </main>
      </div>

      {/* Add / Edit Vehicle Modal Overlay */}
      {(isAddingVehicle || editingVehicle) && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>{editingVehicle ? "Edit Vehicle" : "Add New Vehicle"}</h3>
              <button className="modal-close-btn" onClick={() => { setIsAddingVehicle(false); setEditingVehicle(null); }} aria-label="Close modal">
                <X size={20} />
              </button>
            </div>
            <div className="modal-body">
              <AddVehicleForm
                drivers={drivers}
                initialData={editingVehicle}
                onSubmit={(payload) => editingVehicle ? handleUpdateVehicleSubmit(editingVehicle.id, payload) : handleCreateVehicleSubmit(payload)}
                onCancel={() => { setIsAddingVehicle(false); setEditingVehicle(null); }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Add / Edit Driver Modal Overlay */}
      {(isAddingDriver || editingDriver) && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>{editingDriver ? "Edit Driver" : "Add New Driver"}</h3>
              <button className="modal-close-btn" onClick={() => { setIsAddingDriver(false); setEditingDriver(null); }} aria-label="Close modal">
                <X size={20} />
              </button>
            </div>
            <div className="modal-body">
              <DriverForm
                initialData={editingDriver}
                onSubmit={(payload) => editingDriver ? handleUpdateDriverSubmit(editingDriver.id, payload) : handleCreateDriverSubmit(payload)}
                onCancel={() => { setIsAddingDriver(false); setEditingDriver(null); }}
              />
            </div>
          </div>
        </div>
      )}
      </div>
    </AuthGuard>
  );
}

function DashboardView({
  summary,
  activeTrips,
  vehicles,
  availability,
  complianceVehicles
}: {
  summary: Summary | null;
  activeTrips: Trip[];
  vehicles: Vehicle[];
  availability: Availability[];
  complianceVehicles: Vehicle[];
}) {
  return (
    <>
      <section className="metrics">
        <Metric 
          icon={<Car size={16} />} 
          label="IDLE VEHICLES" 
          value={summary?.vehicles.idle ?? 3} 
          total="of 18 total" 
          trend="16.7%" 
          trendUp={true} 
          color="#3b82f6" 
        />
        <Metric 
          icon={<UserCheck size={16} />} 
          label="AVAILABLE DRIVERS" 
          value={summary?.drivers.available ?? 3} 
          total="of 12 total" 
          trend="25.0%" 
          trendUp={true} 
          color="#10b981" 
        />
        <Metric 
          icon={<CalendarClock size={16} />} 
          label="UNASSIGNED TRIPS" 
          value={summary?.trips.unassigned ?? 2} 
          total="Needs attention" 
          trend="100%" 
          trendUp={false} 
          color="#f59e0b" 
        />
        <Metric 
          icon={<ShieldCheck size={16} />} 
          label="COMPLIANCE ALERTS" 
          value={summary?.compliance_alerts ?? 1} 
          total="Requires action" 
          trend="100%" 
          trendUp={false} 
          color="#ef4444" 
        />
      </section>

      <section className="grid">
        <Panel title="Live Operations">
          <div className="operation-board">
            {vehicles.slice(0, 9).map((vehicle) => {
              const trip = activeTrips.find((item) => item.vehicle?.id === vehicle.id);
              return (
                <div className="vehicle-tile" key={vehicle.id} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Car size={16} style={{ color: "var(--muted)" }} />
                      <strong>{vehicle.registration_number}</strong>
                    </div>
                    <MoreVertical size={16} style={{ color: "var(--muted)", cursor: "pointer" }} />
                  </div>
                  <div>
                    <span style={{ fontSize: 13 }}>{vehicle.make} {vehicle.model}</span>
                    <div style={{ marginTop: 12, marginBottom: 8 }}>
                      <Status value={vehicle.status} />
                    </div>
                    <p>{trip ? `${trip.pickup_city} to ${trip.drop_city}` : `Standing by in ${vehicle.current_city}`}</p>
                  </div>
                  <div style={{ display: "flex", gap: 24, marginTop: "auto", paddingTop: 16, borderTop: "1px solid var(--line)" }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <Fuel size={16} style={{ color: "var(--muted)" }} />
                      <div>
                        <strong style={{ fontSize: 13, display: "block" }}>{Math.floor(Math.random() * 60 + 20)}%</strong>
                        <span style={{ fontSize: 11, color: "var(--muted)" }}>Fuel</span>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <Gauge size={16} style={{ color: "var(--muted)" }} />
                      <div>
                        <strong style={{ fontSize: 13, display: "block" }}>{vehicle.odometer_km.toLocaleString()} km</strong>
                        <span style={{ fontSize: 11, color: "var(--muted)" }}>Odometer</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>

        <Panel title="Next Availability">
          <div className="stack">
            {availability.slice(0, 5).map((item) => (
              <AvailabilityItem item={item} key={item.vehicle_id} />
            ))}
          </div>
        </Panel>
      </section>

      <section className="grid">
        <Panel title="Compliance Watch">
          {complianceVehicles.length ? (
            <div className="stack">
              {complianceVehicles.map((vehicle) => (
                <div className="alert-row" key={vehicle.id} style={{ display: "flex", gap: 16, alignItems: "center", padding: "16px 20px", background: "rgba(245, 158, 11, 0.05)", border: "1px solid rgba(245, 158, 11, 0.2)", borderRadius: 8 }}>
                  <AlertTriangle size={20} style={{ color: "var(--warn)" }} />
                  <span style={{ color: "#fff", fontWeight: 700 }}>{vehicle.registration_number}</span>
                  <div style={{ flex: 1 }}>
                    <strong style={{ color: "var(--warn)", display: "block", fontSize: 13, marginBottom: 4 }}>permit expires soon</strong>
                    <span style={{ color: "var(--muted)", fontSize: 12 }}>{vehicle.compliance_blockers.join(" • ")}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No compliance alerts in the current fleet." />
          )}
        </Panel>
        <Panel title="Dispatch Queue">
          <div className="stack">
            {activeTrips.length ? activeTrips.slice(0, 6).map((trip) => <TripSummary trip={trip} key={trip.id} />) : <EmptyState message="No active trips right now." />}
          </div>
        </Panel>
      </section>
    </>
  );
}

function TripsView(props: {
  role: Role;
  trips: Trip[];
  onTransition: (tripId: number, status: string) => void;
  setError?: (msg: string | null) => void;
  unassignedTrips?: Trip[];
  assignableVehicles?: Vehicle[];
  availableDrivers?: Driver[];
  selectedTrip?: number | null;
  selectedVehicle?: number | null;
  selectedDriver?: number | null;
  onTripChange?: (value: number) => void;
  onVehicleChange?: (value: number) => void;
  onDriverChange?: (value: number) => void;
  onAssign?: () => void;
  onDelete?: (tripId: number) => void;
}) {
  const [activeDropzone, setActiveDropzone] = useState<string | null>(null);
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);

  // Close menus on click outside
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest(".kanban-card-actions")) return;
      setOpenMenuId(null);
    };
    document.addEventListener("click", handleOutsideClick);
    return () => document.removeEventListener("click", handleOutsideClick);
  }, []);

  // Columns specification
  const columns = [
    { key: "assigned", title: "UPDATE", highlightClass: "column-update" },
    { key: "en_route_pickup", title: "EN ROUTE PICKUP", highlightClass: "column-en_route_pickup" },
    { key: "active", title: "ACTIVE", highlightClass: "column-active" },
    { key: "completed", title: "COMPLETED", highlightClass: "column-completed" },
    { key: "cancelled", title: "CANCELLED", highlightClass: "column-cancelled" }
  ];

  // Group trips by column
  const columnTrips = useMemo(() => {
    const groups: Record<string, Trip[]> = {
      assigned: [],
      en_route_pickup: [],
      active: [],
      completed: [],
      cancelled: []
    };

    props.trips.forEach((trip) => {
      if (trip.status === "requested" || trip.status === "assigned") {
        groups.assigned.push(trip);
      } else if (groups[trip.status]) {
        groups[trip.status].push(trip);
      }
    });

    return groups;
  }, [props.trips]);

  // Drag handlers
  const handleDragStart = (e: React.DragEvent, tripId: number) => {
    e.dataTransfer.setData("text/plain", tripId.toString());
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDragEnter = (e: React.DragEvent, columnKey: string) => {
    e.preventDefault();
    setActiveDropzone(columnKey);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setActiveDropzone(null);
  };

  const handleDrop = (e: React.DragEvent, columnKey: string) => {
    e.preventDefault();
    setActiveDropzone(null);
    const tripIdStr = e.dataTransfer.getData("text/plain");
    if (!tripIdStr) return;
    const tripId = parseInt(tripIdStr, 10);
    if (isNaN(tripId)) return;

    const trip = props.trips.find((t) => t.id === tripId);
    if (!trip) return;

    // VALIDATION RULE:
    // Trip must have vehicle and driver before transitioning to en_route_pickup, active, completed.
    if (trip.status === "requested" && columnKey !== "assigned" && columnKey !== "cancelled") {
      if (props.setError) {
        props.setError("Cannot transition unassigned trip. Assign a vehicle and driver first using the form below.");
        setTimeout(() => props.setError!(null), 5000);
      } else {
        alert("Cannot transition unassigned trip. Assign a vehicle and driver first.");
      }
      return;
    }

    // Determine target status
    let targetStatus = columnKey;
    if (columnKey === "assigned") {
      // Reverting to Column 1 (UPDATE)
      targetStatus = trip.vehicle ? "assigned" : "requested";
    }

    props.onTransition(tripId, targetStatus);
  };

  return (
    <div className="stack">
      {props.unassignedTrips && props.unassignedTrips.length > 0 && (
        <Panel title="Trip Dispatch" subtitle="Assign drivers to trips and manage live dispatches.">
          <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr 1fr auto", alignItems: "end", marginBottom: 12 }}>
            <SelectField label="Trip" value={props.selectedTrip ?? ""} onChange={(value) => props.onTripChange?.(Number(value))}>
              <option value="" disabled>Select trip</option>
              {props.unassignedTrips.map((trip) => (
                <option key={trip.id} value={trip.id}>
                  {trip.pickup_city} to {trip.drop_city} {trip.distance_km ? `(${trip.distance_km} km)` : ""} - {trip.customer_name}
                </option>
              ))}
            </SelectField>
            <SelectField label="Vehicle" value={props.selectedVehicle ?? ""} onChange={(value) => props.onVehicleChange?.(Number(value))}>
              <option value="" disabled>Select vehicle</option>
              {props.assignableVehicles?.map((vehicle) => (
                <option key={vehicle.id} value={vehicle.id}>
                  {vehicle.registration_number} - {vehicle.category} - {vehicle.current_city}
                </option>
              ))}
            </SelectField>
            <SelectField label="Driver" value={props.selectedDriver ?? ""} onChange={(value) => props.onDriverChange?.(Number(value))}>
              <option value="" disabled>Select driver</option>
              {props.availableDrivers?.map((driver) => (
                <option key={driver.id} value={driver.id}>
                  {driver.name} - {driver.home_base}
                </option>
              ))}
            </SelectField>
            <div className="actions inline-action">
              <button className="button" type="button" onClick={props.onAssign} style={{ background: "var(--accent-strong)" }}>
                <Navigation size={16} />
                Assign Trip
              </button>
            </div>
          </div>
        </Panel>
      )}

      {/* Kanban Board Area */}
      <div className="kanban-board-container">
        <div className="kanban-board">
          {columns.map((col) => {
            const tripsInCol = columnTrips[col.key] || [];
            
            return (
              <div 
                className={`kanban-column ${col.highlightClass}`} 
                key={col.key}
              >
                <div className="kanban-column-header">
                  <div className="kanban-column-title-group">
                    <span className="kanban-column-title">{col.title}</span>
                    <span className="kanban-column-count">{tripsInCol.length}</span>
                  </div>
                </div>

                {/* Drop Zone Target */}
                <div 
                  className={`kanban-dropzone ${activeDropzone === col.key ? "dragover" : ""}`}
                  onDragOver={handleDragOver}
                  onDragEnter={(e) => handleDragEnter(e, col.key)}
                  onDragLeave={handleDragLeave}
                  onDrop={(e) => handleDrop(e, col.key)}
                >
                  Drop here
                </div>

                <div 
                  className="kanban-cards-list"
                  onDragOver={handleDragOver}
                  onDragEnter={(e) => handleDragEnter(e, col.key)}
                  onDragLeave={handleDragLeave}
                  onDrop={(e) => handleDrop(e, col.key)}
                >
                  {tripsInCol.map((trip) => {
                    // Decide card icon
                    let CardIcon = ClipboardCheck;
                    let iconColorClass = "update";
                    if (trip.status === "en_route_pickup") {
                      CardIcon = Navigation;
                      iconColorClass = "en_route_pickup";
                    } else if (trip.status === "active") {
                      CardIcon = RefreshCw;
                      iconColorClass = "active";
                    } else if (trip.status === "completed") {
                      CardIcon = CheckCircle2;
                      iconColorClass = "completed";
                    } else if (trip.status === "cancelled") {
                      CardIcon = XCircle;
                      iconColorClass = "cancelled";
                    } else if (trip.status === "requested") {
                      CardIcon = Clock;
                      iconColorClass = "update";
                    }

                    // Decide badge text and styling class
                    let badgeText = "PENDING UPDATE";
                    let badgeClass = "update";
                    if (trip.status === "requested") {
                      badgeText = "PENDING ASSIGNMENT";
                      badgeClass = "requested";
                    } else if (trip.status === "en_route_pickup") {
                      badgeText = "EN ROUTE PICKUP";
                      badgeClass = "en_route_pickup";
                    } else if (trip.status === "active") {
                      badgeText = "ACTIVE";
                      badgeClass = "active";
                    } else if (trip.status === "completed") {
                      badgeText = "COMPLETED";
                      badgeClass = "completed";
                    } else if (trip.status === "cancelled") {
                      badgeText = "CANCELLED";
                      badgeClass = "cancelled";
                    }

                    return (
                      <div 
                        className="kanban-card" 
                        key={trip.id}
                        draggable={true}
                        onDragStart={(e) => handleDragStart(e, trip.id)}
                      >
                        <div className="kanban-card-header">
                          <div className={`kanban-card-icon-wrapper ${iconColorClass}`}>
                            <CardIcon size={16} />
                          </div>
                          <div className="kanban-card-title-block">
                            <h4 className="kanban-card-title">{trip.pickup_city} to {trip.drop_city}</h4>
                            <p className="kanban-card-subtitle">{trip.customer_name} {trip.ota_source ? ` - ${trip.ota_source}` : ""}</p>
                          </div>
                        </div>

                        <div className="kanban-card-details">
                          <div className="kanban-card-detail-item">
                            <Clock size={12} />
                            <span>{formatDate(trip.pickup_at)}</span>
                          </div>
                          <div className="kanban-card-detail-item">
                            <Car size={12} />
                            <span>
                              {trip.vehicle 
                                ? `${trip.vehicle.registration_number} • ${trip.driver?.name || "No driver"}`
                                : "No vehicle • No driver"}
                            </span>
                          </div>
                          {trip.status === "active" && (
                            <div className="live-tracking-badge">
                              <span className="pulse-dot"></span>
                              Live Tracking
                            </div>
                          )}
                          {trip.status === "cancelled" && trip.notes && (
                            <div className="cancelled-reason-text">
                              {trip.notes}
                            </div>
                          )}
                        </div>

                        <div className="kanban-card-footer">
                          <span className={`kanban-card-badge ${badgeClass}`}>{badgeText}</span>
                          <div className="kanban-card-actions">
                            <button 
                              className="kanban-card-action-btn"
                              aria-label="Options"
                              onClick={(e) => {
                                e.stopPropagation();
                                setOpenMenuId(openMenuId === trip.id ? null : trip.id);
                              }}
                            >
                              <MoreVertical size={14} />
                            </button>
                            {openMenuId === trip.id && (
                              <div className="dropdown-menu" style={{
                                position: "absolute",
                                right: 0,
                                bottom: "100%",
                                background: "var(--panel-strong)",
                                border: "1px solid var(--line)",
                                borderRadius: 6,
                                padding: 4,
                                zIndex: 1000,
                                boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
                                minWidth: 140
                              }}>
                                {tripTransitions.map((status) => (
                                  <button
                                    key={status}
                                    style={{
                                      width: "100%",
                                      textAlign: "left",
                                      background: "transparent",
                                      border: 0,
                                      padding: "8px 10px",
                                      fontSize: 12,
                                      cursor: "pointer",
                                      borderRadius: 4,
                                      color: "#fff"
                                    }}
                                    onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.05)"}
                                    onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                                    onClick={() => {
                                      props.onTransition(trip.id, status);
                                      setOpenMenuId(null);
                                    }}
                                  >
                                    {labelize(status)}
                                  </button>
                                ))}
                                <div style={{ height: 1, background: "var(--line)", margin: "4px 0" }} />
                                <button
                                  style={{
                                    width: "100%",
                                    textAlign: "left",
                                    background: "transparent",
                                    border: 0,
                                    padding: "8px 10px",
                                    fontSize: 12,
                                    cursor: "pointer",
                                    borderRadius: 4,
                                    color: "var(--danger)",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 6
                                  }}
                                  onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,0,0,0.1)"}
                                  onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    if (props.onDelete) props.onDelete(trip.id);
                                    setOpenMenuId(null);
                                  }}
                                >
                                  <Trash2 size={12} /> Delete
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {tripsInCol.length === 0 && (
                    <div style={{
                      height: "100%",
                      minHeight: 120,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "var(--muted)",
                      fontSize: 13,
                      border: "1px dashed rgba(255,255,255,0.05)",
                      borderRadius: 8
                    }}>
                      No trips
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function CreateTripView(props: {
  role: Role;
  onCreateTrip: (payload: any, onSuccess: () => void) => void;
}) {
  return (
    <section className="grid">

      {props.role !== "accountant" ? (
        <Panel title="New OTA Trip">
          <TripForm onCreateTrip={props.onCreateTrip} />
        </Panel>
      ) : (
        <div className="notice">Accountant mode keeps trip creation disabled and focuses on billing and payout review.</div>
      )}
    </section>
  );
}

function VehiclesView({
  vehicles,
  availability,
  trips,
  onAddClick,
  onEditClick,
  onDeleteClick
}: {
  vehicles: Vehicle[];
  availability: Availability[];
  trips: Trip[];
  onAddClick: () => void;
  onEditClick: (vehicle: Vehicle) => void;
  onDeleteClick: (id: number) => void;
}) {
  return (
    <Panel
      title="Vehicle Registry"
      action={
        <button className="button" onClick={onAddClick}>
          <Plus size={16} />
          Add Vehicle
        </button>
      }
    >
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Vehicle</th>
              <th>Driver</th>
              <th>Location</th>
              <th>Status</th>
              <th>Next availability</th>
              <th>Current trip</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {vehicles.map((vehicle) => {
              const availabilityRecord = availability.find((item) => item.vehicle_id === vehicle.id);
              const activeTrip = trips.find((trip) => trip.vehicle?.id === vehicle.id && ["assigned", "en_route_pickup", "active"].includes(trip.status));
              return (
                <tr key={vehicle.id}>
                  <td><strong>{vehicle.registration_number}</strong><br />{vehicle.make} {vehicle.model} - {vehicle.category}</td>
                  <td>{vehicle.assigned_driver?.name ?? "Unassigned"}</td>
                  <td>{vehicle.current_city}</td>
                  <td><Status value={vehicle.status} /></td>
                  <td>{availabilityRecord ? `${availabilityRecord.available_city}, ${formatDate(availabilityRecord.available_from)}` : "Unknown"}</td>
                  <td>{activeTrip ? `${activeTrip.pickup_city} to ${activeTrip.drop_city}` : "None"}</td>
                  <td>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="button secondary" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => onEditClick(vehicle)} title="Edit vehicle">
                        <Pencil size={14} /> Edit
                      </button>
                      <button className="button secondary" style={{ padding: "4px 8px", fontSize: 12, color: "var(--danger)" }} onClick={() => onDeleteClick(vehicle.id)} title="Delete vehicle">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function AddVehicleForm({
  drivers,
  initialData,
  onSubmit,
  onCancel
}: {
  drivers: Driver[];
  initialData?: Vehicle | null;
  onSubmit: (payload: any) => Promise<void>;
  onCancel: () => void;
}) {
  const [regNumber, setRegNumber] = useState(initialData?.registration_number || "");
  const [make, setMake] = useState(initialData?.make || "");
  const [model, setModel] = useState(initialData?.model || "");
  const [category, setCategory] = useState(initialData?.category || "Sedan");
  const [currentCity, setCurrentCity] = useState(initialData?.current_city || "");
  const [vehicleStatus, setVehicleStatus] = useState(initialData?.status || "idle");
  const [odometerKm, setOdometerKm] = useState(initialData?.odometer_km || 0);
  const [assignedDriverId, setAssignedDriverId] = useState<number | null>(initialData?.assigned_driver?.id || null);

  // Default dates (today + 1 year)
  const getFutureDate = (years: number) => {
    const d = new Date();
    d.setFullYear(d.getFullYear() + years);
    return d.toISOString().split("T")[0];
  };

  const [permitExp, setPermitExp] = useState(initialData?.permit_expires_on || getFutureDate(1));
  const [insuranceExp, setInsuranceExp] = useState(initialData?.insurance_expires_on || getFutureDate(1));
  const [pollutionExp, setPollutionExp] = useState(initialData?.pollution_expires_on || getFutureDate(1));
  const [fitnessExp, setFitnessExp] = useState(initialData?.fitness_expires_on || getFutureDate(1));

  // ALPR OCR States
  const [alprFile, setAlprFile] = useState<File | null>(null);
  const [alprPreviewUrl, setAlprPreviewUrl] = useState<string | null>(null);
  const [alprLoading, setAlprLoading] = useState(false);
  const [alprError, setAlprError] = useState<string | null>(null);
  const [alprSuccess, setAlprSuccess] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setAlprFile(file);
    setAlprError(null);
    setAlprSuccess(null);
    if (file) {
      const url = URL.createObjectURL(file);
      setAlprPreviewUrl(url);
    } else {
      setAlprPreviewUrl(null);
    }
  };

  const handleScanPlate = async () => {
    if (!alprFile) {
      setAlprError("Please select a license plate photo first.");
      return;
    }
    setAlprLoading(true);
    setAlprError(null);
    setAlprSuccess(null);

    try {
      const formData = new FormData();
      formData.append("image", alprFile);

      const response = await fetch("/api/alpr", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errJson = await response.json();
        throw new Error(errJson.error || "Plate scanning failed.");
      }

      const data = await response.json();
      if (data.plate) {
        setRegNumber(data.plate);
        setAlprSuccess(
          `Detected Plate: ${data.plate} (${Math.round(data.confidence * 100)}% confidence)${data.simulated ? " [SIMULATION]" : ""
          }`
        );
      } else {
        throw new Error("No license plate detected in image.");
      }
    } catch (err: any) {
      setAlprError(err.message || "Failed to process license plate image.");
    } finally {
      setAlprLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!regNumber || !make || !model || !currentCity) {
      alert("Please fill in all required fields.");
      return;
    }

    const payload = {
      registration_number: regNumber,
      make,
      model,
      category,
      current_city: currentCity,
      status: vehicleStatus,
      assigned_driver_id: assignedDriverId,
      permit_expires_on: permitExp,
      insurance_expires_on: insuranceExp,
      pollution_expires_on: pollutionExp,
      fitness_expires_on: fitnessExp,
      odometer_km: Number(odometerKm)
    };

    onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit} className="stack">
      {/* ALPR scanner section (shown on creation) */}
      {!initialData && (
        <div className="field">
          <label>Scan License Plate Photo (ALPR)</label>
          <div className={`alpr-scanner-box ${alprLoading ? 'scanning' : ''} ${alprSuccess ? 'success' : ''}`}>
            {!alprPreviewUrl ? (
              <label className="alpr-scanner-placeholder">
                <Camera size={26} />
                <strong>Upload Plate Photo</strong>
                <span>Accepts JPG/PNG Indian license plates</span>
                <input type="file" accept="image/*" onChange={handleFileChange} style={{ display: "none" }} />
              </label>
            ) : (
              <div className="alpr-preview-container">
                <img src={alprPreviewUrl} alt="Plate preview" className="alpr-preview-image" />
                <div className="alpr-scanner-actions">
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => {
                      setAlprFile(null);
                      setAlprPreviewUrl(null);
                      setAlprSuccess(null);
                      setAlprError(null);
                    }}
                  >
                    Remove
                  </button>
                  <button type="button" className="button" onClick={handleScanPlate} disabled={alprLoading}>
                    {alprLoading ? (
                      <>
                        <Loader2 size={16} className="animate-spin" />
                        Scanning...
                      </>
                    ) : (
                      <>
                        <Camera size={16} />
                        Scan Photo
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
          {alprError && <div className="error">{alprError}</div>}
          {alprSuccess && (
            <div className="scan-success-badge" style={{ alignSelf: "center", marginBottom: 12 }}>
              <CheckCircle2 size={16} />
              {alprSuccess}
            </div>
          )}
        </div>
      )}

      {/* Details Inputs */}
      <div className="form-grid">
        <div className="field">
          <label>Registration Number *</label>
          <input
            type="text"
            required
            placeholder="e.g. MH12AB1234"
            value={regNumber}
            onChange={(e) => setRegNumber(e.target.value.toUpperCase())}
          />
        </div>
        <div className="field">
          <label>Category</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="Sedan">Sedan</option>
            <option value="SUV">SUV</option>
            <option value="Hatchback">Hatchback</option>
            <option value="Luxury">Luxury</option>
            <option value="Truck">Truck</option>
          </select>
        </div>
        <div className="field">
          <label>Make *</label>
          <input
            type="text"
            required
            placeholder="e.g. Tata, Mahindra"
            value={make}
            onChange={(e) => setMake(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Model *</label>
          <input
            type="text"
            required
            placeholder="e.g. Nexon, Scorpio"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Current City *</label>
          <input
            type="text"
            required
            placeholder="e.g. Pune"
            value={currentCity}
            onChange={(e) => setCurrentCity(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Status</label>
          <select value={vehicleStatus} onChange={(e) => setVehicleStatus(e.target.value)}>
            <option value="idle">Idle</option>
            <option value="en_route_pickup">En route to pickup</option>
            <option value="active_trip">Active trip</option>
            <option value="maintenance">Maintenance</option>
            <option value="offline">Offline</option>
          </select>
        </div>
        <div className="field">
          <label>Odometer (KM)</label>
          <input
            type="number"
            min="0"
            value={odometerKm}
            onChange={(e) => setOdometerKm(Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label>Assigned Driver</label>
          <select
            value={assignedDriverId || ""}
            onChange={(e) => setAssignedDriverId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Unassigned</option>
            {drivers.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.home_base})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ marginTop: 12, borderTop: "1px solid var(--line)", paddingTop: 16 }}>
        <h4 style={{ margin: "0 0 12px 0", color: "#fff" }}>Compliance Document Expiry</h4>
        <div className="form-grid">
          <div className="field">
            <label>Permit Expiry *</label>
            <input type="date" required value={permitExp} onChange={(e) => setPermitExp(e.target.value)} />
          </div>
          <div className="field">
            <label>Insurance Expiry *</label>
            <input type="date" required value={insuranceExp} onChange={(e) => setInsuranceExp(e.target.value)} />
          </div>
          <div className="field">
            <label>Pollution Expiry *</label>
            <input type="date" required value={pollutionExp} onChange={(e) => setPollutionExp(e.target.value)} />
          </div>
          <div className="field">
            <label>Fitness Expiry *</label>
            <input type="date" required value={fitnessExp} onChange={(e) => setFitnessExp(e.target.value)} />
          </div>
        </div>
      </div>

      <div className="actions">
        <button type="button" className="button secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="button">
          {initialData ? "Update Vehicle" : "Save Vehicle"}
        </button>
      </div>
    </form>
  );
}

function DriversView({
  drivers,
  trips,
  onAddClick,
  onEditClick,
  onDeleteClick
}: {
  drivers: Driver[];
  trips: Trip[];
  onAddClick: () => void;
  onEditClick: (driver: Driver) => void;
  onDeleteClick: (id: number) => void;
}) {
  return (
    <Panel 
      title="Driver Roster"
      action={
        <button className="button" onClick={onAddClick}>
          <UserPlus size={16} />
          Add Driver
        </button>
      }
    >
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Driver</th>
              <th>Phone</th>
              <th>Base</th>
              <th>Status</th>
              <th>Assigned trip</th>
              <th>Rating</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {drivers.map((driver) => {
              const activeTrip = trips.find((trip) => trip.driver?.id === driver.id && ["assigned", "en_route_pickup", "active"].includes(trip.status));
              return (
                <tr key={driver.id}>
                  <td><strong>{driver.name}</strong><br />{driver.license_number}</td>
                  <td>{driver.phone}</td>
                  <td>{driver.home_base}</td>
                  <td><Status value={driver.status} /></td>
                  <td>{activeTrip ? `${activeTrip.pickup_city} to ${activeTrip.drop_city}` : "None"}</td>
                  <td>{driver.rating}</td>
                  <td>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="button secondary" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => onEditClick(driver)} title="Edit driver">
                        <Pencil size={14} /> Edit
                      </button>
                      <button className="button secondary" style={{ padding: "4px 8px", fontSize: 12, color: "var(--danger)" }} onClick={() => onDeleteClick(driver.id)} title="Delete driver">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function DriverForm({
  initialData,
  onSubmit,
  onCancel
}: {
  initialData?: Driver | null;
  onSubmit: (payload: any) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initialData?.name || "");
  const [phone, setPhone] = useState(initialData?.phone || "");
  const [licenseNumber, setLicenseNumber] = useState(initialData?.license_number || "");
  const [homeBase, setHomeBase] = useState(initialData?.home_base || "");
  const [driverStatus, setDriverStatus] = useState(initialData?.status || "available");
  const [rating, setRating] = useState(initialData?.rating || "4.5");

  // Documents state
  const [aadhaarCard, setAadhaarCard] = useState<UploadedAsset | null>(initialData?.aadhaar_card || null);
  const [drivingLicense, setDrivingLicense] = useState<UploadedAsset | null>(initialData?.driving_license || null);
  const [dlExpiryDate, setDlExpiryDate] = useState<string>(initialData?.driving_license_expiry_date || "");
  const [pcc, setPcc] = useState<UploadedAsset | null>(initialData?.police_clearance_certificate || null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !phone || !licenseNumber || !homeBase) {
      alert("Please fill in all required fields.");
      return;
    }

    onSubmit({
      name,
      phone,
      license_number: licenseNumber,
      home_base: homeBase,
      status: driverStatus,
      rating: Number(rating),
      aadhaar_card_id: aadhaarCard?.id || null,
      driving_license_id: drivingLicense?.id || null,
      driving_license_expiry_date: dlExpiryDate || null,
      police_clearance_certificate_id: pcc?.id || null
    });
  };

  return (
    <form onSubmit={handleSubmit} className="stack">
      <div className="form-grid">
        <div className="field">
          <label>Full Name *</label>
          <input
            type="text"
            required
            placeholder="e.g. Ramesh Kumar"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Phone Number *</label>
          <input
            type="text"
            required
            placeholder="e.g. +91 9876543210"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>
        <div className="field">
          <label>License Number *</label>
          <input
            type="text"
            required
            placeholder="e.g. DL-1420110012345"
            value={licenseNumber}
            onChange={(e) => setLicenseNumber(e.target.value.toUpperCase())}
          />
        </div>
        <div className="field">
          <label>Home Base City *</label>
          <input
            type="text"
            required
            placeholder="e.g. Delhi"
            value={homeBase}
            onChange={(e) => setHomeBase(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Status</label>
          <select value={driverStatus} onChange={(e) => setDriverStatus(e.target.value)}>
            <option value="available">Available</option>
            <option value="assigned">Assigned</option>
            <option value="on_trip">On trip</option>
            <option value="off_duty">Off duty</option>
            <option value="suspended">Suspended</option>
          </select>
        </div>
        <div className="field">
          <label>Rating (1.0 to 5.0)</label>
          <input
            type="number"
            min="1"
            max="5"
            step="0.1"
            value={rating}
            onChange={(e) => setRating(e.target.value)}
          />
        </div>
      </div>

      <div style={{ marginTop: 12, borderTop: "1px solid var(--line)", paddingTop: 16 }}>
        <h4 style={{ margin: "0 0 16px 0", color: "#fff" }}>Driver Documents</h4>
        <div className="form-grid">
          <div className="field">
            <label>Aadhaar Card</label>
            <DocumentUpload
              value={aadhaarCard}
              onChange={setAadhaarCard}
              placeholder="Upload Aadhaar Card"
            />
          </div>
          <div className="field">
            <label>Driving License</label>
            <DocumentUpload
              value={drivingLicense}
              onChange={setDrivingLicense}
              placeholder="Upload Driving License"
            />
          </div>
          <div className="field">
            <label>Driving License Expiry Date {drivingLicense && "*"}</label>
            <input
              type="date"
              required={!!drivingLicense}
              value={dlExpiryDate}
              onChange={(e) => setDlExpiryDate(e.target.value)}
            />
          </div>
          <div className="field">
            <label>Police Clearance Certificate (PCC)</label>
            <DocumentUpload
              value={pcc}
              onChange={setPcc}
              placeholder="Upload PCC"
            />
          </div>
        </div>
      </div>

      <div className="actions">
        <button type="button" className="button secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="button">
          {initialData ? "Update Driver" : "Save Driver"}
        </button>
      </div>
    </form>
  );
}

function TrackingView({ vehicles, activeTrips, availability }: { vehicles: Vehicle[]; activeTrips: Trip[]; availability: Availability[] }) {
  return (
    <section className="grid">
      <Panel title="Vehicle Tracking Board">
        <div className="tracking-board">
          {vehicles.map((vehicle) => {
            const trip = activeTrips.find((item) => item.vehicle?.id === vehicle.id);
            const next = availability.find((item) => item.vehicle_id === vehicle.id);
            return (
              <div className="tracking-row" key={vehicle.id}>
                <div className="tracking-marker"><MapPinned size={18} /></div>
                <div>
                  <strong>{vehicle.registration_number}</strong>
                  <span>{vehicle.current_city}</span>
                </div>
                <div>
                  <Status value={vehicle.status} />
                  <p>{trip ? `${trip.pickup_city} pickup, ${trip.drop_city} drop` : "No active trip assigned"}</p>
                </div>
                <div>
                  <span>Next ready</span>
                  <strong>{next ? `${next.available_city} - ${formatDate(next.available_from)}` : "Unknown"}</strong>
                </div>
              </div>
            );
          })}
        </div>
      </Panel>
      <Panel title="How Tracking Works">
        <div className="explain-list">
          <p>Vehicle status changes when dispatch updates a trip: assigned, en route to pickup, active, completed, or cancelled.</p>
          <p>The vehicle location is currently city-level. On trip completion the backend moves the vehicle to the drop city.</p>
          <p>Predictive availability uses the estimated drop time plus a buffer to show where the car can take the next booking.</p>
          <p>GPS tracking can be added next by saving periodic latitude and longitude pings per vehicle.</p>
        </div>
      </Panel>
    </section>
  );
}

function AvailabilityView({ availability, vehicles }: { availability: Availability[]; vehicles: Vehicle[] }) {
  return (
    <Panel title="Predictive Availability">
      <div className="availability-grid">
        {availability.map((item) => {
          const vehicle = vehicles.find((record) => record.id === item.vehicle_id);
          return (
            <div className="availability-card" key={item.vehicle_id}>
              <AvailabilityItem item={item} />
              <div className="mini-grid" style={{ borderTop: "1px solid var(--line)", paddingTop: 10, marginTop: 10 }}>
                <span>Category</span><strong>{item.category}</strong>
                <span>Status</span><strong>{vehicle ? labelize(vehicle.status) : "Unknown"}</strong>
                <span>Bid eligible</span><strong>{item.compliance_blockers.length ? "No" : "Yes"}</strong>
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function ComplianceView({ vehicles }: { vehicles: Vehicle[] }) {
  return (
    <Panel title="Compliance & Permit Guardrails">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Vehicle</th>
              <th>Permit</th>
              <th>Insurance</th>
              <th>Pollution</th>
              <th>Fitness</th>
              <th>Bid status</th>
            </tr>
          </thead>
          <tbody>
            {vehicles.map((vehicle) => (
              <tr key={vehicle.id}>
                <td><strong>{vehicle.registration_number}</strong><br />{vehicle.category}</td>
                <td>{vehicle.permit_expires_on}</td>
                <td>{vehicle.insurance_expires_on}</td>
                <td>{vehicle.pollution_expires_on}</td>
                <td>{vehicle.fitness_expires_on}</td>
                <td>{vehicle.is_compliant ? <Status value="eligible" /> : <Status value="blocked" />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function OtaView({ availability, vehicles, unassignedTrips }: { availability: Availability[]; vehicles: Vehicle[]; unassignedTrips: Trip[] }) {
  const eligibleCars = availability.filter((item) => item.compliance_blockers.length === 0);
  return (
    <section className="grid">
      <Panel title="OTA Bidding Readiness">
        <div className="metrics compact">
          <Metric icon={<Wifi size={18} />} label="Eligible cars" value={eligibleCars.length} />
          <Metric icon={<CalendarClock size={18} />} label="Open OTA trips" value={unassignedTrips.length} />
          <Metric icon={<AlertTriangle size={18} />} label="Blocked cars" value={vehicles.length - eligibleCars.length} />
        </div>
        <div className="table-wrap" style={{ marginTop: 16 }}>
          <table>
            <thead>
              <tr>
                <th>Vehicle</th>
                <th>Bid city</th>
                <th>Bid after</th>
                <th>Decision</th>
              </tr>
            </thead>
            <tbody>
              {availability.map((item) => (
                <tr key={item.vehicle_id}>
                  <td><strong>{item.registration_number}</strong><br />{item.category}</td>
                  <td>{item.available_city}</td>
                  <td>{formatDate(item.available_from)}</td>
                  <td>{item.compliance_blockers.length ? <Status value="blocked" /> : <Status value="eligible" />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel title="Next Backend Module">
        <div className="explain-list">
          <p>The current scaffold prepares the data needed for bidding decisions.</p>
          <p>The next step is an OTA opportunity model: route, pickup time, fare, commission, distance, and source.</p>
          <p>The bidding engine should compare opportunity pickup city and time against predictive availability and compliance.</p>
        </div>
      </Panel>
    </section>
  );
}

function TripsTable({ trips, onTransition }: { trips: Trip[]; onTransition: (tripId: number, status: string) => void }) {
  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>TRIP</th>
              <th>TIMING</th>
              <th>ASSIGNMENT</th>
              <th>STATUS</th>
              <th>ACTION</th>
            </tr>
          </thead>
          <tbody>
            {trips.map((trip) => {
              let Icon = Clock;
              let iconColor = "var(--warn)";
              let iconBg = "rgba(245, 158, 11, 0.1)";

              if (trip.status === "completed") {
                Icon = CheckCircle;
                iconColor = "var(--ok)";
                iconBg = "rgba(34, 197, 94, 0.1)";
              } else if (trip.status === "cancelled") {
                Icon = XCircle;
                iconColor = "var(--danger)";
                iconBg = "rgba(239, 68, 68, 0.1)";
              } else if (trip.status === "active" || trip.status === "assigned" || trip.status === "en_route_pickup") {
                Icon = Navigation;
                iconColor = "var(--info)";
                iconBg = "rgba(59, 130, 246, 0.1)";
              }

              return (
                <tr key={trip.id}>
                  <td style={{ display: "flex", gap: 12, alignItems: "center" }}>
                    <div style={{ background: iconBg, color: iconColor, width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      <Icon size={18} />
                    </div>
                    <div>
                      <strong style={{ display: "block", color: "#fff", fontSize: 13, marginBottom: 2 }}>
                        {trip.pickup_city} to {trip.drop_city}
                        {trip.distance_km && (
                          <span style={{ color: "var(--accent)", fontSize: 11, marginLeft: 8, fontWeight: 600 }}>
                            ({trip.distance_km} km)
                          </span>
                        )}
                      </strong>
                      <span style={{ color: "var(--muted)", fontSize: 12 }}>{trip.customer_name} {trip.ota_source ? `- ${trip.ota_source}` : ""}</span>
                    </div>
                  </td>
                  <td>
                    <span style={{ display: "block", fontSize: 13, color: "#e2e8f0", marginBottom: 2 }}><Clock size={12} style={{ display: "inline", marginRight: 4, verticalAlign: "middle", color: "var(--muted)" }} />{formatDate(trip.pickup_at)}</span>
                    <span style={{ color: "var(--muted)", fontSize: 12 }}>Drop: {formatDate(trip.estimated_drop_at)}</span>
                  </td>
                  <td>
                    <span style={{ display: "block", color: "#fff", fontSize: 13, marginBottom: 2 }}>{trip.vehicle?.registration_number ?? "No vehicle"}</span>
                    <span style={{ color: "var(--muted)", fontSize: 12 }}>{trip.driver?.name ?? "No driver"}</span>
                  </td>
                  <td><Status value={trip.status} /></td>
                  <td>
                    <div style={{ position: "relative", display: "inline-block" }}>
                      <select 
                        value="" 
                        onChange={(event) => onTransition(trip.id, event.target.value)} 
                        aria-label={`Update ${trip.customer_name} status`}
                        style={{ appearance: "none", background: "rgba(255,255,255,0.05)", border: "1px solid var(--line)", borderRadius: 6, padding: "6px 28px 6px 12px", color: "#fff", fontSize: 12, cursor: "pointer" }}
                      >
                        <option value="" disabled>Update</option>
                        {tripTransitions.map((status) => (
                          <option key={status} value={status}>{labelize(status)}</option>
                        ))}
                      </select>
                      <ChevronDown size={14} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", pointerEvents: "none", color: "var(--muted)" }} />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--line)", fontSize: 12, color: "var(--muted)" }}>
        <span>Showing 1 to {Math.min(trips.length, 6)} of {trips.length} trips</span>
        <div style={{ display: "flex", gap: 4 }}>
          <button style={{ background: "rgba(255,255,255,0.05)", border: "1px solid var(--line)", color: "var(--muted)", width: 28, height: 28, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>&lt;</button>
          <button style={{ background: "var(--accent-strong)", border: "none", color: "#fff", width: 28, height: 28, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>1</button>
          <button style={{ background: "transparent", border: "1px solid transparent", color: "var(--muted)", width: 28, height: 28, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>2</button>
          <button style={{ background: "transparent", border: "1px solid transparent", color: "var(--muted)", width: 28, height: 28, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>3</button>
          <span style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 28, height: 28 }}>...</span>
          <button style={{ background: "transparent", border: "1px solid transparent", color: "var(--muted)", width: 28, height: 28, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>4</button>
          <button style={{ background: "rgba(255,255,255,0.05)", border: "1px solid var(--line)", color: "var(--muted)", width: 28, height: 28, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>&gt;</button>
        </div>
      </div>
    </>
  );
}

function TripForm({ onCreateTrip }: { onCreateTrip: (payload: any, onSuccess: () => void) => void }) {
  const [pickupCity, setPickupCity] = useState("");
  const [dropCity, setDropCity] = useState("");
  const [pickupLat, setPickupLat] = useState<number | null>(null);
  const [pickupLng, setPickupLng] = useState<number | null>(null);
  const [dropLat, setDropLat] = useState<number | null>(null);
  const [dropLng, setDropLng] = useState<number | null>(null);
  const [distanceKm, setDistanceKm] = useState<number | null>(null);
  const [mapKey, setMapKey] = useState(0);

  const [pickupDate, setPickupDate] = useState("");
  const [pickupTime, setPickupTime] = useState("");
  const [dropDate, setDropDate] = useState("");
  const [dropTime, setDropTime] = useState("");

  useEffect(() => {
    if (pickupDate && pickupTime && distanceKm) {
      // Estimate duration: assume average speed of 50 km/h + 30 mins buffer
      const hours = distanceKm / 50;
      const ms = (hours * 60 * 60 * 1000) + (30 * 60 * 1000);
      const pickupDateObj = new Date(`${pickupDate}T${pickupTime}`);
      if (!isNaN(pickupDateObj.getTime())) {
        const dropDateObj = new Date(pickupDateObj.getTime() + ms);
        
        // Snap minutes to nearest 15 for consistency with the time picker UI
        const mins = dropDateObj.getMinutes();
        const snappedMins = Math.round(mins / 15) * 15;
        dropDateObj.setMinutes(snappedMins);
        
        const yyyy = dropDateObj.getFullYear();
        const mm = String(dropDateObj.getMonth() + 1).padStart(2, '0');
        const dd = String(dropDateObj.getDate()).padStart(2, '0');
        
        const hh = String(dropDateObj.getHours()).padStart(2, '0');
        const fmm = String(dropDateObj.getMinutes()).padStart(2, '0');
        
        setDropDate(`${yyyy}-${mm}-${dd}`);
        setDropTime(`${hh}:${fmm}`);
      }
    }
  }, [pickupDate, pickupTime, distanceKm]);

  const handleLocationSelected = (data: {
    pickupLat: number | null;
    pickupLng: number | null;
    pickupCity: string;
    dropLat: number | null;
    dropLng: number | null;
    dropCity: string;
    distanceKm: number | null;
  }) => {
    if (data.pickupCity) setPickupCity(data.pickupCity);
    if (data.dropCity) setDropCity(data.dropCity);
    setPickupLat(data.pickupLat);
    setPickupLng(data.pickupLng);
    setDropLat(data.dropLat);
    setDropLng(data.dropLng);
    setDistanceKm(data.distanceKm);
  };

  const [bookingType, setBookingType] = useState<string>("ADHOC");
  const [customersList, setCustomersList] = useState<CorporateCustomer[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null);
  const [dutyType, setDutyType] = useState<string>("LOCAL_8HR_80KM");
  const [vehicleCategory, setVehicleCategory] = useState<string>("sedan");
  const [quote, setQuote] = useState<PricingQuote | null>(null);
  const [quoteLoading, setQuoteLoading] = useState<boolean>(false);
  const [quoteError, setQuoteError] = useState<string | null>(null);

  useEffect(() => {
    getCustomers().then((data) => {
      setCustomersList(data);
      if (data.length > 0) setSelectedCustomerId(data[0].id);
    }).catch((err) => console.error("Error loading customers for trip form:", err));
  }, []);

  // Fetch quote whenever corporate parameters change
  useEffect(() => {
    if (bookingType !== "CORPORATE" || !selectedCustomerId || !pickupCity || !pickupDate || !pickupTime) {
      setQuote(null);
      setQuoteError(null);
      return;
    }

    const fetchQuote = async () => {
      try {
        setQuoteLoading(true);
        setQuoteError(null);
        const pickupDt = `${pickupDate}T${pickupTime}:00Z`;
        const res = await getPricingQuote({
          customer: selectedCustomerId,
          pickup_datetime: pickupDt,
          pickup_city: pickupCity,
          vehicle_category: vehicleCategory,
          duty_type: dutyType,
          planned_km: distanceKm || 0,
        });
        setQuote(res);
      } catch (err: any) {
        setQuote(null);
        setQuoteError(err.message || "No active rate card matched.");
      } finally {
        setQuoteLoading(false);
      }
    };

    const timer = setTimeout(fetchQuote, 400);
    return () => clearTimeout(timer);
  }, [bookingType, selectedCustomerId, pickupCity, pickupDate, pickupTime, dutyType, vehicleCategory, distanceKm]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const formData = new FormData(formElement);

    const payload: any = {
      booking_type: bookingType,
      pickup_city: pickupCity || String(formData.get("pickup_city")),
      drop_city: dropCity || String(formData.get("drop_city")),
      pickup_at: `${pickupDate}T${pickupTime}`,
      estimated_drop_at: `${dropDate}T${dropTime}`,
      pickup_latitude: pickupLat,
      pickup_longitude: pickupLng,
      drop_latitude: dropLat,
      drop_longitude: dropLng,
      distance_km: distanceKm,
    };

    if (bookingType === "CORPORATE") {
      if (!selectedCustomerId) {
        alert("Please select a corporate customer.");
        return;
      }
      if (!quote) {
        alert("Cannot submit corporate trip without a valid rate quote.");
        return;
      }
      payload.customer_id = selectedCustomerId;
      payload.duty_type = dutyType;
      payload.vehicle_category_requested = vehicleCategory;
      payload.fare_amount = quote.total_amount;
    } else {
      payload.customer_name = String(formData.get("customer_name"));
      payload.ota_source = String(formData.get("ota_source"));
      payload.fare_amount = String(formData.get("fare_amount"));
    }

    onCreateTrip(payload, () => {
      setPickupCity("");
      setDropCity("");
      setPickupLat(null);
      setPickupLng(null);
      setDropLat(null);
      setDropLng(null);
      setDistanceKm(null);
      setPickupDate("");
      setPickupTime("");
      setDropDate("");
      setDropTime("");
      setQuote(null);
      setMapKey((prev) => prev + 1);
      formElement.reset();
    });
  };

  return (
    <form className="stack" onSubmit={handleSubmit}>
      <div className="field">
        <label>BOOKING TYPE</label>
        <select value={bookingType} onChange={(e) => setBookingType(e.target.value)}>
          <option value="ADHOC">Ad-hoc / Direct</option>
          <option value="CORPORATE">Corporate Contract</option>
          <option value="OTA">OTA / Aggregator</option>
        </select>
      </div>

      {bookingType === "CORPORATE" ? (
        <>
          <div className="field">
            <label>CORPORATE CUSTOMER *</label>
            <select
              value={selectedCustomerId || ""}
              onChange={(e) => setSelectedCustomerId(Number(e.target.value))}
              required
            >
              {customersList.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.display_name} ({c.code})
                </option>
              ))}
            </select>
          </div>

          <div className="form-grid" style={{ gap: 12 }}>
            <div className="field">
              <label>DUTY TYPE *</label>
              <select value={dutyType} onChange={(e) => setDutyType(e.target.value)}>
                <option value="LOCAL_8HR_80KM">LOCAL (8h / 80km)</option>
                <option value="LOCAL_12HR_120KM">LOCAL (12h / 120km)</option>
                <option value="OUTSTATION">OUTSTATION</option>
                <option value="AIRPORT_TRANSFER">AIRPORT TRANSFER</option>
                <option value="ONE_WAY">ONE WAY</option>
                <option value="FULL_DAY">FULL DAY</option>
              </select>
            </div>
            <div className="field">
              <label>REQUESTED CATEGORY *</label>
              <select value={vehicleCategory} onChange={(e) => setVehicleCategory(e.target.value)}>
                <option value="sedan">Sedan</option>
                <option value="suv">SUV</option>
                <option value="luxury">Luxury</option>
                <option value="hatchback">Hatchback</option>
              </select>
            </div>
          </div>
        </>
      ) : (
        <>
          <InputField label="CUSTOMER NAME" name="customer_name" placeholder="Enter customer name" required />
          {bookingType === "OTA" && (
            <div className="field">
              <label>OTA SOURCE</label>
              <select name="ota_source" defaultValue="MMT">
                <option value="MMT">MMT</option>
                <option value="Goibibo">Goibibo</option>
                <option value="ClearTrip">ClearTrip</option>
              </select>
            </div>
          )}
        </>
      )}

      <MapComponent 
        key={mapKey}
        pickupLat={pickupLat}
        pickupLng={pickupLng}
        pickupCityProp={pickupCity}
        dropLat={dropLat}
        dropLng={dropLng}
        dropCityProp={dropCity}
        onLocationSelected={handleLocationSelected} 
      />

      <AutocompleteField 
        label="PICKUP CITY" 
        placeholder="Type pickup city to autocomplete..." 
        value={pickupCity} 
        onChange={setPickupCity} 
        onSelectSuggestion={(s) => {
          setPickupLat(Number(s.lat.toFixed(6)));
          setPickupLng(Number(s.lng.toFixed(6)));
          setPickupCity(s.city);
        }}
        required 
      />
      <AutocompleteField 
        label="DROP CITY" 
        placeholder="Type drop city to autocomplete..." 
        value={dropCity} 
        onChange={setDropCity} 
        onSelectSuggestion={(s) => {
          setDropLat(Number(s.lat.toFixed(6)));
          setDropLng(Number(s.lng.toFixed(6)));
          setDropCity(s.city);
        }}
        required 
      />
      
      <div className="form-grid" style={{ gap: 12 }}>
        <InputField label="PICKUP DATE" name="pickup_date" type="date" value={pickupDate} onChange={(e) => setPickupDate(e.target.value)} required />
        <TimePickerField label="PICKUP TIME" name="pickup_time" value={pickupTime} onChange={setPickupTime} />
      </div>
      <div className="form-grid" style={{ gap: 12, marginTop: 12 }}>
        <InputField label="DROP DATE" name="drop_date" type="date" value={dropDate} onChange={(e) => setDropDate(e.target.value)} required />
        <TimePickerField label="DROP TIME" name="drop_time" value={dropTime} onChange={setDropTime} />
      </div>

      {bookingType === "CORPORATE" ? (
        <div style={{ padding: 16, background: "rgba(15, 23, 42, 0.6)", border: "1px solid var(--line)", borderRadius: 12, fontSize: 13 }}>
          <div style={{ fontWeight: 700, color: "#fff", marginBottom: 8 }}>Live Contract Pricing Breakdown</div>
          {quoteLoading ? (
            <div style={{ color: "var(--muted)", fontStyle: "italic" }}>Calculating server quote...</div>
          ) : quoteError ? (
            <div style={{ color: "var(--danger)" }}>⚠️ {quoteError}</div>
          ) : quote ? (
            <div style={{ display: "grid", gap: 6 }}>
              <div style={{ display: "flex", justifyContent: "space-between", color: "var(--muted)" }}>
                <span>Contract:</span>
                <strong style={{ color: "#fff" }}>{quote.contract.title} ({quote.contract.version_name})</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", color: "var(--muted)" }}>
                <span>Base Charge ({quote.itemized_charges.included_hours}h / {quote.itemized_charges.included_km}km):</span>
                <span style={{ color: "#fff" }}>₹{quote.itemized_charges.base_charge}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", color: "var(--muted)" }}>
                <span>Taxes (CGST {quote.itemized_charges.cgst_rate}% + SGST {quote.itemized_charges.sgst_rate}%):</span>
                <span style={{ color: "#fff" }}>₹{(Number(quote.itemized_charges.cgst_amount) + Number(quote.itemized_charges.sgst_amount)).toFixed(2)}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", color: "var(--muted)" }}>
                <span>Metering Policy:</span>
                <span style={{ color: "var(--accent)" }}>{quote.contract.metering_policy}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", paddingTop: 8, borderTop: "1px solid var(--line)", fontSize: 15 }}>
                <strong style={{ color: "#fff" }}>Calculated Fare:</strong>
                <strong style={{ color: "#10b981" }}>₹{quote.total_amount}</strong>
              </div>
            </div>
          ) : (
            <div style={{ color: "var(--muted)" }}>Enter pickup city, date, and time to generate quote.</div>
          )}
        </div>
      ) : (
        <InputField label="FARE (₹)" name="fare_amount" type="number" min="0" step="1" defaultValue="0" />
      )}

      {distanceKm !== null && (
        <div style={{ padding: 12, background: "rgba(59, 130, 246, 0.08)", border: "1px solid rgba(59, 130, 246, 0.2)", borderRadius: 8, fontSize: 13, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ color: "var(--muted)", fontWeight: 500 }}>Route Distance:</span>
          <strong style={{ color: "var(--accent)" }}>{distanceKm} km</strong>
        </div>
      )}

      <div className="actions" style={{ marginTop: 8 }}>
        <button
          className="button"
          type="submit"
          disabled={bookingType === "CORPORATE" && (!quote || quoteLoading)}
          style={{
            width: "100%",
            justifyContent: "center",
            background: bookingType === "CORPORATE" && (!quote || quoteLoading) ? "var(--muted)" : "var(--accent-strong)",
            cursor: bookingType === "CORPORATE" && (!quote || quoteLoading) ? "not-allowed" : "pointer"
          }}
        >
          <Plus size={16} />
          {bookingType === "CORPORATE" ? "Create Corporate Trip" : "Create Trip"}
        </button>
      </div>
    </form>
  );
}

function Panel({ children, title, subtitle, action }: { children: React.ReactNode; title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <section className="section">
      <div className="section-header" style={{ alignItems: "flex-start", flexDirection: "column", gap: 4 }}>
        <div style={{ display: "flex", justifyContent: "space-between", width: "100%", alignItems: "center" }}>
          <h2>{title}</h2>
          {action}
        </div>
        {subtitle && <span style={{ color: "var(--muted)", fontSize: 13 }}>{subtitle}</span>}
      </div>
      <div className="section-body">{children}</div>
    </section>
  );
}

function Metric({
  icon,
  label,
  value,
  total,
  trend,
  trendUp,
  color
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  total?: string;
  trend?: string;
  trendUp?: boolean;
  color?: string;
}) {
  const isLive = trend?.toLowerCase() === "live";
  return (
    <div className="metric">
      <div className="metric-header">
        <div style={{ 
          background: color ? color + "1a" : "rgba(255, 255, 255, 0.05)", 
          padding: 8, 
          borderRadius: "50%", 
          display: "flex", 
          color: color || "inherit" 
        }}>
          {icon}
        </div>
        {label}
      </div>
      <div className="metric-content">
        <div className="metric-value">
          <strong>{value}</strong>
          {total && <span>{total}</span>}
        </div>
        {trend && (
          <div className={`metric-trend ${isLive ? "live" : trendUp ? "up" : "down"}`}>
            {!isLive && (trendUp ? "▲ " : "▼ ")}{trend}
          </div>
        )}
      </div>
    </div>
  );
}

function AvailabilityItem({ item }: { item: Availability }) {
  const colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];
  const color = colors[item.vehicle_id % colors.length];

  return (
    <div className="availability-item" style={{ display: "flex", alignItems: "center", gap: 16, background: "rgba(255,255,255,0.02)", padding: 16, borderRadius: 12, border: "1px solid var(--line)" }}>
      <div style={{ background: color, width: 40, height: 40, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", flexShrink: 0 }}>
        <Car size={20} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <strong style={{ display: "block", color: "#fff", fontSize: 14, marginBottom: 4 }}>{item.registration_number} • {item.category}</strong>
        <span style={{ display: "block", color: "var(--muted)", fontSize: 13 }}>{item.available_city} after {formatDate(item.available_from)}</span>
        <span style={{ display: "block", color: "var(--muted)", fontSize: 13 }}>{item.driver_name ?? "No driver assigned"}</span>
        {item.compliance_blockers.length ? <span style={{ display: "block", color: "var(--danger)", fontWeight: 600, fontSize: 13, marginTop: 4 }}>Blocked: {item.compliance_blockers.join(", ")}</span> : null}
      </div>
      <div style={{ padding: "6px 12px", background: "rgba(255,255,255,0.05)", borderRadius: 6, fontSize: 13, fontWeight: 600, color: "#fff" }}>
        5h 45m
      </div>
    </div>
  );
}

function TripSummary({ trip }: { trip: Trip }) {
  return (
    <div className="availability-item" style={{ display: "flex", alignItems: "center", gap: 16, background: "rgba(255,255,255,0.02)", padding: 16, borderRadius: 12, border: "1px solid var(--line)", cursor: "pointer" }}>
      <div style={{ background: "rgba(16, 185, 129, 0.1)", border: "1px solid rgba(16, 185, 129, 0.2)", width: 40, height: 40, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--ok)", flexShrink: 0 }}>
        <MapPin size={20} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <strong style={{ display: "block", color: "#fff", fontSize: 14, marginBottom: 4 }}>
          {trip.pickup_city} to {trip.drop_city}
          {trip.distance_km && (
            <span style={{ color: "var(--accent)", fontSize: 12, marginLeft: 8, fontWeight: 600 }}>
              ({trip.distance_km} km)
            </span>
          )}
        </strong>
        <span style={{ display: "block", color: "var(--muted)", fontSize: 13 }}>{trip.vehicle?.registration_number ?? "No vehicle"} • {trip.driver?.name ?? "No driver"}</span>
        <span style={{ display: "block", color: "var(--muted)", fontSize: 13 }}>{formatDate(trip.pickup_at)} to {formatDate(trip.estimated_drop_at)}</span>
      </div>
      <ChevronRight size={20} style={{ color: "var(--muted)" }} />
    </div>
  );
}

// Custom empty state icon can be added if needed, or stick to simple
function EmptyState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>;
}

function InputField(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const { label, ...inputProps } = props;
  return (
    <div className="field">
      <label>{label}</label>
      <input {...inputProps} />
    </div>
  );
}

function SelectField({
  children,
  label,
  value,
  onChange
}: {
  children: React.ReactNode;
  label: string;
  value: string | number;
  onChange: (value: string) => void;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </div>
  );
}

function Status({ value }: { value: string }) {
  const className = ["completed", "idle", "available", "eligible"].includes(value)
    ? "ok"
    : ["maintenance", "requested", "assigned"].includes(value)
      ? "warn"
      : ["cancelled", "offline", "suspended", "blocked"].includes(value)
        ? "danger"
        : "neutral";

  return <span className={`status ${className}`}>{labelize(value)}</span>;
}

function pageTitle(section: ConsoleSection) {
  const titles: Record<ConsoleSection, string> = {
    dashboard: "Operations Dashboard",
    trips: "Trip Dispatch Board",
    rentals: "Rental Module Console",
    "create-trip": "Create & Dispatch Trip",
    customers: "Corporate Customers",
    contracts: "Rate Contracts",
    billing: "Fleet Billing & Invoicing",
    vehicles: "Vehicle Management",
    drivers: "Driver Management",
    tracking: "Vehicle Tracking",
    availability: "Predictive Availability",
    compliance: "Compliance",
    ota: "OTA Bidding"
  };
  return titles[section];
}

function pageSubtitle(section: ConsoleSection) {
  const subtitles: Record<ConsoleSection, string> = {
    dashboard: "A live view of fleet capacity, dispatch load, and operational exceptions",
    trips: "View trip cards, filter dispatches, and transition trip statuses",
    rentals: "Manage corporate chauffeur rentals, package bookings, pricing, and driver checklists",
    "create-trip": "Create new OTA trips and assign drivers to pending dispatches",
    customers: "Maintain corporate accounts, billing identities, and primary contacts",
    contracts: "Manage versioned rate cards, package matrices, taxes, and allowances",
    billing: "Manage legal entities, draft invoices, tax preview, and payment allocations",
    vehicles: "Review vehicle state, assignment, current city, and next operational slot",
    drivers: "Track driver availability, assignment, base city, and active work",
    tracking: "Monitor each car by status, active trip, city, and predicted next location",
    availability: "See where every car can accept its next booking and when",
    compliance: "Prevent non-compliant cars from being used for outstation work",
    ota: "Prepare route acquisition decisions from OTA opportunities"
  };
  return subtitles[section];
}

function labelize(value: string) {
  return value.replaceAll("_", " ");
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

interface AutocompleteFieldProps {
  label: string;
  placeholder: string;
  value: string;
  onChange: (val: string) => void;
  onSelectSuggestion: (suggestion: { lat: number; lng: number; city: string }) => void;
  required?: boolean;
}

function AutocompleteField({
  label,
  placeholder,
  value,
  onChange,
  onSelectSuggestion,
  required
}: AutocompleteFieldProps) {
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!isTyping || value.length < 3) {
      setSuggestions([]);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&q=${encodeURIComponent(value)}&limit=5`);
        if (res.ok) {
          const data = await res.json();
          setSuggestions(data);
          setShowDropdown(true);
        }
      } catch (err) {
        console.error("Autocomplete search error:", err);
      } finally {
        setLoading(false);
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [value, isTyping]);

  const handleSelect = (item: any) => {
    const addr = item.address || {};
    const cityName = addr.city || addr.town || addr.village || addr.suburb || addr.county || item.display_name.split(",")[0];
    onSelectSuggestion({
      lat: Number(item.lat),
      lng: Number(item.lon),
      city: cityName
    });
    onChange(cityName);
    setIsTyping(false);
    setSuggestions([]);
    setShowDropdown(false);
  };

  return (
    <div className="field" ref={containerRef} style={{ position: "relative" }}>
      <label>{label}</label>
      <input
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => {
          setIsTyping(true);
          onChange(e.target.value);
        }}
        required={required}
        autoComplete="new-password"
      />
      {loading && (
        <div style={{ position: "absolute", right: 12, top: 38, fontSize: 11, color: "var(--muted)", pointerEvents: "none" }}>
          Searching...
        </div>
      )}
      {showDropdown && suggestions.length > 0 && (
        <ul className="autocomplete-dropdown" style={{
          position: "absolute",
          top: "100%",
          left: 0,
          right: 0,
          background: "var(--panel-strong)",
          border: "1px solid var(--line)",
          borderRadius: 8,
          boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
          listStyle: "none",
          padding: 0,
          margin: "4px 0 0 0",
          zIndex: 1000,
          maxHeight: 200,
          overflowY: "auto"
        }}>
          {suggestions.map((item, index) => (
            <li
              key={index}
              onClick={() => handleSelect(item)}
              style={{
                padding: "10px 12px",
                cursor: "pointer",
                borderBottom: index < suggestions.length - 1 ? "1px solid var(--line)" : "none",
                fontSize: 12,
                color: "#e2e8f0",
                lineHeight: "1.4",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap"
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.06)"}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "transparent"}
            >
              {item.display_name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TimePickerField({ label, name, required, value, onChange }: { label: string; name: string; required?: boolean; value?: string; onChange?: (val: string) => void }) {
  const [isOpen, setIsOpen] = useState(false);
  const [internalTime, setInternalTime] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  
  const selectedTime = value !== undefined ? value : internalTime;

  const times = useMemo(() => {
    const t = [];
    for (let h = 0; h < 24; h++) {
      for (let m = 0; m < 60; m += 15) {
        const hh = h.toString().padStart(2, '0');
        const mm = m.toString().padStart(2, '0');
        const period = h < 12 ? 'AM' : 'PM';
        const displayH = h % 12 === 0 ? 12 : h % 12;
        t.push({ value: `${hh}:${mm}`, label: `${displayH}:${mm} ${period}` });
      }
    }
    return t;
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="field" ref={containerRef} style={{ position: "relative" }}>
      <label>{label}</label>
      <div 
        onClick={() => setIsOpen(!isOpen)}
        style={{
          background: "rgba(0, 0, 0, 0.3)",
          border: `1px solid ${isOpen ? "var(--accent)" : "var(--line)"}`,
          boxShadow: isOpen ? "0 0 0 2px var(--accent-glow)" : "none",
          borderRadius: 8,
          padding: "12px 14px",
          color: selectedTime ? "#fff" : "rgba(255, 255, 255, 0.25)",
          cursor: "pointer",
          fontSize: 14,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center"
        }}
      >
        <span>{selectedTime ? times.find(t => t.value === selectedTime)?.label : "Select time..."}</span>
        <Clock size={16} color="var(--muted)" />
      </div>
      
      <input type="hidden" name={name} value={selectedTime} />

      {isOpen && (
        <ul className="time-picker-dropdown" style={{
          position: "absolute",
          top: "100%",
          left: 0,
          right: 0,
          background: "var(--panel-strong)",
          border: "1px solid var(--line)",
          borderRadius: 8,
          boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
          listStyle: "none",
          padding: 8,
          margin: "8px 0 0 0",
          zIndex: 1000,
          maxHeight: 220,
          overflowY: "auto",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 4
        }}>
          {times.map((t) => (
            <li
              key={t.value}
              onClick={() => {
                if (onChange) onChange(t.value);
                else setInternalTime(t.value);
                setIsOpen(false);
              }}
              style={{
                padding: "8px",
                cursor: "pointer",
                borderRadius: 4,
                fontSize: 13,
                color: selectedTime === t.value ? "#fff" : "#cbd5e1",
                background: selectedTime === t.value ? "var(--accent)" : "transparent",
                textAlign: "center",
                transition: "all 0.2s"
              }}
              onMouseEnter={(e) => {
                if (selectedTime !== t.value) e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.05)";
              }}
              onMouseLeave={(e) => {
                if (selectedTime !== t.value) e.currentTarget.style.backgroundColor = "transparent";
              }}
            >
              {t.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
