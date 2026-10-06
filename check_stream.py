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
KICK_CLIENT_ID = os.environ["KICK_CLIENT_ID"]
KICK_CLIENT_SECRET = os.environ["KICK_CLIENT_SECRET"]

KICK_BROADCASTER_ID = 33406855

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
    
def get_kick_token():
    response = requests.post(
        "https://id.kick.com/oauth/token",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "client_credentials",
            "client_id": KICK_CLIENT_ID,
            "client_secret": KICK_CLIENT_SECRET,
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()["access_token"]


def get_kick_stream_info(token):
    response = requests.get(
        "https://api.kick.com/public/v2/livestreams",
        headers={
            "Authorization": f"Bearer {token}",
        },
        params={
            "broadcaster_user_id": KICK_BROADCASTER_ID,
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

    if last_stream_id == stream_id:
        print("⏭️ This Twitch stream was already processed.")
        return False

    last_processed = twitch_state.get("last_processed")

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

def already_processed(state, platform, stream_id):
    last_event = state.get("last_event", {})

    if last_event.get("platform") == platform and \
       last_event.get("stream_id") == stream_id:

        print("⏭️ This stream event was already processed.")
        return True

    return False

def normalize_stream(platform, stream):
    if platform == "twitch":
        return {
            "platform": "Twitch",
            "stream_id": stream["id"],
            "title": stream["title"],
            "viewer_count": stream["viewer_count"],
            "game": "Rust",
            "url": f"https://twitch.tv/{CHANNEL_NAME}"
        }

    if platform == "kick":
        return {
            "platform": "Kick",
            "stream_id": stream["id"],
            "title": stream["stream_title"],
            "viewer_count": stream["viewer_count"],
            "game": stream["category"]["name"],
            "url": f"https://kick.com/{CHANNEL_NAME.lower()}"
        }

    raise ValueError(f"Unknown platform: {platform}")

def generate_discord_message(stream_data):
    prompt = f"""
Sos el community manager de un streamer de Rust llamado CalaveraGamingTV.

El streamer acaba de comenzar un directo.

Datos del directo:
- Plataforma: {stream_data["platform"]}
- Canal: {CHANNEL_NAME}
- Título: {stream_data["title"]}
- Juego: {stream_data["game"]}
- Espectadores actuales: {stream_data["viewer_count"]}
- Enlace: {stream_data["url"]}

Generá un mensaje para anunciar el directo en una comunidad de Discord.

Reglas:
- Escribí en español.
- Tono gamer, energético y natural.
- Puede ser más desarrollado que un tweet.
- Generá un mensaje atractivo que invite a la comunidad a entrar al directo.
- Podés mencionar el título del directo.
- Usá como máximo 3 emojis.
- El mensaje DEBE comenzar con: @everyone
- Incluí el enlace proporcionado.
- No inventes información.
- No agregues explicaciones.
- Devolvé solamente el mensaje final listo para publicar en Discord.
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


def generate_x_message(stream_data):
    prompt = f"""
Sos el community manager de un streamer de Rust llamado CalaveraGamingTV.

Acaba de comenzar un directo.

Datos:
- Plataforma: {stream_data["platform"]}
- Canal: {CHANNEL_NAME}
- Título: {stream_data["title"]}
- Juego: {stream_data["game"]}
- Espectadores actuales: {stream_data["viewer_count"]}
- Enlace: {stream_data["url"]}

Generá un post para X anunciando el directo.

Reglas MUY IMPORTANTES:
- Escribí en español.
- Tiene que ser corto, directo y llamativo.
- Máximo 220 caracteres en total.
- Incluí el enlace proporcionado.
- Incluí entre 2 y 4 hashtags relacionados con Rust/streaming.
- No uses @everyone.
- Máximo 2 emojis.
- No inventes información.
- Devolvé solamente el post final.
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

    twitch_token = get_twitch_token()
    twitch_stream = get_stream_info(twitch_token)
    
    kick_token = get_kick_token()
    kick_stream = get_kick_stream_info(kick_token)
    
    print("")
    
    if twitch_stream:
        print("🟢 Twitch is ONLINE")
        print(f"Twitch Stream ID: {twitch_stream['id']}")
        print(f"Twitch Title: {twitch_stream['title']}")
        print(f"Twitch Viewers: {twitch_stream['viewer_count']}")
    else:
        print("🔴 Twitch is OFFLINE")
    
    if kick_stream:
        print("🟢 Kick is ONLINE")
        print(f"Kick Stream ID: {kick_stream['id']}")
        print(f"Kick Title: {kick_stream['stream_title']}")
        print(f"Kick Viewers: {kick_stream['viewer_count']}")
    else:
        print("🔴 Kick is OFFLINE")
    
    if twitch_stream is None and kick_stream is None:
        print("😴 Both platforms are OFFLINE")
        return

    if stream is None:
        print("🔴 Stream is OFFLINE")
        return
        
    if twitch_stream:
        platform = "twitch"
        stream = twitch_stream
        stream_id = twitch_stream["id"]
    
    elif kick_stream:
        platform = "kick"
        stream = kick_stream
        stream_id = kick_stream["id"]
    
    else:
        return

    print(f"📡 Selected platform: {platform}")
    print(f"📡 Selected stream ID: {stream_id}")
    
    state = load_state()
    
    if already_processed(state, platform, stream_id):
        return
    
    print(f"🚀 Processing new {platform} stream...")

    stream_data = normalize_stream(platform, stream)

    print("")
    print("===== NORMALIZED STREAM =====")
    print(stream_data)
    print("=============================")

    

    # --------------------------------------------------
    # DISCORD
    # --------------------------------------------------

    print("🤖 Generating Discord message with Gemini...")

    discord_message = generate_discord_message(stream_data)

    print("")
    print("===== DISCORD MESSAGE =====")
    print(discord_message)
    print("===========================")
    print("")

    print("📢 Sending message to Discord...")

    send_to_discord(discord_message)

    print("✅ Discord message sent.")

    # --------------------------------------------------
    # X
    # --------------------------------------------------

    print("🤖 Generating X message with Gemini...")

    x_message = generate_x_message(stream_data)

    print("")
    print("===== X MESSAGE =====")
    print(x_message)
    print("=====================")
    print("")

    print("🐦 Sending message to X via Buffer...")

    send_to_buffer(x_message)

    print("✅ X message sent.")

    # --------------------------------------------------
    # SAVE STATE
    # --------------------------------------------------

    twitch_state["last_processed"] = datetime.now(timezone.utc).isoformat()
    twitch_state["last_stream_id"] = stream["id"]

    save_state(state)

    print("✅ Stream ID and processing timestamp saved.")


if __name__ == "__main__":
    main()
