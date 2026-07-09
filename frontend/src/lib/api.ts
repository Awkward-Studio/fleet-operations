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
  const response = await fetch(`${getApiBase()}/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with status ${response.status}`);
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


export function getDrivers() {
  return request<Driver[]>("/drivers/");
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
