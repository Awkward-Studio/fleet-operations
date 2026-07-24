# MMT / InCabs API Flow - Simple Notes

Source: official Apiary docs at `https://incabsapipartnerdocumentationv3.docs.apiary.io`

## One-Line Understanding

MMT sells the cab to the customer. We are the cab supplier. MMT asks our system for availability, blocks a cab, confirms the booking, and then we update MMT as the trip progresses.

## Who Calls Whom

| Step | Who calls | Whose endpoint | Endpoint | Meaning |
|---|---|---|---|---|
| 1 | MMT | Our endpoint | `POST /partnersearchendpoint` | MMT asks: "Do you have cabs for this route/time and what is the fare?" |
| 2 | MMT | Our endpoint | `POST /partnerblockendpoint` | MMT says: "Customer selected this cab option. Hold it for now." |
| 3 | MMT | Our endpoint | `POST /partnerpaidendpoint` | MMT says: "Customer paid/confirmed. Create the booking." |
| 4 | MMT | Our endpoint | `POST /partnercancelendpoint` | MMT says: "Booking is cancelled." |
| 5 | MMT | Our endpoint | `POST /partnercustomerarrivedendpoint` | MMT says: "Customer has landed/arrived." |
| 6 | MMT | Our endpoint | `GET /api/partner/v1/booking/details` | MMT asks: "What is the latest status of this booking?" |
| 7 | We | MMT endpoint | Assign Chauffeur | We send driver and vehicle details to MMT. |
| 8 | We | MMT endpoint | Start / Arrived / Pickup / Alight | We send trip status events to MMT. |
| 9 | We | MMT endpoint | Update Location | We send live cab location to MMT. |

## Simple Full Flow

```text
Customer opens MMT and searches Gurgaon -> Jaipur cab.

MMT -> Our Search API
MMT asks our system for available cab options and prices.

Our system -> MMT
We return car types/SKUs like sedan, SUV, hatchback with fare details.

Customer selects one option.

MMT -> Our Block API
MMT asks us to hold that selected SKU.

Our system -> MMT
We return a partner reference number.
This block is valid for 30 minutes according to the FAQ.

Customer pays or confirms.

MMT -> Our Paid API
MMT sends passenger details, our partner reference number, and MMT booking ID.

Our system
We create the actual booking/trip internally.

Our system -> MMT
We return success.

Before trip starts
We -> MMT Assign Chauffeur API
We send driver and vehicle details.

During trip
We -> MMT tracking APIs
We send Start, Arrived, Pickup/Boarded, Alight, Not Boarded, and location updates.

If customer cancels
MMT -> Our Cancel API
We cancel/release the booking.
```

## The Important IDs

| Field | Created by | Used for |
|---|---|---|
| `search_id` | MMT | Links Search to Block. MMT sends it in Search and again in Block. |
| `reference_number` | Us | Our block/booking reference. We return it from Block. |
| `partner_reference_number` | Us | Same idea as our `reference_number`; MMT sends it in Paid/Cancel. |
| `order_reference_number` | MMT | Final MMT booking ID. MMT sends it in Paid. |
| `booking_id` | MMT | In post-booking APIs, docs say this means `order_reference_number`. |

## Endpoint 1: Search

Who calls it:

```text
MMT -> Us
```

Endpoint:

```http
POST /partnersearchendpoint
```

MMT sends:

```json
{
  "source": {
    "address": "DLF Place, Gurgaon, Haryana, India",
    "latitude": 28.48968,
    "longitude": 77.09224,
    "city": "Gurgaon"
  },
  "destination": {
    "address": "Jaipur, Rajasthan, India",
    "latitude": 26.91243,
    "longitude": 75.78727,
    "city": "Jaipur"
  },
  "trip_type": "ONE_WAY",
  "start_time": "2021-02-08 19:55:00",
  "search_id": "56c5c8a269702d3a1b0b0000",
  "partner_name": "GOMMT",
  "search_tags": ["B2C"],
  "one_way_distance": 230,
  "is_instant_search": false,
  "mandatory_inclusions": ["AE", "ST", "TOLL"],
  "trip_type_details": {
    "basic_trip_type": "OUTSTATION",
    "airport_type": "NONE",
    "train_type": "NONE"
  }
}
```

