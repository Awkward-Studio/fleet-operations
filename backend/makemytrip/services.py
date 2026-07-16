"""
Service layer for MakeMyTrip (Incabs) API integration.
All outbound HTTP calls are kept in this file.
"""

import json
import logging
import re
from typing import Any, Dict
import requests
from django.conf import settings
from rest_framework import status
from makemytrip.exceptions import MakeMyTripAPIException

logger = logging.getLogger("makemytrip")


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
