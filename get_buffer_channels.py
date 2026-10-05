import os
import requests


BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]

QUERY = """
query GetOrganizations {
  account {
    organizations {
      id
      name
      ownerEmail
    }
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
        "query": QUERY
    },
    timeout=30,
)

response.raise_for_status()

data = response.json()

print("===== BUFFER ORGANIZATIONS =====")
print(data)