We send back:

```json
{
  "response": {
    "distance_booked": 230,
    "is_instant_search": false,
    "is_instant_available": true,
    "start_time": "2021-02-08 19:55:00",
    "communication_type": "PRE",
    "verification_type": "OTP",
    "car_types": [
      {
        "sku_id": "SEDAN_BASIC_1",
        "type": "sedan",
        "subcategory": "basic",
        "combustion_type": "Petrol",
        "model": "Dzire",
        "carrier": true,
        "make_year_type": "Older",
        "make_year": 2017,
        "cancellation_rule": "SUPER_FLEXI",
        "fare_details": {
          "base_fare": 2010,
          "per_km_charge": 20,
          "per_km_extra_charge": 10,
          "total_driver_charges": 0,
          "extra_charges": {
            "toll_charges": {
              "amount": 100,
              "is_included_in_base_fare": false,
              "is_included_in_grand_total": true,
              "is_applicable": true
            },
            "state_tax": {
              "amount": 300,
              "is_included_in_base_fare": false,
              "is_included_in_grand_total": true,
              "is_applicable": true
            }
          }
        }
      }
    ]
  },
  "error": null,
  "code": null
}
```

In plain English:

MMT asks for options. We return cab categories/SKUs and fare breakup. This is not the final booking yet.

## Endpoint 2: Block

Who calls it:

```text
MMT -> Us
```

Endpoint:

```http
POST /partnerblockendpoint
```

MMT sends:

```json
{
  "distance": 230,
  "search_id": "56c5c8a269702d3a1b0b0000",
  "vehicle_type": "sedan",
  "vehicle_subcategory": "basic",
  "verification_code": "2748",
  "trip_end_verification_code": "5433",
  "fare_details": {
    "base_fare": 2010,
    "toll_charges": 100,
    "state_tax": 100,
    "night_charges": 0,
    "add_ons_price": 200,
    "total_fare": 2410
  },
  "vehicle_details": {
    "sku_id": "SEDAN_BASIC_1",
    "type": "sedan",
    "subcategory": "basic",
    "combustion_type": "Petrol",
    "model": "Dzire",
    "carrier": true,
    "make_year_type": "Older",
    "make_year": 2017,
    "cancellation_rule": "SUPER_FLEXI"
  }
}
```

We send back:

```json
{
  "response": {
    "success": true,
    "reference_number": "DL519000019",
    "verification_code": "2748",
    "trip_end_verification_code": "5433"
  },
  "error": null,
  "code": null
}
```

In plain English:

MMT says the customer picked this option. We hold inventory and give MMT our reference number. The FAQ says time between Block and Confirm is 30 minutes.

## Endpoint 3: Paid / Confirm

Who calls it:

```text
MMT -> Us
```

Endpoint:

```http
POST /partnerpaidendpoint
```

MMT sends:

```json
{
  "passenger": {
    "name": "Avikal Kohli",
    "email": "avikal_test@gmail.com",
    "phone_number": "7665544221",
    "country_code": "91"
  },
  "partner_reference_number": "DL519000019",
  "order_reference_number": "NC770346218670301",
  "total_fare": 2210,
  "amount_to_be_collected": 200,
  "platform_fee": 50,
  "booking_gst": 50,
  "partner_name": "GOMMT"
}
```

We send back:

```json
{
  "response": {
    "success": true,
    "trip_url": "https://our-trip-page-url"
  },
  "error": null,
  "code": null
}
```

In plain English:

This is the actual booking confirmation. MMT sends passenger details and MMT booking ID. We should create the booking/trip in our system here.

## Endpoint 4: Cancel

Who calls it:

```text
MMT -> Us
```

Endpoint:

```http
POST /partnercancelendpoint
```

MMT sends booking IDs and cancellation reason.

Example:

