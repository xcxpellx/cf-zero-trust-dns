#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare Zero Trust Gateway DNS Auto-Setup Tool
Автоматическая настройка персонального шифрованного DNS (DoH/DoT)
с правилами DNS Override для ИИ-сервисов, Spotify и SoundCloud.
"""

import urllib.request
import urllib.error
import json
import sys


def safe_input(prompt=""):
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""


# 1. Сервисы ИИ и зарубежные платформы (Claude, Grok, Cursor, Perplexity, DeepL, Notion, Canva и др.)
AI_DOMAINS = [
    "claude.ai",
    "claude.com",
    "anthropic.com",
    "claudeusercontent.com",
    "grok.com",
    "grok.x.com",
    "assets.grok.com",
    "x.ai",
    "accounts.x.ai",
    "console.x.ai",
    "api.x.ai",
    "sora.com",
    "perplexity.ai",
    "copilot.microsoft.com",
    "v0.dev",
    "ntc.party",
    "cursor.com",
    "cursor.sh",
    "cursorapi.com",
    "midjourney.com",
    "civitai.com",
    "designer.microsoft.com",
    "canva.com",
    "deepl.com",
    "notion.so",
    "notion.site",
    "elevenlabs.io",
]

# 2. Сервисы OpenAI (ChatGPT, CDN статики и ассетов DALL-E)
OPENAI_DOMAINS = [
    "openai.com",
    "auth.openai.com",
    "auth0.openai.com",
    "api.openai.com",
    "chat.openai.com",
    "tcr9i.chat.openai.com",
    "chatgpt.com",
    "chatgpt.site",
    "oaistatic.com",
    "oaiusercontent.com",
]

# 3. Google Gemini и AI Studio (единый стек без капчи и региональных сбоев)
GEMINI_DOMAINS = [
    "gemini.google.com",
    "gemini.google",
    "geminiweb-pa.clients6.google.com",
    "bard.google.com",
    "aistudio.google.com",
    "makersuite.google.com",
    "alkalimakersuite-pa.clients6.google.com",
    "webchannel-alkalimakersuite-pa.clients6.google.com",
    "generativelanguage.googleapis.com",
    "proactivebackend-pa.googleapis.com",
    "robinfrontend-pa.googleapis.com",
    "deepmind.com",
    "deepmind.google",
]

# 4. Spotify (веб-плеер, авторизация, API и CDN)
SPOTIFY_DOMAINS = [
    "spotify.com",
    "scdn.co",
    "spotifycdn.com",
    "spotifycdn.net",
    "spotify.design",
    "spotify.link",
]

# 5. SoundCloud (опциональный CloudFront-маршрут, по умолчанию выключен)
SOUNDCLOUD_DOMAINS = [
    "soundcloud.com",
    "sndcdn.com",
]

# Проверенные зарубежные IP-релеи (SNI-прокси)
AI_OVERRIDE_IPS = ["31.58.216.201"]
OPENAI_OVERRIDE_IPS = ["31.58.216.201"]
GEMINI_OVERRIDE_IPS = ["109.120.187.249"]
SPOTIFY_OVERRIDE_IPS = ["109.120.187.249"]
SOUNDCLOUD_OVERRIDE_IPS = ["52.84.150.39"]


class CloudflareGatewaySetup:
    def __init__(self, account_id: str, api_token: str):
        self.account_id = account_id.strip()
        self.api_token = api_token.strip()
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/gateway"

    def _api_call(self, endpoint: str, method: str = "GET", data: dict = None):
        url = f"{self.base_url}/{endpoint}" if not endpoint.startswith("https://") else endpoint
        req_data = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=req_data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                errors = err_json.get("errors") or []
                err_msg = errors[0].get("message") if errors else err_body
            except Exception:
                err_msg = err_body

            if e.code == 401:
                hint = (
                    "Проверьте API Token: возможно, он неверный, отозван или "
                    "при копировании попали лишние пробелы."
                )
            elif e.code == 403:
                hint = (
                    "Доступ запрещён. Проверьте 3 вещи:\n"
                    "  1) Активирован ли бесплатный тариф Zero Trust на one.dash.cloudflare.com;\n"
                    "  2) Выданы ли токену права 'Account -> Zero Trust -> Edit' (не Read);\n"
                    "  3) Верно ли указан Account ID (32 символа из URL дашборда)."
                )
            else:
                hint = ""

            msg = f"Ошибка API ({e.code}): {err_msg}"
            if hint:
                msg += f"\n[Подсказка] {hint}"
            raise RuntimeError(msg)
        except Exception as e:
            raise RuntimeError(f"Сетевая ошибка: {e}")

    def verify_token(self):
        # Проверяем сразу реальный эндпоинт Gateway — так валидируются
        # и токен (включая Account Tokens), и Account ID, и активация Zero Trust.
        self._api_call("locations")

    def get_or_create_list(self, name: str, domains: list) -> str:
        res = self._api_call("lists")
        existing_lists = res.get("result") or []
        for lst in existing_lists:
            if lst.get("name") == name:
                list_id = lst.get("id")
                items_res = self._api_call(f"lists/{list_id}/items")
                existing_items = [it.get("value") for it in (items_res.get("result") or [])]
                to_add = [d for d in domains if d not in existing_items]
                to_remove = [d for d in existing_items if d not in domains]
                if to_add or to_remove:
