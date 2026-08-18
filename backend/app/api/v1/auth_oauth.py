"""OAuth helpers for Google and GitHub token exchange.

Implemented as a thin httpx wrapper over each provider's standard OAuth2 token
endpoint. If client credentials are not configured we return a deterministic
demo identity so local development does not require a real OAuth app.
"""

from __future__ import annotations

import hashlib

import httpx

from app.core.config import get_settings


async def _token_request(url: str, data: dict, headers: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, data=data, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def exchange_google(code: str) -> dict:
    settings = get_settings()
    if not (settings.google_client_id and settings.google_client_secret):
        return _demo_profile("google", code)
    token = await _token_request(
        "https://oauth2.googleapis.com/token",
        {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": "http://localhost:3000/auth/callback",
        },
    )
    async with httpx.AsyncClient(timeout=20) as client:
        info = (
            await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
        ).json()
    return {
        "email": info["email"],
        "name": info.get("name"),
        "avatar_url": info.get("picture"),
    }


async def exchange_github(code: str) -> dict:
    settings = get_settings()
    if not (settings.github_client_id and settings.github_client_secret):
        return _demo_profile("github", code)
    token = await _token_request(
        "https://github.com/login/oauth/access_token",
        {
            "code": code,
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
        },
        headers={"Accept": "application/json"},
    )
    async with httpx.AsyncClient(timeout=20) as client:
        headers = {
            "Authorization": f"Bearer {token['access_token']}",
            "Accept": "application/vnd.github+json",
        }
        info = (await client.get("https://api.github.com/user", headers=headers)).json()
        emails = (await client.get("https://api.github.com/user/emails", headers=headers)).json()
        primary = next((e for e in emails if e.get("primary")), emails[0] if emails else {})
    return {
        "email": primary.get("email", f"{info.get('login', 'demo')}@demo.cloudpilot.ai"),
        "name": info.get("name") or info.get("login"),
        "avatar_url": info.get("avatar_url"),
    }


def _demo_profile(provider: str, code: str) -> dict:
    """Deterministic demo identity used when OAuth is not configured."""
    digest = hashlib.md5(f"{provider}:{code}".encode()).hexdigest()[:12]
    return {
        "email": f"user-{digest}@demo.cloudpilot.ai",
        "name": "Demo User",
        "avatar_url": None,
    }
