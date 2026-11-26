#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare Zero Trust Gateway DNS Auto-Setup Tool
Автоматическая настройка персонального шифрованного DNS (DoH/DoT)
с разделёнными группами DNS Override, выбором активных групп и защитой от IPv6.
"""

import json
import re
import sys
import urllib.error
import urllib.request


def safe_input(prompt=""):
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""


# ==============================================================================
# ПРОВЕРЕННЫЕ СПИСКИ ДОМЕНОВ (разделены по группам и совместимым релеям)
# В Cloudflare Gateway правило any(dns.domains[*] in $list) покрывает
# как корневой домен, так и все его поддомены.
# ==============================================================================

# 1. Claude (Anthropic) -> 31.58.216.201
CLAUDE_DOMAINS = [
    "claude.ai",
    "claude.com",
    "anthropic.com",
    "claudeusercontent.com",
]

# 2. Grok / xAI -> 31.58.216.201
GROK_XAI_DOMAINS = [
    "grok.com",
    "grok.x.com",
    "grok.x.ai",
    "assets.grok.com",
    "x.ai",
    "accounts.x.ai",
    "console.x.ai",
    "api.x.ai",
    "assets.x.ai",
]

# 3. OpenAI (ChatGPT, API, CDN статики и ассетов) -> 31.58.216.201
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

# 4. Google Gemini, AI Studio, NotebookLM и Google Labs -> 109.120.187.249
GEMINI_DOMAINS = [
    "gemini.google.com",
    "gemini.google",
    "geminiweb-pa.clients6.google.com",
    "bard.google.com",
    "aistudio.google.com",
    "makersuite.google.com",
    "alkalimakersuite-pa.clients6.google.com",
    "webchannel-alkalimakersuite-pa.clients6.google.com",
    "alkalicore-pa.clients6.google.com",
    "generativelanguage.googleapis.com",
    "proactivebackend-pa.googleapis.com",
    "robinfrontend-pa.googleapis.com",
    "deepmind.com",
    "deepmind.google",
    "notebooklm.google.com",
    "notebooklm.google",
    "notebooklm-pa.googleapis.com",
    "notebook.google.com",
    "notebook.google",
    "notebook-pa.googleapis.com",
    "jules.google.com",
    "jules.google",
    "opal.google.com",
    "labs.google.com",
    "labs.google",
    "aitestkitchen.withgoogle.com",
    "stitch.withgoogle.com",
    "flow.google",
    "ai.google.dev",
    "generativeai.google",
]

# 5. Прочие ИИ-сервисы и AI-IDE (совместимы с 31.58.216.201)
OTHER_AI_DOMAINS = [
    "perplexity.ai",
    "copilot.microsoft.com",
    "v0.dev",
    "cursor.com",
    "cursor.sh",
    "cursor-cdn.com",
    "windsurf.com",
    "codeium.com",
    "trae.ai",
    "designer.microsoft.com",
    "elevenlabs.io",
    "elevenreader.io",
    "openrouter.ai",
    "mistral.ai",
    "cerebras.ai",
    "manus.im",
    "genspark.ai",
    "kaleido.ai",
    "remove.bg",
    "unscreen.com",
    "pi.ai",
]

# 6. Креатив, ИИ-генерация и Dev-платформы (совместимы с 109.120.187.249)
AI_MEDIA_DEV_DOMAINS = [
    "sora.com",
    "midjourney.com",
    "civitai.com",
    "groq.com",
    "together.ai",
    "replicate.com",
    "cohere.com",
    "canva.com",
    "figma.com",
    "notion.so",
    "notion.com",
    "notion.site",
    "notion.new",
    "jetbrains.com",
    "jetbrains.ai",
    "datalore.jetbrains.com",
    "docker.io",
]

# 7. Геоблокированные зарубежные сервисы (проверены на 31.58.216.201)
GEO_DOMAINS = [
    "strava.com",
    "deepl.com",
    "linguee.com",
    "miro.com",
    "linear.app",
    "clickup.com",
    "atlassian.com",
    "framer.com",
    "buymeacoffee.com",
    "scribd.com",
    "behance.net",
    "adobe.io",
    "autodesk.com",
    "autocad.com",
    "sketchup.com",
    "trimble.com",
    "mongodb.com",
    "sentry.io",
    "ngrok.com",
    "tailscale.com",
    "parsec.app",
    "malwarebytes.com",
    "avast.com",
    "dell.com",
    "amd.com",
    "oracle.com",
    "wise.com",
    "revolut.com",
    "deezer.com",
    "last.fm",
    "themoviedb.org",
    "tmdb.org",
    "chess.com",
    "supercell.com",
    "clashofclans.com",
    "xbox.com",
    "geforcenow.com",
    "ikea.com",
    "etsy.com",
    "bestbuy.com",
    "dyson.com",
    "lego.com",
]

# 8. Spotify (опциональный профиль, по умолчанию выключен) -> 109.120.187.249
SPOTIFY_DOMAINS = [
    "spotify.com",
    "scdn.co",
    "spotifycdn.com",
    "spotifycdn.net",
    "spotify.design",
    "spotify.link",
    "spotify.dev",
]

# 9. SoundCloud (опциональный быстрый CloudFront IP, по умолчанию выключен) -> 108.156.22.80
SOUNDCLOUD_DOMAINS = [
    "soundcloud.com",
    "sndcdn.com",
]

# Декларативная конфигурация групп и правил
DOMAIN_GROUPS = [
    {
        "list_name": "Claude_Domains",
        "rule_name": "Claude AI Override",
        "label": "Claude (Anthropic)",
        "domains": CLAUDE_DOMAINS,
        "override_ips": ["31.58.216.201"],
        "default_enabled": True,
    },
    {
        "list_name": "Grok_xAI_Domains",
        "rule_name": "Grok & xAI Override",
        "label": "Grok / xAI",
        "domains": GROK_XAI_DOMAINS,
        "override_ips": ["31.58.216.201"],
        "default_enabled": True,
    },
    {
        "list_name": "OpenAI_Domains",
        "rule_name": "OpenAI Backend Override",
        "label": "OpenAI (ChatGPT & API)",
        "domains": OPENAI_DOMAINS,
        "override_ips": ["31.58.216.201"],
        "default_enabled": True,
    },
    {
        "list_name": "Gemini_Domains",
        "rule_name": "Google Gemini Override",
        "label": "Google Gemini, AI Studio & NotebookLM",
        "domains": GEMINI_DOMAINS,
        "override_ips": ["109.120.187.249"],
        "default_enabled": True,
    },
    {
        "list_name": "Other_AI_Domains",
        "rule_name": "Other AI Services Override",
        "label": "AI-IDE и ассистенты (Cursor, Windsurf, Perplexity, ElevenLabs...)",
        "domains": OTHER_AI_DOMAINS,
        "override_ips": ["31.58.216.201"],
        "default_enabled": True,
    },
    {
        "list_name": "AI_Media_Dev_Domains",
        "rule_name": "AI Media & Dev Override",
        "label": "Sora, Midjourney, Civitai, Canva, Figma, Notion, JetBrains, Docker",
        "domains": AI_MEDIA_DEV_DOMAINS,
        "override_ips": ["109.120.187.249"],
        "default_enabled": True,
    },
    {
        "list_name": "Geo_Domains",
        "rule_name": "Geo Blocked Services Override",
        "label": "Зарубежные сервисы (Strava, DeepL, Miro, Linear, Wise...)",
        "domains": GEO_DOMAINS,
        "override_ips": ["31.58.216.201"],
        "default_enabled": True,
    },
    {
        "list_name": "Spotify_Domains",
        "rule_name": "Spotify Override",
        "label": "Spotify (веб-плеер и обложки)",
        "domains": SPOTIFY_DOMAINS,
        "override_ips": ["109.120.187.249"],
        "default_enabled": False,
    },
    {
        "list_name": "SoundCloud_Domains",
        "rule_name": "SoundCloud Override",
        "label": "SoundCloud (быстрый CloudFront IP; для SNI-DPI нужен d2o/Zapret)",
        "domains": SOUNDCLOUD_DOMAINS,
        "override_ips": ["108.156.22.80"],
        "default_enabled": False,
    },
]


def select_enabled_groups(groups: list) -> list[bool]:
    """Интерактивный выбор активных групп доменов перед применением правил."""
    states = [bool(g["default_enabled"]) for g in groups]

    def print_menu():
        print("\n[?] Выберите, какие группы правил включить (невыбранные создадутся с выключенным тумблером):")
        for idx, (grp, on) in enumerate(zip(groups, states), start=1):
            mark = "ВКЛ " if on else "ВЫКЛ"
            print(f"    {idx}. [{mark}] {grp['label']} ({len(grp['domains'])} дом.)")

    print_menu()
    print("    Enter — применить текущий выбор | Номера (напр. 7 8 9) — переключить | 'all' / 'none'")

    while True:
        raw = safe_input("Ваш выбор [Enter для продолжения]: ").strip().lower()
        if not raw or raw in ("ok", "done", "go"):
            break
        if raw == "all":
            states = [True] * len(groups)
            print_menu()
            continue
        if raw == "none":
            states = [False] * len(groups)
            print_menu()
            continue

        tokens = re.findall(r"\d+", raw)
        if not tokens:
            print("    [!] Введите номера через пробел/запятую, 'all', 'none' или нажмите Enter.")
            continue

        changed = False
        for tok in tokens:
            idx = int(tok) - 1
            if 0 <= idx < len(states):
                states[idx] = not states[idx]
                changed = True
            else:
                print(f"    [!] Номер {tok} вне диапазона (1–{len(groups)}).")
        if changed:
            print_menu()

    return states


class CloudflareGatewaySetup:
    """Клиент настройки списков и DNS-правил Cloudflare Zero Trust Gateway."""

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
                    "  3) Верно ли указан Account ID (профиль в правом верхнем углу -> Copy account ID)."
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
        # Проверка через locations валидирует Account API Tokens, Account ID и активацию Zero Trust.
        self._api_call("locations")

    def cleanup_existing_settings(self):
        print("\n[*] Очистка старых DNS-правил и списков доменов...")
        rules_res = self._api_call("rules")
        existing_rules = rules_res.get("result") or []
        dns_rules = [r for r in existing_rules if "dns" in (r.get("filters") or [])]

        for rule in dns_rules:
            rule_id = rule.get("id")
            rule_name = rule.get("name", rule_id)
            try:
                self._api_call(f"rules/{rule_id}", method="DELETE")
                print(f"  [-] Удалено правило '{rule_name}'")
            except Exception as e:
                print(f"  [!] Не удалось удалить правило '{rule_name}': {e}")

        lists_res = self._api_call("lists")
        existing_lists = lists_res.get("result") or []
        domain_lists = [lst for lst in existing_lists if lst.get("type") == "DOMAIN"]

        for lst in domain_lists:
            list_id = lst.get("id")
            list_name = lst.get("name", list_id)
            try:
                self._api_call(f"lists/{list_id}", method="DELETE")
                print(f"  [-] Удалён список '{list_name}'")
            except Exception as e:
                print(f"  [!] Пропущен список '{list_name}' (возможно, используется в другом правиле): {e}")

    def maybe_prompt_cleanup(self):
        rules_res = self._api_call("rules")
        existing_rules = rules_res.get("result") or []
        dns_rules_count = sum(1 for r in existing_rules if "dns" in (r.get("filters") or []))

        lists_res = self._api_call("lists")
        existing_lists = lists_res.get("result") or []
        domain_lists_count = sum(1 for lst in existing_lists if lst.get("type") == "DOMAIN")

        if dns_rules_count == 0 and domain_lists_count == 0:
            return

        print(f"\n[?] На аккаунте найдены существующие настройки (DNS-правил: {dns_rules_count}, списков доменов: {domain_lists_count}).")
        print("    1 — Оставить как есть и обновить/добавить наши правила (по умолчанию)")
        print("    2 — Удалить все старые DNS-правила и списки перед настройкой")
        print("        (ваша точка DNS и адреса DoH/DoT при этом сохранятся)")
        choice = safe_input("Выберите действие [1/2]: ").strip()
        if choice == "2":
            self.cleanup_existing_settings()
        else:
            print("    -> Существующие настройки сохранены, обновляем поверх.")

    def get_or_create_list(self, name: str, domains: list) -> str:
        unique_domains = list(dict.fromkeys(domains))
        res = self._api_call("lists")
        existing_lists = res.get("result") or []
        for lst in existing_lists:
            if lst.get("name") == name:
                list_id = lst.get("id")
                items_res = self._api_call(f"lists/{list_id}/items")
                existing_items = [it.get("value") for it in (items_res.get("result") or [])]
                to_add = [d for d in unique_domains if d not in existing_items]
                to_remove = [d for d in existing_items if d not in unique_domains]
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

        items = [{"value": d} for d in unique_domains]
        payload = {
            "name": name,
            "description": f"Managed domains for {name}",
            "type": "DOMAIN",
            "items": items,
        }
        res = self._api_call("lists", method="POST", data=payload)
        list_id = (res.get("result") or {}).get("id")
        print(f"  [+] Создан список '{name}' ({len(unique_domains)} доменов)")
        return list_id

    def get_or_create_ipv6_block_rule(self, name: str, list_ids: list, enabled: bool = True):
        res = self._api_call("rules")
        existing_rules = res.get("result") or []

        if not list_ids:
            for rule in existing_rules:
                if rule.get("name") == name:
                    rule_id = rule.get("id")
                    payload = {
                        "name": name,
                        "description": rule.get("description", "Block AAAA (IPv6) queries"),
                        "enabled": False,
                        "action": "block",
                        "precedence": rule.get("precedence", 1),
                        "traffic": rule.get("traffic"),
                        "rule_settings": {"block_page_enabled": False},
                        "filters": ["dns"],
                    }
                    self._api_call(f"rules/{rule_id}", method="PUT", data=payload)
                    print(f"  [✓] Отключено правило '{name}' (нет активных групп)")
                    return rule_id
            print(f"  [-] Пропущено правило '{name}' (нет активных групп)")
            return None

        used_precedences = {
            r.get("precedence")
            for r in existing_rules
            if r.get("name") != name and r.get("precedence") is not None
        }
        precedence = 1
        while precedence in used_precedences:
            precedence += 1

        domains_expr = " or ".join([f"any(dns.domains[*] in ${lid})" for lid in list_ids])
        traffic_str = f'({domains_expr}) and dns.query_rtype == "AAAA"'

        payload = {
            "name": name,
            "description": "Block AAAA (IPv6) queries for active overridden domains to force IPv4 SNI proxy",
            "enabled": enabled,
            "action": "block",
            "precedence": precedence,
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
                print(f"  [✓] Обновлено правило '{name}' (precedence={precedence}, списков={len(list_ids)}, enabled={enabled})")
                return rule_id

        res = self._api_call("rules", method="POST", data=payload)
        rule_id = (res.get("result") or {}).get("id")
        print(f"  [+] Создано правило '{name}' (precedence={precedence}, списков={len(list_ids)}, enabled={enabled})")
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

        self.maybe_prompt_cleanup()
        enabled_states = select_enabled_groups(DOMAIN_GROUPS)

        print("\n[2/4] Создание и синхронизация списков доменов...")
        list_ids = []
        for grp in DOMAIN_GROUPS:
            lid = self.get_or_create_list(grp["list_name"], grp["domains"])
            list_ids.append(lid)

        print("\n[3/4] Настройка правил перенаправления (DNS Override + защита от IPv6)...")
        active_list_ids = [lid for lid, on in zip(list_ids, enabled_states) if on]
        self.get_or_create_ipv6_block_rule(
            "Force IPv4 for Overridden Services",
            active_list_ids,
            enabled=bool(active_list_ids),
        )
        for grp, lid, on in zip(DOMAIN_GROUPS, list_ids, enabled_states):
            self.get_or_create_rule(grp["rule_name"], lid, grp["override_ips"], enabled=on)

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
    print("1. Account ID (иконка профиля в правом верхнем углу -> Copy account ID)")
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
