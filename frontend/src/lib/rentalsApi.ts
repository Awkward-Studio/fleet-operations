import { Driver, Vehicle } from "./api";

export type PackageType = "local" | "airport" | "outstation";

export type CorporateCustomer = {
  id: number;
  name: string;
  gst_number: string;
  pan_number: string;
  billing_address: string;
  email: string;
  contact_person: string;
  phone: string;
  created_at: string;
};

export type RentalPackage = {
  id: number;
  name: string;
  package_type: PackageType;
  included_hours: string | number;
  included_km: string | number;
  default_base_price: string | number;
  extra_hour_rate: string | number;
  extra_km_rate: string | number;
  driver_allowance_per_day: string | number;
  night_stay_charge: string | number;
  is_active: boolean;
};

export type RentalPricingRule = {
  id: number;
  company: number | null;
  company_name?: string;
  city: string;
  package: number;
  package_name?: string;
  base_price: string | number;
  extra_hour_rate: string | number;
  extra_km_rate: string | number;
  driver_allowance: string | number;
};

export type RentalChecklist = {
  id: number;
  booking: number;
  checklist_type: "start" | "end";
  front_photo?: string;
  rear_photo?: string;
  left_photo?: string;
  right_photo?: string;
  dashboard_photo?: string;
  odometer_photo?: string;
  fuel_gauge_photo?: string;
  odometer_reading: number;
  notes?: string;
  created_at: string;
};

export type RentalInvoice = {
  id: number;
  invoice_number: string;
  booking: number;
  distance_travelled: string | number;
  hours_used: string | number;
  included_km: string | number;
  included_hours: string | number;
  extra_km: string | number;
  extra_hours: string | number;
  package_price: string | number;
  extra_km_charges: string | number;
  extra_hour_charges: string | number;
  driver_allowance: string | number;
  subtotal: string | number;
  tax_rate_percent: string | number;
  tax_amount: string | number;
  final_total: string | number;
  issued_at: string;
};

export type RentalBooking = {
  id: number;
  booking_number: string;
  customer_type: "individual" | "corporate";
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  corporate_customer?: CorporateCustomer | null;
  pickup_address: string;
  drop_address?: string;
  pickup_city: string;
  pickup_at: string;
  expected_return_at: string;
  package: RentalPackage;
  vehicle_category: string;
  vehicle?: Vehicle | null;
  driver?: Driver | null;
  notes?: string;
  status:
    | "pending"
    | "vehicle_assigned"
    | "driver_assigned"
    | "ready"
    | "started"
    | "in_progress"
    | "completed"
    | "cancelled";
  start_time?: string | null;
  end_time?: string | null;
  start_odometer?: number | null;
  end_odometer?: number | null;
  distance_travelled?: string | number | null;
  actual_hours_used?: string | number | null;
  checklists?: RentalChecklist[];
  invoice?: RentalInvoice | null;
  created_at: string;
  updated_at: string;
};

export type RentalSummary = {
  cards: {
    active_rentals: number;
    upcoming_rentals: number;
    available_vehicles: number;
    available_drivers: number;
    rentals_ending_today: number;
  };
  alerts: Array<{
    id: number;
    type: string;
    title: string;
    description: string;
  }>;
  todays_rentals: RentalBooking[];
  upcoming_pickups: RentalBooking[];
  recent_rentals: RentalBooking[];
};

export type DriverPortalData = {
  driver: {
    id: number;
    name: string;
    phone: string;
    status: string;
  };
  assigned_rentals: RentalBooking[];
};

