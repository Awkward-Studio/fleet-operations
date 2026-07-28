# MMT Integration Readiness & Gaps

This document tracks what is ready for mock testing, what is already implemented in the fleet/driver flow, and what must still be built before MMT staging or production.

## Executive Summary

The project is ready for local/mock MMT experimentation, but it is not ready for a production URL flip.

The strongest parts are:

- Driver app stays behind our backend and does not call MMT directly.
- OTP mode is explicit: MMT rides use MMT OTP, local/personal rides use backend OTP.
- Driver ride flow now covers pre-ride checklist, pickup arrival, OTP verification, active ride tracking, and final odometer closeout.
- MMT outbound URL/header configuration is centralized enough to support mock/staging/prod switching later.

The main missing part is MMT business integration:

- MMT inbound endpoints still need to create/hold/confirm/cancel real internal trips.
- Backend trip transitions still need to trigger outbound MMT tracking/status updates.
- MMT authentication, idempotency, audit logs, and retry handling need to be formalized.

## Current Implementation

### Driver App

- Logs in through our backend.
- Shows assigned/current driver trip.
- Runs pre-ride checklist with starting odometer photo.
- Opens native pickup navigation.
- Marks arrival at pickup.
- Verifies guest pickup OTP.
- Starts live GPS tracking for `ACTIVE` trips.
- Shows `Live GPS Tracking Active` badge.
- Captures ending odometer photo and ending KM.
- Submits trip completion through `/api/fleet/trips/{id}/complete/`.
- Stops local GPS tracking after successful completion.

### Fleet Backend

- Provides `/api/fleet/driver/my-trips/current/`.
- Supports trip status transitions.
- Stores pre-ride checklist and odometer evidence.
- Stores GPS telemetry in `TripLocationLog`.
- Supports local `TripOTP` generation.
- Supports MMT pickup OTP verification from `Trip.pricing_snapshot["verification_code"]`.
- Exposes `otp_mode` to the driver app.
- Successful pickup OTP verification activates the trip, vehicle, and driver.
- Completion updates trip status, vehicle status, vehicle city/odometer, and driver status.

### MMT App

- Django `makemytrip` app exists.
- Routes are mounted under `/api/makemytrip/`.
- MMT serializers exist for mock/API payload shapes.
- Service layer centralizes outbound MMT calls.
- Local development currently points to the Apiary mock server.

## Configuration Readiness

Current setup is close to URL-switchable for the existing mock/proxy calls:

- Base URL is centralized.
- Headers are centralized.
- Endpoint paths are appended in the service layer.

Before staging:

- Rename or alias `MAKEMYTRIP_MOCK_SERVER_URL` to `MAKEMYTRIP_BASE_URL`.
- Keep Apiary mock as the local default.
- Move credentials and headers to environment variables.
- Add clear local/staging/production settings.

## Open Gaps

### 1. Inbound MMT APIs Need Real Business Behavior

Current MMT views mostly validate payloads and proxy to the mock service. They should become our actual partner endpoints.

Needed behavior:

- `partnersearchendpoint`
  - Check actual fleet availability.
  - Return real cab categories/SKUs.
  - Return real pricing and fare breakup.

- `partnerblockendpoint`
  - Hold inventory for the selected option.
  - Generate and return our partner reference number.
  - Save MMT `search_id`.
  - Save pickup OTP from `verification_code`.
  - Save end-trip OTP from `trip_end_verification_code`, if MMT requires it.
  - Store block expiry.

- `partnerpaidendpoint`
  - Confirm booking.
  - Create or update internal `Trip`.
  - Save MMT `order_reference_number`.
  - Attach passenger, pickup, package, pricing, and OTP data.

- `partnercancelendpoint`
  - Find booking by partner/MMT reference.
  - Cancel trip.
  - Release held vehicle/driver inventory.
  - Store cancellation reason.

- `partnercustomerarrivedendpoint`
  - Store customer arrived/landed event.
  - Surface to dispatch or driver app if operationally useful.

- `booking/details`
  - Return our latest stored booking/trip state.
  - Stop proxying once we own the booking record.

### 2. Outbound MMT Updates Are Not Wired

After a booking is confirmed, backend trip events should call MMT.

Missing outbound events:

- Assign Chauffeur after driver/vehicle assignment.
- Start / left for pickup after pre-ride checklist.
- Arrived when driver reaches pickup.
- Pickup / boarded after OTP verification.
- Alight / completed after final closeout.
- Not boarded, if needed.
- Live location updates during active ride.

