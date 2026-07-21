export type Driver = {
  id: number;
  name: string;
  phone: string;
  license_number: string;
  home_base: string;
  status: string;
  rating: string;
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

export type User = {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
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

