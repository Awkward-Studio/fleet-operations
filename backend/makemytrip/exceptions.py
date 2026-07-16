"""
Custom exceptions for the MakeMyTrip (Incabs) integration.
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class MakeMyTripAPIException(APIException):
    """
    Exception raised when communication with the MakeMyTrip API fails.
    """
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Failed to communicate with MakeMyTrip API."
    default_code = "makemytrip_api_error"

    def __init__(self, detail: str = None, status_code: int = None, code: str = None) -> None:
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail, code)
