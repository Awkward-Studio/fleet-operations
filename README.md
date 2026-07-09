# Index Fleet

A bespoke fleet-management platform scaffold with a Next.js frontend and Django REST backend.

The first slice focuses on the operational base:

- vehicles and driver records
- car-to-driver assignment
- trip assignment and lifecycle tracking
- driver and vehicle availability
- compliance expiry checks
- predictive availability for future return trips
- role-aware dashboard foundations

## Project Structure

```text
backend/   Django + Django REST Framework API
frontend/  Next.js App Router frontend
```

## Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver 0.0.0.0:8001
```

API base: `http://localhost:8001/api/` or `http://YOUR-LAN-IP:8001/api/`

## Frontend

```bash
cd frontend
npm install
npm run dev:network
```

App URL: `http://localhost:3001` or `http://YOUR-LAN-IP:3001`

By default, the browser calls the backend on the same hostname at port `8001`.
Set `NEXT_PUBLIC_API_BASE_URL` only if your backend is on a different host or port.

## Frontend Pages

- `/` - operations dashboard
- `/trips` - trip creation, assignment, and lifecycle updates
- `/vehicles` - vehicle registry, assigned drivers, current city, and next availability
- `/drivers` - driver roster and current work
- `/tracking` - vehicle status board using city, assigned trip, and predicted next location
- `/availability` - predictive availability by vehicle
- `/compliance` - permit, insurance, pollution, and fitness guardrails
- `/ota` - OTA bidding readiness view

## Tracking Model

The current scaffold tracks vehicles at an operational level:

1. A dispatcher creates or receives a trip.
2. A dispatcher assigns one available driver and one compliant idle vehicle.
3. Trip status updates move the vehicle through the state machine.
4. When a trip is completed, the backend marks the vehicle idle and moves its current city to the trip drop city.
5. Predictive availability calculates where and when the vehicle can take the next trip.

GPS-level live tracking can be added by creating a vehicle location ping model with latitude, longitude, speed, heading, and timestamp.

## Core API Resources

- `GET /api/dashboard/summary/`
- `GET /api/vehicles/`
- `GET /api/drivers/`
- `GET /api/trips/`
- `POST /api/trips/`
- `POST /api/trips/{id}/assign/`
- `POST /api/trips/{id}/transition/`
- `GET /api/availability/`