```json
{
  "partner_reference_number": "DL519000019",
  "order_reference_number": "NC770346218670301",
  "cancelled_by": "Customer",
  "cancellation_reason": "Customer cancelled booking"
}
```

We send back success/failure.

In plain English:

MMT tells us the booking is cancelled. We release the vehicle/driver and mark the trip cancelled.

## Endpoint 5: Customer Landed

Who calls it:

```text
MMT -> Us
```

Endpoint:

```http
POST /partnercustomerarrivedendpoint
```

MMT sends:

```json
{
  "booking_id": "NC725926968039039426"
}
```

We send back:

```json
{
  "response": {
    "success": true
  },
  "error": null,
  "code": null
}
```

In plain English:

Mostly useful for airport/train pickup. MMT tells us customer has landed/arrived.

## Endpoint 6: Booking Details

Who calls it:

```text
MMT -> Us
```

Endpoint:

```http
GET /api/partner/v1/booking/details?order_reference_number=NC770346218670301&partner_reference_number=DL519000019
```

We send back:

```json
{
  "response": {
    "status": "CONFIRMED",
    "failure_reason": "",
    "reference_number": "DL519000019",
    "verification_code": "3476"
  }
}
```

In plain English:

If MMT is unsure whether booking got confirmed, it asks us for latest status.

Possible status values:

```text
CONFIRMED
FAILURE
MISSING
HOLD
CANCELLED
TRAVELLED
NOT_TRAVELLED
```

## After Booking: We Call MMT

Once booking exists, direction changes.

```text
Before booking confirmed: MMT calls us.
After booking confirmed: we call MMT for updates.
```

Post-booking APIs we call on MMT side:

| We call MMT API | Meaning |
|---|---|
| Assign Chauffeur | Send driver and vehicle details. |
| Reassign Chauffeur | Change driver/vehicle. |
| Unassign Chauffeur | Remove assigned driver/vehicle. |
| Start / Left for Pickup | Driver started moving toward pickup. |
| Arrived | Driver reached pickup. |
| Pickup / Boarded | Customer boarded cab. |
| Alight | Customer completed trip / got down. |
| Not Boarded | Customer did not board. |
| Update Location | Send live cab location. |
| Detach Trip | Give up booking if we cannot serve it. Docs warn SLA penalty may apply. |

Important:

- In these APIs, `booking_id` means MMT `order_reference_number`.
- Tracking timestamps must be in milliseconds.
- Tracking events are mandatory.
- Driver mobile should be 10 digits, no `91` or `+91`.
- Chauffeur ID and vehicle ID should be 10 characters or less.

Plain version:

MMT first gives us the booking through `Paid`. After that, MMT expects us to keep them updated because their customer app depends on those updates.

Example:

```text
MMT -> Us: Paid API
Booking confirmed.

Us -> MMT: Assign Chauffeur
We tell MMT driver name, phone, cab number, vehicle details.

Us -> MMT: Start / Left for Pickup
Driver has started going to pickup point.

Us -> MMT: Arrived
Driver reached pickup point.

Us -> MMT: Pickup / Boarded
Customer sat in the cab.

Us -> MMT: Update Location
We keep sending GPS/location updates during trip.

Us -> MMT: Alight
Trip ended.
```

So there are two systems:

```text
Pre-booking:
MMT calls our server.

Post-booking:
Our server/driver app calls MMT server.
```

This means we need both:

- public APIs for MMT to call
- outbound API integration to call MMT after booking

## Auth, Security, And Access

Docs say MMT supports Basic Auth.

Basic Auth means every API call includes an HTTP header like:

```http
Authorization: Basic <encoded-username-password-or-token>
Content-type: Application/json
```

For pre-booking APIs:

```text
MMT -> Our API
```

MMT will send Basic Auth credentials in the request header. Our server must check those credentials before accepting Search, Block, Paid, Cancel, etc.

For post-booking APIs:

```text
Our API -> MMT API
```

We will send Basic Auth credentials given by MMT when calling their Assign Chauffeur, Tracking, Location, Payment Details APIs.

What we need from MMT:

