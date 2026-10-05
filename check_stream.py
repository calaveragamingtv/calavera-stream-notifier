import os
import requests

TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_CLIENT_SECRET = os.environ["TWITCH_CLIENT_SECRET"]

CHANNEL_NAME = "CalaveraGamingTV"


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


def main():
    print(f"Checking Twitch channel: {CHANNEL_NAME}")

    token = get_twitch_token()
    stream = get_stream_info(token)

    if stream is None:
        print("🔴 Stream is OFFLINE")
        return

    print("🟢 Stream is ONLINE")
    print(f"Title: {stream['title']}")
    print(f"Game ID: {stream['game_id']}")
    print(f"Viewers: {stream['viewer_count']}")


if __name__ == "__main__":
    main()
