"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  AlertTriangle,
  Building2,
  CalendarClock,
  Car,
  CheckCircle,
  CheckCircle2,
  ChevronDown,
  Clock,
  DollarSign,
  FileText,
  Filter,
  Fuel,
  Gauge,
  KeyRound,
  LayoutDashboard,
  Loader2,
  MapPin,
  MapPinned,
  Package,
  Pencil,
  Plus,
  Printer,
  RefreshCw,
  Route,
  Search,
  ShieldCheck,
  Tag,
  Trash2,
  Upload,
  UserCheck,
  UserPlus,
  Users,
  Wifi,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/AuthContext";
import { AuthGuard } from "@/components/AuthGuard";
import { Driver, Vehicle, getDrivers, getVehicles } from "@/lib/api";
import {
  CorporateCustomer,
  RentalBooking,
  RentalInvoice,
  RentalPackage,
  RentalPricingRule,
  RentalSummary,
  assignRentalBooking,
  cancelRentalBooking,
  createCorporateCustomer,
  createRentalBooking,
  createRentalPackage,
  deletePricingRule,
  endRentalBooking,
  getCorporateCustomers,
  getPricingRules,
  getRentalBookings,
  getRentalPackages,
  getRentalSummary,
  savePricingRule,
  startRentalBooking,
  submitFuelLog,
} from "@/lib/rentalsApi";

export type RentalSection =
  | "dashboard"
  | "bookings"
  | "customers"
  | "packages"
  | "pricing"
  | "history";

const mainNavItems = [
  { href: "/", label: "Fleet Dashboard", icon: LayoutDashboard },
  { href: "/trips", label: "Fleet Trips", icon: Route },
  { href: "/rentals", label: "Rentals", icon: KeyRound },
  { href: "/vehicles", label: "Vehicles", icon: Car },
  { href: "/drivers", label: "Drivers", icon: Users },
  { href: "/tracking", label: "Tracking", icon: MapPinned },
] as const;

const rentalSubNavItems = [
  { href: "/rentals", section: "dashboard", label: "Rental Dashboard", icon: LayoutDashboard },
  { href: "/rentals/bookings", section: "bookings", label: "Bookings", icon: KeyRound },
  { href: "/rentals/customers", section: "customers", label: "Corporate CRM", icon: Building2 },
  { href: "/rentals/packages", section: "packages", label: "Packages", icon: Package },
  { href: "/rentals/pricing", section: "pricing", label: "City & Corp Pricing", icon: DollarSign },
  { href: "/rentals/history", section: "history", label: "History & Invoices", icon: FileText },
] as const;

export function RentalConsole({ section }: { section: RentalSection }) {
  const { user, logout } = useAuth();
  const [profileOpen, setProfileOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  const [summary, setSummary] = useState<RentalSummary | null>(null);
  const [bookings, setBookings] = useState<RentalBooking[]>([]);
  const [customers, setCustomers] = useState<CorporateCustomer[]>([]);
  const [packages, setPackages] = useState<RentalPackage[]>([]);
  const [pricingRules, setPricingRules] = useState<RentalPricingRule[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modal states
  const [isBookingModalOpen, setIsBookingModalOpen] = useState(false);
  const [isCustomerModalOpen, setIsCustomerModalOpen] = useState(false);
  const [isPackageModalOpen, setIsPackageModalOpen] = useState(false);
  const [isPricingModalOpen, setIsPricingModalOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState<{ booking: RentalBooking; invoice: RentalInvoice } | null>(null);
  const [checklistModalBooking, setChecklistModalBooking] = useState<{ booking: RentalBooking; type: "start" | "end" } | null>(null);

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [cityFilter, setCityFilter] = useState("all");

  async function loadAllData() {
    setLoading(true);
    setError(null);
    try {
      const [sumData, bookData, custData, pkgData, ruleData, vehData, drvData] = await Promise.all([
        getRentalSummary(),
        getRentalBookings(),
        getCorporateCustomers(),
        getRentalPackages(),
        getPricingRules(),
        getVehicles(),
        getDrivers(),
      ]);
      setSummary(sumData);
      setBookings(bookData);
      setCustomers(custData);
      setPackages(pkgData);
      setPricingRules(ruleData);
      setVehicles(vehData);
      setDrivers(drvData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load rental data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAllData();
  }, []);

  function triggerSuccess(msg: string) {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 4000);
  }

  return (
    <AuthGuard>
      <div className="console-shell">
        <aside className="sidebar">
          <div className="sidebar-brand">
            <span className="brand-mark">
              <KeyRound size={20} />
            </span>
            <div>
              <strong>Rental Console</strong>
              <span>Index Fleet Module</span>
            </div>
          </div>

          <nav className="sidebar-nav" aria-label="Rental console navigation">
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, padding: "8px 12px 4px" }}>
              Main Navigation
            </div>
            {mainNavItems.map((item) => {
              const Icon = item.icon;
              const active = item.href === "/rentals" || (item.href === "/" && pathname === "/");
              return (
                <Link className={active ? "active" : ""} href={item.href} key={item.href}>
                  <Icon size={17} />
                  {item.label}
                </Link>
              );
            })}

            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, padding: "16px 12px 4px" }}>
              Rental Sub-Modules
            </div>
            {rentalSubNavItems.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href || (item.section === "dashboard" && pathname === "/rentals");
              return (
                <Link className={active ? "active" : ""} href={item.href} key={item.href} style={{ paddingLeft: 20 }}>
                  <Icon size={15} />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div style={{ marginTop: "auto", position: "relative" }}>
            <div
              onClick={() => setProfileOpen(!profileOpen)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "12px",
                background: "rgba(255,255,255,0.03)",
                borderRadius: 12,
                border: "1px solid var(--line)",
                cursor: "pointer",
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  background: "linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%)",
                  display: "flex",
                  alignItems: "center",
                  fontSize: 13,
                  fontWeight: "bold",
                  color: "#fff",
                  justifyContent: "center",
                }}
              >
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
              <div
                style={{
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
                  zIndex: 1000,
                }}
              >
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
                    gap: 8,
                  }}
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
              <h1>{sectionTitle(section)}</h1>
              <p>{sectionSubtitle(section)}</p>
            </div>
            <div className="topbar-actions" style={{ gap: 12 }}>
              <button
                className="button"
                onClick={() => setIsBookingModalOpen(true)}
                style={{ display: "flex", alignItems: "center", gap: 8 }}
              >
                <Plus size={16} /> New Rental Booking
              </button>
            </div>
          </header>

          <main className="main">
            {error && <div className="error">{error}</div>}
            {successMsg && (
              <div
                style={{
                  position: "fixed",
                  bottom: 24,
                  right: 24,
                  background: "var(--ok)",
                  color: "#fff",
                  padding: "14px 20px",
                  borderRadius: 8,
                  boxShadow: "var(--card-shadow)",
                  zIndex: 9999,
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  fontWeight: 500,
                  fontSize: 14,
                }}
              >
                <CheckCircle2 size={20} />
                {successMsg}
              </div>
            )}

            {loading ? (
              <div className="notice">Loading rental workspace & configuration...</div>
            ) : (
              <>
                {section === "dashboard" && (
                  <RentalDashboardView
                    summary={summary}
                    bookings={bookings}
                    vehicles={vehicles}
                    drivers={drivers}
                    onOpenBooking={() => setIsBookingModalOpen(true)}
                    onOpenChecklist={(booking, type) => setChecklistModalBooking({ booking, type })}
                    onViewInvoice={(booking) => {
                      if (booking.invoice) {
                        setSelectedInvoice({ booking, invoice: booking.invoice });
                      }
                    }}
                  />
                )}

                {section === "bookings" && (
                  <RentalBookingsView
                    bookings={bookings}
                    vehicles={vehicles}
                    drivers={drivers}
                    onNewBooking={() => setIsBookingModalOpen(true)}
                    onRefresh={loadAllData}
                    onOpenChecklist={(booking, type) => setChecklistModalBooking({ booking, type })}
                    onViewInvoice={(booking) => {
                      if (booking.invoice) {
                        setSelectedInvoice({ booking, invoice: booking.invoice });
                      }
                    }}
                    triggerSuccess={triggerSuccess}
                  />
                )}

                {section === "customers" && (
                  <CorporateCustomersView
                    customers={customers}
                    onAddClick={() => setIsCustomerModalOpen(true)}
                    pricingRules={pricingRules}
                  />
                )}

                {section === "packages" && (
                  <RentalPackagesView
                    packages={packages}
                    onAddClick={() => setIsPackageModalOpen(true)}
                  />
                )}

                {section === "pricing" && (
                  <PricingSystemView
                    pricingRules={pricingRules}
                    customers={customers}
                    packages={packages}
                    onAddClick={() => setIsPricingModalOpen(true)}
                    onRefresh={loadAllData}
                    triggerSuccess={triggerSuccess}
                  />
                )}

                {section === "history" && (
                  <RentalHistoryView
                    bookings={bookings}
                    onViewInvoice={(booking) => {
                      if (booking.invoice) {
                        setSelectedInvoice({ booking, invoice: booking.invoice });
                      }
                    }}
                  />
                )}


              </>
            )}
          </main>
        </div>
      </div>

      {/* New Booking Modal */}
      {isBookingModalOpen && (
        <NewBookingModal
          customers={customers}
          packages={packages}
          vehicles={vehicles}
          drivers={drivers}
          onClose={() => setIsBookingModalOpen(false)}
          onSuccess={() => {
            setIsBookingModalOpen(false);
            loadAllData();
            triggerSuccess("Rental booking created successfully!");
          }}
        />
      )}

      {/* New Corporate Customer Modal */}
      {isCustomerModalOpen && (
        <NewCustomerModal
          onClose={() => setIsCustomerModalOpen(false)}
          onSuccess={() => {
            setIsCustomerModalOpen(false);
            loadAllData();
            triggerSuccess("Corporate customer added to CRM!");
          }}
        />
      )}

      {/* New Package Modal */}
      {isPackageModalOpen && (
        <NewPackageModal
          onClose={() => setIsPackageModalOpen(false)}
          onSuccess={() => {
            setIsPackageModalOpen(false);
            loadAllData();
            triggerSuccess("Rental package created!");
          }}
        />
      )}

      {/* New Pricing Rule Modal */}
      {isPricingModalOpen && (
        <NewPricingRuleModal
          customers={customers}
          packages={packages}
          onClose={() => setIsPricingModalOpen(false)}
          onSuccess={() => {
            setIsPricingModalOpen(false);
            loadAllData();
            triggerSuccess("Pricing rule saved!");
          }}
        />
      )}

      {/* Checklist Photo Upload Drawer / Modal */}
      {checklistModalBooking && (
        <ChecklistModal
          booking={checklistModalBooking.booking}
          type={checklistModalBooking.type}
          onClose={() => setChecklistModalBooking(null)}
          onSuccess={() => {
            setChecklistModalBooking(null);
            loadAllData();
            triggerSuccess(`Pre-rental ${checklistModalBooking.type} checklist submitted successfully!`);
          }}
        />
      )}

      {/* Printable Invoice Modal */}
      {selectedInvoice && (
        <InvoiceModal
          booking={selectedInvoice.booking}
          invoice={selectedInvoice.invoice}
          onClose={() => setSelectedInvoice(null)}
        />
      )}
    </AuthGuard>
  );
}

