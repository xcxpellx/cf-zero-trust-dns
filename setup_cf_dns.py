#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare Zero Trust Gateway DNS Auto-Setup Tool
Автоматическая настройка персонального шифрованного DNS (DoH/DoT)
с сохранением профиля, редактированием доменов/релеев, диагностикой и автообновлением.
"""

import ast
import copy
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_VERSION = "1.7.0"
GITHUB_REPO = "xcxpellx/cf-zero-trust-dns"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RAW_SCRIPT_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/setup_cf_dns.py"


def init_console():
    """Включает UTF-8 и поддержку ANSI-цветов в консоли Windows."""
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            for handle_id in (-11, -12):
                handle = kernel32.GetStdHandle(handle_id)
                if handle and handle != -1:
                    mode = ctypes.c_uint32()
                    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def supports_color() -> bool:
    return bool(sys.stdout.isatty() and not os.environ.get("NO_COLOR"))


def style_text(text: str, ansi_code: str) -> str:
    if not supports_color():
        return text
    return f"\033[{ansi_code}m{text}\033[0m"


def green(text: str) -> str:
    return style_text(text, "92")


def red(text: str) -> str:
    return style_text(text, "91")


def yellow(text: str) -> str:
    return style_text(text, "93")


def safe_input(prompt=""):
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""


def clear_screen():
    """Очищает консоль при работе в интерактивном терминале (.exe / CLI)."""
    if sys.stdout.isatty():
        os.system("cls" if os.name == "nt" else "clear")


def pause(prompt: str = "\nНажмите Enter, чтобы продолжить..."):
    """Ждёт подтверждения пользователя перед сменой экрана в интерактивном режиме."""
    if sys.stdin.isatty() and sys.stdout.isatty():
        safe_input(prompt)


def mask_secret(value: str, head: int = 4, tail: int = 4) -> str:
    val = (value or "").strip()
    if len(val) <= head + tail:
        return "*" * len(val)
    return f"{val[:head]}...{val[-tail:]}"


def is_valid_ipv4(ip: str) -> bool:
    parts = (ip or "").strip().split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit():
            return False
        num = int(part)
        if num < 0 or num > 255 or (len(part) > 1 and part.startswith("0")):
            return False
    return True


def normalize_domain(raw: str) -> str:
    val = (raw or "").strip().lower()
    val = re.sub(r"^https?://", "", val)
    val = val.split("/")[0].split(":")[0].strip(".")
    if val.startswith("*."):
        val = val[2:]
    if not re.match(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$", val):
        return ""
    return val


def parse_domain_batch(raw_text: str) -> tuple:
    """Разбирает список доменов (через пробел, запятую, ';' или перевод строки)."""
    valid = []
    invalid = []
    seen = set()
    for token in re.split(r"[\s,;]+", (raw_text or "").strip()):
        if not token:
            continue
        dom = normalize_domain(token)
        if dom:
            if dom not in seen:
                seen.add(dom)
                valid.append(dom)
        else:
            invalid.append(token)
    return valid, invalid


_CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def make_safe_slug(name: str) -> str:
    """Преобразует произвольное имя группы в безопасный ASCII-идентификатор."""
    out = []
    for ch in (name or "").strip().lower():
        if ch in _CYR_TO_LAT:
            out.append(_CYR_TO_LAT[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    slug = re.sub(r"_+", "_", "".join(out)).strip("_")
    return slug or f"group_{int(time.time())}"


def parse_version(tag: str) -> tuple:
    nums = [int(x) for x in re.findall(r"\d+", (tag or ""))]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


# ==============================================================================
# ПРОВЕРЕННЫЕ СПИСКИ ДОМЕНОВ (разделены по группам и совместимым релеям)
# ==============================================================================

CLAUDE_DOMAINS = [
    "claude.ai",
    "claude.com",
    "anthropic.com",
    "claudeusercontent.com",
]

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

SPOTIFY_DOMAINS = [
    "spotify.com",
    "scdn.co",
    "spotifycdn.com",
    "spotifycdn.net",
    "spotify.design",
    "spotify.link",
    "spotify.dev",
]

SOUNDCLOUD_DOMAINS = [
    "soundcloud.com",
    "sndcdn.com",
]

DEFAULT_DOMAIN_GROUPS = [
    {
        "list_name": "Claude_Domains",
        "rule_name": "Claude AI Override",
        "label": "Claude (Anthropic)",
        "domains": CLAUDE_DOMAINS,
        "override_ips": ["31.58.216.201"],
        "default_enabled": True,
        "probe_domain": "claude.com",
    },
    {
        "list_name": "Grok_xAI_Domains",
        "rule_name": "Grok & xAI Override",
        "label": "Grok / xAI",
        "domains": GROK_XAI_DOMAINS,
        "override_ips": ["31.58.216.201"],
        "default_enabled": True,
        "probe_domain": "grok.com",
    },
    {
        "list_name": "OpenAI_Domains",
        "rule_name": "OpenAI Backend Override",
        "label": "OpenAI (ChatGPT & API)",
        "domains": OPENAI_DOMAINS,
        "override_ips": ["31.58.216.201"],
        "default_enabled": True,
        "probe_domain": "chatgpt.com",
    },
    {
        "list_name": "Gemini_Domains",
        "rule_name": "Google Gemini Override",
        "label": "Google Gemini, AI Studio & NotebookLM",
        "domains": GEMINI_DOMAINS,
        "override_ips": ["109.120.187.249"],
        "default_enabled": True,
        "probe_domain": "gemini.google.com",
    },
    {
        "list_name": "Other_AI_Domains",
        "rule_name": "Other AI Services Override",
        "label": "AI-IDE и ассистенты (Cursor, Windsurf, Perplexity, ElevenLabs...)",
        "domains": OTHER_AI_DOMAINS,
        "override_ips": ["31.58.216.201"],
        "default_enabled": True,
        "probe_domain": "cursor.com",
    },
    {
        "list_name": "AI_Media_Dev_Domains",
        "rule_name": "AI Media & Dev Override",
        "label": "Sora, Midjourney, Civitai, Canva, Figma, Notion, JetBrains, Docker",
        "domains": AI_MEDIA_DEV_DOMAINS,
        "override_ips": ["109.120.187.249"],
        "default_enabled": True,
        "probe_domain": "civitai.com",
    },
    {
        "list_name": "Geo_Domains",
        "rule_name": "Geo Blocked Services Override",
        "label": "Зарубежные сервисы (Strava, DeepL, Miro, Linear, Wise...)",
        "domains": GEO_DOMAINS,
        "override_ips": ["31.58.216.201"],
        "default_enabled": True,
        "probe_domain": "strava.com",
    },
    {
        "list_name": "Spotify_Domains",
        "rule_name": "Spotify Override",
        "label": "Spotify (веб-плеер и обложки)",
        "domains": SPOTIFY_DOMAINS,
        "override_ips": ["109.120.187.249"],
        "default_enabled": False,
        "probe_domain": "open.spotify.com",
    },
    {
        "list_name": "SoundCloud_Domains",
        "rule_name": "SoundCloud Override",
        "label": "SoundCloud (быстрый CloudFront IP; для SNI-DPI нужен d2k/z2k или аналог)",
        "domains": SOUNDCLOUD_DOMAINS,
        "override_ips": ["108.156.22.80"],
        "default_enabled": False,
        "probe_domain": "soundcloud.com",
    },
]

# Совместимость со старым именем переменной для внешних тестов/импортов
DOMAIN_GROUPS = DEFAULT_DOMAIN_GROUPS

# Проверенные альтернативные Relay IP для выбора в меню редактирования
RELAY_PRESETS = [
    {
        "ip": "31.58.216.201",
        "label": "Основной быстрый SNI-релей (Claude, Grok, ChatGPT, Gemini, Cursor, Geo, Spotify)",
        "kind": "sni",
    },
    {
        "ip": "109.120.187.249",
        "label": "SNI-релей #2 (Gemini, Civitai, AI Media & Dev, Claude, ChatGPT, Spotify)",
        "kind": "sni",
    },
    {
        "ip": "91.108.243.78",
        "label": "Универсальный SNI-релей Bezmezhau (все AI, Civitai, Geo, Spotify)",
        "kind": "sni",
    },
    {
        "ip": "217.60.179.6",
        "label": "Резервный SNI-релей malw.link (Claude, Grok, ChatGPT, Gemini, Geo, Spotify)",
        "kind": "sni",
    },
    {
        "ip": "108.156.22.80",
        "label": "Amazon CloudFront (для SoundCloud, основной)",
        "kind": "cloudfront",
    },
    {
        "ip": "52.84.150.39",
        "label": "Amazon CloudFront (для SoundCloud, резервный)",
        "kind": "cloudfront",
    },
]


# ==============================================================================
# ЛОКАЛЬНАЯ КОНФИГУРАЦИЯ (ПРОФИЛЬ, КАСТОМНЫЕ ДОМЕНЫ, ГРУППЫ И РЕЛЕИ)
# ==============================================================================

def get_default_config_path() -> Path:
    return Path.home() / ".cloudflare_dns_setup" / "config.json"


class AppConfig:
    """Управление сохранённым профилем (Account ID/Token) и кастомными правилами."""

    def __init__(self, path: Path = None):
        self.path = Path(path) if path else get_default_config_path()
        self.account_id = ""
        self.api_token = ""
        self.enabled_overrides = {}   # list_name -> bool
        self.relay_overrides = {}     # list_name -> list[str]
        self.domain_overrides = {}    # list_name -> list[str]
        self.custom_groups = []       # list[dict]
        self.load()

    def load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.account_id = (data.get("account_id") or "").strip()
            self.api_token = (data.get("api_token") or "").strip()
            self.enabled_overrides = dict(data.get("enabled_overrides") or {})
            self.relay_overrides = dict(data.get("relay_overrides") or {})
            self.domain_overrides = dict(data.get("domain_overrides") or {})
            raw_custom = data.get("custom_groups") or []
            self.custom_groups = [g for g in raw_custom if isinstance(g, dict) and g.get("list_name")]
        except Exception as e:
            print(f"[!] Не удалось прочитать конфиг {self.path}: {e}")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "account_id": self.account_id,
            "api_token": self.api_token,
            "enabled_overrides": self.enabled_overrides,
            "relay_overrides": self.relay_overrides,
            "domain_overrides": self.domain_overrides,
            "custom_groups": self.custom_groups,
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        if os.name != "nt":
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def clear_credentials(self):
        self.account_id = ""
        self.api_token = ""
        self.save()

    def build_groups(self) -> list:
        groups = copy.deepcopy(DEFAULT_DOMAIN_GROUPS)
        for cg in self.custom_groups:
            item = copy.deepcopy(cg)
            item.setdefault("rule_name", f"{item['list_name']} Override")
            item.setdefault("label", item["list_name"])
            item.setdefault("domains", [])
            item.setdefault("override_ips", [RELAY_PRESETS[0]["ip"]])
            item.setdefault("default_enabled", True)
            if not item.get("probe_domain") and item["domains"]:
                item["probe_domain"] = item["domains"][0]
            item["custom"] = True
            groups.append(item)

        for grp in groups:
            lname = grp["list_name"]
            if lname in self.enabled_overrides:
                grp["default_enabled"] = bool(self.enabled_overrides[lname])
            if lname in self.relay_overrides and self.relay_overrides[lname]:
                grp["override_ips"] = list(self.relay_overrides[lname])
            if lname in self.domain_overrides:
                grp["domains"] = list(self.domain_overrides[lname])
        return groups


# ==============================================================================
# ЖИВАЯ ДИАГНОСТИКА ПРОКСИ И DOH
# ==============================================================================

def extract_latency_suffix(msg: str) -> str:
    m = re.search(r"(\d+\s*мс)", msg or "")
    return f" ({m.group(1)})" if m else ""


def probe_tls_endpoint(ip: str, host: str, timeout: float = 3.0) -> tuple:
    """Проверяет TCP + TLS + HEAD-ответ для пары (IP, домен). Возвращает (ok, info_str)."""
    ctx = ssl.create_default_context()
    sock = socket.socket()
    sock.settimeout(timeout)
    t0 = time.time()
    try:
        sock.connect((ip, 443))
        with ctx.wrap_socket(sock, server_hostname=host) as ss:
            req = (
                f"HEAD / HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36\r\n"
                f"Connection: close\r\n\r\n"
            ).encode("ascii")
            ss.sendall(req)
            first = ss.recv(128).split(b"\r\n")[0].decode("latin1", errors="ignore").strip()
        ms = int((time.time() - t0) * 1000)
        return True, f"{first or 'OK'} ({ms} мс)"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:45]}"
    finally:
        try:
            sock.close()
        except OSError:
            pass


def query_doh_ip(doh_url: str, domain: str, timeout: float = 4.0) -> list:
    req = urllib.request.Request(
        f"{doh_url}?name={domain}&type=A",
        headers={"Accept": "application/dns-json", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [a.get("data") for a in (data.get("Answer") or []) if a.get("data")]


def run_live_diagnostics(groups: list, doh_url: str = ""):
    print("\n[*] Живая проверка текущих Relay IP и сервисов...")
    for grp in groups:
        host = grp.get("probe_domain") or (grp["domains"][0] if grp["domains"] else "")
        ips = grp["override_ips"]
        state = "ВКЛ " if grp["default_enabled"] else "ВЫКЛ"
        if not host or not ips:
            continue
        for ip in ips:
            ok, msg = probe_tls_endpoint(ip, host)
            if ok:
                raw_status = f"✓ Отвечает{extract_latency_suffix(msg)}"
                status_text = green(f"{raw_status:<20}")
            else:
                status_text = red(f"{'✗ Не отвечает':<20}")
            doh_note = ""
            if doh_url:
                try:
                    ans = query_doh_ip(doh_url, host)
                    doh_note = f" | DoH: {green('✓')} {', '.join(ans[:2])}" if ans else f" | DoH: {red('✗')} пусто"
                except Exception:
                    doh_note = f" | DoH: {red('✗')} ошибка"
            print(f"  {status_text} | [{state}] {grp['list_name']:22} | {ip:15} | {host}{doh_note}")


# ==============================================================================
# ОБНОВЛЕНИЯ (GITHUB RELEASES + БЕЗОПАСНОЕ ПОДТЯГИВАНИЕ СПИСКОВ ЧЕРЕЗ AST)
# ==============================================================================

def fetch_latest_release_info(timeout: float = 4.0) -> dict:
    req = urllib.request.Request(
        RELEASES_API_URL,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"CloudflareDNS-Setup/{APP_VERSION}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_remote_definitions(script_source: str) -> dict:
    """Безопасно извлекает *_DOMAINS и DEFAULT_DOMAIN_GROUPS из исходника через AST без exec()."""
    tree = ast.parse(script_source)
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name.endswith("_DOMAINS"):
                val = ast.literal_eval(node.value)
                if isinstance(val, list) and all(isinstance(x, str) for x in val):
                    constants[name] = val
            elif name in ("DEFAULT_DOMAIN_GROUPS", "DOMAIN_GROUPS"):
                # Разрешаем ссылки на ранее разобранные *_DOMAINS внутри словарей
                groups_out = []
                if isinstance(node.value, ast.List):
                    for elt in node.value.elts:
                        if not isinstance(elt, ast.Dict):
                            continue
                        item = {}
                        for k_node, v_node in zip(elt.keys, elt.values):
                            key = ast.literal_eval(k_node)
                            if isinstance(v_node, ast.Name) and v_node.id in constants:
                                item[key] = list(constants[v_node.id])
                            else:
                                item[key] = ast.literal_eval(v_node)
                        if "list_name" in item and "override_ips" in item and "domains" in item:
                            groups_out.append(item)
                if groups_out:
                    return {g["list_name"]: g for g in groups_out}
    raise ValueError("Не удалось распознать списки доменов в удалённом файле.")


def sync_definitions_from_github(cfg: AppConfig) -> int:
    req = urllib.request.Request(RAW_SCRIPT_URL, headers={"User-Agent": f"CloudflareDNS-Setup/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        source = resp.read().decode("utf-8")
    parsed = parse_remote_definitions(source)
    updated = 0
    for lname, grp in parsed.items():
        cfg.domain_overrides[lname] = list(grp["domains"])
        cfg.relay_overrides[lname] = list(grp["override_ips"])
        updated += 1
    cfg.save()
    return updated


def download_file_bytes(url: str, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": f"CloudflareDNS-Setup/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def apply_self_update(release_info: dict) -> bool:
    """Обновляет текущий .py или Windows .exe из последнего релиза GitHub."""
    is_frozen = bool(getattr(sys, "frozen", False))
    if not is_frozen:
        source = download_file_bytes(RAW_SCRIPT_URL, timeout=15).decode("utf-8")
        ast.parse(source)
        target_py = Path(__file__).resolve()
        tmp_py = target_py.with_suffix(".py.tmp")
        tmp_py.write_text(source, encoding="utf-8", newline="\n")
        os.replace(tmp_py, target_py)
        print(f"\n[✓] Скрипт {target_py.name} обновлён! Перезапускаю...")
        os.execv(sys.executable, [sys.executable, str(target_py)] + sys.argv[1:])
        return True

    if os.name != "nt":
        print("\n[!] Автообновление бинарника поддерживается только для Windows .exe (или запускайте через Python).")
        return False

    assets = release_info.get("assets") or []
    exe_asset = next((a for a in assets if (a.get("name") or "").lower().endswith(".exe")), None)
    if not exe_asset:
        print("\n[!] В этом релизе ещё не прикреплён .exe файл (возможно, GitHub Actions ещё собирает его).")
        return False

    download_url = exe_asset.get("browser_download_url")
    print(f"\n[*] Скачиваю {exe_asset.get('name')}...")
    exe_bytes = download_file_bytes(download_url, timeout=60)
    if len(exe_bytes) < 100_000 or not exe_bytes.startswith(b"MZ"):
        raise RuntimeError("Скачанный файл не похож на корректный Windows .exe.")

    current_exe = Path(sys.executable).resolve()
    new_exe = current_exe.with_name(f"{current_exe.stem}.new.exe")
    new_exe.write_bytes(exe_bytes)

    bat_path = Path(tempfile.gettempdir()) / f"cf_dns_updater_{os.getpid()}.cmd"
    bat_content = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "echo Обновляю CloudflareDNS_Setup.exe...\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        ":retry\r\n"
        f'move /y "{new_exe}" "{current_exe}" >nul 2>&1\r\n'
        "if errorlevel 1 (\r\n"
        "  timeout /t 1 /nobreak >nul\r\n"
        "  goto retry\r\n"
        ")\r\n"
        f'start "" "{current_exe}"\r\n'
        'del "%~f0"\r\n'
    )
    bat_path.write_text(bat_content, encoding="utf-8")
    subprocess.Popen(["cmd", "/c", str(bat_path)], creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    print("[✓] Обновление скачано. Закрываю старую версию и запускаю новую...")
    sys.exit(0)


def check_updates_on_startup(cfg: AppConfig):
    try:
        rel = fetch_latest_release_info(timeout=3.5)
    except Exception:
        return

    tag = rel.get("tag_name") or ""
    if parse_version(tag) <= parse_version(APP_VERSION):
        return

    print(f"\n[!] Доступна новая версия {tag} (у вас {APP_VERSION})!")
    body = (rel.get("body") or "").strip()
    if body:
        preview = "\n".join("    " + line for line in body.splitlines()[:6])
        print(preview)
    ans = safe_input("Обновить сейчас? [y/N, или 'l' — обновить только списки/IP без перекачки .exe]: ").strip().lower()
    if ans in ("y", "yes", "д", "да"):
        try:
            apply_self_update(rel)
        except Exception as e:
            print(f"[!] Не удалось обновиться автоматически: {e}")
    elif ans in ("l", "lists", "с"):
        try:
            count = sync_definitions_from_github(cfg)
            print(f"[✓] Обновлены списки и Relay IP для {count} групп из GitHub!")
        except Exception as e:
            print(f"[!] Ошибка синхронизации списков: {e}")


# ==============================================================================
# КЛИЕНТ CLOUDFLARE ZERO TRUST API
# ==============================================================================

class CloudflareGatewaySetup:
    """Клиент настройки списков и DNS-правил Cloudflare Zero Trust Gateway."""

    def __init__(self, account_id: str, api_token: str, timeout: float = 15.0):
        self.account_id = account_id.strip()
        self.api_token = api_token.strip()
        self.timeout = timeout
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
            with urllib.request.urlopen(req, timeout=getattr(self, "timeout", 15.0)) as resp:
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
                    "  1) Активирован ли тариф Zero Trust Free на one.dash.cloudflare.com (нужна привязка иностранной карты);\n"
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

    def get_existing_doh_url(self) -> str:
        res = self._api_call("locations")
        existing = res.get("result") or []
        if existing and existing[0].get("doh_subdomain"):
            return f"https://{existing[0]['doh_subdomain']}.cloudflare-gateway.com/dns-query"
        return ""

    def print_status(self):
        rules = sorted(self._api_call("rules").get("result") or [], key=lambda r: r.get("precedence") or 0)
        lists = self._api_call("lists").get("result") or []
        locs = self._api_call("locations").get("result") or []

        total_items = sum(int(l.get("count") or 0) for l in lists if l.get("type") == "DOMAIN")
        print(f"\n=== Списки доменов (занято {total_items} из 1000 записей Free-плана) ===")
        for lst in lists:
            if lst.get("type") == "DOMAIN":
                print(f"  • {lst.get('name'):24} : {lst.get('count', 0)} дом.")

        print(f"\n=== Правила Gateway ({len(rules)} шт.) ===")
        for r in rules:
            ips = (r.get("rule_settings") or {}).get("override_ips") or []
            ip_str = ", ".join(ips) if ips else r.get("action")
            state = "ВКЛ " if r.get("enabled") else "ВЫКЛ"
            print(f"  [{r.get('precedence', '-'):>4}] [{state}] {r.get('name'):34} -> {ip_str}")

        if locs:
            sub = locs[0].get("doh_subdomain")
            print(f"\n=== Точка DNS '{locs[0].get('name')}' ===")
            print(f"  DoH: https://{sub}.cloudflare-gateway.com/dns-query")
            print(f"  DoT: {sub}.cloudflare-gateway.com")

    def run(self, groups: list = None, interactive_groups: bool = False):
        groups = groups if groups is not None else DEFAULT_DOMAIN_GROUPS
        print("\n[1/4] Проверка подключения к Cloudflare Zero Trust...")
        self.verify_token()
        print("      Авторизация успешна!")

        self.maybe_prompt_cleanup()
        if interactive_groups:
            enabled_states = select_enabled_groups(groups)
        else:
            enabled_states = [bool(g.get("default_enabled", True)) for g in groups]

        print("\n[2/4] Создание и синхронизация списков доменов...")
        list_ids = []
        for grp in groups:
            lid = self.get_or_create_list(grp["list_name"], grp["domains"])
            list_ids.append(lid)

        print("\n[3/4] Настройка правил перенаправления (DNS Override + защита от IPv6)...")
        active_list_ids = [lid for lid, on in zip(list_ids, enabled_states) if on]
        self.get_or_create_ipv6_block_rule(
            "Force IPv4 for Overridden Services",
            active_list_ids,
            enabled=bool(active_list_ids),
        )
        for grp, lid, on in zip(groups, list_ids, enabled_states):
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


# ==============================================================================
# ИНТЕРАКТИВНЫЕ МЕНЮ
# ==============================================================================

def select_enabled_groups(groups: list) -> list:
    """Интерактивный выбор активных групп доменов."""
    states = [bool(g.get("default_enabled", True)) for g in groups]

    def print_menu(notice: str = ""):
        clear_screen()
        print("=" * 68)
        print("  ВЫБОР АКТИВНЫХ ГРУПП ПРАВИЛ")
        print("=" * 68)
        print("Невыбранные группы создаются в Cloudflare с выключенным тумблером:\n")
        for idx, (grp, on) in enumerate(zip(groups, states), start=1):
            mark = "ВКЛ " if on else "ВЫКЛ"
            print(f"    {idx}. [{mark}] {grp['label']} ({len(grp['domains'])} дом.)")
        print("\n    Enter — подтвердить | Номера (напр. 7 8 9) — переключить | 'all' / 'none'")
        if notice:
            print(f"\n    {notice}")

    print_menu()

    while True:
        raw = safe_input("Ваш выбор [Enter — подтвердить]: ").strip().lower()
        if not raw or raw in ("ok", "done", "go"):
            break
        if raw == "all":
            states = [True] * len(groups)
            print_menu("[✓] Включены все группы.")
            continue
        if raw == "none":
            states = [False] * len(groups)
            print_menu("[✓] Выключены все группы.")
            continue

        tokens = re.findall(r"\d+", raw)
        if not tokens:
            print_menu("[!] Введите номера через пробел/запятую, 'all', 'none' или нажмите Enter.")
            continue

        changed = False
        bad = []
        for tok in tokens:
            idx = int(tok) - 1
            if 0 <= idx < len(states):
                states[idx] = not states[idx]
                changed = True
            else:
                bad.append(tok)
        msg = f"[!] Номера вне диапазона (1–{len(groups)}): {', '.join(bad)}" if bad else ""
        if changed or bad:
            print_menu(msg)

    return states


def prompt_credentials(cfg: AppConfig, force_new: bool = False) -> tuple:
    """Запрашивает или загружает сохранённые Account ID и API Token."""
    if not force_new and cfg.account_id and cfg.api_token:
        clear_screen()
        print("=" * 68)
        print("  ПРОФИЛЬ CLOUDFLARE")
        print("=" * 68)
        print(f"  Account ID: {mask_secret(cfg.account_id, 6, 4)}")
        print(f"  API Token:  {mask_secret(cfg.api_token, 6, 4)}")
        use_saved = safe_input("\nИспользовать сохранённый профиль? [Enter — да / n — ввести заново]: ").strip().lower()
        if use_saved not in ("n", "no", "н", "нет"):
            return cfg.account_id, cfg.api_token

    clear_screen()
    print("=" * 68)
    print("  ВВОД КЛЮЧЕЙ CLOUDFLARE ZERO TRUST")
    print("=" * 68)
    print("  1. Account ID (профиль в правом верхнем углу -> Copy account ID)")
    print("  2. API Token с правами 'Account -> Zero Trust -> Edit'\n")

    account_id = safe_input("Введите ваш Account ID: ").strip()
    if not account_id:
        print("\n[!] Account ID не может быть пустым.")
        pause()
        return "", ""
    if len(account_id) != 32:
        print("\n[!] Предупреждение: Account ID обычно состоит ровно из 32 символов.")

    api_token = safe_input("Введите ваш API Token: ").strip()
    if not api_token:
        print("\n[!] API Token не может быть пустым.")
        pause()
        return "", ""

    save_ans = safe_input("Запомнить Account ID и API Token локально для будущих запусков? [Y/n]: ").strip().lower()
    if save_ans not in ("n", "no", "н", "нет"):
        cfg.account_id = account_id
        cfg.api_token = api_token
        cfg.save()
        print(f"  [✓] Ключи сохранены локально: {cfg.path}")

    return account_id, api_token


def read_domain_batch_input(title: str = "Введите домен или список доменов") -> tuple:
    """Считывает один домен, список через пробел/запятую либо построчно ('m')."""
    print(f"\n{title} (через запятую или пробел, напр. site1.com, site2.org).")
    print("  Либо введите 'm' для построчного ввода (удобно для вставки столбиком).")
    first = safe_input("Домены: ").strip()
    if not first:
        return [], []
    if first.lower() in ("m", "multi", "м"):
        print("  Вставляйте/вводите домены построчно; пустая строка (Enter) завершит ввод:")
        lines = []
        while True:
            line = safe_input("  > ").strip()
            if not line:
                break
            lines.append(line)
        raw = "\n".join(lines)
    else:
        raw = first
    return parse_domain_batch(raw)


def choose_relay_ip(
    title: str,
    probe_domain: str,
    current_ips: list = None,
    allow_default: str = "",
) -> str:
    """Показывает пресеты Relay IP (с живым тестом) или принимает свой IPv4."""
    current_set = set(current_ips or [])
    is_sc = "soundcloud" in (probe_domain or "").lower() or "sndcdn" in (probe_domain or "").lower()
    ordered = sorted(
        RELAY_PRESETS,
        key=lambda p: 0 if (p["kind"] == ("cloudfront" if is_sc else "sni")) else 1,
    )
    probe_cache = {}

    def render(notice: str = ""):
        clear_screen()
        print("=" * 68)
        print(f"  {title}")
        print("=" * 68)
        if current_ips:
            print(f"  Текущий IP: {', '.join(current_ips)}")
        print(f"  Проверка доступности выполняется для: {probe_domain}\n")
        print("  Предложенные проверенные релеи:")
        for idx, preset in enumerate(ordered, start=1):
            ip = preset["ip"]
            cur_tag = " [текущий]" if ip in current_set else ""
            status_tag = ""
            if ip in probe_cache:
                ok, msg = probe_cache[ip]
                status_tag = f" | {green('✓ Отвечает') + extract_latency_suffix(msg)}" if ok else f" | {red('✗ Не отвечает')}"
            print(f"  {idx}. {ip:15}{cur_tag}{status_tag}")
            print(f"     {preset['label']}")
        print("\n  T. Проверить все предложенные релеи прямо сейчас")
        print("  Либо введите свой IPv4 вручную (напр. IP вашего VPS)")
        if allow_default:
            print(f"  Enter — использовать основной ({allow_default})")
        print("  0. Отмена")
        if notice:
            print(f"\n  {notice}")

    render()
    while True:
        prompt_str = (
            f"\nВыберите [1–{len(ordered)}], T, свой IPv4 или Enter ({allow_default}): "
            if allow_default
            else f"\nВыберите [1–{len(ordered)}], T, свой IPv4 или 0: "
        )
        raw = safe_input(prompt_str).strip()
        low = raw.lower()
        if low == "0":
            return ""
        if not raw:
            if allow_default:
                chosen_ip = allow_default
                break
            return ""
        if low in ("t", "т", "test"):
            print("\n[*] Проверяю предложенные релеи...")
            for preset in ordered:
                ip = preset["ip"]
                probe_cache[ip] = probe_tls_endpoint(ip, probe_domain)
            render("[✓] Проверка завершена.")
            continue
        if raw.isdigit() and 1 <= int(raw) <= len(ordered):
            chosen_ip = ordered[int(raw) - 1]["ip"]
            break
        if is_valid_ipv4(raw):
            chosen_ip = raw
            break
        render("[!] Введите номер из списка, корректный IPv4-адрес, 'T' или '0'.")

    print(f"  [*] Проверяю {chosen_ip} на {probe_domain}...")
    ok, msg = probe_tls_endpoint(chosen_ip, probe_domain)
    if ok:
        print(f"  {green('✓ Отвечает')}{extract_latency_suffix(msg)}")
        return chosen_ip

    print(f"  {red('✗ Не отвечает')} ({msg})")
    confirm = safe_input("  Прокси не ответил. Всё равно сохранить? [y/N]: ").strip().lower()
    return chosen_ip if confirm in ("y", "yes", "д", "да") else ""


def menu_create_custom_group(cfg: AppConfig):
    groups = cfg.build_groups()
    total_before = sum(len(g["domains"]) for g in groups)
    clear_screen()
    print("=" * 68)
    print("  СОЗДАНИЕ СВОЕЙ ГРУППЫ ДОМЕНОВ")
    print("=" * 68)
    print(f"  Занято сейчас: {total_before}/1000 доменов (лимит Free-плана)\n")

    raw_name = safe_input("Название группы (напр. Work или Streaming, Enter — отмена): ").strip()
    if not raw_name:
        return

    slug = make_safe_slug(raw_name)
    existing_names = {g["list_name"] for g in groups}
    base_list_name = f"Custom_{slug}_Domains"
    list_name = base_list_name
    suffix = 2
    while list_name in existing_names:
        list_name = f"Custom_{slug}_{suffix}_Domains"
        suffix += 1

    valid, invalid = read_domain_batch_input("Домены для новой группы")
    if invalid:
        print(f"  [!] Пропущены некорректные значения: {', '.join(invalid[:8])}")
    if not valid:
        print("  [!] Не добавлено ни одного корректного домена. Создание отменено.")
        pause()
        return

    relay_ip = choose_relay_ip(
        f"RELAY IP ДЛЯ ГРУППЫ '{raw_name}'",
        probe_domain=valid[0],
        allow_default=RELAY_PRESETS[0]["ip"],
    )
    if not relay_ip:
        print("  [!] Создание группы отменено.")
        pause()
        return

    new_group = {
        "list_name": list_name,
        "rule_name": f"Custom {slug} Override",
        "label": raw_name,
        "domains": valid,
        "override_ips": [relay_ip],
        "default_enabled": True,
        "probe_domain": valid[0],
        "custom": True,
    }
    cfg.custom_groups.append(new_group)
    cfg.enabled_overrides[list_name] = True
    cfg.relay_overrides[list_name] = [relay_ip]
    cfg.domain_overrides[list_name] = list(valid)
    cfg.save()
    print(f"\n  {green('✓')} Создана группа '{raw_name}' ({list_name}, {len(valid)} дом. -> {relay_ip}).")
    if total_before + len(valid) > 1000:
        print(f"  {yellow('[!] Внимание: превышен лимит 1000 записей бесплатного тарифа!')}")
    print("  Примените изменения через '1. Быстрая настройка'.")
    pause()


def menu_edit_domains(cfg: AppConfig):
    while True:
        groups = cfg.build_groups()
        total_domains = sum(len(g["domains"]) for g in groups)
        clear_screen()
        print("=" * 68)
        print("  РЕДАКТИРОВАНИЕ ДОМЕНОВ И АКТИВНЫХ ГРУПП")
        print("=" * 68)
        print(f"  Групп: {len(groups)} | Доменов всего: {total_domains}/1000 (лимит Free-плана)")
        print("-" * 68)
        print("  1. Включить / выключить группы правил (тумблеры)")
        print("  2. Добавить домены в группу (по одному или списком)")
        print("  3. Удалить домены из группы (по одному или списком)")
        print("  4. Показать домены группы")
        print("  5. Создать свою группу доменов")
        print("  6. Удалить свою группу доменов")
        print("  7. Сбросить изменения доменов и тумблеров к значениям по умолчанию")
        print("  0. Назад в главное меню")

        choice = safe_input("\nВыберите действие: ").strip()
        if choice in ("0", ""):
            break
        if choice == "1":
            states = select_enabled_groups(groups)
            for grp, on in zip(groups, states):
                cfg.enabled_overrides[grp["list_name"]] = on
            cfg.save()
            print("\n  [✓] Выбор групп сохранён! Примените его через '1. Быстрая настройка'.")
            pause()
        elif choice == "5":
            menu_create_custom_group(cfg)
        elif choice == "6":
            if not cfg.custom_groups:
                print("\n  [!] Пользовательских групп пока нет.")
                pause()
                continue
            clear_screen()
            print("=" * 68)
            print("  УДАЛЕНИЕ СВОЕЙ ГРУППЫ ДОМЕНОВ")
            print("=" * 68)
            for idx, cg in enumerate(cfg.custom_groups, start=1):
                print(f"  {idx}. {cg.get('label', cg['list_name'])} [{cg['list_name']}] ({len(cg.get('domains') or [])} дом.)")
            raw_idx = safe_input(f"\nНомер группы для удаления [1–{len(cfg.custom_groups)}], 0 — отмена: ").strip()
            if raw_idx in ("0", ""):
                continue
            if not raw_idx.isdigit() or not (1 <= int(raw_idx) <= len(cfg.custom_groups)):
                print("  [!] Неверный номер.")
                pause()
                continue
            removed = cfg.custom_groups.pop(int(raw_idx) - 1)
            rname = removed["list_name"]
            cfg.enabled_overrides.pop(rname, None)
            cfg.relay_overrides.pop(rname, None)
            cfg.domain_overrides.pop(rname, None)
            cfg.save()
            print(f"  [-] Группа '{rname}' удалена локально.")
            pause()
        elif choice in ("2", "3", "4"):
            clear_screen()
            print("=" * 68)
            print("  ВЫБОР ГРУППЫ ДОМЕНОВ")
            print("=" * 68)
            for idx, grp in enumerate(groups, start=1):
                custom_mark = " [своя]" if grp.get("custom") else ""
                print(f"  {idx}. {grp['list_name']} ({len(grp['domains'])} дом.){custom_mark}")
            raw_idx = safe_input(f"\nНомер группы [1–{len(groups)}]: ").strip()
            if not raw_idx.isdigit() or not (1 <= int(raw_idx) <= len(groups)):
                print("  [!] Неверный номер.")
                pause()
                continue
            grp = groups[int(raw_idx) - 1]
            lname = grp["list_name"]
            doms = list(grp["domains"])

            if choice == "4":
                clear_screen()
                print(f"=== {lname} ({len(doms)} дом.) ===\n")
                print(", ".join(doms) if doms else "(список пуст)")
                pause()
            elif choice == "2":
                valid, invalid = read_domain_batch_input(f"Добавить домены в {lname}")
                added = []
                skipped = []
                for dom in valid:
                    if dom in doms:
                        skipped.append(dom)
                    else:
                        doms.append(dom)
                        added.append(dom)
                if added:
                    cfg.domain_overrides[lname] = doms
                    cfg.save()
                    print(f"  [+] Добавлено в {lname} ({len(added)}): {', '.join(added)}")
                if skipped:
                    print(f"  [!] Уже были в списке ({len(skipped)}): {', '.join(skipped[:8])}")
                if invalid:
                    print(f"  [!] Некорректные домены ({len(invalid)}): {', '.join(invalid[:8])}")
                if not added and not skipped and not invalid:
                    print("  [!] Ничего не введено.")
                pause()
            elif choice == "3":
                valid, invalid = read_domain_batch_input(f"Удалить домены из {lname}")
                targets = set(valid)
                for raw_tok in invalid:
                    targets.add(raw_tok.strip().lower())
                if not targets:
                    print("  [!] Ничего не введено.")
                    pause()
                    continue
                removed_list = [d for d in doms if d in targets]
                not_found = [d for d in targets if d not in doms]
                if removed_list:
                    doms = [d for d in doms if d not in targets]
                    cfg.domain_overrides[lname] = doms
                    cfg.save()
                    print(f"  [-] Удалено из {lname} ({len(removed_list)}): {', '.join(removed_list)}")
                if not_found:
                    print(f"  [!] Не найдены в {lname}: {', '.join(not_found[:8])}")
                pause()
        elif choice == "7":
            cfg.domain_overrides = {}
            cfg.enabled_overrides = {}
            if cfg.custom_groups:
                drop_custom = safe_input("\nУдалить также созданные вами группы доменов? [y/N]: ").strip().lower()
                if drop_custom in ("y", "yes", "д", "да"):
                    cfg.custom_groups = []
            cfg.save()
            print("\n  [✓] Домены и тумблеры сброшены к встроенным значениям.")
            pause()


def menu_edit_relays(cfg: AppConfig):
    while True:
        groups = cfg.build_groups()
        clear_screen()
        print("=" * 68)
        print("  РЕДАКТИРОВАНИЕ RELAY IP")
        print("=" * 68)
        for idx, grp in enumerate(groups, start=1):
            ips = ", ".join(grp["override_ips"])
            print(f"  {idx}. {grp['list_name']:24} -> {ips}")
        print("\n  A. Заменить конкретный IP сразу во всех группах (если узел лёг)")
        print("  R. Сбросить все Relay IP к значениям по умолчанию")
        print("  0. Назад в главное меню")

        choice = safe_input(f"\nВыберите группу [1–{len(groups)}], A, R или 0: ").strip().lower()
        if choice in ("0", ""):
            break
        if choice == "r":
            cfg.relay_overrides = {}
            cfg.save()
            print("\n  [✓] Все Relay IP сброшены по умолчанию.")
            pause()
            continue
        if choice == "a":
            active_ips = []
            for grp in groups:
                for ip in grp["override_ips"]:
                    if ip not in active_ips:
                        active_ips.append(ip)
            print(f"\n  Используемые сейчас IP: {', '.join(active_ips)}")
            old_ip = safe_input("Какой старый IP заменить: ").strip()
            if not old_ip:
                continue
            new_ip = choose_relay_ip(
                f"ЗАМЕНА RELAY {old_ip} ВО ВСЕХ ГРУППАХ",
                probe_domain="chatgpt.com",
            )
            if not new_ip:
                continue
            ans = safe_input("Применить замену? [Y/n]: ").strip().lower()
            if ans not in ("n", "no", "н", "нет"):
                count = 0
                for grp in groups:
                    if old_ip in grp["override_ips"]:
                        cfg.relay_overrides[grp["list_name"]] = [new_ip]
                        count += 1
                cfg.save()
                print(f"  [✓] Заменено в {count} группах. Запустите '1. Быстрая настройка' для применения.")
            pause()
            continue

        if not choice.isdigit() or not (1 <= int(choice) <= len(groups)):
            print("  [!] Неверный выбор.")
            pause()
            continue

        grp = groups[int(choice) - 1]
        lname = grp["list_name"]
        probe_dom = grp.get("probe_domain") or (grp["domains"][0] if grp["domains"] else "example.com")
        new_ip = choose_relay_ip(
            f"РЕДАКТИРОВАНИЕ RELAY IP: {lname}",
            probe_domain=probe_dom,
            current_ips=grp["override_ips"],
        )
        if not new_ip:
            continue

        cfg.relay_overrides[lname] = [new_ip]
        cfg.save()
        print(f"  [✓] Для {lname} сохранён IP {new_ip}. Примените через '1. Быстрая настройка'.")
        pause()


def menu_profile(cfg: AppConfig, profile_connected: bool = False) -> bool:
    while True:
        clear_screen()
        status_badge = green("✓ Подключен") if profile_connected else red("✗ Не подключен")
        print("=" * 68)
        print("  ПРОФИЛЬ CLOUDFLARE (ACCOUNT ID & API TOKEN)")
        print("=" * 68)
        print(f"  Статус:        {status_badge}")
        print(f"  Файл настроек: {cfg.path}")
        print(f"  Account ID:    {mask_secret(cfg.account_id, 6, 4) if cfg.account_id else '(не задан)'}")
        print(f"  API Token:     {mask_secret(cfg.api_token, 6, 4) if cfg.api_token else '(не задан)'}")
        print("\n  1. Ввести / сменить ключи и проверить подключение")
        print("  2. Удалить сохранённые ключи с диска")
        print("  3. Проверить текущее подключение")
        print("  0. Назад")
        choice = safe_input("\nВаш выбор: ").strip()
        if choice in ("0", ""):
            return profile_connected
        if choice == "1":
            aid, tok = prompt_credentials(cfg, force_new=True)
            if aid and tok:
                try:
                    CloudflareGatewaySetup(aid, tok, timeout=8.0).verify_token()
                    profile_connected = True
                    print(f"  {green('✓ Подключен')} — авторизация в Cloudflare Zero Trust подтверждена!")
                except Exception as e:
                    profile_connected = False
                    print(f"  {red('✗ Не подключен')} — ошибка проверки: {e}")
                pause()
        elif choice == "2":
            cfg.clear_credentials()
            profile_connected = False
            print("  [✓] Ключи удалены из локального конфига.")
            pause()
        elif choice == "3":
            if not cfg.account_id or not cfg.api_token:
                profile_connected = False
                print(f"  {red('✗ Не подключен')} — ключи не заданы.")
            else:
                try:
                    CloudflareGatewaySetup(cfg.account_id, cfg.api_token, timeout=8.0).verify_token()
                    profile_connected = True
                    print(f"  {green('✓ Подключен')} — токен активен.")
                except Exception as e:
                    profile_connected = False
                    print(f"  {red('✗ Не подключен')} — {e}")
            pause()


def menu_updates(cfg: AppConfig):
    clear_screen()
    print("=" * 68)
    print(f"  ПРОВЕРКА ОБНОВЛЕНИЙ (текущая версия: v{APP_VERSION})")
    print("=" * 68)
    print("  1. Проверить новый релиз на GitHub и обновить скрипт / .exe")
    print("  2. Подтянуть свежие списки доменов и Relay IP из GitHub (без перекачки .exe)")
    print("  0. Назад")
    choice = safe_input("\nВаш выбор: ").strip()
    if choice == "1":
        try:
            rel = fetch_latest_release_info(timeout=6)
            tag = rel.get("tag_name") or "?"
            print(f"\n  Последний релиз на GitHub: {tag}")
            if parse_version(tag) <= parse_version(APP_VERSION):
                print("  [✓] У вас уже установлена актуальная версия.")
                reinstall = safe_input("Перекачать принудительно? [y/N]: ").strip().lower()
                if reinstall not in ("y", "yes", "д", "да"):
                    return
            apply_self_update(rel)
        except Exception as e:
            print(f"  [!] Ошибка обновления: {e}")
        pause()
    elif choice == "2":
        try:
            cnt = sync_definitions_from_github(cfg)
            print(f"\n  [✓] Синхронизированы домены и Relay IP для {cnt} групп! Примените через '1. Быстрая настройка'.")
        except Exception as e:
            print(f"  [!] Ошибка загрузки списков: {e}")
        pause()


def ensure_client(cfg: AppConfig) -> CloudflareGatewaySetup | None:
    aid, tok = prompt_credentials(cfg, force_new=False)
    if not aid or not tok:
        return None
    return CloudflareGatewaySetup(aid, tok)


def main():
    init_console()
    cfg = AppConfig()
    profile_connected = False
    if cfg.account_id and cfg.api_token:
        try:
            CloudflareGatewaySetup(cfg.account_id, cfg.api_token, timeout=3.0).verify_token()
            profile_connected = True
        except Exception:
            profile_connected = False

    check_updates_on_startup(cfg)

    while True:
        groups = cfg.build_groups()
        active_cnt = sum(1 for g in groups if g["default_enabled"])
        prof_str = green("✓ Подключен") if profile_connected else red("✗ Не подключен")

        clear_screen()
        print("=" * 68)
        print(f"  Cloudflare Zero Trust Gateway DNS (v{APP_VERSION})")
        print(f"  Профиль: {prof_str} | Активных групп: {active_cnt}/{len(groups)}")
        print("=" * 68)
        print("  1. Быстрая настройка (применить правила в Cloudflare и получить DNS)")
        print("  2. Редактирование доменов и выбор групп (вкл/выкл, добавить/своя группа)")
        print("  3. Редактирование Relay IP (выбор из списка или свой IPv4)")
        print("  4. Живая диагностика (проверка текущих Relay IP и DoH)")
        print("  5. Статус Cloudflare и очистка правил")
        print("  6. Профиль Cloudflare (запомнить / сменить / удалить ID и Token)")
        print("  7. Проверить обновления (обновить .exe / подтянуть свежие списки)")
        print("  0. Выход")
        print("=" * 68)

        choice = safe_input("Выберите пункт [0–7]: ").strip()
        if choice == "0":
            clear_screen()
            break
        if not choice:
            continue

        try:
            if choice == "1":
                client = ensure_client(cfg)
                if client:
                    clear_screen()
                    client.run(groups=groups, interactive_groups=False)
                    profile_connected = True
                    pause("\nНажмите Enter, чтобы вернуться в главное меню...")
            elif choice == "2":
                menu_edit_domains(cfg)
            elif choice == "3":
                menu_edit_relays(cfg)
            elif choice == "4":
                clear_screen()
                doh_url = ""
                if cfg.account_id and cfg.api_token:
                    try:
                        doh_url = CloudflareGatewaySetup(cfg.account_id, cfg.api_token, timeout=4.0).get_existing_doh_url()
                    except Exception:
                        pass
                run_live_diagnostics(groups, doh_url=doh_url)
                pause("\nНажмите Enter, чтобы вернуться в главное меню...")
            elif choice == "5":
                client = ensure_client(cfg)
                if client:
                    clear_screen()
                    client.verify_token()
                    profile_connected = True
                    client.print_status()
                    clean = safe_input("\nУдалить все DNS-правила и списки доменов? [y/N]: ").strip().lower()
                    if clean in ("y", "yes", "д", "да"):
                        client.cleanup_existing_settings()
                    pause("\nНажмите Enter, чтобы вернуться в главное меню...")
            elif choice == "6":
                profile_connected = menu_profile(cfg, profile_connected=profile_connected)
            elif choice == "7":
                menu_updates(cfg)
            else:
                print("  [!] Неизвестный пункт меню.")
                pause()
        except Exception as e:
            if "Ошибка API (401)" in str(e) or "Ошибка API (403)" in str(e):
                profile_connected = False
            print(f"\n[!] Ошибка: {e}")
            pause("\nНажмите Enter, чтобы вернуться в главное меню...")


if __name__ == "__main__":
    main()