These should be triggered by backend state changes, not by the Flutter app.

### 3. MMT Authentication Is Not Production-Ready

Current MMT views use open permissions.

Needed:

- Basic Auth validation for inbound MMT calls.
- Environment-backed credentials.
- Confirmation of MMT IP allowlisting requirements.
- Request logging with credentials redacted.
- Consistent auth failure responses.

### 4. MMT Data Mapping Is Incomplete

Important MMT fields need explicit storage/mapping:

- `search_id`
- `reference_number`
- `partner_reference_number`
- `order_reference_number`
- `booking_id`
- passenger name and phone
- pickup address and coordinates
- package/duty type
- cab category/SKU
- fare breakup
- amount paid / amount to collect
- `verification_code`
- `trip_end_verification_code`

Recommended model direction:

- Add explicit MMT booking/reference fields or a separate integration table.
- Keep raw MMT payloads for audit/debugging.
- Avoid burying important references only inside `pricing_snapshot`.

### 5. OTP Gaps

Implemented for pickup:

- MMT/local OTP mode detection.
- Local OTP for non-MMT rides.
- MMT OTP for MMT rides.
- Backend-owned activation after successful pickup OTP.

Still open:

- Persist MMT pickup OTP during `partnerblockendpoint`.
- Confirm whether MMT pickup OTP is always present.
- Confirm whether `trip_end_verification_code` is required for all MMT trips or only rental/local packages.
- Implement end-trip OTP if MMT requires it.
- Add SMS/WhatsApp delivery for local OTP resend.
- Store OTP source explicitly if audit needs it.

### 6. Metering Policy Milestones Are Not Modeled Yet

Current fleet trip statuses are simple:

- `ASSIGNED`
- `EN_ROUTE_PICKUP`
- `ARRIVED_AT_PICKUP`
- `ACTIVE`
- `COMPLETED`
- `CANCELLED`

Task 08 introduced richer policy-driven milestones:

- `GUEST_DROPPED`
- `RETURNING_TO_GARAGE`
- final garage return closeout for `GARAGE_TO_GARAGE`
- pickup-to-drop/disposal closeout when backend validation allows it

Current driver completion performs `ACTIVE -> COMPLETED` with final odometer evidence. This works for the current backend, but it does not yet distinguish guest drop from garage return.

### 7. Location Tracking Gaps

Implemented locally:

- Backend stores `TripLocationLog`.
- Driver app starts GPS tracking for `ACTIVE` trips.
- Driver app uses Android foreground/background service.
- Driver app posts telemetry every 15 seconds, with a 50-meter movement threshold.
- Driver app stops local tracking when the trip is no longer `ACTIVE`.

Still open:

- Forward live location to MMT tracking APIs.
- Add outbound retry queue when MMT is unavailable.
- Validate Android background behavior on a physical device across screen lock, app backgrounding, and battery optimization.

### 8. Idempotency, Audit, And Retry Handling

Needed:

- Idempotency/dedupe rules for MMT inbound calls.
- Safe repeated handling for Block, Paid, Cancel, and status callbacks.
- Audit log for inbound MMT requests.
- Audit log for outbound MMT requests.
- Retry queue for outbound MMT updates.
- Clear timeout and partial-failure handling.

### 9. Test Coverage

Existing tests cover local fleet trip operations and basic MMT serializer/service behavior.

Needed before staging:

- Search returns real fleet availability and pricing.
- Block creates inventory hold and stores OTP/reference data.
- Paid creates or confirms a trip.
- Cancel releases inventory.
- Driver state transitions trigger outbound MMT events.
- Duplicate/retried MMT calls are safe.
- Invalid MMT auth is rejected.
- MMT OTP verification works from persisted Block data.
- End-trip OTP works if required.

## Recommended Build Order

1. Rename MMT config to `MAKEMYTRIP_BASE_URL` and environment-backed credentials.
2. Add inbound Basic Auth for `/api/makemytrip/`.
3. Add MMT booking/reference fields or an integration model.
4. Implement `partnersearchendpoint` using real fleet availability and pricing.
5. Implement `partnerblockendpoint` as inventory hold plus OTP/reference capture.
6. Implement `partnerpaidendpoint` as trip creation/confirmation.
7. Implement `partnercancelendpoint` and `booking/details`.
8. Implement outbound MMT status updates from backend trip transitions.
9. Implement outbound MMT location forwarding.
10. Add idempotency, audit logs, retry handling, and staging tests.
