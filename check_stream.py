
import os
import json
from datetime import datetime, timezone, timedelta

import requests

from src.notifier_summary import finalize_summary


TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_CLIENT_SECRET = os.environ["TWITCH_CLIENT_SECRET"]
KICK_CLIENT_ID = os.environ["KICK_CLIENT_ID"]
KICK_CLIENT_SECRET = os.environ["KICK_CLIENT_SECRET"]

# Las credenciales de publicación son opcionales mientras el canal
# correspondiente esté deshabilitado en config/notifier.json.
BUFFER_CHANNEL_ID = "6a987c1f065799be4676bb2a"
NOTIFIER_CONFIG_FILE = "config/notifier.json"
TWITCH_CHANNEL_NAME = "CalaveraGamingTV"
KICK_CHANNEL_SLUG = "CalaveraGamingTV"

STATE_FILE = "stream_state.json"
COOLDOWN_HOURS = 14

GEMINI_MODEL = "gemini-3.5-flash-lite"
POST_HISTORY_FILE = "data/post_history.json"
HISTORY_DAYS = 7


def require_env(name):
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Missing required GitHub Actions secret/environment variable: {name}"
        )

    return value


def load_notifier_config():
    if not os.path.isfile(NOTIFIER_CONFIG_FILE):
        raise FileNotFoundError(
            f"Notifier configuration not found: {NOTIFIER_CONFIG_FILE}"
        )

    with open(NOTIFIER_CONFIG_FILE, "r", encoding="utf-8") as file:
        config = json.load(file)

    publishing = config.get("publishing")

    if not isinstance(publishing, dict):
        raise ValueError(
            "Invalid notifier config: expected an object named 'publishing'."
        )

    for channel in ("discord", "x", "instagram"):
        if channel not in publishing:
            raise ValueError(
                f"Invalid notifier config: missing publishing.{channel}."
            )

        if not isinstance(publishing[channel], bool):
            raise ValueError(
                f"Invalid notifier config: publishing.{channel} must be true or false."
            )

    return publishing


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


def load_post_history():
    if not os.path.exists(POST_HISTORY_FILE):
        return {
            "discord": [],
            "x": []
        }

    with open(POST_HISTORY_FILE, "r", encoding="utf-8") as file:
        history = json.load(file)

    history.setdefault("discord", [])
    history.setdefault("x", [])

    return history


def save_post_history(history):
    os.makedirs(os.path.dirname(POST_HISTORY_FILE), exist_ok=True)

    with open(POST_HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history, file, indent=2, ensure_ascii=False)


