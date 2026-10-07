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

TWITCH_CHANNEL_NAME = "CalaveraGamingTV"
KICK_CHANNEL_SLUG = "CalaveraGamingTV"

STATE_FILE = "stream_state.json"
COOLDOWN_HOURS = 14

GEMINI_MODEL = "gemini-3.5-flash-lite"
STREAM_CONTEXT = ""



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
            "user_login": TWITCH_CHANNEL_NAME,
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
        "https://api.kick.com/public/v1/channels",
        headers={
            "Authorization": f"Bearer {token}",
        },
        params={
            "slug": KICK_CHANNEL_SLUG,
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()["data"]

    if not data:
        return None

    channel = data[0]

    if not channel["stream"]["is_live"]:
        return None

    return channel


def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "last_event": {
                "platform": None,
                "stream_id": None,
                "started_at": None,
                "processed_at": None
            },
            "last_messages": [],
            "last_posts": []
        }

    with open(STATE_FILE, "r", encoding="utf-8") as file:
        state = json.load(file)

    if "last_messages" not in state:
        state["last_messages"] = []
        
    if "last_posts" not in state:
        state["last_posts"] = []

    return state

def load_prompt(filename):
    prompt_path = os.path.join("prompt", filename)

    with open(prompt_path, "r", encoding="utf-8") as file:
        return file.read()

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)

def save_last_post(state, post):
    posts = state.get("last_posts", [])
    posts.append(post)
    state["last_posts"] = posts[-5:]

def save_last_message(state, message):
    messages = state.get("last_messages", [])
    messages.append(message)
    state["last_messages"] = messages[-5:]


def should_process(state):
    last_event = state.get("last_event", {})
    last_processed = last_event.get("processed_at")

    if last_processed is None:
        print("🆕 No previous stream event found.")
        return True

    last_time = datetime.fromisoformat(last_processed)
    now = datetime.now(timezone.utc)

    elapsed = now - last_time

    print(f"Time since last processing: {elapsed}")

    if elapsed < timedelta(hours=COOLDOWN_HOURS):
        print(f"⏳ {COOLDOWN_HOURS}-hour cooldown active.")
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
            "channel": TWITCH_CHANNEL_NAME,
            "stream_id": stream["id"],
            "title": stream["title"],
            "viewer_count": stream["viewer_count"],
            "game": stream["game_name"],
            "url": f"https://twitch.tv/{TWITCH_CHANNEL_NAME}"
        }

    if platform == "kick":
        return {
            "platform": "Kick",
            "channel": KICK_CHANNEL_SLUG,
            "stream_id": f"kick-{stream['broadcaster_user_id']}-{stream['stream']['start_time']}",
            "title": stream["stream_title"],
            "viewer_count": stream["stream"]["viewer_count"],
            "game": stream["category"]["name"],
            "url": f"https://kick.com/{KICK_CHANNEL_SLUG}"
        }
    
    raise ValueError(f"Unknown platform: {platform}")

def generate_discord_message(stream_data, context, last_messages):
    prompt_template = load_prompt("discord_prompt.txt")

    last_messages_text = "\n".join(
        f"- {message}" for message in last_messages
    )

    if not last_messages_text:
        last_messages_text = "(No hay avisos anteriores.)"

    prompt = prompt_template.format(
        platform=stream_data["platform"],
        channel=(
            TWITCH_CHANNEL_NAME
            if stream_data["platform"] == "Twitch"
            else KICK_CHANNEL_SLUG
        ),
        title=stream_data["title"],
        game=stream_data["game"],
        url=stream_data["url"],
        context=context,
        last_messages=last_messages_text
    )

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

def generate_x_message(stream_data, context, last_posts):
    prompt_template = load_prompt("x_prompt.txt")

    last_posts_text = "\n".join(
        f"- {post}" for post in last_posts
    )

    if not last_posts_text:
        last_posts_text = "(No hay posts anteriores.)"

    prompt = prompt_template.format(
        platform=stream_data["platform"],
        channel=(
            TWITCH_CHANNEL_NAME
            if stream_data["platform"] == "Twitch"
            else KICK_CHANNEL_SLUG
        ),
        title=stream_data["title"],
        game=stream_data["game"],
        viewer_count=stream_data["viewer_count"],
        url=stream_data["url"],
        context=context,
        last_posts=last_posts_text
    )

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

def validate_x_message(message, url):
    if not message:
        return False, "El mensaje está vacío."

    if len(message) > 220:
        return False, f"El mensaje tiene {len(message)} caracteres."

    if url not in message:
        return False, "El mensaje no contiene el enlace del directo."

    hashtag_count = message.count("#")

    if hashtag_count < 1:
        return False, "El mensaje no tiene ningún hashtag."
    
    if hashtag_count > 2:
        return False, "El mensaje tiene más de 2 hashtags."

    return True, "Mensaje válido."

def print_section(title):
    print("")
    print("=" * 50)
    print(title)
    print("=" * 50)


