import os
import requests


KICK_CLIENT_ID = os.environ["KICK_CLIENT_ID"]
KICK_CLIENT_SECRET = os.environ["KICK_CLIENT_SECRET"]

KICK_USERNAME = "CalaveraGamingTV"


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

    data = response.json()

    return data["access_token"]


def get_channel(token):
    response = requests.get(
        "https://api.kick.com/public/v1/channels",
        headers={
            "Authorization": f"Bearer {token}",
        },
        params={
            "slug": KICK_USERNAME,
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def main():
    print(f"Checking Kick channel: {KICK_USERNAME}")

    token = get_kick_token()

    print("✅ Kick App Access Token obtained.")

    channel = get_channel(token)

    print("")
    print("===== KICK CHANNEL =====")
    print(channel)
    print("========================")


if __name__ == "__main__":
    main()