function sectionTitle(section: RentalSection): string {
  switch (section) {
    case "dashboard":
      return "Rental Module Dashboard";
    case "bookings":
      return "Rental Bookings";
    case "customers":
      return "Corporate Clients CRM";
    case "packages":
      return "Rental Packages & Offerings";
    case "pricing":
      return "City & Corporate Pricing Engine";
    case "history":
      return "Rental History & Invoices";

  }
}

function sectionSubtitle(section: RentalSection): string {
  switch (section) {
    case "dashboard":
      return "Chauffeur & Corporate rental overview, active trips, upcoming pickups, and alerts.";
    case "bookings":
      return "Manage individual & corporate rental bookings, vehicle assignments, and trip status.";
    case "customers":
      return "Business accounts, GST & PAN registry, custom pricing profiles.";
    case "packages":
      return "Hourly/KM packages, Airport Transfers, and Outstation overnight rentals.";
    case "pricing":
      return "Configurable hierarchy: Company -> City -> Package -> Price & extra rates.";
    case "history":
      return "Completed rental records, distance logs, and auto-generated invoices.";

  }
}

/* ==========================================================================
   SUB-VIEWS
   ========================================================================== */

function RentalDashboardView({
  summary,
  bookings,
  vehicles,
  drivers,
  onOpenBooking,
  onOpenChecklist,
  onViewInvoice,
}: {
  summary: RentalSummary | null;
  bookings: RentalBooking[];
  vehicles: Vehicle[];
  drivers: Driver[];
  onOpenBooking: () => void;
  onOpenChecklist: (booking: RentalBooking, type: "start" | "end") => void;
  onViewInvoice: (booking: RentalBooking) => void;
}) {
  const cards = summary?.cards || {
    active_rentals: bookings.filter((b) => ["started", "in_progress"].includes(b.status)).length,
    upcoming_rentals: bookings.filter((b) => ["pending", "ready", "vehicle_assigned", "driver_assigned"].includes(b.status)).length,
    available_vehicles: vehicles.filter((v) => v.status === "idle").length,
    available_drivers: drivers.filter((d) => d.status === "available").length,
    rentals_ending_today: 1,
  };

  return (
    <div style={{ display: "grid", gap: 24 }}>
      {/* Metric Cards */}
      <section className="metrics" style={{ gridTemplateColumns: "repeat(5, minmax(0, 1fr))" }}>
        <MetricCard icon={<KeyRound size={16} />} label="ACTIVE RENTALS" value={cards.active_rentals} color="#3b82f6" />
        <MetricCard icon={<Clock size={16} />} label="UPCOMING PICKUPS" value={cards.upcoming_rentals} color="#8b5cf6" />
        <MetricCard icon={<Car size={16} />} label="AVAILABLE VEHICLES" value={cards.available_vehicles} color="#10b981" />
        <MetricCard icon={<Users size={16} />} label="AVAILABLE DRIVERS" value={cards.available_drivers} color="#eab308" />
        <MetricCard icon={<CalendarClock size={16} />} label="ENDING TODAY" value={cards.rentals_ending_today} color="#ec4899" />
      </section>

      {/* Alerts */}
      {summary?.alerts && summary.alerts.length > 0 && (
        <div className="section" style={{ border: "1px solid rgba(239, 68, 68, 0.3)" }}>
          <div className="section-header" style={{ background: "rgba(239, 68, 68, 0.08)" }}>
            <h2 style={{ color: "var(--danger)" }}>
              <AlertTriangle size={18} /> Overdue & Alert Notifications ({summary.alerts.length})
            </h2>
          </div>
          <div className="section-body" style={{ display: "grid", gap: 12 }}>
            {summary.alerts.map((alert) => (
              <div key={alert.id} className="alert-row" style={{ borderColor: "rgba(239, 68, 68, 0.2)", color: "var(--danger)" }}>
                <AlertTriangle size={18} />
                <span>{alert.title}</span>
                <strong>{alert.description}</strong>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Tables Grid */}
      <div className="grid">
        <div className="section">
          <div className="section-header">
            <h2>
              <KeyRound size={18} style={{ color: "var(--accent)" }} /> Today's & Active Rentals
            </h2>
          </div>
          <div className="section-body" style={{ padding: 0 }}>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Booking #</th>
                    <th>Customer</th>
                    <th>Package</th>
                    <th>Pickup Time</th>
                    <th>Vehicle & Driver</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {bookings.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: "center", color: "var(--muted)", padding: 32 }}>
                        No rental bookings found. Click "New Rental Booking" to create one.
                      </td>
                    </tr>
                  ) : (
                    bookings.slice(0, 8).map((b) => (
                      <tr key={b.id}>
                        <td>
                          <strong style={{ color: "#fff" }}>{b.booking_number}</strong>
                          <span style={{ display: "block", fontSize: 11, color: "var(--muted)" }}>
                            {b.customer_type === "corporate" ? "Corporate" : "Individual"}
                          </span>
                        </td>
                        <td>
                          <div style={{ fontWeight: 600, color: "#fff" }}>{b.customer_name}</div>
                          <div style={{ fontSize: 12, color: "var(--muted)" }}>{b.customer_phone}</div>
                        </td>
                        <td>
                          <span className="status neutral">{b.package?.name || "Standard"}</span>
                        </td>
                        <td>
                          <div>{new Date(b.pickup_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
                          <div style={{ fontSize: 11, color: "var(--muted)" }}>{b.pickup_city}</div>
                        </td>
                        <td>
                          {b.vehicle ? (
                            <div style={{ fontSize: 13, fontWeight: 500 }}>
                              🚗 {b.vehicle.registration_number} ({b.vehicle.make})
                            </div>
                          ) : (
                            <span style={{ color: "var(--warn)", fontSize: 12 }}>Unassigned Vehicle</span>
                          )}
                          {b.driver ? (
                            <div style={{ fontSize: 12, color: "var(--muted)" }}>👨‍✈️ {b.driver.name}</div>
                          ) : (
                            <span style={{ color: "var(--warn)", fontSize: 12, display: "block" }}>Unassigned Driver</span>
                          )}
                        </td>
                        <td>
                          <RentalStatusPill status={b.status} />
                        </td>
                        <td>
                          {["ready", "vehicle_assigned", "driver_assigned"].includes(b.status) && (
                            <button
                              className="button secondary"
                              style={{ padding: "4px 10px", fontSize: 12, minHeight: 32 }}
                              onClick={() => onOpenChecklist(b, "start")}
                            >
                              Start Trip
                            </button>
                          )}
                          {["started", "in_progress"].includes(b.status) && (
                            <button
                              className="button"
                              style={{ padding: "4px 10px", fontSize: 12, minHeight: 32, background: "var(--ok)" }}
                              onClick={() => onOpenChecklist(b, "end")}
                            >
                              End Trip & Bill
                            </button>
                          )}
                          {b.status === "completed" && b.invoice && (
                            <button
                              className="button secondary"
                              style={{ padding: "4px 10px", fontSize: 12, minHeight: 32 }}
                              onClick={() => onViewInvoice(b)}
                            >
                              <FileText size={13} /> Invoice
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Sidebar Availability List */}
        <div style={{ display: "grid", gap: 24 }}>
          <div className="section">
            <div className="section-header">
              <h2>
                <Car size={18} style={{ color: "var(--ok)" }} /> Ready Vehicles ({vehicles.filter((v) => v.status === "idle").length})
              </h2>
            </div>
            <div className="section-body" style={{ display: "grid", gap: 10 }}>
              {vehicles
                .filter((v) => v.status === "idle")
                .slice(0, 5)
                .map((v) => (
                  <div key={v.id} className="availability-item">
                    <strong style={{ display: "flex", justifyContent: "space-between" }}>
                      {v.registration_number} <span className="status ok">{v.category}</span>
                    </strong>
                    <span>
                      {v.make} {v.model} • {v.current_city}
                    </span>
                  </div>
                ))}
            </div>
          </div>

          <div className="section">
            <div className="section-header">
              <h2>
                <Users size={18} style={{ color: "var(--warn)" }} /> Ready Drivers ({drivers.filter((d) => d.status === "available").length})
              </h2>
            </div>
            <div className="section-body" style={{ display: "grid", gap: 10 }}>
              {drivers
                .filter((d) => d.status === "available")
                .slice(0, 5)
                .map((d) => (
                  <div key={d.id} className="availability-item">
                    <strong style={{ display: "flex", justifyContent: "space-between" }}>
                      {d.name} <span className="status ok">⭐ {d.rating}</span>
                    </strong>
                    <span>
                      📞 {d.phone} • Base: {d.home_base}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function RentalBookingsView({
  bookings,
  vehicles,
  drivers,
  onNewBooking,
  onRefresh,
  onOpenChecklist,
  onViewInvoice,
  triggerSuccess,
}: {
  bookings: RentalBooking[];
  vehicles: Vehicle[];
  drivers: Driver[];
  onNewBooking: () => void;
  onRefresh: () => void;
  onOpenChecklist: (booking: RentalBooking, type: "start" | "end") => void;
  onViewInvoice: (booking: RentalBooking) => void;
  triggerSuccess: (msg: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [assigningBooking, setAssigningBooking] = useState<RentalBooking | null>(null);
  const [selectedVehId, setSelectedVehId] = useState<number | "">("");
  const [selectedDrvId, setSelectedDrvId] = useState<number | "">("");

  const filtered = useMemo(() => {
    return bookings.filter((b) => {
      const matchText =
        search === "" ||
        b.booking_number.toLowerCase().includes(search.toLowerCase()) ||
        b.customer_name.toLowerCase().includes(search.toLowerCase()) ||
        b.pickup_city.toLowerCase().includes(search.toLowerCase());
      const matchStatus = statusFilter === "all" || b.status === statusFilter;
      return matchText && matchStatus;
    });
  }, [bookings, search, statusFilter]);

  async function handleAssignSubmit() {
    if (!assigningBooking) return;
    try {
      await assignRentalBooking(
        assigningBooking.id,
        selectedVehId ? Number(selectedVehId) : undefined,
        selectedDrvId ? Number(selectedDrvId) : undefined
      );
      setAssigningBooking(null);
      onRefresh();
      triggerSuccess("Vehicle and Driver assigned to booking!");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Assignment failed.");
    }
  }

  async function handleCancelBooking(id: number) {
    if (!confirm("Are you sure you want to cancel this booking?")) return;
    try {
      await cancelRentalBooking(id);
      onRefresh();
      triggerSuccess("Rental booking cancelled.");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Cancellation failed.");
    }
  }

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div className="search-filter-bar">
        <div className="search-input-wrapper">
          <Search size={18} className="search-icon" />
          <input
            type="text"
            placeholder="Search bookings by number, customer, city..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="filter-select-wrapper">
          <Filter size={16} style={{ color: "var(--muted)" }} />
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="ready">Ready</option>
            <option value="started">Started / Active</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
      </div>

      <div className="section">
        <div className="section-header">
          <h2>Rental Bookings ({filtered.length})</h2>
          <button className="button" onClick={onNewBooking}>
            <Plus size={16} /> Create Booking
          </button>
        </div>
        <div className="section-body" style={{ padding: 0 }}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Booking Details</th>
                  <th>Customer Info</th>
                  <th>Pickup & Drop</th>
                  <th>Package & Category</th>
                  <th>Vehicle & Driver</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((b) => (
                  <tr key={b.id}>
                    <td>
                      <strong style={{ color: "#fff", display: "block" }}>{b.booking_number}</strong>
                      <span style={{ fontSize: 11, color: "var(--muted)" }}>
                        Created: {new Date(b.created_at).toLocaleDateString()}
                      </span>
                    </td>
                    <td>
                      <strong style={{ color: "#fff" }}>{b.customer_name}</strong>
                      <div style={{ fontSize: 12, color: "var(--muted)" }}>📞 {b.customer_phone}</div>
                      {b.corporate_customer && (
                        <span className="status ok" style={{ marginTop: 4, fontSize: 9 }}>
                          🏢 {b.corporate_customer.name}
                        </span>
                      )}
                    </td>
                    <td>
                      <div style={{ fontWeight: 500 }}>
                        📍 {b.pickup_address} ({b.pickup_city})
                      </div>
                      <div style={{ fontSize: 11, color: "var(--muted)" }}>
                        🕒 {new Date(b.pickup_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
                      </div>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: "var(--accent)" }}>{b.package?.name}</div>
                      <span className="status neutral" style={{ marginTop: 2 }}>
                        {b.vehicle_category}
                      </span>
                    </td>
                    <td>
                      {b.vehicle ? (
                        <div style={{ fontSize: 13 }}>🚗 {b.vehicle.registration_number}</div>
                      ) : (
                        <span style={{ color: "var(--warn)", fontSize: 12, display: "block" }}>No Vehicle</span>
                      )}
                      {b.driver ? (
                        <div style={{ fontSize: 12, color: "var(--muted)" }}>👨‍✈️ {b.driver.name}</div>
                      ) : (
                        <span style={{ color: "var(--warn)", fontSize: 12, display: "block" }}>No Driver</span>
                      )}
                      {(!b.vehicle || !b.driver) && b.status !== "cancelled" && b.status !== "completed" && (
                        <button
                          className="button secondary"
                          style={{ padding: "2px 8px", fontSize: 11, minHeight: 26, marginTop: 4 }}
                          onClick={() => {
                            setAssigningBooking(b);
                            setSelectedVehId(b.vehicle?.id || "");
                            setSelectedDrvId(b.driver?.id || "");
                          }}
                        >
                          Assign
                        </button>
                      )}
                    </td>
                    <td>
                      <RentalStatusPill status={b.status} />
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        {["ready", "vehicle_assigned", "driver_assigned"].includes(b.status) && (
                          <button
                            className="button secondary"
                            style={{ padding: "4px 8px", fontSize: 12, minHeight: 30 }}
                            onClick={() => onOpenChecklist(b, "start")}
                          >
                            Start
                          </button>
                        )}
                        {["started", "in_progress"].includes(b.status) && (
                          <button
                            className="button"
                            style={{ padding: "4px 8px", fontSize: 12, minHeight: 30, background: "var(--ok)" }}
                            onClick={() => onOpenChecklist(b, "end")}
                          >
                            End & Invoice
                          </button>
                        )}
                        {b.status === "completed" && b.invoice && (
                          <button
                            className="button secondary"
                            style={{ padding: "4px 8px", fontSize: 12, minHeight: 30 }}
                            onClick={() => onViewInvoice(b)}
                          >
                            <FileText size={12} /> Invoice
                          </button>
                        )}
                        {b.status !== "completed" && b.status !== "cancelled" && (
                          <button
                            className="button secondary"
                            style={{ padding: "4px 8px", fontSize: 12, minHeight: 30, color: "var(--danger)" }}
                            onClick={() => handleCancelBooking(b.id)}
                          >
                            Cancel
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Assign Modal */}
      {assigningBooking && (
        <div className="modal-backdrop" style={modalBackdropStyle}>
          <div className="modal-card" style={modalCardStyle}>
            <div className="modal-header" style={modalHeaderStyle}>
              <h3>Assign Vehicle & Driver to {assigningBooking.booking_number}</h3>
              <X size={18} style={{ cursor: "pointer" }} onClick={() => setAssigningBooking(null)} />
            </div>
            <div className="modal-body" style={{ padding: 24, display: "grid", gap: 16 }}>
              <div className="field">
                <label>Select Vehicle</label>
                <select value={selectedVehId} onChange={(e) => setSelectedVehId(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">-- Choose Available Vehicle --</option>
                  {vehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.registration_number} - {v.make} {v.model} ({v.current_city}) [{v.status}]
                    </option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label>Select Chauffeur / Driver</label>
                <select value={selectedDrvId} onChange={(e) => setSelectedDrvId(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">-- Choose Available Driver --</option>
                  {drivers.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.phone}) - Base: {d.home_base} [{d.status}]
                    </option>
                  ))}
                </select>
              </div>

              <div className="actions" style={{ marginTop: 12 }}>
                <button className="button secondary" onClick={() => setAssigningBooking(null)}>
                  Cancel
                </button>
                <button className="button" onClick={handleAssignSubmit}>
                  Confirm Assignment
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CorporateCustomersView({
  customers,
  onAddClick,
  pricingRules,
}: {
  customers: CorporateCustomer[];
  onAddClick: () => void;
  pricingRules: RentalPricingRule[];
}) {
  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div className="section">
        <div className="section-header">
          <h2>
            <Building2 size={18} style={{ color: "var(--accent)" }} /> Corporate Business Clients CRM ({customers.length})
          </h2>
          <button className="button" onClick={onAddClick}>
            <Plus size={16} /> Add Business Account
          </button>
        </div>
        <div className="section-body" style={{ padding: 0 }}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Company Name</th>
                  <th>Tax IDs (GST / PAN)</th>
                  <th>Contact Person & Phone</th>
                  <th>Billing Address</th>
                  <th>Custom Pricing Rules</th>
                </tr>
              </thead>
              <tbody>
                {customers.map((c) => {
                  const companyRules = pricingRules.filter((r) => r.company === c.id);
                  return (
                    <tr key={c.id}>
                      <td>
                        <strong style={{ color: "#fff", fontSize: 15 }}>{c.name}</strong>
                        <div style={{ fontSize: 12, color: "var(--muted)" }}>✉️ {c.email}</div>
                      </td>
                      <td>
                        <div style={{ fontSize: 13 }}>
                          <strong>GST:</strong> {c.gst_number || "N/A"}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--muted)" }}>
                          <strong>PAN:</strong> {c.pan_number || "N/A"}
                        </div>
                      </td>
                      <td>
                        <strong style={{ color: "#fff" }}>{c.contact_person}</strong>
                        <div style={{ fontSize: 12, color: "var(--muted)" }}>📞 {c.phone}</div>
                      </td>
                      <td>
                        <div style={{ fontSize: 13, maxWidth: 260 }}>{c.billing_address}</div>
                      </td>
                      <td>
                        <span className="status ok">{companyRules.length} Custom Rates Set</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function RentalPackagesView({
  packages,
  onAddClick,
}: {
  packages: RentalPackage[];
  onAddClick: () => void;
}) {
  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div className="section-header" style={{ background: "transparent", padding: 0 }}>
        <h2>Configured Rental Packages ({packages.length})</h2>
        <button className="button" onClick={onAddClick}>
          <Plus size={16} /> Create Package
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 20 }}>
        {packages.map((pkg) => (
          <div key={pkg.id} className="vehicle-tile" style={{ border: "1px solid var(--line)", padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="status neutral">{pkg.package_type.toUpperCase()}</span>
              <strong style={{ fontSize: 20, color: "var(--accent)" }}>₹{pkg.default_base_price}</strong>
            </div>

            <h3 style={{ margin: "12px 0 4px", fontSize: 18, color: "#fff" }}>{pkg.name}</h3>

            <div style={{ display: "grid", gap: 8, fontSize: 13, color: "var(--muted)", margin: "12px 0" }}>
              <div>
                <strong>Included Time:</strong> {pkg.included_hours} Hours
              </div>
              <div>
                <strong>Included Distance:</strong> {pkg.included_km} KM
              </div>
              <div>
                <strong>Extra Hour Charge:</strong> ₹{pkg.extra_hour_rate} / hr
              </div>
              <div>
                <strong>Extra KM Charge:</strong> ₹{pkg.extra_km_rate} / km
              </div>
              {Number(pkg.driver_allowance_per_day) > 0 && (
                <div>
                  <strong>Driver Allowance:</strong> ₹{pkg.driver_allowance_per_day} / day
                </div>
              )}
            </div>

            <div style={{ fontSize: 11, color: "var(--ok)", fontWeight: 600 }}>Active Package</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PricingSystemView({
  pricingRules,
  customers,
  packages,
  onAddClick,
  onRefresh,
  triggerSuccess,
}: {
  pricingRules: RentalPricingRule[];
  customers: CorporateCustomer[];
  packages: RentalPackage[];
  onAddClick: () => void;
  onRefresh: () => void;
  triggerSuccess: (msg: string) => void;
}) {
  async function handleDeleteRule(id: number) {
    if (!confirm("Delete this pricing rule?")) return;
    try {
      await deletePricingRule(id);
      onRefresh();
      triggerSuccess("Pricing rule deleted.");
    } catch (e) {
      alert("Failed to delete pricing rule.");
    }
  }

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div className="notice" style={{ background: "rgba(59, 130, 246, 0.08)", borderColor: "rgba(59, 130, 246, 0.2)", color: "#fff" }}>
        💡 <strong>Pricing Hierarchy Rule:</strong> System evaluates rates by: <code>Company + City</code> → <code>Company Default</code> → <code>City Default</code> → <code>Base Package Default</code>.
      </div>

      <div className="section">
        <div className="section-header">
          <h2>
            <DollarSign size={18} style={{ color: "var(--ok)" }} /> City & Corporate Pricing Rules ({pricingRules.length})
          </h2>
          <button className="button" onClick={onAddClick}>
            <Plus size={16} /> Add Pricing Rule
          </button>
        </div>
        <div className="section-body" style={{ padding: 0 }}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Company</th>
                  <th>City</th>
                  <th>Package</th>
                  <th>Configured Base Price</th>
                  <th>Extra Hour Rate</th>
                  <th>Extra KM Rate</th>
                  <th>Driver Allowance</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pricingRules.map((rule) => (
                  <tr key={rule.id}>
                    <td>
                      <strong style={{ color: "#fff" }}>{rule.company_name || "All Companies (Default)"}</strong>
                    </td>
                    <td>
                      <span className="status ok">{rule.city || "All Cities"}</span>
                    </td>
                    <td>
                      <strong style={{ color: "var(--accent)" }}>{rule.package_name || `Package #${rule.package}`}</strong>
                    </td>
                    <td>
                      <strong style={{ fontSize: 16, color: "#fff" }}>₹{rule.base_price}</strong>
                    </td>
                    <td>₹{rule.extra_hour_rate} / hr</td>
                    <td>₹{rule.extra_km_rate} / km</td>
                    <td>₹{rule.driver_allowance}</td>
                    <td>
                      <button
                        className="button secondary"
                        style={{ padding: "4px 8px", color: "var(--danger)", minHeight: 28 }}
                        onClick={() => handleDeleteRule(rule.id)}
                      >
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function RentalHistoryView({
  bookings,
  onViewInvoice,
}: {
  bookings: RentalBooking[];
  onViewInvoice: (booking: RentalBooking) => void;
}) {
  const completedOrCancelled = bookings.filter((b) => ["completed", "cancelled"].includes(b.status));

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div className="section">
        <div className="section-header">
          <h2>Rental History & Invoice Registry ({completedOrCancelled.length})</h2>
        </div>
        <div className="section-body" style={{ padding: 0 }}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Booking #</th>
                  <th>Customer</th>
                  <th>Start & End Time</th>
                  <th>Distance & Duration</th>
                  <th>Invoice Amount</th>
                  <th>Status</th>
                  <th>Invoice Action</th>
                </tr>
              </thead>
              <tbody>
                {completedOrCancelled.map((b) => (
                  <tr key={b.id}>
                    <td>
                      <strong style={{ color: "#fff" }}>{b.booking_number}</strong>
                    </td>
                    <td>{b.customer_name}</td>
                    <td>
                      <div style={{ fontSize: 12 }}>
                        {b.start_time ? new Date(b.start_time).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "N/A"}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--muted)" }}>
                        to {b.end_time ? new Date(b.end_time).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "N/A"}
                      </div>
                    </td>
                    <td>
                      <div>📏 {b.distance_travelled || 0} KM</div>
                      <div style={{ fontSize: 12, color: "var(--muted)" }}>⏱️ {b.actual_hours_used || 0} Hours</div>
                    </td>
                    <td>
                      {b.invoice ? (
                        <strong style={{ color: "var(--ok)", fontSize: 16 }}>₹{b.invoice.final_total}</strong>
                      ) : (
                        <span style={{ color: "var(--muted)" }}>-</span>
                      )}
                    </td>
                    <td>
                      <RentalStatusPill status={b.status} />
                    </td>
                    <td>
                      {b.invoice ? (
                        <button className="button secondary" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => onViewInvoice(b)}>
                          <FileText size={14} /> View Invoice
                        </button>
                      ) : (
                        <span style={{ fontSize: 12, color: "var(--muted)" }}>No Invoice</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}



/* ==========================================================================
   MODALS
   ========================================================================== */

function NewBookingModal({
  customers,
  packages,
  vehicles,
  drivers,
  onClose,
  onSuccess,
}: {
  customers: CorporateCustomer[];
  packages: RentalPackage[];
  vehicles: Vehicle[];
  drivers: Driver[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [customerType, setCustomerType] = useState<"individual" | "corporate">("individual");
  const [custName, setCustName] = useState("");
  const [custPhone, setCustPhone] = useState("");
  const [custEmail, setCustEmail] = useState("");
  const [corpCustId, setCorpCustId] = useState<number | "">("");
  const [pickupAddr, setPickupAddr] = useState("");
  const [dropAddr, setDropAddr] = useState("");
  const [city, setCity] = useState("Ahmedabad");
  const [pickupDateTime, setPickupDateTime] = useState("");
  const [expectedReturnDateTime, setExpectedReturnDateTime] = useState("");
  const [packageId, setPackageId] = useState<number | "">(packages[0]?.id || "");
  const [category, setCategory] = useState("Sedan");
  const [vehicleId, setVehicleId] = useState<number | "">("");
  const [driverId, setDriverId] = useState<number | "">("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    if (!custName || !custPhone || !pickupAddr || !city || !pickupDateTime || !packageId) {
      alert("Please fill all required fields.");
      return;
    }
    setSubmitting(true);
    try {
      await createRentalBooking({
        customer_type: customerType,
        customer_name: custName,
        customer_phone: custPhone,
        customer_email: custEmail,
        corporate_customer_id: corpCustId ? Number(corpCustId) : undefined,
        pickup_address: pickupAddr,
        drop_address: dropAddr,
        pickup_city: city,
        pickup_at: new Date(pickupDateTime).toISOString(),
        expected_return_at: expectedReturnDateTime ? new Date(expectedReturnDateTime).toISOString() : new Date(pickupDateTime).toISOString(),
        package_id: Number(packageId),
        vehicle_category: category,
        vehicle_id: vehicleId ? Number(vehicleId) : undefined,
        driver_id: driverId ? Number(driverId) : undefined,
        notes,
      });
      onSuccess();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to create booking.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop" style={modalBackdropStyle}>
      <div className="modal-card" style={{ ...modalCardStyle, maxWidth: 680 }}>
        <div className="modal-header" style={modalHeaderStyle}>
          <h3>New Rental Booking Form</h3>
          <X size={18} style={{ cursor: "pointer" }} onClick={onClose} />
        </div>
        <div className="modal-body" style={{ padding: 24, display: "grid", gap: 16 }}>
          <div className="form-grid">
            <div className="field">
              <label>Customer Type</label>
              <select value={customerType} onChange={(e) => setCustomerType(e.target.value as any)}>
                <option value="individual">Individual Customer</option>
                <option value="corporate">Corporate Client (CRM)</option>
              </select>
            </div>

            {customerType === "corporate" && (
              <div className="field">
                <label>Select Business Account</label>
                <select value={corpCustId} onChange={(e) => setCorpCustId(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">-- Choose Corporate Company --</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      🏢 {c.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="form-grid">
            <div className="field">
              <label>Customer Name *</label>
              <input type="text" placeholder="Full Name" value={custName} onChange={(e) => setCustName(e.target.value)} />
            </div>
            <div className="field">
              <label>Phone Number *</label>
              <input type="text" placeholder="+91 98765 00000" value={custPhone} onChange={(e) => setCustPhone(e.target.value)} />
            </div>
          </div>

          <div className="form-grid">
            <div className="field">
              <label>Email Address</label>
              <input type="email" placeholder="customer@email.com" value={custEmail} onChange={(e) => setCustEmail(e.target.value)} />
            </div>
            <div className="field">
              <label>Pickup City *</label>
              <input type="text" placeholder="e.g. Ahmedabad, Delhi, Mumbai" value={city} onChange={(e) => setCity(e.target.value)} />
            </div>
          </div>

          <div className="form-grid">
            <div className="field">
              <label>Pickup Address *</label>
              <input type="text" placeholder="Pickup Address" value={pickupAddr} onChange={(e) => setPickupAddr(e.target.value)} />
            </div>
            <div className="field">
              <label>Drop Address (Optional)</label>
              <input type="text" placeholder="Drop Address" value={dropAddr} onChange={(e) => setDropAddr(e.target.value)} />
            </div>
          </div>

          <div className="form-grid">
            <div className="field">
              <label>Pickup Date & Time *</label>
              <input type="datetime-local" value={pickupDateTime} onChange={(e) => setPickupDateTime(e.target.value)} />
            </div>
            <div className="field">
              <label>Expected Return Date & Time</label>
              <input type="datetime-local" value={expectedReturnDateTime} onChange={(e) => setExpectedReturnDateTime(e.target.value)} />
            </div>
          </div>

          <div className="form-grid">
            <div className="field">
              <label>Select Rental Package *</label>
              <select value={packageId} onChange={(e) => setPackageId(Number(e.target.value))}>
                {packages.map((pkg) => (
                  <option key={pkg.id} value={pkg.id}>
                    📦 {pkg.name} (Base: ₹{pkg.default_base_price})
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Vehicle Category</label>
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                <option value="Sedan">Sedan (Etios / Dzire)</option>
                <option value="SUV">SUV (Innova / Ertiga)</option>
                <option value="Luxury">Luxury (Camry / Mercedes)</option>
              </select>
            </div>
          </div>

          <div className="form-grid">
            <div className="field">
              <label>Assign Vehicle (Optional)</label>
              <select value={vehicleId} onChange={(e) => setVehicleId(e.target.value ? Number(e.target.value) : "")}>
                <option value="">-- Assign Later --</option>
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    🚗 {v.registration_number} - {v.make} {v.model}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Assign Driver (Optional)</label>
              <select value={driverId} onChange={(e) => setDriverId(e.target.value ? Number(e.target.value) : "")}>
                <option value="">-- Assign Later --</option>
                {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    👨‍✈️ {d.name} ({d.phone})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="field">
            <label>Notes / Instructions</label>
            <textarea rows={2} placeholder="Special instructions for chauffeur or flight details..." value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>

          <div className="actions">
            <button className="button secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button className="button" onClick={handleSubmit} disabled={submitting}>
              {submitting ? "Creating..." : "Create Rental Booking"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function NewCustomerModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [name, setName] = useState("");
  const [gst, setGst] = useState("");
  const [pan, setPan] = useState("");
  const [addr, setAddr] = useState("");
  const [email, setEmail] = useState("");
  const [person, setPerson] = useState("");
  const [phone, setPhone] = useState("");

  async function handleSubmit() {
    if (!name || !email || !person || !phone) {
      alert("Please fill name, email, contact person, and phone.");
      return;
    }
    try {
      await createCorporateCustomer({
        name,
        gst_number: gst,
        pan_number: pan,
        billing_address: addr,
        email,
        contact_person: person,
        phone,
      });
      onSuccess();
    } catch (e) {
      alert("Failed to create customer.");
    }
  }

  return (
    <div className="modal-backdrop" style={modalBackdropStyle}>
      <div className="modal-card" style={modalCardStyle}>
        <div className="modal-header" style={modalHeaderStyle}>
          <h3>Add Corporate Customer Account</h3>
          <X size={18} style={{ cursor: "pointer" }} onClick={onClose} />
        </div>
        <div className="modal-body" style={{ padding: 24, display: "grid", gap: 14 }}>
          <div className="field">
            <label>Company Name *</label>
            <input type="text" placeholder="e.g. Google India Pvt Ltd" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="form-grid">
            <div className="field">
              <label>GST Number</label>
              <input type="text" placeholder="24AAACG1234H1Z0" value={gst} onChange={(e) => setGst(e.target.value)} />
            </div>
            <div className="field">
              <label>PAN Number</label>
              <input type="text" placeholder="AAACG1234H" value={pan} onChange={(e) => setPan(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label>Billing Address</label>
            <textarea rows={2} placeholder="Full Registered Corporate Address" value={addr} onChange={(e) => setAddr(e.target.value)} />
          </div>
          <div className="form-grid">
            <div className="field">
              <label>Contact Person *</label>
              <input type="text" placeholder="Admin / Travel Head" value={person} onChange={(e) => setPerson(e.target.value)} />
            </div>
            <div className="field">
              <label>Phone Number *</label>
              <input type="text" placeholder="+91 98765 43210" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label>Corporate Email *</label>
            <input type="email" placeholder="corporate@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="actions">
            <button className="button secondary" onClick={onClose}>
              Cancel
            </button>
            <button className="button" onClick={handleSubmit}>
              Save Corporate Client
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function NewPackageModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [name, setName] = useState("");
  const [pkgType, setPkgType] = useState<any>("local");
  const [hrs, setHrs] = useState("8");
  const [km, setKm] = useState("80");
  const [price, setPrice] = useState("2200");
  const [extraHr, setExtraHr] = useState("150");
  const [extraKm, setExtraKm] = useState("15");

  async function handleSubmit() {
    if (!name || !price) return alert("Fill name and price");
    try {
      await createRentalPackage({
        name,
        package_type: pkgType,
        included_hours: Number(hrs),
        included_km: Number(km),
        default_base_price: Number(price),
        extra_hour_rate: Number(extraHr),
        extra_km_rate: Number(extraKm),
        driver_allowance_per_day: 300,
        night_stay_charge: 500,
        is_active: true,
      });
      onSuccess();
    } catch (e) {
      alert("Failed to create package");
    }
  }

  return (
    <div className="modal-backdrop" style={modalBackdropStyle}>
      <div className="modal-card" style={modalCardStyle}>
        <div className="modal-header" style={modalHeaderStyle}>
          <h3>Create Rental Package</h3>
          <X size={18} style={{ cursor: "pointer" }} onClick={onClose} />
        </div>
        <div className="modal-body" style={{ padding: 24, display: "grid", gap: 14 }}>
          <div className="field">
            <label>Package Name *</label>
            <input type="text" placeholder="e.g. 8 Hours / 80 KM" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="form-grid">
            <div className="field">
              <label>Package Type</label>
              <select value={pkgType} onChange={(e) => setPkgType(e.target.value)}>
                <option value="local">Local Package</option>
                <option value="airport">Airport Transfer</option>
                <option value="outstation">Outstation</option>
              </select>
            </div>
            <div className="field">
              <label>Base Price (₹) *</label>
              <input type="number" value={price} onChange={(e) => setPrice(e.target.value)} />
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label>Included Hours</label>
              <input type="number" value={hrs} onChange={(e) => setHrs(e.target.value)} />
            </div>
            <div className="field">
              <label>Included KM</label>
              <input type="number" value={km} onChange={(e) => setKm(e.target.value)} />
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label>Extra Hour Rate (₹/hr)</label>
              <input type="number" value={extraHr} onChange={(e) => setExtraHr(e.target.value)} />
            </div>
            <div className="field">
              <label>Extra KM Rate (₹/km)</label>
              <input type="number" value={extraKm} onChange={(e) => setExtraKm(e.target.value)} />
            </div>
          </div>
          <div className="actions">
            <button className="button secondary" onClick={onClose}>
              Cancel
            </button>
            <button className="button" onClick={handleSubmit}>
              Save Package
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function NewPricingRuleModal({
  customers,
  packages,
  onClose,
  onSuccess,
}: {
  customers: CorporateCustomer[];
  packages: RentalPackage[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [compId, setCompId] = useState<number | "">("");
  const [city, setCity] = useState("");
  const [pkgId, setPkgId] = useState<number | "">(packages[0]?.id || "");
  const [basePrice, setBasePrice] = useState("1200");
  const [extraHr, setExtraHr] = useState("150");
  const [extraKm, setExtraKm] = useState("15");
  const [driverAllowance, setDriverAllowance] = useState("300");

  async function handleSubmit() {
    if (!pkgId || !basePrice) return alert("Select package and price.");
    try {
      await savePricingRule({
        company: compId ? Number(compId) : null,
        city,
        package: Number(pkgId),
        base_price: Number(basePrice),
        extra_hour_rate: Number(extraHr),
        extra_km_rate: Number(extraKm),
        driver_allowance: Number(driverAllowance),
      });
      onSuccess();
    } catch (e) {
      alert("Failed to save pricing rule.");
    }
  }

  return (
    <div className="modal-backdrop" style={modalBackdropStyle}>
      <div className="modal-card" style={modalCardStyle}>
        <div className="modal-header" style={modalHeaderStyle}>
          <h3>Add Custom Pricing Rule</h3>
          <X size={18} style={{ cursor: "pointer" }} onClick={onClose} />
        </div>
        <div className="modal-body" style={{ padding: 24, display: "grid", gap: 14 }}>
          <div className="form-grid">
            <div className="field">
              <label>Company (Optional - Leave blank for default)</label>
              <select value={compId} onChange={(e) => setCompId(e.target.value ? Number(e.target.value) : "")}>
                <option value="">-- All Companies --</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    🏢 {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>City (Optional - Leave blank for all cities)</label>
              <input type="text" placeholder="e.g. Ahmedabad, Delhi, Mumbai" value={city} onChange={(e) => setCity(e.target.value)} />
            </div>
          </div>

          <div className="field">
            <label>Rental Package *</label>
            <select value={pkgId} onChange={(e) => setPkgId(Number(e.target.value))}>
              {packages.map((p) => (
                <option key={p.id} value={p.id}>
                  📦 {p.name}
                </option>
              ))}
            </select>
          </div>

          <div className="form-grid">
            <div className="field">
              <label>Custom Base Price (₹) *</label>
              <input type="number" value={basePrice} onChange={(e) => setBasePrice(e.target.value)} />
            </div>
            <div className="field">
              <label>Driver Allowance (₹)</label>
              <input type="number" value={driverAllowance} onChange={(e) => setDriverAllowance(e.target.value)} />
            </div>
          </div>

          <div className="form-grid">
            <div className="field">
              <label>Extra Hour Rate (₹/hr)</label>
              <input type="number" value={extraHr} onChange={(e) => setExtraHr(e.target.value)} />
            </div>
            <div className="field">
              <label>Extra KM Rate (₹/km)</label>
              <input type="number" value={extraKm} onChange={(e) => setExtraKm(e.target.value)} />
            </div>
          </div>

          <div className="actions">
            <button className="button secondary" onClick={onClose}>
              Cancel
            </button>
            <button className="button" onClick={handleSubmit}>
              Save Pricing Rule
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChecklistModal({
  booking,
  type,
  onClose,
  onSuccess,
}: {
  booking: RentalBooking;
  type: "start" | "end";
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [odometer, setOdometer] = useState(
    type === "end" ? String(booking.start_odometer ? booking.start_odometer + 45 : booking.vehicle?.odometer_km || 52000) : String(booking.vehicle?.odometer_km || 52000)
  );
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    if (!odometer) return alert("Odometer reading required.");
    setSubmitting(true);
    try {
      const checklist = {
        front_photo: "",
        rear_photo: "",
        left_photo: "",
        right_photo: "",
        dashboard_photo: "",
        odometer_photo: "",
        fuel_gauge_photo: "",
        odometer_reading: Number(odometer),
        notes,
      };

      if (type === "start") {
        await startRentalBooking(booking.id, checklist);
      } else {
        await endRentalBooking(booking.id, checklist);
      }
      onSuccess();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Checklist submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop" style={modalBackdropStyle}>
      <div className="modal-card" style={modalCardStyle}>
        <div className="modal-header" style={modalHeaderStyle}>
          <h3>
            📋 Driver {type === "start" ? "Pre-Rental Start" : "Post-Rental End"} Checklist - {booking.booking_number}
          </h3>
          <X size={18} style={{ cursor: "pointer" }} onClick={onClose} />
        </div>
        <div className="modal-body" style={{ padding: 24, display: "grid", gap: 16 }}>
          <div className="field">
            <label>Current Odometer Reading (KM) *</label>
            <input type="number" value={odometer} onChange={(e) => setOdometer(e.target.value)} />
          </div>

          <div className="field">
            <label>Notes / Vehicle Condition Comments</label>
            <textarea rows={2} placeholder="No dents or scratches observed..." value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>

          <div className="actions">
            <button className="button secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button className="button" onClick={handleSubmit} disabled={submitting} style={{ background: type === "end" ? "var(--ok)" : "var(--accent)" }}>
              {submitting ? "Submitting..." : type === "start" ? "Complete Checklist & Start Trip" : "Upload Checklist & Generate Bill"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function InvoiceModal({ booking, invoice, onClose }: { booking: RentalBooking; invoice: RentalInvoice; onClose: () => void }) {
  return (
    <div className="modal-backdrop" style={modalBackdropStyle}>
      <div className="modal-card" style={{ ...modalCardStyle, maxWidth: 650 }}>
        <div className="modal-header" style={modalHeaderStyle}>
          <h3>Tax Invoice - {invoice.invoice_number}</h3>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button className="button secondary" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => window.print()}>
              <Printer size={14} /> Print Receipt
            </button>
            <X size={18} style={{ cursor: "pointer" }} onClick={onClose} />
          </div>
        </div>

        <div className="modal-body" style={{ padding: 28, background: "var(--panel-strong)", color: "#fff" }}>
          <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--line)", paddingBottom: 16 }}>
            <div>
              <strong style={{ fontSize: 20, color: "var(--accent)" }}>INDEX FLEET RENTALS</strong>
              <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>Chauffeur & Corporate Vehicle Rental Services</div>
              <div style={{ fontSize: 12, color: "var(--muted)" }}>GSTIN: 24ABCDE1234F1Z9</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <strong style={{ fontSize: 16 }}>INVOICE #{invoice.invoice_number}</strong>
              <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>Date: {new Date(invoice.issued_at).toLocaleDateString()}</div>
              <div style={{ fontSize: 12, color: "var(--ok)", fontWeight: "bold" }}>PAID</div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, margin: "20px 0", fontSize: 13 }}>
            <div>
              <strong style={{ color: "var(--muted)", fontSize: 11, textTransform: "uppercase" }}>Billed To:</strong>
              <div style={{ fontWeight: "bold", fontSize: 15, marginTop: 4 }}>{booking.customer_name}</div>
              {booking.corporate_customer && <div>🏢 {booking.corporate_customer.name}</div>}
              <div>📞 {booking.customer_phone}</div>
              <div>📍 {booking.pickup_city}</div>
            </div>

            <div>
              <strong style={{ color: "var(--muted)", fontSize: 11, textTransform: "uppercase" }}>Rental Details:</strong>
              <div>Booking #: {booking.booking_number}</div>
              <div>Package: {booking.package?.name}</div>
              <div>Distance: {invoice.distance_travelled} KM (Inc: {invoice.included_km} KM)</div>
              <div>Duration: {invoice.hours_used} Hours (Inc: {invoice.included_hours} Hrs)</div>
            </div>
          </div>

          {/* Invoice Charges Table */}
          <table style={{ width: "100%", margin: "20px 0", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "rgba(0,0,0,0.3)", borderBottom: "1px solid var(--line)" }}>
                <th style={{ textAlign: "left", padding: 10 }}>Description</th>
                <th style={{ textAlign: "center", padding: 10 }}>Units / Extra</th>
                <th style={{ textAlign: "right", padding: 10 }}>Amount (₹)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ padding: 10 }}>Base Package Price ({booking.package?.name})</td>
                <td style={{ textAlign: "center", padding: 10 }}>Fixed</td>
                <td style={{ textAlign: "right", padding: 10 }}>₹{invoice.package_price}</td>
              </tr>
              {Number(invoice.extra_km) > 0 && (
                <tr>
                  <td style={{ padding: 10 }}>Extra Kilometer Charges</td>
                  <td style={{ textAlign: "center", padding: 10 }}>{invoice.extra_km} KM</td>
                  <td style={{ textAlign: "right", padding: 10 }}>₹{invoice.extra_km_charges}</td>
                </tr>
              )}
              {Number(invoice.extra_hours) > 0 && (
                <tr>
                  <td style={{ padding: 10 }}>Extra Hour Charges</td>
                  <td style={{ textAlign: "center", padding: 10 }}>{invoice.extra_hours} Hrs</td>
                  <td style={{ textAlign: "right", padding: 10 }}>₹{invoice.extra_hour_charges}</td>
                </tr>
              )}
              {Number(invoice.driver_allowance) > 0 && (
                <tr>
                  <td style={{ padding: 10 }}>Driver Allowance / Night Charge</td>
                  <td style={{ textAlign: "center", padding: 10 }}>1 Day</td>
                  <td style={{ textAlign: "right", padding: 10 }}>₹{invoice.driver_allowance}</td>
                </tr>
              )}
              <tr style={{ borderTop: "1px solid var(--line)" }}>
                <td colSpan={2} style={{ textAlign: "right", padding: 10, fontWeight: "bold" }}>
                  Subtotal:
                </td>
                <td style={{ textAlign: "right", padding: 10, fontWeight: "bold" }}>₹{invoice.subtotal}</td>
              </tr>
              <tr>
                <td colSpan={2} style={{ textAlign: "right", padding: 10 }}>
                  GST Tax ({invoice.tax_rate_percent}%):
                </td>
                <td style={{ textAlign: "right", padding: 10 }}>₹{invoice.tax_amount}</td>
              </tr>
              <tr style={{ borderTop: "2px solid var(--accent)", fontSize: 16 }}>
                <td colSpan={2} style={{ textAlign: "right", padding: 12, fontWeight: "bold", color: "var(--accent)" }}>
                  Final Invoice Total:
                </td>
                <td style={{ textAlign: "right", padding: 12, fontWeight: "bold", color: "var(--accent)" }}>₹{invoice.final_total}</td>
              </tr>
            </tbody>
          </table>

          <div style={{ textAlign: "center", fontSize: 12, color: "var(--muted)", marginTop: 20 }}>
            Thank you for choosing Index Fleet Rentals! Safe travels.
          </div>
        </div>
      </div>
    </div>
  );
}

/* Helper Components & Styles */

function MetricCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number; color: string }) {
  return (
    <div className="metric">
      <div className="metric-header">
        <span style={{ color }}>{icon}</span> {label}
      </div>
      <div className="metric-content">
        <div className="metric-value">
          <strong>{value}</strong>
        </div>
      </div>
    </div>
  );
}

function RentalStatusPill({ status }: { status: string }) {
  switch (status) {
    case "started":
    case "in_progress":
      return <span className="status ok">In Progress</span>;
    case "completed":
      return <span className="status neutral">Completed</span>;
    case "ready":
    case "vehicle_assigned":
    case "driver_assigned":
      return <span className="status warn">Assigned / Ready</span>;
    case "pending":
      return <span className="status warn">Pending</span>;
    case "cancelled":
      return <span className="status danger">Cancelled</span>;
    default:
      return <span className="status neutral">{status}</span>;
  }
}

const modalBackdropStyle: React.CSSProperties = {
  position: "fixed",
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: "rgba(0, 0, 0, 0.75)",
  backdropFilter: "blur(8px)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 9999,
  padding: 20,
};

const modalCardStyle: React.CSSProperties = {
  background: "var(--panel)",
  border: "1px solid var(--line)",
  borderRadius: 16,
  width: "100%",
  maxWidth: 580,
  maxHeight: "90vh",
  overflowY: "auto",
  boxShadow: "0 20px 50px rgba(0,0,0,0.5)",
};

const modalHeaderStyle: React.CSSProperties = {
  padding: "18px 24px",
  borderBottom: "1px solid var(--line)",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
};