def main():
    
    print_section("🎬 CALAVERA STREAM NOTIFIER")
    print(f"📡 Checking Twitch channel: {TWITCH_CHANNEL_NAME}")

    twitch_stream = None
    kick_stream = None
    
    twitch_error = None
    kick_error = None

    print_section("📡 CHECKING PLATFORMS")
    
    # TWITCH
    try:
        twitch_token = get_twitch_token()
        twitch_stream = get_stream_info(twitch_token)
    except Exception as e:
        twitch_error = str(e)
    
    # KICK
    try:
        kick_token = get_kick_token()
        kick_stream = get_kick_stream_info(kick_token)
    except Exception as e:
        kick_error = str(e)
    
    print("")
    
    if twitch_error:
        print(f"   Twitch: ⚠️ API ERROR")
        print(f"   └─ {twitch_error}")
    elif twitch_stream:
        print("   Twitch: 🟢 ONLINE")
        print(f"   ├─ Stream ID: {twitch_stream['id']}")
        print(f"   ├─ Title: {twitch_stream['title']}")
        print(f"   └─ Viewers: {twitch_stream['viewer_count']}")
    else:
        print("   Twitch: 🔴 OFFLINE")
    
    if kick_error:
        print(f"   Kick:   ⚠️ API ERROR")
        print(f"   └─ {kick_error}")
    elif kick_stream:
        print("   Kick:   🟢 ONLINE")
        print(f"   ├─ Broadcaster ID: {kick_stream['broadcaster_user_id']}")
        print(f"   ├─ Title: {kick_stream['stream_title']}")
        print(f"   └─ Viewers: {kick_stream['stream']['viewer_count']}")
    else:
        print("   Kick:   🔴 OFFLINE")
    
    if twitch_stream is None and kick_stream is None:

        if twitch_error and kick_error:
            print_section("📊 RESULT")
            print("   ❌ Twitch and Kick API errors.")
            return
    
        if twitch_error:
            print_section("📊 RESULT")
            print("   ⚠️ Twitch API error. Kick is offline.")
            return
    
        if kick_error:
            print_section("📊 RESULT")
            print("   ⚠️ Kick API error. Twitch is offline.")
            return
    
        print_section("📊 RESULT")
        print("   😴 No active stream found.")
        return
        
    if twitch_stream:
        platform = "twitch"
        stream = twitch_stream
        stream_id = twitch_stream["id"]
    
    elif kick_stream:
        platform = "kick"
        stream = kick_stream
        stream_id = f"kick-{kick_stream['broadcaster_user_id']}-{kick_stream['stream']['start_time']}"
    
    else:
        return

    print_section("🎯 STREAM SELECTED")

    print(f"   Platform: {platform}")
    print(f"   Stream ID: {stream_id}")
        
    state = load_state()
    
    if not should_process(state):
        return
    
    print("")
    
    print(f"   Platform: {platform}")
    print(f"   Stream ID: {stream_id}")

    stream_data = normalize_stream(platform, stream)

    print_section("📺 STREAM DATA")

    print(f"   Platform: {stream_data['platform']}")
    print(f"   Channel: {stream_data['channel']}")
    print(f"   Title: {stream_data['title']}")
    print(f"   Game: {stream_data['game']}")
    print(f"   Viewers: {stream_data['viewer_count']}")
    print(f"   URL: {stream_data['url']}")

    

    # --------------------------------------------------
    # DISCORD
    # --------------------------------------------------

    print("🤖 Generating Discord message with Gemini...")

    discord_message = generate_discord_message(
        stream_data,
        STREAM_CONTEXT,
        state.get("last_messages", [])
    )

    print("")
    print("===== DISCORD MESSAGE =====")
    print(discord_message)
    print("===========================")
    print("")

    discord_sent = False
    x_sent = False
    
    try:
        send_to_discord(discord_message)
        discord_sent = True
        save_last_message(state, discord_message)
        print("✅ Discord message sent.")
    except Exception as e:
        discord_sent = False
        print(f"❌ Discord failed: {e}")

    # --------------------------------------------------
    # X
    # --------------------------------------------------

    print("🤖 Generating X message with Gemini...")

    x_message = generate_x_message(
        stream_data,
        STREAM_CONTEXT,
        state.get("last_posts", [])
    )

    print("")
    print("===== X MESSAGE =====")
    print(x_message)
    print("=====================")
    print("")

    is_valid, validation_message = validate_x_message(
            x_message,
            stream_data["url"]
    )
    
    print(f"🔎 X validation: {validation_message}")
    
    if is_valid:
        print("🐦 Sending message to X via Buffer...")
    
        try:
            send_to_buffer(x_message)
            x_sent = True
            save_last_post(state, x_message)
            print("✅ X message sent.")
        except Exception as e:
            x_sent = False
            print(f"❌ X failed: {e}")
    else:
        x_sent = False
        print("❌ X message rejected. It will NOT be published.")

    # --------------------------------------------------
    # SAVE STATE
    # --------------------------------------------------

    state["last_event"] = {
        "platform": platform,
        "stream_id": stream_id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "discord_sent": discord_sent,
        "x_sent": x_sent
    }

    save_state(state)

    print("✅ Stream event saved.")


if __name__ == "__main__":
    main()
