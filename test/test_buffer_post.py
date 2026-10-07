import os
import requests


BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]

CHANNEL_ID = "6a987c1f065799be4676bb2a"

MESSAGE = """🔥 PRUEBA 2 - CALAVERAGAMINGTV ESTÁ EN DIRECTO AHORA

Esta publicación fue enviada directamente desde GitHub Actions mediante Buffer."""


QUERY = """
mutation CreatePost {
  createPost(input: {
    text: "🔥 PRUEBA 2 - CALAVERAGAMINGTV ESTÁ EN DIRECTO AHORA. Esta publicación fue enviada directamente desde GitHub Actions mediante Buffer."
    channelId: "6a987c1f065799be4676bb2a"
    schedulingType: automatic
    mode: shareNow
  }) {
    ... on PostActionSuccess {
      post {
        id
        text
        dueAt
        status
      }
    }

    ... on MutationError {
      message
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

print("===== BUFFER TEST POST =====")
print(data)