def add_post_to_history(history, platform, message):
    if platform not in ("discord", "x"):
        raise ValueError(f"Unknown history platform: {platform}")

    now = datetime.now(timezone.utc)

    posts = history.get(platform, [])

    posts.append({
        "message": message,
        "posted_at": now.isoformat()
    })

    cutoff = now - timedelta(days=HISTORY_DAYS)

    history[platform] = [
        post for post in posts
        if datetime.fromisoformat(post["posted_at"]) >= cutoff
    ]

    save_post_history(history)


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

    if (
        last_event.get("platform") == platform
        and last_event.get("stream_id") == stream_id
    ):
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
            "stream_id": (
                f"kick-{stream['broadcaster_user_id']}-"
                f"{stream['stream']['start_time']}"
            ),
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
            "x-goog-api-key": require_env("GEMINI_API_KEY"),
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
            "x-goog-api-key": require_env("GEMINI_API_KEY"),
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
        require_env("DISCORD_WEBHOOK_URL"),
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
            "Authorization": f"Bearer {require_env('BUFFER_API_KEY')}",
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

    execution = {
        "status": "STARTED",
        "reason": "Execution started"
    }

    services = {
        "twitch": {"status": "NOT_CHECKED"},
        "kick": {"status": "NOT_CHECKED"},
        "gemini": {"status": "NOT_CHECKED"},
        "discord_webhook": {"status": "NOT_CHECKED"},
        "buffer_x": {"status": "NOT_CHECKED"},
        "instagram": {"status": "NOT_CHECKED"}
    }

    stream_summary = {
        "status": "UNKNOWN",
        "platform": None,
        "channel": None,
        "game": None,
        "viewers": 0,
        "stream_id": None,
        "url": None,
        "title": None
    }

    publications = {
        "discord": {"status": "NOT_ATTEMPTED", "message": None},
        "x": {"status": "NOT_ATTEMPTED", "message": None},
        "instagram": {"status": "NOT_ATTEMPTED", "message": None}
    }

    errors = []

    def finish():
        summary_data = {
            "execution": execution,
            "services": services,
            "stream": stream_summary,
            "publications": publications,
            "errors": errors
        }

        try:
            finalize_summary(summary_data)
        except Exception as summary_error:
            print(
                f"[SUMMARY] Could not generate execution summary: "
                f"{summary_error}"
            )

    try:
        publishing = load_notifier_config()

    except Exception as e:
        execution["status"] = "FAILED"
        execution["reason"] = "Could not load publishing configuration"
        errors.append(f"Notifier configuration: {e}")

        print(f"❌ Could not load notifier configuration: {e}")

        finish()
        return

    print("📣 PUBLISHING CONFIGURATION")
    print(f"   Discord:   {'ENABLED' if publishing['discord'] else 'DISABLED'}")
    print(f"   X:         {'ENABLED' if publishing['x'] else 'DISABLED'}")
    print(f"   Instagram: {'ENABLED' if publishing['instagram'] else 'DISABLED'}")

    print(f"📡 Checking Twitch channel: {TWITCH_CHANNEL_NAME}")

    twitch_stream = None
    kick_stream = None
    twitch_error = None
    kick_error = None

    print_section("📡 CHECKING PLATFORMS")

    try:
        twitch_token = get_twitch_token()
        twitch_stream = get_stream_info(twitch_token)

        services["twitch"] = {
            "status": "OK",
            "detail": "API request successful"
        }

    except Exception as e:
        twitch_error = str(e)

        services["twitch"] = {
            "status": "API_ERROR",
            "detail": twitch_error
        }

        errors.append(f"Twitch API: {twitch_error}")

    try:
        kick_token = get_kick_token()
        kick_stream = get_kick_stream_info(kick_token)

        services["kick"] = {
            "status": "OK",
            "detail": "API request successful"
        }

    except Exception as e:
        kick_error = str(e)

        services["kick"] = {
            "status": "API_ERROR",
            "detail": kick_error
        }

        errors.append(f"Kick API: {kick_error}")

    print("")

    if twitch_error:
        print("   Twitch: ⚠️ API ERROR")
        print(f"   └─ {twitch_error}")

    elif twitch_stream:
        print("   Twitch: 🟢 ONLINE")
        print(f"   ├─ Stream ID: {twitch_stream['id']}")
        print(f"   ├─ Title: {twitch_stream['title']}")
        print(f"   └─ Viewers: {twitch_stream['viewer_count']}")

    else:
        print("   Twitch: 🔴 OFFLINE")

    if kick_error:
        print("   Kick:   ⚠️ API ERROR")
        print(f"   └─ {kick_error}")

    elif kick_stream:
        print("   Kick:   🟢 ONLINE")
        print(f"   ├─ Broadcaster ID: {kick_stream['broadcaster_user_id']}")
        print(f"   ├─ Title: {kick_stream['stream_title']}")
        print(f"   └─ Viewers: {kick_stream['stream']['viewer_count']}")

    else:
        print("   Kick:   🔴 OFFLINE")

    # --------------------------------------------------
    # NO ACTIVE STREAM
    # --------------------------------------------------
    # Si ambas APIs respondieron y ambos canales están offline,
    # se termina sin Gemini ni publicaciones.
    #
    # Si alguna API falló y no hay otro stream online,
    # tampoco publicamos: no podemos confirmar que haya un directo.
    # --------------------------------------------------

    if not twitch_stream and not kick_stream:

        if twitch_error or kick_error:
            execution["status"] = "INCOMPLETE"
            execution["reason"] = (
                "Could not confirm an active stream because "
                "at least one platform API failed"
            )

            stream_summary["status"] = "UNKNOWN"

            for name in ("discord", "x", "instagram"):
                publications[name] = {
                    "status": "NOT_PUBLISHED",
                    "message": None,
                    "detail": (
                        "No stream was confirmed; "
                        "publishing was not attempted"
                    )
                }

            print_section("📊 RESULT")
            print(
                "   ⚠️ No confirmed active stream. "
                "Nothing will be published."
            )

        else:
            execution["status"] = "SUCCESS"
            execution["reason"] = (
                "Twitch and Kick are offline; "
                "no publication attempted"
            )

            stream_summary["status"] = "OFFLINE"

            for name in ("discord", "x", "instagram"):
                publications[name] = {
                    "status": "SKIPPED",
                    "message": None,
                    "detail": "No active stream"
                }

            print_section("📊 RESULT")
            print(
                "   😴 No active stream found. "
                "No messages generated or published."
            )

        finish()
        return

    # Twitch mantiene prioridad cuando ambas plataformas están online.
    if twitch_stream:
        platform = "twitch"
        stream = twitch_stream
        stream_id = twitch_stream["id"]

    else:
        platform = "kick"
        stream = kick_stream

        stream_id = (
            f"kick-{kick_stream['broadcaster_user_id']}-"
            f"{kick_stream['stream']['start_time']}"
        )

    print_section("🎯 STREAM SELECTED")
    print(f"   Platform: {platform}")
    print(f"   Stream ID: {stream_id}")

    state = load_state()
    post_history = load_post_history()

    stream_data = normalize_stream(platform, stream)

    stream_summary.update({
        "status": "ONLINE",
        "platform": stream_data["platform"],
        "channel": stream_data["channel"],
        "game": stream_data["game"],
        "viewers": stream_data["viewer_count"],
        "stream_id": stream_data["stream_id"],
        "url": stream_data["url"],
        "title": stream_data["title"]
    })

    # --------------------------------------------------
    # DUPLICATE EVENT
    # --------------------------------------------------

    if already_processed(state, platform, stream_id):
        execution["status"] = "SUCCESS"
        execution["reason"] = "This stream event was already processed"

        for name in publications:
            publications[name] = {
                "status": "SKIPPED",
                "message": None,
                "detail": "Stream event already processed"
            }

        finish()
        return

    # --------------------------------------------------
    # COOLDOWN
    # --------------------------------------------------

    if not should_process(state):
        execution["status"] = "SUCCESS"
        execution["reason"] = f"{COOLDOWN_HOURS}-hour cooldown active"

        for name in publications:
            publications[name] = {
                "status": "SKIPPED",
                "message": None,
                "detail": f"Cooldown of {COOLDOWN_HOURS} hours is active"
            }

        finish()
        return

    print_section("📺 STREAM DATA")
    print(f"   Platform: {stream_data['platform']}")
    print(f"   Channel: {stream_data['channel']}")
    print(f"   Title: {stream_data['title']}")
    print(f"   Game: {stream_data['game']}")
    print(f"   Viewers: {stream_data['viewer_count']}")
    print(f"   URL: {stream_data['url']}")

    gemini_successes = 0
    gemini_failures = []

    # --------------------------------------------------
    # INSTAGRAM STORIES
    # --------------------------------------------------

    if publishing["instagram"]:
        print_section("📸 INSTAGRAM STORY")

        try:
            from src.instagram.config import load_config
            from src.instagram.publisher import publish_story

            instagram_config = load_config()

            publish_story(
                platform=platform,
                config=instagram_config
            )

            if instagram_config["dry_run"]:
                publications["instagram"] = {
                    "status": "DRY_RUN",
                    "message": None,
                    "detail": (
                        "Validation completed; "
                        "no Story published"
                    )
                }

                services["instagram"] = {
                    "status": "OK",
                    "detail": "Dry-run validation successful"
                }

                print(
                    "ℹ️ Instagram dry-run completed. "
                    "Nothing was published."
                )

            else:
                publications["instagram"] = {
                    "status": "PUBLISHED",
                    "message": None,
                    "detail": f"Story video for {platform}"
                }

                services["instagram"] = {
                    "status": "OK",
                    "detail": "Story upload completed"
                }

                print("✅ Instagram Story published.")

        except Exception as e:
            publications["instagram"] = {
                "status": "FAILED",
                "message": None,
                "detail": str(e)
            }

            services["instagram"] = {
                "status": "ERROR",
                "detail": str(e)
            }

            errors.append(f"Instagram: {e}")

            print(f"❌ Instagram failed: {e}")

    else:
        publications["instagram"] = {
            "status": "DISABLED",
            "message": None,
            "detail": "Disabled in config/notifier.json"
        }

        services["instagram"] = {
            "status": "DISABLED"
        }

        print_section("📸 INSTAGRAM STORY")
        print(
            "⏭️ Instagram disabled in config/notifier.json. "
            "Skipping."
        )

    # --------------------------------------------------
    # DISCORD
    # --------------------------------------------------

    if publishing["discord"]:
        print_section("💬 DISCORD")

        try:
            print("🤖 Generating Discord message with Gemini...")

            discord_messages = [
                item["message"]
                for item in post_history.get("discord", [])
            ]

            discord_message = generate_discord_message(
                stream_data,
                stream_data["title"],
                discord_messages
            )

            gemini_successes += 1

            publications["discord"]["message"] = discord_message

            print("")
            print("===== DISCORD MESSAGE =====")
            print(discord_message)
            print("===========================")
            print("")

            try:
                send_to_discord(discord_message)

                publications["discord"].update({
                    "status": "PUBLISHED",
                    "detail": "Successfully sent to Discord webhook"
                })

                services["discord_webhook"] = {
                    "status": "OK",
                    "detail": "Webhook accepted the message"
                }

                try:
                    save_last_message(state, discord_message)

                    add_post_to_history(
                        post_history,
                        "discord",
                        discord_message
                    )

                except Exception as history_error:
                    errors.append(
                        f"Discord history update: {history_error}"
                    )

                    print(
                        "⚠️ Discord was published, but history "
                        f"could not be updated: {history_error}"
                    )

                print("✅ Discord message sent.")

            except Exception as e:
                publications["discord"].update({
                    "status": "FAILED",
                    "detail": str(e)
                })

                services["discord_webhook"] = {
                    "status": "ERROR",
                    "detail": str(e)
                }

                errors.append(f"Discord webhook: {e}")

                print(f"❌ Discord publishing failed: {e}")

        except Exception as e:
            publications["discord"] = {
                "status": "FAILED",
                "message": None,
                "detail": f"Message generation failed: {e}"
            }

            gemini_failures.append(
                f"Discord message generation: {e}"
            )

            print(f"❌ Discord message generation failed: {e}")

    else:
        publications["discord"] = {
            "status": "DISABLED",
            "message": None,
            "detail": "Disabled in config/notifier.json"
        }

        services["discord_webhook"] = {
            "status": "DISABLED"
        }

        print_section("💬 DISCORD")
        print(
            "⏭️ Discord disabled in config/notifier.json. "
            "Skipping."
        )

    # --------------------------------------------------
    # X (VIA BUFFER)
    # --------------------------------------------------

    if publishing["x"]:
        print_section("🐦 X")

        try:
            print("🤖 Generating X message with Gemini...")

            x_posts = [
                item["message"]
                for item in post_history.get("x", [])
            ]

            x_message = generate_x_message(
                stream_data,
                stream_data["title"],
                x_posts
            )

            gemini_successes += 1

            publications["x"]["message"] = x_message

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

            if not is_valid:
                publications["x"].update({
                    "status": "REJECTED",
                    "detail": validation_message
                })

                services["buffer_x"] = {
                    "status": "NOT_CALLED",
                    "detail": "Message rejected by validation"
                }

                print(
                    "❌ X message rejected. "
                    "It will NOT be published."
                )

            else:
                try:
                    print("🐦 Sending message to X via Buffer...")

                    send_to_buffer(x_message)

                    publications["x"].update({
                        "status": "PUBLISHED",
                        "detail": "Successfully sent through Buffer"
                    })

                    services["buffer_x"] = {
                        "status": "OK",
                        "detail": "Buffer accepted the post"
                    }

                    try:
                        save_last_post(state, x_message)

                        add_post_to_history(
                            post_history,
                            "x",
                            x_message
                        )

                    except Exception as history_error:
                        errors.append(
                            f"X history update: {history_error}"
                        )

                        print(
                            "⚠️ X was published, but history "
                            f"could not be updated: {history_error}"
                        )

                    print("✅ X message sent.")

                except Exception as e:
                    publications["x"].update({
                        "status": "FAILED",
                        "detail": str(e)
                    })

                    services["buffer_x"] = {
                        "status": "ERROR",
                        "detail": str(e)
                    }

                    errors.append(f"X via Buffer: {e}")

                    print(f"❌ X publishing failed: {e}")

        except Exception as e:
            publications["x"] = {
                "status": "FAILED",
                "message": None,
                "detail": f"Message generation failed: {e}"
            }

            gemini_failures.append(
                f"X message generation: {e}"
            )

            print(f"❌ X message generation failed: {e}")

    else:
        publications["x"] = {
            "status": "DISABLED",
            "message": None,
            "detail": "Disabled in config/notifier.json"
        }

        services["buffer_x"] = {
            "status": "DISABLED"
        }

        print_section("🐦 X")
        print(
            "⏭️ X disabled in config/notifier.json. "
            "Skipping."
        )

    # --------------------------------------------------
    # GEMINI SERVICE STATUS
    # --------------------------------------------------

    if gemini_successes and gemini_failures:
        services["gemini"] = {
            "status": "PARTIAL",
            "detail": (
                f"{gemini_successes} generation(s) succeeded; "
                + "; ".join(gemini_failures)
            )
        }

    elif gemini_successes:
        services["gemini"] = {
            "status": "OK",
            "detail": (
                f"{gemini_successes} message(s) generated successfully"
            )
        }

    elif gemini_failures:
        services["gemini"] = {
            "status": "ERROR",
            "detail": "; ".join(gemini_failures)
        }

    else:
        services["gemini"] = {
            "status": "NOT_USED"
        }

    errors.extend(gemini_failures)

    # --------------------------------------------------
    # SAVE STATE
    # --------------------------------------------------

    state["last_event"] = {
        "platform": platform,
        "stream_id": stream_id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "instagram_sent": (
            publications["instagram"]["status"] == "PUBLISHED"
        ),
        "discord_sent": (
            publications["discord"]["status"] == "PUBLISHED"
        ),
        "x_sent": (
            publications["x"]["status"] == "PUBLISHED"
        )
    }

    try:
        save_state(state)

    except Exception as e:
        errors.append(f"Saving stream state: {e}")

        execution["status"] = "PARTIAL"
        execution["reason"] = (
            "Stream processed, but state could not be saved"
        )

    published_count = sum(
        1 for item in publications.values()
        if item.get("status") == "PUBLISHED"
    )

    failed_count = sum(
        1 for item in publications.values()
        if item.get("status") == "FAILED"
    )

    if execution["status"] != "PARTIAL":

        if failed_count or errors:
            execution["status"] = "PARTIAL"

            execution["reason"] = (
                f"Stream processed; {published_count} publication(s) "
                f"sent and {failed_count} publication(s) failed"
            )

        else:
            execution["status"] = "SUCCESS"

            execution["reason"] = (
                f"Stream processed; {published_count} publication(s) sent"
            )

    print_section("📊 FINAL RESULT")

    print(f"   Platform: {platform}")

    for name, result in publications.items():
        print(f"   {name.capitalize()}: {result['status']}")

    print("✅ Stream event processing finished.")

    finish()


if __name__ == "__main__":
    main()
