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
                    patch_payload = {}
                    if to_add:
                        patch_payload["append"] = [{"value": d} for d in to_add]
                    if to_remove:
                        patch_payload["remove"] = to_remove
                    self._api_call(f"lists/{list_id}", method="PATCH", data=patch_payload)
                    print(f"  [✓] Обновлён список '{name}' (+{len(to_add)}, -{len(to_remove)})")
                else:
                    print(f"  [✓] Список '{name}' уже актуален")
                return list_id

        items = [{"value": d} for d in domains]
        payload = {
            "name": name,
            "description": f"Managed domains for {name}",
            "type": "DOMAIN",
            "items": items,
        }
        res = self._api_call("lists", method="POST", data=payload)
        list_id = (res.get("result") or {}).get("id")
        print(f"  [+] Создан список '{name}' ({len(domains)} доменов)")
        return list_id

    def get_or_create_ipv6_block_rule(self, name: str, list_ids: list, enabled: bool = True):
        res = self._api_call("rules")
        existing_rules = res.get("result") or []

        domains_expr = " or ".join([f"any(dns.domains[*] in ${lid})" for lid in list_ids])
        traffic_str = f'({domains_expr}) and dns.query_rtype == "AAAA"'

        payload = {
            "name": name,
            "description": "Block AAAA (IPv6) queries for overridden domains to force IPv4 SNI proxy",
            "enabled": enabled,
            "action": "block",
            "precedence": 10,
            "traffic": traffic_str,
            "rule_settings": {
                "block_page_enabled": False,
            },
            "filters": ["dns"],
        }

        for rule in existing_rules:
            if rule.get("name") == name:
                rule_id = rule.get("id")
                self._api_call(f"rules/{rule_id}", method="PUT", data=payload)
                print(f"  [✓] Обновлено правило '{name}' (enabled={enabled})")
                return rule_id

        res = self._api_call("rules", method="POST", data=payload)
        rule_id = (res.get("result") or {}).get("id")
        print(f"  [+] Создано правило '{name}' (enabled={enabled})")
        return rule_id

    def get_or_create_rule(self, name: str, list_id: str, override_ips: list, enabled: bool = True):
        if isinstance(override_ips, str):
            override_ips = [override_ips]

        res = self._api_call("rules")
        existing_rules = res.get("result") or []
        traffic_str = f"any(dns.domains[*] in ${list_id})"
        payload = {
            "name": name,
            "description": f"DNS override to {', '.join(override_ips)}",
            "enabled": enabled,
            "action": "override",
            "traffic": traffic_str,
            "rule_settings": {
                "override_ips": override_ips,
            },
            "filters": ["dns"],
        }

        for rule in existing_rules:
            if rule.get("name") == name:
                rule_id = rule.get("id")
                self._api_call(f"rules/{rule_id}", method="PUT", data=payload)
                print(f"  [✓] Обновлено правило '{name}' -> {', '.join(override_ips)} (enabled={enabled})")
                return rule_id

        res = self._api_call("rules", method="POST", data=payload)
        rule_id = (res.get("result") or {}).get("id")
        print(f"  [+] Создано правило '{name}' -> {', '.join(override_ips)} (enabled={enabled})")
        return rule_id

    def get_or_create_location(self, name: str = "home") -> dict:
        res = self._api_call("locations")
        existing = res.get("result") or []
        if existing:
            loc = existing[0]
            print(f"  [✓] Найдена существующая точка DNS '{loc.get('name')}'")
            return loc

        payload = {
            "name": name,
            "client_default": True,
        }
        res = self._api_call("locations", method="POST", data=payload)
        loc = res.get("result") or {}
        print(f"  [+] Создана точка DNS '{name}'")
        return loc

    def run(self):
        print("\n[1/4] Проверка подключения к Cloudflare Zero Trust...")
        self.verify_token()
        print("      Авторизация успешна!")

        print("\n[2/4] Создание списков доменов...")
        ai_list_id = self.get_or_create_list("AI_Bypass_Domains", AI_DOMAINS)
        openai_list_id = self.get_or_create_list("OpenAI_Domains", OPENAI_DOMAINS)
        gemini_list_id = self.get_or_create_list("Gemini_Domains", GEMINI_DOMAINS)
        spotify_list_id = self.get_or_create_list("Spotify_Domains", SPOTIFY_DOMAINS)
        soundcloud_list_id = self.get_or_create_list("SoundCloud_Domains", SOUNDCLOUD_DOMAINS)

        print("\n[3/4] Настройка правил перенаправления (DNS Override + защита от IPv6)...")
        self.get_or_create_ipv6_block_rule(
            "Force IPv4 for Overridden Services",
            [ai_list_id, openai_list_id, gemini_list_id, spotify_list_id, soundcloud_list_id],
            enabled=True,
        )
        self.get_or_create_rule("AI Services SNI Override", ai_list_id, AI_OVERRIDE_IPS, enabled=True)
        self.get_or_create_rule("OpenAI Backend Override", openai_list_id, OPENAI_OVERRIDE_IPS, enabled=True)
        self.get_or_create_rule("Google Gemini Override", gemini_list_id, GEMINI_OVERRIDE_IPS, enabled=True)
        self.get_or_create_rule("Spotify SNI Override", spotify_list_id, SPOTIFY_OVERRIDE_IPS, enabled=False)
        self.get_or_create_rule("SoundCloud SNI Override", soundcloud_list_id, SOUNDCLOUD_OVERRIDE_IPS, enabled=False)

        print("\n[4/4] Получение адресов вашей персональной точки DNS...")
        loc = self.get_or_create_location("home")
        subdomain = loc.get("doh_subdomain")
        doh_url = f"https://{subdomain}.cloudflare-gateway.com/dns-query"
        dot_host = f"{subdomain}.cloudflare-gateway.com"
        ipv4 = loc.get("ipv4_destination", "172.64.36.1")

        print("\n" + "=" * 68)
        print("ГОТОВО! ВАШ ПЕРСОНАЛЬНЫЙ DNS УСПЕШНО НАСТРОЕН:")
        print("=" * 68)
        print("\n DoH адрес (DNS-over-HTTPS):")
        print(f"   {doh_url}\n")
        print(" DoT адрес (DNS-over-TLS для Android / роутеров):")
        print(f"   {dot_host}\n")
        print(" IPv4 адрес:")
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
    print("1. Account ID (32 символа из адресной строки дашборда)")
    print("2. API Token с правами 'Account -> Zero Trust -> Edit'\n")

    account_id = safe_input("Введите ваш Account ID: ").strip()
    if not account_id:
        print("\n[!] Ошибка: Account ID не может быть пустым.")
        safe_input("\nНажмите Enter для выхода...")
        sys.exit(1)

    if len(account_id) != 32:
        print("\n[!] Предупреждение: Account ID обычно состоит ровно из 32 символов (проверьте, что не вставили лишний текст или ссылку).")

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
