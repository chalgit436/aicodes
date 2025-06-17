import requests
import time

class OAuthClient:
    def __init__(self, client_id, client_secret, token_url, refresh_token):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.refresh_token = refresh_token
        self.access_token = None
        self.expiry_time = 0  # Unix timestamp (seconds)

    def is_token_expired(self):
        return time.time() >= self.expiry_time

    def refresh_access_token(self):
        print("🔄 Refreshing access token...")
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        response = requests.post(self.token_url, data=payload, headers=headers)
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)  # default to 1 hour
            self.expiry_time = time.time() + expires_in - 60  # refresh 1 min before expiry
            print("✅ Token refreshed successfully.")
        else:
            raise Exception(f"❌ Token refresh failed: {response.status_code} {response.text}")

    def get_access_token(self):
        if self.access_token is None or self.is_token_expired():
            self.refresh_access_token()
        return self.access_token

    def make_authenticated_request(self, method, url, **kwargs):
        token = self.get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        response = requests.request(method, url, headers=headers, **kwargs)
        return response


# -----------------------------
# ✅ Example usage
# -----------------------------

if __name__ == "__main__":
    # Replace these with real values from your OAuth provider
    CLIENT_ID = "your-client-id"
    CLIENT_SECRET = "your-client-secret"
    TOKEN_URL = "https://oauth.example.com/token"
    REFRESH_TOKEN = "your-refresh-token"

    API_URL = "https://api.example.com/protected/resource"

    oauth_client = OAuthClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_url=TOKEN_URL,
        refresh_token=REFRESH_TOKEN
    )

    try:
        response = oauth_client.make_authenticated_request("GET", API_URL)
        if response.ok:
            print("📦 API Response:", response.json())
        else:
            print("❌ API Error:", response.status_code, response.text)
    except Exception as e:
        print("❗ Exception:", str(e))
