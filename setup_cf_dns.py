#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare Zero Trust Gateway DNS Auto-Setup Tool
Автоматическая настройка персонального безопасного DNS со встроенным обходом блокировок ИИ-сервисов и Spotify.
"""

import urllib.request
import urllib.error
import json
import sys
import os

def safe_input(prompt=""):
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""

# 1. Сервисы ИИ (Claude, Cursor, Perplexity, Canva, Google AI Studio и др.)
AI_DOMAINS = [
    "generativelanguage.googleapis.com",
    "robinfrontend-pa.googleapis.com",
    "proactivebackend-pa.googleapis.com",
    "alkalimakersuite-pa.clients6.google.com",
    "bard.google.com",
    "claude.ai",
    "claude.com",
    "anthropic.com",
    "claudeusercontent.com",
    "aistudio.google.com",
    "makersuite.google.com",
    "deepmind.com",
    "deepmind.google",
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
]

# 2. Сервисы OpenAI (ChatGPT)
OPENAI_DOMAINS = [
    "openai.com",
    "auth.openai.com",
    "auth0.openai.com",
    "api.openai.com",
    "chat.openai.com",
    "tcr9i.chat.openai.com",
    "chatgpt.com",
    "chatgpt.site",
]

# 3. Google Gemini (вынесен отдельно для стабильной работы без капчи)
GEMINI_DOMAINS = [
    "gemini.google.com",
    "gemini.google",
]

# 4. Spotify (веб-плеер, авторизация, API и CDN)
SPOTIFY_DOMAINS = [
    "spotify.com",
    "scdn.co",
    "spotifycdn.com",
]

# Проверенные зарубежные IP-релеи
AI_OVERRIDE_IPS = ["143.20.64.192"]
OPENAI_OVERRIDE_IPS = ["37.221.93.141"]
GEMINI_OVERRIDE_IPS = ["109.120.187.249", "217.144.190.216"]
SPOTIFY_OVERRIDE_IPS = ["217.144.190.216", "109.120.187.249"]


class CloudflareGatewaySetup:
    def __init__(self, account_id: str, api_token: str):
        self.account_id = account_id.strip()
        self.api_token = api_token.strip()
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/gateway"

    def _api_call(self, endpoint: str, method: str = "GET", data: dict = None):
        url = f"{self.base_url}/{endpoint}" if not endpoint.startswith("https://") else endpoint
        req_data = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=req_data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                errors = err_json.get("errors", [])
                err_msg = errors[0].get("message") if errors else err_body
            except Exception:
                err_msg = err_body
            raise RuntimeError(f"Ошибка API ({e.code}): {err_msg}")
        except Exception as e:
            raise RuntimeError(f"Сетевая ошибка: {e}")

    def verify_token(self):
        url = "https://api.cloudflare.com/client/v4/user/tokens/verify"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("success"):
                    raise RuntimeError("Токен недействителен")
        except Exception as e:
            raise RuntimeError(f"Неверный API Token: {e}")

    def get_or_create_list(self, name: str, domains: list) -> str:
        res = self._api_call("lists")
        existing_lists = res.get("result", [])
        for lst in existing_lists:
            if lst.get("name") == name:
                list_id = lst.get("id")
                print(f"  [✓] Список '{name}' уже существует")
                return list_id

        items = [{"value": d} for d in domains]
        payload = {
            "name": name,
            "description": f"Managed domains for {name}",
            "type": "DOMAIN",
            "items": items
        }
        res = self._api_call("lists", method="POST", data=payload)
        list_id = res.get("result", {}).get("id")
        print(f"  [+] Создан список '{name}' ({len(domains)} доменов)")
        return list_id

    def get_or_create_rule(self, name: str, list_id: str, override_ips: list):
        if isinstance(override_ips, str):
            override_ips = [override_ips]

        res = self._api_call("rules")
        existing_rules = res.get("result", [])
        traffic_str = 'any(dns.domains[*] in $' + list_id + ')'
        payload = {
            "name": name,
            "description": f"SNI override to {', '.join(override_ips)}",
            "enabled": True,
            "action": "override",
            "traffic": traffic_str,
            "rule_settings": {
                "override_ips": override_ips
            },
            "filters": ["dns"]
        }

        for rule in existing_rules:
            if rule.get("name") == name:
                rule_id = rule.get("id")
                self._api_call(f"rules/{rule_id}", method="PUT", data=payload)
                print(f"  [✓] Обновлено правило '{name}' -> {', '.join(override_ips)}")
                return rule_id

        res = self._api_call("rules", method="POST", data=payload)
        rule_id = res.get("result", {}).get("id")
        print(f"  [+] Создано правило '{name}' -> {', '.join(override_ips)}")
        return rule_id

    def get_or_create_location(self, name: str = "home") -> dict:
        res = self._api_call("locations")
        existing = res.get("result", [])
        if existing:
            loc = existing[0]
            print(f"  [✓] Найдена существующая точка DNS '{loc.get('name')}'")
            return loc

        payload = {
            "name": name,
            "client_default": True
        }
        res = self._api_call("locations", method="POST", data=payload)
        loc = res.get("result", {})
        print(f"  [+] Создана точка DNS '{name}'")
        return loc

    def run(self):
        print("\n[1/4] Проверка подключения к Cloudflare...")
        self.verify_token()
        print("      Авторизация успешна!")

        print("\n[2/4] Создание списков доменов...")
        ai_list_id = self.get_or_create_list("AI_Bypass_Domains", AI_DOMAINS)
        openai_list_id = self.get_or_create_list("OpenAI_Domains", OPENAI_DOMAINS)
        gemini_list_id = self.get_or_create_list("Gemini_Domains", GEMINI_DOMAINS)
        spotify_list_id = self.get_or_create_list("Spotify_Domains", SPOTIFY_DOMAINS)

        print("\n[3/4] Настройка правил перенаправления (SNI Override)...")
        self.get_or_create_rule("AI Services SNI Override", ai_list_id, AI_OVERRIDE_IPS)
        self.get_or_create_rule("OpenAI Backend Override", openai_list_id, OPENAI_OVERRIDE_IPS)
        self.get_or_create_rule("Google Gemini Override", gemini_list_id, GEMINI_OVERRIDE_IPS)
        self.get_or_create_rule("Spotify SNI Override", spotify_list_id, SPOTIFY_OVERRIDE_IPS)

        print("\n[4/4] Получение адресов вашей персональной точки DNS...")
        loc = self.get_or_create_location("home")
        subdomain = loc.get("doh_subdomain")
        doh_url = f"https://{subdomain}.cloudflare-gateway.com/dns-query"
        dot_host = f"{subdomain}.cloudflare-gateway.com"
        ipv4 = loc.get("ipv4_destination", "172.64.36.1")

        print("\n" + "=" * 68)
        print("ГОТОВО! ВАШ ПЕРСОНАЛЬНЫЙ DNS УСПЕШНО НАСТРОЕН:")
        print("=" * 68)
        print(f"\n DoH адрес (DNS-over-HTTPS):")
        print(f"   {doh_url}\n")
        print(f" DoT адрес (DNS-over-TLS для Android / роутеров):")
        print(f"   {dot_host}\n")
        print(f" IPv4 адрес:")
        print(f"   {ipv4}\n")
        print("=" * 68)
        print("КАК ИСПОЛЬЗОВАТЬ:")
        print("1. В браузере (Chrome / Edge / Яндекс / Firefox / Opera):")
        print("   Настройки -> Безопасность -> Использовать безопасный DNS (DoH)")
        print(f"   -> Выберите 'Свой поставщик' и вставьте: {doh_url}")
        print("\n2. На телефоне (Android):")
        print("   Настройки -> Сеть / Подключения -> Частный DNS (Private DNS)")
        print(f"   -> Вставьте имя хоста: {dot_host}")
        print("\n3. На роутере (Keenetic / OpenWrt / Asus):")
        print(f"   Добавьте DoH-сервер с адресом: {doh_url}")
        print("=" * 68 + "\n")


def main():
    print("=" * 68)
    print("  Cloudflare Zero Trust — Автоматическая настройка Gateway DNS")
    print("=" * 68)
    print("Для работы понадобятся данные из вашего кабинета Cloudflare:")
    print("1. Account ID (на главной странице справа)")
    print("2. API Token с правами 'Account -> Zero Trust -> Edit'\n")

    account_id = safe_input("Введите ваш Account ID: ").strip()
    if not account_id:
        print("\n[!] Ошибка: Account ID не может быть пустым.")
        safe_input("\nНажмите Enter для выхода...")
        sys.exit(1)

    api_token = safe_input("Введите ваш API Token: ").strip()
    if not api_token:
        print("\n[!] Ошибка: API Token не может быть пустым.")
        safe_input("\nНажмите Enter для выхода...")
        sys.exit(1)

    try:
        setup = CloudflareGatewaySetup(account_id, api_token)
        setup.run()
    except Exception as e:
        print(f"\n[!] Ошибка: {e}")
    
    safe_input("Нажмите Enter, чтобы закрыть окно...")


if __name__ == "__main__":
    main()
