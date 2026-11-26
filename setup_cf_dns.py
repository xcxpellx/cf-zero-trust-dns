#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare Zero Trust Gateway DNS Auto-Setup Tool
Автоматическая настройка персонального шифрованного DNS (DoH/DoT)
с разделёнными группами DNS Override для ИИ-сервисов и геоблокированных ресурсов.
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


# 1. Claude (Anthropic)
CLAUDE_DOMAINS = [
    "claude.ai",
    "claude.com",
    "clau.de",
    "anthropic.com",
    "claudeusercontent.com",
    "claudemcpclient.com",
    "claudemcpcontent.com",
]

# 2. Grok / xAI и Sora
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
    "sora.com",
]

# 3. OpenAI (ChatGPT, API, CDN статики и ассетов)
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

# 4. Google Gemini, AI Studio, NotebookLM и Google Labs
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
    "opal.google",
    "opal.withgoogle.com",
    "labs.google.com",
    "labs.google",
    "aitestkitchen.withgoogle.com",
    "stitch.withgoogle.com",
    "flow.google.com",
    "flow.google",
    "ai.google.dev",
    "generativeai.google",
]

# 5. Прочие ИИ-сервисы и AI-IDE (Cursor, Windsurf, Perplexity, Midjourney, OpenRouter и др.)
OTHER_AI_DOMAINS = [
    "perplexity.ai",
    "copilot.microsoft.com",
    "v0.dev",
    "cursor.com",
    "cursor.sh",
    "cursorapi.com",
    "cursor-cdn.com",
    "cursorvm.com",
    "windsurf.com",
    "codeium.com",
    "codeiumdata.com",
    "trae.ai",
    "augmentcode.com",
    "midjourney.com",
    "civitai.com",
    "designer.microsoft.com",
    "elevenlabs.io",
    "elevenmusic.io",
    "elevenreader.io",
    "openrouter.ai",
    "groq.com",
    "together.ai",
    "fireworks.ai",
    "replicate.com",
    "cohere.com",
    "mistral.ai",
    "cerebras.ai",
    "manus.im",
    "manuscdn.com",
    "genspark.ai",
    "recraft.ai",
    "kaleido.ai",
    "remove.bg",
    "unscreen.com",
    "pi.ai",
    "meta.ai",
]

# 6. Геоблокированные и зарубежные сервисы (Strava, Canva, DeepL, Notion, JetBrains, Figma/Miro/Trello и др.)
GEO_DOMAINS = [
    "strava.com",
    "canva.com",
    "canva-apps.com",
    "canva.dev",
    "deepl.com",
    "deepl.app",
    "linguee.com",
    "notion.so",
    "notion.site",
    "notion.com",
    "notion.new",
    "notion-static.com",
    "ntc.party",
    "jetbrains.com",
    "jetbrains.ai",
    "jetbrains.space",
    "jetbrains.team",
    "myjetbrains.com",
    "youtrack.cloud",
    "qodana.cloud",
    "datalore.jetbrains.com",
    "miro.com",
    "linear.app",
    "clickup.com",
    "atlassian.com",
    "slack.com",
    "slack-edge.com",
    "slack-files.com",
    "slack-imgs.com",
    "slack-core.com",
    "slackb.com",
    "framer.com",
    "framer.app",
    "framercanvas.com",
    "framercdn.com",
    "framerstatic.com",
    "framerusercontent.com",
    "wix.com",
    "editorx.com",
    "weebly.com",
    "grammarly.com",
    "coursera.com",
    "patreon.com",
    "patreonusercontent.com",
    "buymeacoffee.com",
    "medium.com",
    "scribd.com",
    "scribdassets.com",
    "slideshare.net",
    "imgur.com",
    "giphy.com",
    "unsplash.com",
    "pexels.com",
    "pixabay.com",
    "behance.net",
    "adobe.com",
    "adobe.io",
    "adobe.net",
    "autodesk.com",
    "autodesk.net",
    "autodesk360.com",
    "autocad.com",
    "sketchup.com",
    "trimble.com",
    "onshape.com",
    "mongodb.com",
    "mongodb.net",
    "elastic.co",
    "grafana.com",
    "terraform.io",
    "hashicorp.com",
    "docker.io",
    "sentry.io",
    "sentry.dev",
    "ngrok.com",
    "ngrok-agent.com",
    "tailscale.com",
    "parsec.app",
    "teamviewer.com",
    "anydesk.com",
    "malwarebytes.com",
    "mbamupdates.com",
    "avast.com",
    "avcdn.net",
    "bitdefender.com",
    "norton.com",
    "dell.com",
    "dellcdn.com",
    "intel.com",
    "amd.com",
    "nvidia.com",
    "cisco.com",
    "broadcom.com",
    "vmware.com",
    "oracle.com",
    "oraclecloud.com",
    "sap.com",
    "salesforce.com",
    "force.com",
    "intel.io",
    "4pda.to",
    "4pda.ws",
    "habr.com",
    "tuta.com",
    "tutanota.com",
    "proton.me",
    "protonmail.com",
    "wise.com",
    "transferwise.com",
    "revolut.com",
    "tidal.com",
    "deezer.com",
    "qobuz.com",
    "last.fm",
    "audioscrobbler.com",
    "crunchyroll.com",
    "netflix.com",
    "nflxvideo.net",
    "nflximg.net",
    "nflxext.com",
    "nflxso.net",
    "themoviedb.org",
    "tmdb.org",
    "chess.com",
    "supercell.com",
    "brawlstarsgame.com",
    "clashofclans.com",
    "clashroyaleapp.com",
    "xbox.com",
    "xboxlive.com",
    "epicgames.com",
    "ubisoft.com",
    "battle.net",
    "geforcenow.com",
    "boosteroid.com",
    "nike.com",
    "adidas.com",
    "ikea.com",
    "iherb.com",
    "etsy.com",
    "ebay.com",
    "amazon.com",
    "bestbuy.com",
    "walmart.com",
    "dyson.com",
    "lego.com",
]

