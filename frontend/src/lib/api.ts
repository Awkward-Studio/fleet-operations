export type UploadedAsset = {
  id: string;
  kind: "image" | "invoice" | "pdf";
  original_name: string;
  content_type: string;
  created_at: string;
  href: string;
};

export type Driver = {
  id: number;
  name: string;
  phone: string;
  license_number: string;
  home_base: string;
  status: string;
  rating: string;
  aadhaar_card?: UploadedAsset | null;
  driving_license?: UploadedAsset | null;
  driving_license_expiry_date?: string | null;
  police_clearance_certificate?: UploadedAsset | null;
};

export type Vehicle = {
  id: number;
  registration_number: string;
  make: string;
  model: string;
  category: string;
  current_city: string;
  status: string;
  assigned_driver: Driver | null;
  permit_expires_on: string;
  insurance_expires_on: string;
  pollution_expires_on: string;
  fitness_expires_on: string;
  compliance_blockers: string[];
  is_compliant: boolean;
  odometer_km: number;
};

export type Trip = {
  id: number;
  customer_name: string;
  pickup_city: string;
  drop_city: string;
  pickup_at: string;
  estimated_drop_at: string;
  status: string;
  vehicle: Vehicle | null;
  driver: Driver | null;
  ota_source: string;
  fare_amount: string;
  notes?: string;
  pickup_latitude?: string | number | null;
  pickup_longitude?: string | number | null;
  drop_latitude?: string | number | null;
  drop_longitude?: string | number | null;
  distance_km?: string | number | null;
};

export type Availability = {
  vehicle_id: number;
  registration_number: string;
  category: string;
  available_from: string;
  available_city: string;
  driver_name: string | null;
  compliance_blockers: string[];
};

export type Summary = {
  vehicles: {
    total: number;
    idle: number;
    on_trip: number;
    maintenance: number;
  };
  drivers: {
    total: number;
    available: number;
    assigned: number;
    on_trip: number;
  };
  trips: {
    today: number;
    unassigned: number;
    active: number;
  };
  compliance_alerts: number;
};

export type CustomerContact = {
  id: number;
  customer: number;
  name: string;
  contact_type: string;
  phone: string;
  email: string;
  is_primary: boolean;
  created_at?: string;
  updated_at?: string;
};

export type CorporateCustomer = {
  id: number;
  code: string;
  legal_name: string;
  display_name: string;
  status: "ACTIVE" | "INACTIVE" | "SUSPENDED";
  is_active: boolean;
  gstin: string;
  billing_address: string;
  billing_email: string;
  billing_phone: string;
  booking_contact_name: string;
  booking_contact_email: string;
  booking_contact_phone: string;
  payment_terms_days: number;
  po_required: boolean;
  notes: string;
  contacts?: CustomerContact[];
  active_contract_summary?: {
    id: number;
    title: string;
    version_name: string;
    rates_count: number;
  } | null;
  created_at?: string;
  updated_at?: string;
};

export type ContractRate = {
  id?: number;
  contract?: number;
  city: string;
  vehicle_category: string;
  duty_type: string;
  included_hours: number;
  included_km: number;
  base_rate: string | number;
  extra_hour_rate: string | number;
  extra_km_rate: string | number;
  switch_threshold_hours?: number | null;
  switch_threshold_km?: number | null;
  outstation_daily_min_km?: number | null;
  created_at?: string;
  updated_at?: string;
};

export type ContractAllowance = {
  id?: number;
  contract?: number;
  allowance_type: string;
  amount: string | number;
  description?: string;
  created_at?: string;
  updated_at?: string;
};

export type CorporateContract = {
  id: number;
  customer: number;
  customer_display_name?: string;
  title: string;
  version_name: string;
  effective_start: string;
  effective_end?: string | null;
  status: "DRAFT" | "ACTIVE" | "EXPIRED" | "TERMINATED" | "ARCHIVED";
  currency: string;
  cgst_rate: string | number;
  sgst_rate: string | number;
  payment_terms_days?: number | null;
  cancellation_terms?: string;
  metering_policy: string;
  notes?: string;
  rates?: ContractRate[];
  allowances?: ContractAllowance[];
  created_at?: string;
  updated_at?: string;
};

