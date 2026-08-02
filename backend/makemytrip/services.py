"""
Service layer for MakeMyTrip (Incabs) API integration.
All outbound HTTP calls are kept in this file.
"""

import json
import logging
import re
import datetime
from typing import Any, Dict
from decimal import Decimal, ROUND_HALF_UP
import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from billing.models import OTABookingSnapshot, OTACounterparty, OTASettlementStatus
from fleet.models import BookingType, PricingAmountStatus, Trip, TripStatus
from makemytrip.exceptions import MakeMyTripAPIException
from makemytrip.models import MMTBookingLifecycle, MMTLifecycleEvent, MMTLifecycleEventType
from typing import Optional

logger = logging.getLogger("makemytrip")
MONEY = Decimal("0.01")


def _parse_json_response(response: requests.Response) -> Dict[str, Any]:
    """
    Parse JSON response from the mock server, stripping Javascript-style comments
    and removing any trailing commas before closing braces/brackets.
    """
    body_text = response.text
    
    # 1. Strip Javascript-style comments (//... and /*...*/)
    comment_pattern = r'("(?:\\.|[^"\\])*")|(/\*.*?\*/|//[^\r\n]*)'
    cleaned = re.sub(comment_pattern, lambda m: m.group(1) if m.group(1) else '', body_text, flags=re.DOTALL)
    
    # 2. Strip trailing commas before closing braces } or brackets ]
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    
    return json.loads(cleaned)


def _get_api_client_config() -> tuple[str, Dict[str, str]]:
    """
    Helper to fetch and prepare mock server base URL and default headers.
    """
    base_url = getattr(settings, "MAKEMYTRIP_MOCK_SERVER_URL", "https://private-7902fd-incabsapipartnerdocumentationv3.apiary-mock.com/tracking/pp2").rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Default mock authorization header if none provided in settings
        "Authorization": "Basic ZmU1NzNkN2UxNGY1NWUwOWZiYzhiZDhjOTRiYzAzZDQxOGRkNGJmZDVkZmEw",
    }
    
    # Overwrite/add custom headers from Django settings if configured
    settings_headers = getattr(settings, "MAKEMYTRIP_HEADERS", {})
    headers.update(settings_headers)
    
    return base_url, headers