# 7. Spotify (опциональный отдельный профиль, по умолчанию выключен)
SPOTIFY_DOMAINS = [
    "spotify.com",
    "scdn.co",
    "spotifycdn.com",
    "spotifycdn.net",
    "spotify.design",
    "spotify.link",
    "spotify.dev",
]

# 8. SoundCloud (опциональный CloudFront-маршрут, по умолчанию выключен)
SOUNDCLOUD_DOMAINS = [
    "soundcloud.com",
    "sndcdn.com",
]

# Проверенные зарубежные IP-релеи (SNI-прокси)
CLAUDE_OVERRIDE_IPS = ["31.58.216.201"]
GROK_OVERRIDE_IPS = ["31.58.216.201"]
OPENAI_OVERRIDE_IPS = ["31.58.216.201"]
GEMINI_OVERRIDE_IPS = ["109.120.187.249"]
OTHER_AI_OVERRIDE_IPS = ["31.58.216.201"]
GEO_OVERRIDE_IPS = ["31.58.216.201"]
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
        # Проверяем сразу реальный эндпоинт Gateway — так валидируются
        # и токен (включая Account Tokens), и Account ID, и активация Zero Trust.
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
        # Убираем дубликаты с сохранением порядка
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
            "description": "Block AAAA (IPv6) queries for overridden domains to force IPv4 SNI proxy",
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
                print(f"  [✓] Обновлено правило '{name}' (precedence={precedence}, enabled={enabled})")
                return rule_id

        res = self._api_call("rules", method="POST", data=payload)
        rule_id = (res.get("result") or {}).get("id")
        print(f"  [+] Создано правило '{name}' (precedence={precedence}, enabled={enabled})")
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

        print("\n[2/4] Создание разделённых списков доменов...")
        claude_list_id = self.get_or_create_list("Claude_Domains", CLAUDE_DOMAINS)
        grok_list_id = self.get_or_create_list("Grok_xAI_Domains", GROK_XAI_DOMAINS)
        openai_list_id = self.get_or_create_list("OpenAI_Domains", OPENAI_DOMAINS)
        gemini_list_id = self.get_or_create_list("Gemini_Domains", GEMINI_DOMAINS)
        other_ai_list_id = self.get_or_create_list("Other_AI_Domains", OTHER_AI_DOMAINS)
        geo_list_id = self.get_or_create_list("Geo_Domains", GEO_DOMAINS)
        spotify_list_id = self.get_or_create_list("Spotify_Domains", SPOTIFY_DOMAINS)
        soundcloud_list_id = self.get_or_create_list("SoundCloud_Domains", SOUNDCLOUD_DOMAINS)

        print("\n[3/4] Настройка правил перенаправления (DNS Override + защита от IPv6)...")
        all_list_ids = [
            claude_list_id,
            grok_list_id,
            openai_list_id,
            gemini_list_id,
            other_ai_list_id,
            geo_list_id,
            spotify_list_id,
            soundcloud_list_id,
        ]
        self.get_or_create_ipv6_block_rule(
            "Force IPv4 for Overridden Services",
            all_list_ids,
            enabled=True,
        )
        self.get_or_create_rule("Claude AI Override", claude_list_id, CLAUDE_OVERRIDE_IPS, enabled=True)
        self.get_or_create_rule("Grok & xAI Override", grok_list_id, GROK_OVERRIDE_IPS, enabled=True)
        self.get_or_create_rule("OpenAI Backend Override", openai_list_id, OPENAI_OVERRIDE_IPS, enabled=True)
        self.get_or_create_rule("Google Gemini Override", gemini_list_id, GEMINI_OVERRIDE_IPS, enabled=True)
        self.get_or_create_rule("Other AI Services Override", other_ai_list_id, OTHER_AI_OVERRIDE_IPS, enabled=True)
        self.get_or_create_rule("Geo Blocked Services Override", geo_list_id, GEO_OVERRIDE_IPS, enabled=True)
        self.get_or_create_rule("Spotify Override", spotify_list_id, SPOTIFY_OVERRIDE_IPS, enabled=False)
        self.get_or_create_rule("SoundCloud Override", soundcloud_list_id, SOUNDCLOUD_OVERRIDE_IPS, enabled=False)

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