export type PricingQuote = {
  customer: {
    id: number;
    code: string;
    display_name: string;
  };
  contract: {
    id: number;
    title: string;
    version_name: string;
    metering_policy: string;
  };
  rate: {
    id: number;
    city: string;
    vehicle_category: string;
    duty_type: string;
  };
  inputs: {
    pickup_datetime: string;
    pickup_city: string;
    vehicle_category: string;
    duty_type: string;
    planned_hours: number;
    planned_km: number;
    effective_km: number;
    outstation_days: number;
  };
  itemized_charges: {
    base_charge: string;
    included_hours: number;
    included_km: number;
    excess_hours: string;
    extra_hour_rate: string;
    excess_hour_charge: string;
    excess_km: string;
    extra_km_rate: string;
    excess_km_charge: string;
    allowances: any[];
    allowances_total: string;
    subtotal: string;
    cgst_rate: string;
    cgst_amount: string;
    sgst_rate: string;
    sgst_amount: string;
    total_amount: string;
  };
  total_amount: string;
  explanation: string;
};

export type User = {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role?: string;
  permissions?: string[];
};

export type AuthResponse = {
  access: string;
  refresh: string;
};

export type RegisterResponse = {
  message: string;
  user: User;
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

let refreshPromise: Promise<boolean> | null = null;

async function attemptTokenRefresh(): Promise<boolean> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    const refreshToken = typeof window !== "undefined" ? localStorage.getItem("refreshToken") : null;
    if (!refreshToken) {
      return false;
    }

    try {
      const res = await fetch(`${getApiBase()}/api/auth/token/refresh/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ refresh: refreshToken })
      });

      if (res.ok) {
        const data = await res.json() as { access: string; refresh?: string };
        if (typeof window !== "undefined") {
          localStorage.setItem("accessToken", data.access);
          if (data.refresh) {
            localStorage.setItem("refreshToken", data.refresh);
          }
        }
        return true;
      }
    } catch (e) {
      console.error("Token refresh failed:", e);
    }

    if (typeof window !== "undefined") {
      localStorage.removeItem("accessToken");
      localStorage.removeItem("refreshToken");
    }
    return false;
  })();

  const result = await refreshPromise;
  refreshPromise = null;
  return result;
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

  let response = await fetch(`${getApiBase()}/api${path}`, {
    ...init,
    headers: {
      ...headers,
      ...init?.headers
    },
    cache: "no-store"
  });

  if (
    response.status === 401 &&
    path !== "/auth/login/" &&
    path !== "/auth/register/" &&
    path !== "/auth/token/refresh/"
  ) {
    const refreshed = await attemptTokenRefresh();
    if (refreshed && typeof window !== "undefined") {
      const newToken = localStorage.getItem("accessToken");
      const retryHeaders = {
        ...headers,
        ...init?.headers,
        "Authorization": `Bearer ${newToken}`
      };
      response = await fetch(`${getApiBase()}/api${path}`, {
        ...init,
        headers: retryHeaders,
        cache: "no-store"
      });
    }
  }

  if (!response.ok) {
    const body = await response.text();
    let errMsg = body;
    try {
      const json = JSON.parse(body);
      errMsg = json.detail || json.message || Object.values(json).flat().join(" ") || body;
    } catch {
      // use raw body text
    }
    throw new Error(errMsg || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getSummary() {
  return request<Summary>("/dashboard/summary/");
}

export function getVehicles() {
  return request<Vehicle[]>("/vehicles/");
}

export function createVehicle(payload: {
  registration_number: string;
  make: string;
  model: string;
  category: string;
  current_city: string;
  status: string;
  assigned_driver_id: number | null;
  permit_expires_on: string;
  insurance_expires_on: string;
  pollution_expires_on: string;
  fitness_expires_on: string;
  odometer_km: number;
}) {
  return request<Vehicle>("/vehicles/", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}


export function updateVehicle(id: number, payload: Partial<{
  registration_number: string;
  make: string;
  model: string;
  category: string;
  current_city: string;
  status: string;
  assigned_driver_id: number | null;
  permit_expires_on: string;
  insurance_expires_on: string;
  pollution_expires_on: string;
  fitness_expires_on: string;
  odometer_km: number;
}>) {
  return request<Vehicle>(`/vehicles/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteVehicle(id: number) {
  return request<void>(`/vehicles/${id}/`, {
    method: "DELETE"
  });
}

export function getDrivers() {
  return request<Driver[]>("/drivers/");
}

export function createDriver(payload: {
  name: string;
  phone: string;
  license_number: string;
  home_base: string;
  status?: string;
  rating?: string | number;
  aadhaar_card_id?: string | null;
  driving_license_id?: string | null;
  driving_license_expiry_date?: string | null;
  police_clearance_certificate_id?: string | null;
}) {
  return request<Driver>("/drivers/", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateDriver(id: number, payload: Partial<{
  name: string;
  phone: string;
  license_number: string;
  home_base: string;
  status: string;
  rating: string | number;
  aadhaar_card_id?: string | null;
  driving_license_id?: string | null;
  driving_license_expiry_date?: string | null;
  police_clearance_certificate_id?: string | null;
}>) {
  return request<Driver>(`/drivers/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteTrip(id: number) {
  return request<void>(`/trips/${id}/`, {
    method: "DELETE"
  });
}

export function deleteDriver(id: number) {
  return request<void>(`/drivers/${id}/`, {
    method: "DELETE"
  });
}

export function getTrips() {
  return request<Trip[]>("/trips/");
}

export function getAvailability() {
  return request<Availability[]>("/availability/");
}

export function createTrip(payload: {
  customer_name: string;
  pickup_city: string;
  drop_city: string;
  pickup_at: string;
  estimated_drop_at: string;
  ota_source: string;
  fare_amount: string;
  pickup_latitude?: string | number | null;
  pickup_longitude?: string | number | null;
  drop_latitude?: string | number | null;
  drop_longitude?: string | number | null;
  distance_km?: string | number | null;
}) {
  return request<Trip>("/trips/", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function assignTrip(tripId: number, vehicleId: number, driverId: number) {
  return request<Trip>(`/trips/${tripId}/assign/`, {
    method: "POST",
    body: JSON.stringify({ vehicle_id: vehicleId, driver_id: driverId })
  });
}

export function transitionTrip(tripId: number, status: string) {
  return request<Trip>(`/trips/${tripId}/transition/`, {
    method: "POST",
    body: JSON.stringify({ status })
  });
}

export function loginUser(payload: Record<string, string>) {
  return request<AuthResponse>("/auth/login/", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function registerUser(payload: Record<string, string>) {
  return request<RegisterResponse>("/auth/register/", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getCurrentUser() {
  return request<User>("/auth/me/");
}

export function logoutUser(payload: { refresh: string }) {
  return request<{ message: string }>("/auth/logout/", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function changeUserPassword(payload: Record<string, string>) {
  return request<{ message: string }>("/auth/change-password/", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function uploadAsset(
  file: File,
  kind: "image" | "pdf" | "invoice",
  onProgress?: (progress: number) => void
): Promise<UploadedAsset> {
  return new Promise((resolve, reject) => {
    const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
    const xhr = new XMLHttpRequest();
    const endpointMap = {
      image: "/uploads/images/",
      pdf: "/uploads/pdfs/",
      invoice: "/uploads/invoices/",
    };
    const url = `${getApiBase()}/api${endpointMap[kind]}`;

    xhr.open("POST", url);

    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }

    if (onProgress && xhr.upload) {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100);
          onProgress(percentComplete);
        }
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText) as UploadedAsset;
          resolve(data);
        } catch (e) {
          reject(new Error("Failed to parse upload response"));
        }
      } else {
        let errMsg = xhr.responseText;
        try {
          const json = JSON.parse(xhr.responseText);
          errMsg = json.error || json.detail || json.message || Object.values(json).flat().join(" ") || xhr.responseText;
        } catch {
          // Keep raw response text
        }
        reject(new Error(errMsg || `Upload failed with status ${xhr.status}`));
      }
    };

    xhr.onerror = () => {
      reject(new Error("Network error during file upload."));
    };

    const formData = new FormData();
    formData.append("file", file);
    xhr.send(formData);
  });
}

// Customers API
export function getCustomers(params?: { search?: string; status?: string; is_active?: boolean }) {
  const query = new URLSearchParams();
  if (params?.search) query.append("search", params.search);
  if (params?.status) query.append("status", params.status);
  if (params?.is_active !== undefined) query.append("is_active", String(params.is_active));
  const queryString = query.toString() ? `?${query.toString()}` : "";
  return request<CorporateCustomer[]>(`/customers/${queryString}`);
}

export function getCustomer(id: number) {
  return request<CorporateCustomer>(`/customers/${id}/`);
}

export function createCustomer(payload: Partial<CorporateCustomer>) {
  return request<CorporateCustomer>("/customers/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCustomer(id: number, payload: Partial<CorporateCustomer>) {
  return request<CorporateCustomer>(`/customers/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteCustomer(id: number) {
  return request<{ detail: string }>(`/customers/${id}/`, {
    method: "DELETE",
  });
}

// Customer Contacts API
export function getCustomerContacts(customerId: number) {
  return request<CustomerContact[]>(`/customers/${customerId}/contacts/`);
}

export function createCustomerContact(customerId: number, payload: Partial<CustomerContact>) {
  return request<CustomerContact>(`/customers/${customerId}/contacts/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCustomerContact(id: number, payload: Partial<CustomerContact>) {
  return request<CustomerContact>(`/contacts/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteCustomerContact(id: number) {
  return request<void>(`/contacts/${id}/`, {
    method: "DELETE",
  });
}

// Contracts API
export function getContracts(params?: { customer?: number; status?: string; search?: string }) {
  const query = new URLSearchParams();
  if (params?.customer) query.append("customer", String(params.customer));
  if (params?.status) query.append("status", params.status);
  if (params?.search) query.append("search", params.search);
  const queryString = query.toString() ? `?${query.toString()}` : "";
  return request<CorporateContract[]>(`/contracts/${queryString}`);
}

export function getContract(id: number) {
  return request<CorporateContract>(`/contracts/${id}/`);
}

export function createContract(payload: Partial<CorporateContract>) {
  return request<CorporateContract>("/contracts/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateContract(id: number, payload: Partial<CorporateContract>) {
  return request<CorporateContract>(`/contracts/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function activateContract(id: number) {
  return request<CorporateContract>(`/contracts/${id}/activate/`, {
    method: "POST",
  });
}

export function validateContract(id: number) {
  return request<{ is_valid: boolean; errors: string[]; warnings: string[]; rates_count: number }>(
    `/contracts/${id}/validate_contract/`,
    { method: "POST" }
  );
}

export function copyContract(id: number) {
  return request<CorporateContract>(`/contracts/${id}/copy_contract/`, {
    method: "POST",
  });
}

export function deleteContract(id: number) {
  return request<void>(`/contracts/${id}/`, {
    method: "DELETE",
  });
}

// Pricing Quote API
export function getPricingQuote(payload: {
  customer: number;
  pickup_datetime: string;
  pickup_city: string;
  vehicle_category: string;
  duty_type: string;
  planned_hours?: number;
  planned_km?: number;
  outstation_days?: number;
  allowances?: any[];
}) {
  return request<PricingQuote>("/pricing/quote/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

