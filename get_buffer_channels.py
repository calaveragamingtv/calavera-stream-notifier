import os
import requests


BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]

ORGANIZATION_ID = "6a987b6e1a5421441ef43b13"

QUERY = """
query GetChannels($input: ChannelsInput!) {
  channels(input: $input) {
    id
    name
    service
  }
}
"""


response = requests.post(
    "https://api.buffer.com",
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BUFFER_API_KEY}",
    },
    json={
        "query": QUERY,
        "variables": {
            "input": {
                "organizationId": ORGANIZATION_ID
            }
        }
    },
    timeout=30,
)

response.raise_for_status()

data = response.json()

print("===== BUFFER CHANNELS =====")
print(data)
