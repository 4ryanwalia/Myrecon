"""One-time interactive authorization. Run locally; never paste secrets in chat.

Prints Google's consent URL and stores the authorized-user JSON in a private
output location for transfer to Render's secret environment configuration.
"""
import argparse
import getpass
from importlib import resources
import json
import os
from pathlib import Path


def main():
    from google_auth_oauthlib.flow import InstalledAppFlow

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    destination = Path(args.output).resolve()
    if destination.exists():
        raise SystemExit("Choose a new output path; existing credentials are not overwritten.")
    config = json.loads(resources.files("colab_cli").joinpath("oauth_config.json").read_text())
    scopes = ["https://www.googleapis.com/auth/userinfo.email",
              "https://www.googleapis.com/auth/colaboratory"]
    flow = InstalledAppFlow.from_client_config(config, scopes=scopes,
        redirect_uri="https://sdk.cloud.google.com/applicationdefaultauthcode.html")
    url, _ = flow.authorization_url(access_type="offline", prompt="consent", token_usage="remote")
    print("Open this Google authorization URL with the account that owns your Colab units:")
    print(url)
    flow.fetch_token(code=getpass.getpass("Google authorization code (hidden): ").strip())
    credentials = flow.credentials
    if not credentials.refresh_token:
        raise SystemExit("No refresh token returned; authorization was not saved.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as target:
        json.dump({"type": "authorized_user", "client_id": credentials.client_id,
                   "client_secret": credentials.client_secret,
                   "refresh_token": credentials.refresh_token}, target)
    print("Authorization saved. Transfer this file only to Render's COLAB_GOOGLE_CREDENTIALS_JSON secret.")
    print("Do not commit it or paste it into chat.")


if __name__ == "__main__":
    main()
