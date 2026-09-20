import os
import json
import urllib.request
import urllib.parse
import logging
from typing import Any

logger = logging.getLogger(__name__)

TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
REDIRECT_URI = "https://test-n8n.autobotsdev.dev/callback"

def get_auth_url() -> str:
    """Get TikTok OAuth authorization URL."""
    print("\n" + "="*40)
    print("DEBUGGING TIKTOK OAUTH")
    print(f"Client Key leído: '{TIKTOK_CLIENT_KEY}'")
    print(f"Client Secret leído: '{TIKTOK_CLIENT_SECRET}'")
    state = "tiktok_auth"
    scopes = "user.info.basic,video.upload"
    
    url = (
        "https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={TIKTOK_CLIENT_KEY}"
        f"&response_type=code"
        f"&scope={scopes}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        f"&state={state}"
    )
    
    # 2. Usa urllib.parse.urlencode para construir los parámetros de forma segura
    params = {
        "client_key": TIKTOK_CLIENT_KEY,
        "response_type": "code",
        "scope": scopes,
        "redirect_uri": REDIRECT_URI,
        "state": state
    }
    
    url = f"https://www.tiktok.com/v2/auth/authorize/?{urllib.parse.urlencode(params)}"
    print(f"URL final generada:\n{url}")
    print("="*40 + "\n")
    return url

def exchange_code(code: str) -> dict[str, Any]:
    """Exchange authorization code for access tokens."""
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    
    data = urllib.parse.urlencode({
        "client_key": TIKTOK_CLIENT_KEY,
        "client_secret": TIKTOK_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Cache-Control": "no-cache"
    })
    
    with urllib.request.urlopen(req) as response:
        response_data = response.read()
        return json.loads(response_data)
