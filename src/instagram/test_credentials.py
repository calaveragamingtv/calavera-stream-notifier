
import os
import sys

from instagrapi import Client


def test_credentials():
    session_id = os.getenv("IG_SESSIONID")

    if not session_id:
        raise ValueError(
            "Missing IG_SESSIONID environment variable."
        )

    client = Client()

    print("[INSTAGRAM TEST] Starting authentication...")
    print("[INSTAGRAM TEST] Using session ID from GitHub Secrets.")

    client.login_by_sessionid(session_id)

    if not client.user_id:
        raise RuntimeError(
            "Authentication failed: Instagram user ID not available."
        )

    print("[INSTAGRAM TEST] Authentication successful.")
    print("[INSTAGRAM TEST] Checking account information...")

    account = client.user_info(client.user_id)

    print("-----------------------------------")
    print("[INSTAGRAM TEST] RESULT: SUCCESS")
    print(f"[INSTAGRAM TEST] Username: @{account.username}")
    print(f"[INSTAGRAM TEST] Account ID: {account.pk}")
    print("-----------------------------------")
    print("[INSTAGRAM TEST] No content was published.")


if __name__ == "__main__":
    try:
        test_credentials()
    except Exception as error:
        print(f"[INSTAGRAM TEST] ERROR: {error}")
        sys.exit(1)
