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


// Portal Guest Profile Type
export type GuestProfile = {
  id: number;
  company: number;
  company_name?: string;
  name: string;
  phone: string;
  email?: string;
  employee_id?: string;
  is_active: boolean;
};

// Portal Corporate Approval Policy Type
export type CorporateApprovalPolicy = {
  id: number;
  company: number;
  company_name?: string;
  require_po: boolean;
  require_cost_centre: boolean;
  approval_threshold_amount: string | number;
};

// Portal Booking Request Status
export type BookingRequestStatus =
  | "draft"
  | "submitted"
  | "approval_required"
  | "approved"
  | "accepted"
  | "dispatched"
  | "active"
  | "completed"
  | "cancelled"
  | "rejected";

// Portal Booking Request Amendment Type
export type BookingRequestAmendment = {
  id: number;
  booking_request: number;
  amended_by: number;
  amended_by_username?: string;
  changes: Record<string, any>;
  reason: string;
  created_at: string;
};

// Portal Booking Request Type
export type BookingRequest = {
  id: number;
  booking_number: string;
  company: number;
  company_name?: string;
  requester: number;
  requester_username?: string;
  guest?: number | null;
  guest_details?: GuestProfile | null;
  passenger_name: string;
  passenger_phone: string;
  passenger_email?: string;
  pickup_address: string;
  drop_address?: string;
  pickup_city: string;
  pickup_at: string;
  expected_return_at: string;
  package: number;
  package_name?: string;
  vehicle_category: string;
  cost_centre?: string;
  po_reference?: string;
  status: BookingRequestStatus;
  approver?: number | null;
  approved_at?: string | null;
  quote_base_price?: string | number;
  quote_extra_km_rate?: string | number;
  quote_extra_hour_rate?: string | number;
  quote_driver_allowance?: string | number;
  amendments?: BookingRequestAmendment[];
  created_at: string;
  updated_at: string;
};

// Portal Signed Quote Response
export type SignedQuoteResponse = {
  company_id: number;
  pickup_city: string;
  package_id: number;
  package_name: string;
  vehicle_category: string;
  base_price: string;
  extra_km_rate: string;
  extra_hour_rate: string;
  driver_allowance: string;
  included_km: number;
  included_hours: number;
  expires_at: string;
  signature: string;
};

// Portal Discovery API
export function getPortalPackages(companyId?: number, city?: string) {
  let query = "";
  const params: string[] = [];
  if (companyId) params.push(`company_id=${companyId}`);
  if (city) params.push(`city=${encodeURIComponent(city)}`);
  if (params.length > 0) query = `?${params.join("&")}`;
  return request<RentalPackage[]>(`/portal/packages/${query}`);
}

// Portal Quoting API
export function getPortalQuote(payload: {
  company_id: number;
  pickup_city: string;
  package_id: number;
  vehicle_category?: string;
}) {
  return request<SignedQuoteResponse>("/portal/quote/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Portal Guest Profiles API
export function getGuestProfiles() {
  return request<GuestProfile[]>("/portal/guests/");
}

export function createGuestProfile(payload: Partial<GuestProfile>) {
  return request<GuestProfile>("/portal/guests/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Portal Booking Requests API
export function getBookingRequests() {
  return request<BookingRequest[]>("/portal/booking-requests/");
}

export type PortalInvoice = {
  id: number;
  invoice_number: string;
  type: "trip" | "chauffeur";
  type_display: string;
  issue_date: string;
  due_date: string;
  po_number: string;
  total_amount: number;
  balance_amount: number;
  status: string;
};

export type PortalStatement = {
  company_id: number;
  start_date: string;
  end_date: string;
  opening_balance: number;
  closing_balance: number;
  entries: Array<{
    date: string;
    type: string;
    reference: string;
    description: string;
    debit: number;
    credit: number;
    balance: number;
  }>;
};

export function getPortalInvoices() {
  return request<PortalInvoice[]>("/portal/invoices/");
}

export function getPortalStatement(companyId: number) {
  return request<PortalStatement>(`/portal/statements/?company_id=${companyId}`);
}

export function createBookingRequest(payload: Partial<BookingRequest> & { quote_signature?: string }) {
  return request<BookingRequest>("/portal/booking-requests/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function approveBookingRequest(id: number) {
  return request<BookingRequest>(`/portal/booking-requests/${id}/approve/`, {
    method: "POST",
  });
}

export function rejectBookingRequest(id: number) {
  return request<BookingRequest>(`/portal/booking-requests/${id}/reject/`, {
    method: "POST",
  });
}

export function cancelBookingRequest(id: number) {
  return request<BookingRequest>(`/portal/booking-requests/${id}/cancel/`, {
    method: "POST",
  });
}

export function amendBookingRequest(id: number, payload: Partial<BookingRequest> & { reason: string }) {
  return request<BookingRequest>(`/portal/booking-requests/${id}/amend/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
