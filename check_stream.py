import os
import json
from datetime import datetime, timezone, timedelta

import requests


TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_CLIENT_SECRET = os.environ["TWITCH_CLIENT_SECRET"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]

BUFFER_CHANNEL_ID = "6a987c1f065799be4676bb2a"

CHANNEL_NAME = "CalaveraGamingTV"

STATE_FILE = "stream_state.json"
COOLDOWN_HOURS = 14

GEMINI_MODEL = "gemini-3.5-flash-lite"


def get_twitch_token():
    response = requests.post(
        "https://id.twitch.tv/oauth2/token",
        params={
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()["access_token"]


def get_stream_info(token):
    response = requests.get(
        "https://api.twitch.tv/helix/streams",
        headers={
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}",
        },
        params={
            "user_login": CHANNEL_NAME,
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()["data"]

    if not data:
        return None

    return data[0]


def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "twitch": {
                "last_processed": None,
                "last_stream_id": None
            },
            "kick": {
                "last_processed": None
            }
        }

    with open(STATE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)


def should_process(twitch_state, stream_id):
    last_stream_id = twitch_state.get("last_stream_id")

    # Si este stream ya fue procesado, no hacemos nada.
    if last_stream_id == stream_id:
        print("⏭️ This Twitch stream was already processed.")
        return False

    last_processed = twitch_state.get("last_processed")

    # Si nunca procesamos nada, podemos continuar.
    if last_processed is None:
        return True

    last_time = datetime.fromisoformat(last_processed)
    now = datetime.now(timezone.utc)

    elapsed = now - last_time

    print(f"Time since last processing: {elapsed}")

    if elapsed < timedelta(hours=COOLDOWN_HOURS):
        print("⏳ 14-hour cooldown active.")
        return False

    return True


def generate_with_gemini(stream):
    prompt = f"""
Sos el community manager de un streamer de Rust llamado CalaveraGamingTV.

El streamer acaba de comenzar un directo en Twitch.

Datos del directo:
- Canal: {CHANNEL_NAME}
- Título: {stream["title"]}
- Juego: Rust
- Espectadores actuales: {stream["viewer_count"]}

Generá un mensaje corto y atractivo para anunciar el directo.

Reglas:
- Escribí en español.
- Tono gamer, directo y natural.
- No inventes información.
- No seas demasiado formal.
- Usá como máximo 2 emojis.
- El mensaje debe invitar a entrar al directo.
- Incluí el enlace: https://twitch.tv/{CHANNEL_NAME}

Devolvé solamente el mensaje final, sin explicaciones.
"""

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        headers={
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        },
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def send_to_discord(message):
    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json={
            "content": message
        },
        timeout=30,
    )

    response.raise_for_status()


def send_to_buffer(message):
    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post {
            id
            text
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
            "query": query,
            "variables": {
                "input": {
                    "text": message,
                    "channelId": BUFFER_CHANNEL_ID,
                    "schedulingType": "automatic",
                    "mode": "shareNow"
                }
            }
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if "errors" in data:
        raise RuntimeError(data["errors"])

    result = data["data"]["createPost"]

    if "message" in result:
        raise RuntimeError(result["message"])

    print("✅ Message sent to X via Buffer.")


def main():
    print(f"Checking Twitch channel: {CHANNEL_NAME}")

    token = get_twitch_token()
    stream = get_stream_info(token)

    if stream is None:
        print("🔴 Stream is OFFLINE")
        return

    print("🟢 Stream is ONLINE")
    print(f"Stream ID: {stream['id']}")
    print(f"Title: {stream['title']}")
    print(f"Game ID: {stream['game_id']}")
    print(f"Viewers: {stream['viewer_count']}")

    state = load_state()

    twitch_state = state.setdefault(
        "twitch",
        {
            "last_processed": None,
            "last_stream_id": None
        }
    )

    if not should_process(twitch_state, stream["id"]):
        return

    print("🚀 Processing new Twitch stream...")

    print("🤖 Sending stream information to Gemini...")

    message = generate_with_gemini(stream)

    print("")
    print("===== GEMINI MESSAGE =====")
    print(message)
    print("==========================")
    print("")

    print("📢 Sending message to Discord...")

    send_to_discord(message)

    print("✅ Message sent to Discord.")

    print("🐦 Sending message to X via Buffer...")

    send_to_buffer(message)

    print("✅ Message sent to X.")

    twitch_state["last_processed"] = datetime.now(timezone.utc).isoformat()
    twitch_state["last_stream_id"] = stream["id"]

    save_state(state)

    print("✅ Stream ID and processing timestamp saved.")


if __name__ == "__main__":
    main()
