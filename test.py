import requests
from urllib.parse import quote

ACCESS_TOKEN = "uldgjejakjcgxdjfdzdbegnnisdkxnyepfkw"

address = "237 Okhla Industrial Estate Phase 3, New Delhi"

url = (
    "https://search.mappls.com/search/address/geocode"
    f"?address={quote(address)}"
    f"&access_token={ACCESS_TOKEN}"
)

response = requests.get(url, timeout=30)

print("Status:", response.status_code)

response.raise_for_status()

data = response.json()

print(data)