- staging Basic Auth username/token
- production Basic Auth username/token
- whether token is same for all APIs or different per flow
- whether MMT also wants IP whitelisting
- whether we need to whitelist MMT's IPs on our side
- production base URL for MMT post-booking APIs
- our production endpoint URL that MMT should call

Example inbound request from MMT to us:

```http
POST https://our-domain.com/partnersearchendpoint
Authorization: Basic <mmt-provided-token>
Content-type: Application/json
```

Example outbound request from us to MMT:

```http
POST https://cabs-partners-staging.makemytrip.com/tracking/pp2/<mmt-post-booking-endpoint>
Authorization: Basic <mmt-provided-token>
Content-type: Application/json
```

Ask clearly:

```text
Will the same Basic Auth credential be used both ways, or separate credentials?
```

Also ask:

```text
Will MMT call our staging server first for UAT?
What public URL should we give for UAT?
Do they need SSL certificate validation rules?
Do they need static IP from our side?
Will their staging and production IPs be shared for whitelisting?
```

## Rental Booking

Rental is like normal booking, but Search has only source.

Rules:

```text
trip_type = LOCAL_RENTAL
package_id tells rental package
```

Package examples:

```text
PKG_80_8 = 80 km, 8 hours
PKG_120_12 = 120 km, 12 hours
```

Block, Paid, Cancel, Booking Details remain same as normal flow.

Plain version:

Normal outstation search has pickup and drop.

Rental search is hourly package based. Customer wants cab for local use, like 8 hours / 80 km.

So MMT does not need destination in the same way. They send source and package.

Example:

```text
Customer searches local rental in Delhi.
MMT -> Us: Search with trip_type LOCAL_RENTAL and package_id PKG_80_8.
Us -> MMT: Return rental cab options and fare.
MMT -> Us: Block selected option.
MMT -> Us: Paid after confirmation.
```

Question:

```text
Are we doing local rental from day one, or only outstation/airport first?
```

## Reverse Booking

Reverse booking means MMT already has a confirmed booking and flashes it to partners.

Flow:

```text
MMT -> Us: Reverse Booking Search
We -> MMT: Accept if we want it
MMT -> Us: Unavailable if someone else took it or it expired
```

Ask MMT if this is required for launch. It is separate from normal search/block/paid flow.

Plain version:

Normal booking:

```text
MMT asks many partners for options before customer books.
```

Reverse booking:

```text
MMT already has a booking/opportunity and offers it to configured partners.
Partner accepts or ignores it.
```

This is more like a booking lead pushed to us.

Do not assume this is required. Ask if this is in launch scope.

## Reschedule

Used when existing booking start time changes.

Rules from docs:

- Pickup/drop cannot change.
- Only start time changes.
- Partner should change only `base_fare` if fare changes.
- Extra charge components should remain same.
- For system reschedule, price should not change.

Ask MMT if this is required for launch.

Plain version:

Customer changes pickup time.

MMT checks with us if we can still serve it.

If fare changes, docs say only `base_fare` should change. Extra charges should remain same.

Example:

```text
Original pickup: 10:00 AM
Customer changes pickup: 12:00 PM

MMT -> Us: Reschedule Block
Can you serve new time? Any base fare change?

MMT -> Us: Reschedule Confirm
Confirm new time.
```

Ask if reschedule support is mandatory for UAT or can come later.

## Key Business Rules

- Basic Auth is required.
- OTP verification is mandatory.
- Block to Confirm timeframe is 30 minutes.
- Serviceable cities/routes are enabled by MMT at city level based on our inventory.
- UAT uses MMT staging and Postman collection before go-live.
- For airport routes, docs say exclusive pricing is not allowed.

Meaning of these:

```text
Basic Auth required
```

We cannot keep these APIs open publicly. MMT will authenticate when calling us. We authenticate when calling MMT.

```text
OTP mandatory
```

Driver/customer trip verification must use OTP. MMT sends `verification_code` in Block. Local rental may also use `trip_end_verification_code`.

```text
Block to Confirm is 30 minutes
```

After Block, we hold the cab/SKU for 30 minutes. If Paid does not come in that time, we should release it.