def _send_request(method: str, path: str, json_data: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Send an HTTP request to the mock server, logging requests and handling failures.
    """
    base_url, headers = _get_api_client_config()
    url = f"{base_url}/{path.lstrip('/')}"
    
    logger.info(
        "Outgoing MakeMyTrip API Request - Method: %s, URL: %s, Params: %s, Headers: %s",
        method, url, params, {k: v for k, v in headers.items() if k.lower() != "authorization"}
    )
    if json_data:
        logger.debug("Request Payload: %s", json_data)

    try:
        response = requests.request(
            method=method,
            url=url,
            json=json_data,
            params=params,
            headers=headers,
            timeout=15
        )
        
        logger.info(
            "MakeMyTrip API Response - Status: %s, URL: %s",
            response.status_code, url
        )
        logger.debug("Response Content: %s", response.text)
        
        # Raise for status if not 2xx
        if not (200 <= response.status_code < 300):
            logger.error(
                "MakeMyTrip API failure - Status: %s, Body: %s",
                response.status_code, response.text
            )
            # Try to return JSON error if available, else raise exception
            try:
                return _parse_json_response(response)
            except (ValueError, TypeError, json.JSONDecodeError):
                raise MakeMyTripAPIException(
                    detail=f"Apiary Mock Server returned error status {response.status_code}.",
                    status_code=response.status_code
                )
        
        try:
            return _parse_json_response(response)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            logger.error(
                "Failed to parse response JSON from MakeMyTrip API. Status: %s, Body: %r, Error: %s",
                response.status_code, response.text, str(e)
            )
            raise MakeMyTripAPIException(
                detail="Invalid response JSON received from MakeMyTrip API.",
                status_code=status.HTTP_502_BAD_GATEWAY
            )
            
    except requests.exceptions.Timeout as e:
        logger.error("MakeMyTrip API connection timed out: %s", str(e))
        raise MakeMyTripAPIException(
            detail="MakeMyTrip API request timed out.",
            status_code=status.HTTP_504_TIMEOUT
        )
    except requests.exceptions.RequestException as e:
        logger.error("MakeMyTrip API connection failed: %s", str(e))
        raise MakeMyTripAPIException(
            detail=f"Failed to connect to MakeMyTrip API mock server: {str(e)}",
            status_code=status.HTTP_502_BAD_GATEWAY
        )


def _payload_hash(payload: Dict[str, Any]) -> str:
    import hashlib

    body = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(MONEY, rounding=ROUND_HALF_UP)


def _parse_mmt_datetime(value: Optional[str]):

    if not value:
        return timezone.now()
    parsed = parse_datetime(value)
    if parsed is None:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                parsed = datetime.datetime.strptime(value[:19], fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return timezone.now()
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _event_key(event_type: str, payload: Dict[str, Any], fallback_hash: str) -> str:
    if event_type in {MMTLifecycleEventType.SEARCH, MMTLifecycleEventType.MARKETPLACE_SEARCH}:
        identifier = payload.get("search_id") or fallback_hash
    elif event_type == MMTLifecycleEventType.BLOCK:
        identifier = payload.get("search_id") or fallback_hash
    elif event_type == MMTLifecycleEventType.PAID:
        identifier = payload.get("order_reference_number") or payload.get("partner_reference_number") or fallback_hash
    elif event_type == MMTLifecycleEventType.CANCEL:
        identifier = payload.get("order_reference_number") or payload.get("partner_reference_number") or fallback_hash
    elif event_type == MMTLifecycleEventType.CUSTOMER_ARRIVED:
        identifier = payload.get("booking_id") or fallback_hash
    else:
        identifier = fallback_hash
    return f"{event_type}:{identifier}"


def _location_facts(location: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    location = location or {}
    return {
        "address": location.get("address", ""),
        "city": location.get("city", ""),
        "latitude": str(location.get("latitude", "")),
        "longitude": str(location.get("longitude", "")),
    }


def _normalize_search(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "search_id": data.get("search_id", ""),
        "partner_name": data.get("partner_name", ""),
        "vendor_id": data.get("vendor_id", ""),
        "trip_type": data.get("trip_type", ""),
        "start_time": data.get("start_time", ""),
        "end_time": data.get("end_time", ""),
        "source": _location_facts(data.get("source")),
        "destination": _location_facts(data.get("destination")),
        "distance_km": str(data.get("one_way_distance") or data.get("distance") or ""),
        "trip_type_details": data.get("trip_type_details", {}),
    }


def _normalize_block(data: Dict[str, Any], partner_reference_number: str) -> Dict[str, Any]:
    fare = data.get("fare_details") or {}
    total_fare = _money(fare.get("total_fare"))
    fare_tax = _money(fare.get("state_tax"))
    return {
        "search_id": data.get("search_id", ""),
        "partner_reference_number": partner_reference_number,
        "partner_name": data.get("partner_name", ""),
        "vendor_id": data.get("vendor_id", ""),
        "vehicle_type": data.get("vehicle_type", ""),
        "vehicle_subcategory": data.get("vehicle_subcategory", ""),
        "vehicle_details": data.get("vehicle_details", {}),
        "source": _location_facts(data.get("source")),
        "destination": _location_facts(data.get("destination")),
        "distance_km": str(data.get("distance") or ""),
        "gross_fare": str(total_fare),
        "fare_tax": str(fare_tax),
        "fare_details": fare,
        "verification_code": data.get("verification_code", ""),
        "trip_end_verification_code": data.get("trip_end_verification_code", ""),
        "flight_number": data.get("flight_number", ""),
        "trip_type_details": data.get("trip_type_details", {}),
    }


def _normalize_paid(data: Dict[str, Any]) -> Dict[str, Any]:
    passenger = data.get("passenger") or {}
    return {
        "partner_reference_number": data.get("partner_reference_number", ""),
        "order_reference_number": data.get("order_reference_number", ""),
        "partner_name": data.get("partner_name", ""),
        "vendor_id": data.get("vendor_id", ""),
        "gross_fare": str(_money(data.get("total_fare"))),
        "amount_to_be_collected": str(_money(data.get("amount_to_be_collected"))),
        "platform_fee": str(_money(data.get("platform_fee"))),
        "booking_gst": str(_money(data.get("booking_gst"))),
        "passenger": {
            "name": passenger.get("name", ""),
            "email": passenger.get("email", ""),
            "phone_number": passenger.get("phone_number", ""),
            "country_code": passenger.get("country_code", "91"),
        },
        "flight_details": data.get("flight_details", {}),
    }


def _record_event(event_type: str, payload: Dict[str, Any], facts: Dict[str, Any], response: Dict[str, Any], trip=None):
    request_hash = _payload_hash(payload)
    event_key = _event_key(event_type, payload, request_hash)
    event, created = MMTLifecycleEvent.objects.get_or_create(
        event_key=event_key,
        defaults={
            "event_type": event_type,
            "request_hash": request_hash,
            "search_id": payload.get("search_id", ""),
            "partner_reference_number": payload.get("partner_reference_number", ""),
            "order_reference_number": payload.get("order_reference_number") or payload.get("booking_id", ""),
            "request_payload": payload,
            "normalized_facts": facts,
            "response_payload": response,
            "trip": trip,
        },
    )
    return event, created


def _partner_reference_for_search(search_id: str) -> str:
    import hashlib

    digest = hashlib.sha1(search_id.encode("utf-8")).hexdigest()[:10].upper()
    return f"IF-MMT-{digest}"


def _get_counterparty() -> OTACounterparty:
    counterparty, _ = OTACounterparty.objects.get_or_create(
        code="MMT",
        defaults={"name": "MakeMyTrip", "provider_type": "OTA", "default_currency": "INR"},
    )
    return counterparty


def _commercial_sources(source: str) -> Dict[str, str]:
    return {
        "gross_fare": source,
        "fare_tax": source,
        "commission_amount": source,
        "commission_tax": source,
        "withholding_amount": source,
        "cancellation_amount": source,
        "net_expected": source,
    }


def ingest_search(data: Dict[str, Any], *, marketplace: bool = False) -> Dict[str, Any]:
    event_type = MMTLifecycleEventType.MARKETPLACE_SEARCH if marketplace else MMTLifecycleEventType.SEARCH
    facts = _normalize_search(data)
    with transaction.atomic():
        lifecycle, _ = MMTBookingLifecycle.objects.update_or_create(
            search_id=facts["search_id"],
            defaults={
                "status": "SEARCHED",
                "search_payload": data,
                "normalized_facts": {**facts},
            },
        )
        response = {
            "response": {
                "success": True,
                "search_id": lifecycle.search_id,
                "status": lifecycle.status,
            }
        }
        _record_event(event_type, data, facts, response, lifecycle.trip)
        return response


def ingest_block(data: Dict[str, Any]) -> Dict[str, Any]:
    search_id = data.get("search_id", "")
    partner_reference = _partner_reference_for_search(search_id)
    facts = _normalize_block(data, partner_reference)
    with transaction.atomic():
        lifecycle, _ = MMTBookingLifecycle.objects.select_for_update().get_or_create(
            search_id=search_id,
            defaults={"status": "SEARCHED", "search_payload": {}, "normalized_facts": {}},
        )
        existing_reference = lifecycle.partner_reference_number or partner_reference
        facts["partner_reference_number"] = existing_reference
        normalized = {
            **(lifecycle.normalized_facts or {}),
            "block": facts,
        }
        lifecycle.partner_reference_number = existing_reference
        lifecycle.status = "BLOCKED"
        lifecycle.block_payload = data
        lifecycle.normalized_facts = normalized
        lifecycle.save(update_fields=[
            "partner_reference_number",
            "status",
            "block_payload",
            "normalized_facts",
            "updated_at",
        ])
        response = {
            "response": {
                "success": True,
                "reference_number": existing_reference,
                "partner_reference_number": existing_reference,
                "search_id": search_id,
            }
        }
        _record_event(MMTLifecycleEventType.BLOCK, data, facts, response, lifecycle.trip)
        return response


def _trip_fields_from_lifecycle(lifecycle: MMTBookingLifecycle, paid_facts: Dict[str, Any]) -> Dict[str, Any]:
    block = (lifecycle.normalized_facts or {}).get("block", {})
    search = lifecycle.normalized_facts or {}
    source = block.get("source") or search.get("source") or {}
    destination = block.get("destination") or search.get("destination") or {}
    pickup_at = _parse_mmt_datetime(search.get("start_time"))
    estimated_drop_at = _parse_mmt_datetime(search.get("end_time"))
    if estimated_drop_at <= pickup_at:
        estimated_drop_at = pickup_at + datetime.timedelta(hours=4)
    gross_fare = _money(paid_facts.get("gross_fare") or block.get("gross_fare"))
    fare_tax = _money(paid_facts.get("booking_gst") or block.get("fare_tax"))
    taxable = gross_fare - fare_tax
    passenger = paid_facts.get("passenger") or {}
    pricing_snapshot = {
        "source": "MAKEMYTRIP",
        "search": search,
        "block": block,
        "paid": paid_facts,
        "verification_code": block.get("verification_code", ""),
        "trip_end_verification_code": block.get("trip_end_verification_code", ""),
        "ota_commercial": {
            "gross_customer_fare": str(gross_fare),
            "commission_rate": "0.00",
            "commission_amount": str(_money(paid_facts.get("platform_fee"))),
            "withholding_rate": "0.00",
            "withholding_amount": "0.00",
            "expected_net_settlement": str(gross_fare - _money(paid_facts.get("platform_fee"))),
            "exception": None,
        },
    }
    return {
        "booking_type": BookingType.OTA,
        "ota_source": "MMT",
        "ota_external_reference": paid_facts["order_reference_number"],
        "customer_name": passenger.get("name", "MMT Passenger"),
        "customer_phone": passenger.get("phone_number", ""),
        "customer_display_name_snapshot": passenger.get("name", "MMT Passenger"),
        "pickup_city": source.get("city") or "Unknown",
        "drop_city": destination.get("city") or "Unknown",
        "pickup_address": source.get("address", ""),
        "drop_address": destination.get("address", ""),
        "pickup_at": pickup_at,
        "estimated_drop_at": estimated_drop_at,
        "status": TripStatus.REQUESTED,
        "fare_amount": gross_fare,
        "pricing_amount_status": PricingAmountStatus.QUOTED,
        "quoted_taxable_amount": taxable,
        "quoted_tax_amount": fare_tax,
        "quoted_total_amount": gross_fare,
        "pricing_snapshot": pricing_snapshot,
        "calculation_version": "mmt-paid-v1",
        "vehicle_category_requested": block.get("vehicle_type", ""),
        "duty_type": (block.get("trip_type_details") or search.get("trip_type_details") or {}).get("basic_trip_type", ""),
    }


def ingest_paid(data: Dict[str, Any]) -> Dict[str, Any]:
    paid_facts = _normalize_paid(data)
    partner_ref = paid_facts["partner_reference_number"]
    order_ref = paid_facts["order_reference_number"]
    with transaction.atomic():
        lifecycle = (
            MMTBookingLifecycle.objects.select_for_update()
            .filter(partner_reference_number=partner_ref)
            .first()
        )
        if lifecycle is None:
            lifecycle = MMTBookingLifecycle.objects.create(
                partner_reference_number=partner_ref,
                status="BLOCKED",
            )
        if lifecycle.trip_id:
            trip = lifecycle.trip
        else:
            trip_fields = _trip_fields_from_lifecycle(lifecycle, paid_facts)
            trip = Trip.objects.create(**trip_fields)
            lifecycle.trip = trip

        lifecycle.order_reference_number = order_ref
        lifecycle.status = "PAID"
        lifecycle.paid_payload = data
        lifecycle.normalized_facts = {
            **(lifecycle.normalized_facts or {}),
            "paid": paid_facts,
        }
        lifecycle.save(update_fields=[
            "order_reference_number",
            "status",
            "paid_payload",
            "normalized_facts",
            "trip",
            "updated_at",
        ])

        gross = _money(paid_facts["gross_fare"])
        fare_tax = _money(paid_facts["booking_gst"])
        commission = _money(paid_facts["platform_fee"])
        net_expected = gross - commission
        OTABookingSnapshot.objects.get_or_create(
            trip=trip,
            defaults={
                "counterparty": _get_counterparty(),
                "provider_booking_id": order_ref,
                "partner_reference_number": partner_ref,
                "currency": "INR",
                "gross_fare": gross,
                "fare_tax": fare_tax,
                "commission_basis": "GROSS_FARE",
                "commission_rate": Decimal("0.0000"),
                "commission_amount": commission,
                "commission_tax": Decimal("0.00"),
                "withholding_rate": Decimal("0.0000"),
                "withholding_amount": Decimal("0.00"),
                "cancellation_amount": Decimal("0.00"),
                "net_expected": net_expected,
                "settlement_status": OTASettlementStatus.PENDING,
                "monetary_sources": _commercial_sources("MMT_PAID_CALLBACK"),
                "source_system": "MAKEMYTRIP",
                "source_payload_hash": _payload_hash(data),
            },
        )

        response = {
            "response": {
                "success": True,
                "order_reference_number": order_ref,
                "partner_reference_number": partner_ref,
                "trip_id": trip.id,
                "status": lifecycle.status,
            }
        }
        _record_event(MMTLifecycleEventType.PAID, data, paid_facts, response, trip)
        return response


def ingest_cancel(data: Dict[str, Any]) -> Dict[str, Any]:
    order_ref = data.get("order_reference_number", "")
    partner_ref = data.get("partner_reference_number", "")
    facts = {
        "order_reference_number": order_ref,
        "partner_reference_number": partner_ref,
        "cancelled_by": data.get("cancelled_by", ""),
        "cancellation_reason": data.get("cancellation_reason", ""),
        "cancelled_at": data.get("cancelled_at", ""),
    }
    with transaction.atomic():
        lifecycle = (
            MMTBookingLifecycle.objects.select_for_update()
            .filter(order_reference_number=order_ref)
            .first()
            or MMTBookingLifecycle.objects.select_for_update()
            .filter(partner_reference_number=partner_ref)
            .first()
        )
        if lifecycle is None:
            lifecycle = MMTBookingLifecycle.objects.create(
                order_reference_number=order_ref,
                partner_reference_number=partner_ref,
            )
        if lifecycle.trip_id and lifecycle.trip.status != TripStatus.COMPLETED:
            lifecycle.trip.status = TripStatus.CANCELLED
            lifecycle.trip.save(update_fields=["status", "updated_at"])
            snapshot = getattr(lifecycle.trip, "ota_booking_snapshot", None)
            if snapshot:
                snapshot.settlement_status = OTASettlementStatus.CANCELLED
                snapshot.save(update_fields=["settlement_status", "updated_at"])
        lifecycle.status = "CANCELLED"
        lifecycle.cancel_payload = data
        lifecycle.normalized_facts = {
            **(lifecycle.normalized_facts or {}),
            "cancel": facts,
        }
        lifecycle.save(update_fields=["status", "cancel_payload", "normalized_facts", "updated_at"])
        response = {
            "response": {
                "success": True,
                "order_reference_number": order_ref,
                "partner_reference_number": partner_ref,
                "status": lifecycle.status,
            }
        }
        _record_event(MMTLifecycleEventType.CANCEL, data, facts, response, lifecycle.trip)
        return response


def ingest_customer_landed(data: Dict[str, Any]) -> Dict[str, Any]:
    facts = {"booking_id": data.get("booking_id", "")}
    response = {"response": {"success": True, **facts}}
    _record_event(MMTLifecycleEventType.CUSTOMER_ARRIVED, data, facts, response)
    return response


def get_booking_details(order_reference_number: str, partner_reference_number: str = None) -> Dict[str, Any]:
    lifecycle = MMTBookingLifecycle.objects.filter(order_reference_number=order_reference_number).first()
    if lifecycle is None and partner_reference_number:
        lifecycle = MMTBookingLifecycle.objects.filter(partner_reference_number=partner_reference_number).first()
    if lifecycle is None:
        return {"response": {"success": False, "status": "NOT_FOUND"}}
    trip = lifecycle.trip
    return {
        "response": {
            "success": True,
            "order_reference_number": lifecycle.order_reference_number,
            "partner_reference_number": lifecycle.partner_reference_number,
            "status": lifecycle.status,
            "trip_id": trip.id if trip else None,
            "trip_status": trip.status if trip else None,
        }
    }


def call_search_api(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call MakeMyTrip Cab Search API.
    
    Args:
        data: Validated request payload matching SearchSerializer schema.
        
    Returns:
        JSON response payload from the API mock server.
    """
    return _send_request("POST", "partnersearchendpoint", json_data=data)


def call_search_marketplace_api(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call MakeMyTrip Cab B2B Marketplace Search API.
    
    Args:
        data: Validated request payload matching SearchMarketPlaceSerializer schema.
        
    Returns:
        JSON response payload from the API mock server.
    """
    return _send_request("POST", "partnermarketplacesearchendpoint", json_data=data)


def call_block_api(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call MakeMyTrip Cab Blocking API.
    
    Args:
        data: Validated request payload matching BlockSerializer schema.
        
    Returns:
        JSON response payload from the API mock server.
    """
    return _send_request("POST", "partnerblockendpoint", json_data=data)


def call_paid_api(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call MakeMyTrip Cab Booking Confirm/Payment API.
    
    Args:
        data: Validated request payload matching PaidSerializer schema.
        
    Returns:
        JSON response payload from the API mock server.
    """
    return _send_request("POST", "partnerpaidendpoint", json_data=data)


def call_cancel_api(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call MakeMyTrip Cab Booking Cancellation API.
    
    Args:
        data: Validated request payload matching CancelSerializer schema.
        
    Returns:
        JSON response payload from the API mock server.
    """
    return _send_request("POST", "partnercancelendpoint", json_data=data)


def call_customer_landed_api(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call MakeMyTrip Customer Landed/Arrived API.
    
    Args:
        data: Validated request payload matching CustomerLandedSerializer schema.
        
    Returns:
        JSON response payload from the API mock server.
    """
    return _send_request("POST", "partnercustomerarrivedendpoint", json_data=data)


def call_booking_details_api(order_reference_number: str, partner_reference_number: str = None) -> Dict[str, Any]:
    """
    Call MakeMyTrip Cab Booking Details query API.
    
    Args:
        order_reference_number: MMT order reference identifier.
        partner_reference_number: Optional partner booking reference identifier.
        
    Returns:
        JSON response payload from the API mock server.
    """
    params = {"order_reference_number": order_reference_number}
    if partner_reference_number:
        params["partner_reference_number"] = partner_reference_number
        
    return _send_request("GET", "api/partner/v1/booking/details", params=params)
