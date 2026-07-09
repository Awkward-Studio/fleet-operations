"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
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
  X
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  Availability,
  Driver,
  Summary,
  Trip,
  Vehicle,
  assignTrip,
  createTrip,
  createVehicle,
  getAvailability,
  getDrivers,
  getSummary,
  getTrips,
  getVehicles,
  transitionTrip
} from "@/lib/api";

type Role = "admin" | "dispatcher" | "accountant";
export type ConsoleSection = "dashboard" | "trips" | "vehicles" | "drivers" | "tracking" | "availability" | "compliance" | "ota";

const navItems = [
  { href: "/", section: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/trips", section: "trips", label: "Trips", icon: Route },
  { href: "/vehicles", section: "vehicles", label: "Vehicles", icon: Car },
  { href: "/drivers", section: "drivers", label: "Drivers", icon: Users },
  { href: "/tracking", section: "tracking", label: "Tracking", icon: MapPinned },
  { href: "/availability", section: "availability", label: "Availability", icon: CalendarClock },
  { href: "/compliance", section: "compliance", label: "Compliance", icon: ShieldCheck },
  { href: "/ota", section: "ota", label: "OTA Bidding", icon: Wifi }
] as const;

const tripTransitions = ["en_route_pickup", "active", "completed", "cancelled"];

export function FleetConsole({ section }: { section: ConsoleSection }) {
  const pathname = usePathname();
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
  const [loading, setLoading] = useState(true);

  // Search & Filter States
  const [vehicleSearch, setVehicleSearch] = useState("");
  const [vehicleStatusFilter, setVehicleStatusFilter] = useState("all");

  const [driverSearch, setDriverSearch] = useState("");
  const [driverStatusFilter, setDriverStatusFilter] = useState("all");

  const [tripSearch, setTripSearch] = useState("");
  const [tripStatusFilter, setTripStatusFilter] = useState("all");

  // Add Vehicle modal state
  const [isAddingVehicle, setIsAddingVehicle] = useState(false);

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
    return trips.filter((t) => {
      const matchesSearch =
        tripSearch === "" ||
        t.customer_name.toLowerCase().includes(tripSearch.toLowerCase()) ||
        t.pickup_city.toLowerCase().includes(tripSearch.toLowerCase()) ||
        t.drop_city.toLowerCase().includes(tripSearch.toLowerCase()) ||
        (t.ota_source && t.ota_source.toLowerCase().includes(tripSearch.toLowerCase()));
      const matchesStatus =
        tripStatusFilter === "all" || t.status === tripStatusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [trips, tripSearch, tripStatusFilter]);

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

  async function handleCreateTrip(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);

    try {
      await createTrip({
        customer_name: String(formData.get("customer_name")),
        pickup_city: String(formData.get("pickup_city")),
        drop_city: String(formData.get("drop_city")),
        pickup_at: String(formData.get("pickup_at")),
        estimated_drop_at: String(formData.get("estimated_drop_at")),
        ota_source: String(formData.get("ota_source")),
        fare_amount: String(formData.get("fare_amount"))
      });
      event.currentTarget.reset();
      await loadData();
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

  return (
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
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <h1>{pageTitle(section)}</h1>
            <p>{pageSubtitle(section)}</p>
          </div>
          <div className="topbar-actions">
            <button className="button secondary" type="button" onClick={loadData}>
              <RefreshCw size={16} />
              Refresh
            </button>
            <div className="role-select">
              <UserCheck size={18} />
              <select value={role} onChange={(event) => setRole(event.target.value as Role)} aria-label="Dashboard role">
                <option value="dispatcher">Dispatcher</option>
                <option value="admin">Admin</option>
                <option value="accountant">Accountant</option>
              </select>
            </div>
          </div>
        </header>

        <main className="main">
          {error ? <div className="error">{error}</div> : null}
          {loading ? <div className="notice">Loading fleet data from Django API...</div> : null}

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
              <div className="search-filter-bar">
                <div className="search-input-wrapper">
                  <Search size={18} className="search-icon" />
                  <input
                    type="text"
                    placeholder="Search by customer name, pickup city, drop city..."
                    value={tripSearch}
                    onChange={(e) => setTripSearch(e.target.value)}
                  />
                </div>
                <div className="filter-select-wrapper">
                  <Filter size={16} style={{ marginRight: 4, color: "var(--muted)" }} />
                  <select
                    value={tripStatusFilter}
                    onChange={(e) => setTripStatusFilter(e.target.value)}
                  >
                    <option value="all">All Statuses</option>
                    <option value="requested">Requested</option>
                    <option value="assigned">Assigned</option>
                    <option value="en_route_pickup">En route to pickup</option>
                    <option value="active">Active</option>
                    <option value="completed">Completed</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                </div>
              </div>
              <TripsView
                role={role}
                trips={filteredTrips}
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
                onTransition={handleTransition}
                onCreateTrip={handleCreateTrip}
              />
            </>
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
              <DriversView drivers={filteredDrivers} trips={trips} />
            </>
          ) : null}

          {section === "tracking" ? <TrackingView vehicles={vehicles} activeTrips={activeTrips} availability={availability} /> : null}
          {section === "availability" ? <AvailabilityView availability={availability} vehicles={vehicles} /> : null}
          {section === "compliance" ? <ComplianceView vehicles={vehicles} /> : null}
          {section === "ota" ? <OtaView availability={availability} vehicles={vehicles} unassignedTrips={unassignedTrips} /> : null}
        </main>
      </div>

      {/* Add Vehicle Modal Overlay */}
      {isAddingVehicle && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Add New Vehicle</h3>
              <button className="modal-close-btn" onClick={() => setIsAddingVehicle(false)} aria-label="Close modal">
                <X size={20} />
              </button>
            </div>
            <div className="modal-body">
              <AddVehicleForm
                drivers={drivers}
                onSubmit={handleCreateVehicleSubmit}
                onCancel={() => setIsAddingVehicle(false)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
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
        <Metric icon={<Car size={19} />} label="Idle vehicles" value={summary?.vehicles.idle ?? 0} />
        <Metric icon={<UserCheck size={19} />} label="Available drivers" value={summary?.drivers.available ?? 0} />
        <Metric icon={<CalendarClock size={19} />} label="Unassigned trips" value={summary?.trips.unassigned ?? 0} />
        <Metric icon={<ShieldCheck size={19} />} label="Compliance alerts" value={summary?.compliance_alerts ?? 0} />
      </section>

      <section className="grid">
        <Panel title="Live Operations">
          <div className="operation-board">
            {vehicles.slice(0, 9).map((vehicle) => {
              const trip = activeTrips.find((item) => item.vehicle?.id === vehicle.id);
              return (
                <div className="vehicle-tile" key={vehicle.id}>
                  <div>
                    <strong>{vehicle.registration_number}</strong>
                    <span>{vehicle.make} {vehicle.model}</span>
                  </div>
                  <Status value={vehicle.status} />
                  <p>{trip ? `${trip.pickup_city} to ${trip.drop_city}` : `Standing by in ${vehicle.current_city}`}</p>
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
                <div className="alert-row" key={vehicle.id}>
                  <AlertTriangle size={18} />
                  <span>{vehicle.registration_number}</span>
                  <strong>{vehicle.compliance_blockers.join(", ")}</strong>
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
  unassignedTrips: Trip[];
  assignableVehicles: Vehicle[];
  availableDrivers: Driver[];
  selectedTrip: number | null;
  selectedVehicle: number | null;
  selectedDriver: number | null;
  onTripChange: (value: number) => void;
  onVehicleChange: (value: number) => void;
  onDriverChange: (value: number) => void;
  onAssign: () => void;
  onTransition: (tripId: number, status: string) => void;
  onCreateTrip: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="grid">
      <Panel title="Trip Dispatch">
        <div className="stack">
          {props.unassignedTrips.length > 0 ? (
            <div className="form-grid">
              <SelectField label="Trip" value={props.selectedTrip ?? ""} onChange={(value) => props.onTripChange(Number(value))}>
                <option value="" disabled>Select trip</option>
                {props.unassignedTrips.map((trip) => (
                  <option key={trip.id} value={trip.id}>
                    {trip.pickup_city} to {trip.drop_city} - {trip.customer_name}
                  </option>
                ))}
              </SelectField>
              <SelectField label="Vehicle" value={props.selectedVehicle ?? ""} onChange={(value) => props.onVehicleChange(Number(value))}>
                <option value="" disabled>Select vehicle</option>
                {props.assignableVehicles.map((vehicle) => (
                  <option key={vehicle.id} value={vehicle.id}>
                    {vehicle.registration_number} - {vehicle.category} - {vehicle.current_city}
                  </option>
                ))}
              </SelectField>
              <SelectField label="Driver" value={props.selectedDriver ?? ""} onChange={(value) => props.onDriverChange(Number(value))}>
                <option value="" disabled>Select driver</option>
                {props.availableDrivers.map((driver) => (
                  <option key={driver.id} value={driver.id}>
                    {driver.name} - {driver.home_base}
                  </option>
                ))}
              </SelectField>
              <div className="actions inline-action">
                <button className="button" type="button" onClick={props.onAssign}>
                  <ClipboardCheck size={16} />
                  Assign Trip
                </button>
              </div>
            </div>
          ) : (
            <div className="notice" style={{ marginBottom: 12 }}>All trips currently assigned. Create new OTA trips on the right.</div>
          )}
          <TripsTable trips={props.trips} onTransition={props.onTransition} />
        </div>
      </Panel>

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
  onAddClick
}: {
  vehicles: Vehicle[];
  availability: Availability[];
  trips: Trip[];
  onAddClick: () => void;
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
  onSubmit,
  onCancel
}: {
  drivers: Driver[];
  onSubmit: (payload: any) => Promise<void>;
  onCancel: () => void;
}) {
  const [regNumber, setRegNumber] = useState("");
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [category, setCategory] = useState("Sedan");
  const [currentCity, setCurrentCity] = useState("");
  const [odometerKm, setOdometerKm] = useState(0);
  const [assignedDriverId, setAssignedDriverId] = useState<number | null>(null);

  // Default dates (today + 1 year)
  const getFutureDate = (years: number) => {
    const d = new Date();
    d.setFullYear(d.getFullYear() + years);
    return d.toISOString().split("T")[0];
  };

  const [permitExp, setPermitExp] = useState(getFutureDate(1));
  const [insuranceExp, setInsuranceExp] = useState(getFutureDate(1));
  const [pollutionExp, setPollutionExp] = useState(getFutureDate(1));
  const [fitnessExp, setFitnessExp] = useState(getFutureDate(1));

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
          `Detected Plate: ${data.plate} (${Math.round(data.confidence * 100)}% confidence)${
            data.simulated ? " [SIMULATION]" : ""
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
      status: "idle",
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
      {/* ALPR scanner section */}
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
          <label>Odometer (KM)</label>
          <input
            type="number"
            min="0"
            value={odometerKm}
            onChange={(e) => setOdometerKm(Number(e.target.value))}
          />
        </div>
        <div className="field" style={{ gridColumn: "span 2" }}>
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
          Save Vehicle
        </button>
      </div>
    </form>
  );
}

function DriversView({ drivers, trips }: { drivers: Driver[]; trips: Trip[] }) {
  return (
    <Panel title="Driver Roster">
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
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
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
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Trip</th>
            <th>Timing</th>
            <th>Assignment</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {trips.map((trip) => (
            <tr key={trip.id}>
              <td><strong>{trip.pickup_city} to {trip.drop_city}</strong><br />{trip.customer_name} {trip.ota_source ? `- ${trip.ota_source}` : ""}</td>
              <td>{formatDate(trip.pickup_at)}<br />Drop: {formatDate(trip.estimated_drop_at)}</td>
              <td>{trip.vehicle?.registration_number ?? "No vehicle"}<br />{trip.driver?.name ?? "No driver"}</td>
              <td><Status value={trip.status} /></td>
              <td>
                <select value="" onChange={(event) => onTransition(trip.id, event.target.value)} aria-label={`Update ${trip.customer_name} status`}>
                  <option value="" disabled>Update</option>
                  {tripTransitions.map((status) => (
                    <option key={status} value={status}>{labelize(status)}</option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TripForm({ onCreateTrip }: { onCreateTrip: (event: FormEvent<HTMLFormElement>) => void }) {
  return (
    <form className="stack" onSubmit={onCreateTrip}>
      <div className="form-grid single">
        <InputField label="Customer" name="customer_name" required />
        <InputField label="OTA Source" name="ota_source" placeholder="MMT" />
        <InputField label="Pickup City" name="pickup_city" required />
        <InputField label="Drop City" name="drop_city" required />
        <InputField label="Pickup At" name="pickup_at" type="datetime-local" required />
        <InputField label="Drop At" name="estimated_drop_at" type="datetime-local" required />
        <InputField label="Fare" name="fare_amount" type="number" min="0" step="0.01" defaultValue="0" />
      </div>
      <div className="actions">
        <button className="button" type="submit">
          <Plus size={16} />
          Create Trip
        </button>
      </div>
    </form>
  );
}

function Panel({ children, title, action }: { children: React.ReactNode; title: string; action?: React.ReactNode }) {
  return (
    <section className="section">
      <div className="section-header">
        <h2>{title}</h2>
        {action}
      </div>
      <div className="section-body">{children}</div>
    </section>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="metric">
      <span>{icon} {label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AvailabilityItem({ item }: { item: Availability }) {
  return (
    <div className="availability-item">
      <strong>{item.registration_number} - {item.category}</strong>
      <span>{item.available_city} after {formatDate(item.available_from)}</span>
      <span>{item.driver_name ?? "No driver assigned"}</span>
      {item.compliance_blockers.length ? <span style={{ color: "var(--danger)", fontWeight: 600 }}>Blocked: {item.compliance_blockers.join(", ")}</span> : null}
    </div>
  );
}

function TripSummary({ trip }: { trip: Trip }) {
  return (
    <div className="availability-item">
      <strong>{trip.pickup_city} to {trip.drop_city}</strong>
      <span>{trip.vehicle?.registration_number ?? "No vehicle"} - {trip.driver?.name ?? "No driver"}</span>
      <span>{formatDate(trip.pickup_at)} to {formatDate(trip.estimated_drop_at)}</span>
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
    trips: "Trip Dispatch",
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
    trips: "Create trips, assign vehicles and drivers, and move trips through their lifecycle",
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