```text
Serviceable cities enabled by MMT
```

We do not just start selling everywhere. MMT enables routes/cities based on where we provide inventory.

```text
UAT before live
```

They will test our staging endpoint using their Postman collection before production.

```text
Exclusive pricing not allowed on airport routes
```

For airport trips, charges like airport entry fee etc. cannot be hidden as payable later if MMT expects them included. Confirm exact fare display rules.

## Fare Terms

| Code | Meaning |
|---|---|
| `ST` | State tax |
| `NC` | Night charges |
| `TOLL` | Toll charges |
| `PC` | Parking charges |
| `AE` | Airport entry fee |
| `SE` | Station entry fee |

Extra charge logic:

```text
is_applicable = false
  -> ignore charge

is_included_in_base_fare = true
  -> already inside base fare

is_included_in_grand_total = true
  -> included in total fare

applicable but not included in base or grand total
  -> shown as exclusion / payable on actuals
```

Simpler explanation:

MMT wants fare split, not just one total number.

A fare can include:

- base fare
- per km charge
- extra km charge
- driver charges
- night charges
- toll
- state tax
- parking
- airport entry fee
- waiting charges
- add-ons like carrier/language/baby seat

Each charge has flags telling MMT how to show it:

```text
Included in base fare
Customer sees it as already part of base price.

Included in grand total
Customer pays it in total booking amount.

Not included in grand total
Customer may need to pay it separately/on actuals.
```

This is important because wrong flags will cause customer price mismatch and settlement problems.

## Payment / GST / Zero Payment

Docs mention zero payment and part payment.

Meaning:

```text
Full prepaid:
Customer pays full amount online to MMT.
Driver collects 0.

Part payment:
Customer pays some online.
Driver/partner collects remaining amount.

Zero payment:
Customer pays nothing or nominal amount upfront.
Driver/partner collects amount later.
```

Important fields in Paid API:

```text
total_fare
amount_to_be_collected
platform_fee
booking_gst
```

Docs formula:

```text
amount_to_be_collected = total_fare + platform_fee + booking_gst - paid_online
```

Plain meaning:

`amount_to_be_collected` is what still needs to be collected from the customer, usually by driver/partner.

Ask MMT:

```text
Are we full prepaid, part payment, or zero payment?
Are we eCom or non-eCom for GST?
Should driver collect anything from customer?
How will settlement/reconciliation work?
```

## Questions To Ask MMT

1. Which flows are required for launch: normal, rental, reverse booking, reschedule, provisional, zero payment?
2. What exact endpoint paths should we expose on our server?
3. Will MMT call us using Basic Auth only, or also IP whitelisting?
4. What are the timeout and retry rules for Search, Block, Paid, Cancel?
5. Is Block always valid for 30 minutes?
6. What should we return if Paid arrives after block expiry?
7. Should Search return real vehicles or only category/SKU options?
8. When should we assign actual driver and vehicle?
9. Are OTPs always generated by MMT?
10. Is end-trip OTP required for all bookings?
11. Are we eCom or non-eCom for GST?
12. Are we supporting zero payment or part payment?
13. Who owns fare calculation: us or MMT?
14. Which cities/routes will MMT enable for us?
15. Do we need marketplace B2B search?
16. Do we need reverse booking?
17. Do we need reschedule?
18. What exact Postman collection/UAT checklist should we follow?

## Most Important Questions If Time Is Short

Ask these first:

1. Will MMT call our APIs exactly in this order: Search -> Block -> Paid -> post-booking updates?
2. Which flows are required for launch: normal booking only, or rental/reverse/reschedule too?
3. What exact endpoint URLs should we expose for MMT?
4. What Basic Auth credentials and IP whitelisting are required both ways?
5. Is Block always held for 30 minutes?
6. At what point should we assign the real car and driver?
7. Are we full prepaid, part payment, or zero payment?
8. Who calculates final fare and which charges must be included upfront?
9. What post-booking events are mandatory for UAT?
10. Can they share the Postman collection and sample success/failure payloads?
