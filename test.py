import requests, json
BASE_URL = "http://127.0.0.1:8000/api/makemytrip"

values = """
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
    "trip_type": "ONE_WAY/ROUND_TRIP",
    "start_time": "2021-02-08 19:55:00",
    "end_time": "2021-02-08 20:55:00",
    "search_id": "56c5c8a269702d3a1b0b0000",
    "vendor_id": "PARTNER_CODE",
    "partner_name": "GOMMT",
    "search_tags": ["B2C", "PB", "B2B", "FF", "CO"],
    "one_way_distance": 230,
    "is_instant_search": false,
    "corporate_id": "6c5c8a2697_string_id",
    "stopovers": [
        {
            "address": "DLF Place, Gurgaon, Haryana, India",
            "latitude": 28.48968,
            "longitude": 77.09224
        }
    ],
    "mandatory_inclusions": ["AE", "ST", "TOLL", "NC", "PC", "SE"],
    "mandatory_exclusions": [],
    "trip_type_details": {
        "basic_trip_type": "OUTSTATION/TRAIN/AIRPORT",
        "airport_type": "NONE",
        "train_type": "NONE/PICKUP/DROP"
    },
    "expressway_distance": 144,
    "expressway_duration": 156,
    "eligible_cancellation_policy": ["PRE_FLEXI", "12H_FLEXI"]
}
"""


data = json.loads(values)
response = requests.post(
    f"{BASE_URL}/partnermarketplacesearchendpoint/",
    json=data,
    timeout=30,
)

print("Status:", response.status_code)

try:
    print(response.json())
except ValueError:
    print(response.text)