function getApiBase() {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (typeof window !== "undefined") {
    const token = localStorage.getItem("accessToken");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${getApiBase()}/api/rentals${path}`, {
    ...init,
    headers: {
      ...headers,
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    let errMsg = body;
    try {
      const json = JSON.parse(body);
      errMsg = json.detail || json.message || Object.values(json).flat().join(" ") || body;
    } catch {
      // raw body
    }
    throw new Error(errMsg || `Rental API request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

// API functions
export function getRentalSummary() {
  return request<RentalSummary>("/dashboard/summary/");
}

export function getRentalBookings() {
  return request<RentalBooking[]>("/bookings/");
}

export function createRentalBooking(payload: {
  customer_type: "individual" | "corporate";
  customer_name: string;
  customer_phone: string;
  customer_email?: string;
  corporate_customer_id?: number | null;
  pickup_address: string;
  drop_address?: string;
  pickup_city: string;
  pickup_at: string;
  expected_return_at: string;
  package_id: number;
  vehicle_category: string;
  vehicle_id?: number | null;
  driver_id?: number | null;
  notes?: string;
}) {
  return request<RentalBooking>("/bookings/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function assignRentalBooking(bookingId: number, vehicleId?: number, driverId?: number) {
  return request<RentalBooking>(`/bookings/${bookingId}/assign/`, {
    method: "POST",
    body: JSON.stringify({ vehicle_id: vehicleId, driver_id: driverId }),
  });
}

export function startRentalBooking(
  bookingId: number,
  checklist: {
    front_photo?: string;
    rear_photo?: string;
    left_photo?: string;
    right_photo?: string;
    dashboard_photo?: string;
    odometer_photo?: string;
    fuel_gauge_photo?: string;
    odometer_reading: number;
    notes?: string;
  }
) {
  return request<RentalBooking>(`/bookings/${bookingId}/start_rental/`, {
    method: "POST",
    body: JSON.stringify({ checklist }),
  });
}

export function endRentalBooking(
  bookingId: number,
  checklist: {
    front_photo?: string;
    rear_photo?: string;
    left_photo?: string;
    right_photo?: string;
    dashboard_photo?: string;
    odometer_photo?: string;
    fuel_gauge_photo?: string;
    odometer_reading: number;
    notes?: string;
  }
) {
  return request<RentalBooking>(`/bookings/${bookingId}/end_rental/`, {
    method: "POST",
    body: JSON.stringify({ checklist }),
  });
}

export function cancelRentalBooking(bookingId: number) {
  return request<RentalBooking>(`/bookings/${bookingId}/cancel_rental/`, {
    method: "POST",
  });
}

export function getCorporateCustomers() {
  return request<CorporateCustomer[]>("/customers/");
}

export function createCorporateCustomer(payload: Omit<CorporateCustomer, "id" | "created_at">) {
  return request<CorporateCustomer>("/customers/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCorporateCustomer(id: number, payload: Partial<CorporateCustomer>) {
  return request<CorporateCustomer>(`/customers/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getRentalPackages() {
  return request<RentalPackage[]>("/packages/");
}

export function createRentalPackage(payload: Omit<RentalPackage, "id">) {
  return request<RentalPackage>("/packages/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getPricingRules(companyId?: number, city?: string) {
  let query = "";
  const params: string[] = [];
  if (companyId) params.push(`company_id=${companyId}`);
  if (city) params.push(`city=${encodeURIComponent(city)}`);
  if (params.length > 0) query = `?${params.join("&")}`;
  return request<RentalPricingRule[]>(`/pricing-rules/${query}`);
}

export function savePricingRule(payload: Omit<RentalPricingRule, "id" | "company_name" | "package_name"> & { id?: number }) {
  if (payload.id) {
    return request<RentalPricingRule>(`/pricing-rules/${payload.id}/`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }
  return request<RentalPricingRule>("/pricing-rules/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deletePricingRule(id: number) {
  return request<void>(`/pricing-rules/${id}/`, {
    method: "DELETE",
  });
}

export function getDriverPortalToday(driverId?: number) {
  const query = driverId ? `?driver_id=${driverId}` : "";
  return request<DriverPortalData>(`/driver-portal/today/${query}`);
}

export function submitFuelLog(payload: {
  booking_id?: number | null;
  vehicle_id: number;
  driver_id: number;
  fuel_quantity_liters: number;
  fuel_cost: number;
  odometer_reading: number;
  fuel_station?: string;
}) {
  return request<any>("/fuel-logs/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
