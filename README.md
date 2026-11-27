# Cloudflare Zero Trust — Персональный шифрованный DNS для доступа к ИИ и зарубежным сервисам

Автоматическая настройка собственного шифрованного DNS-сервера (**DoH / DoT**) на базе бесплатного тарифа **Cloudflare Zero Trust Gateway** с правилами **DNS Override** через проверенные зарубежные SNI-прокси.

Обычные сайты (банки, Госуслуги, локальные сервисы, видеохостинги) продолжают открываться напрямую через вашего провайдера без потери скорости, а запросы к ИИ-платформам и геоблокированным ресурсам направляются через зарубежный узел.

---

## Возможности утилиты (`v1.7.0`)

После запуска открывается интерактивное меню:

1. **Быстрая настройка:** в один шаг создаёт/обновляет списки доменов, правила `DNS Override`, защиту от утечки IPv6 и выдаёт личные адреса **DoH / DoT**.
2. **Редактирование доменов и выбор групп:** можно включать/отключать любые группы, добавлять или удалять домены **по одному или сразу списком**, а также **создавать свои группы доменов**.
3. **Редактирование Relay IP:** выбор из предложенных проверенных релеев (с живой проверкой доступности) либо ввод своего IPv4 для отдельной группы или сразу во всех группах.
4. **Живая диагностика:** проверяет прямо с вашего ПК отклик текущих Relay IP (зелёный `✓ Отвечает` / красный `✗ Не отвечает`) и ответы вашего DoH-шлюза.
5. **Статус Cloudflare и очистка:** показывает занятый лимит записей Free-плана (`из 1000`), активные правила и позволяет безопасно очистить старые настройки.
6. **Сохранение профиля:** запоминает `Account ID` и `API Token` локально (`~/.cloudflare_dns_setup/config.json`), чтобы не вводить их при каждом запуске.
7. **Автопроверка обновлений:** проверяет новые релизы на GitHub, умеет самообновлять `.exe`/`.py` либо подтягивать свежие списки доменов и Relay IP прямо из репозитория **без перекачки `.exe`**.

---

## Что настраивается по умолчанию

| # | Группа / Правило | Что входит | Статус по умолчанию |
| :---: | :--- | :--- | :--- |
| 1 | **Claude AI Override** (`Claude_Domains`) | `claude.ai`, `claude.com`, `anthropic.com`, `claudeusercontent.com` | Включено |
| 2 | **Grok & xAI Override** (`Grok_xAI_Domains`) | `grok.com`, `grok.x.com`, `grok.x.ai`, `assets.grok.com`, `x.ai`, `accounts.x.ai`, `console.x.ai`, `api.x.ai` | Включено |
| 3 | **OpenAI Backend Override** (`OpenAI_Domains`) | `chatgpt.com`, `openai.com`, `api.openai.com`, `auth.openai.com`, `oaistatic.com`, `oaiusercontent.com` | Включено |
| 4 | **Google Gemini Override** (`Gemini_Domains`) | `gemini.google.com`, `aistudio.google.com`, `notebooklm.google.com`, `labs.google`, API Google AI | Включено |
| 5 | **Other AI Services Override** (`Other_AI_Domains`) | `cursor.com`, `cursor.sh`, `windsurf.com`, `perplexity.ai`, `copilot.microsoft.com`, `elevenlabs.io`, `mistral.ai`, `openrouter.ai` и др. | Включено |
| 6 | **AI Media & Dev Override** (`AI_Media_Dev_Domains`) | `sora.com`, `midjourney.com`, `civitai.com`, `canva.com`, `figma.com`, `notion.*`, `jetbrains.*`, `docker.io`, `groq.com`, `replicate.com` | Включено |
| 7 | **Geo Blocked Services Override** (`Geo_Domains`) | `strava.com`, `deepl.com`, `miro.com`, `linear.app`, `atlassian.com`, `framer.com`, `tailscale.com`, `wise.com`, `deezer.com` и др. | Включено |
| 8 | **Spotify Override** (`Spotify_Domains`) | `spotify.com`, `scdn.co`, `spotifycdn.com` | Выключено (включается в меню или в панели) |
| 9 | **SoundCloud Override** (`SoundCloud_Domains`) | `soundcloud.com`, `sndcdn.com` *(быстрый маршрут Amazon CloudFront)* | Выключено (включается в меню или в панели) |
| — | **Force IPv4 for Overridden Services** | Блокировка `AAAA`-запросов (IPv6) только для **активных** групп выше, чтобы IPv6 не обходил `DNS Override` | Включено автоматически при наличии активных групп |

> **Про SoundCloud:** публичные SNI-прокси не обслуживают `soundcloud.com` (сбрасывают TLS), поэтому правило использует быстрый рабочий IP **Amazon CloudFront**. Это решает блокировку или троттлинг отдельных подсетей CloudFront, а для обхода SNI-DPI нужен `d2k`/`z2k` или аналог.

---

## Шаг 1. Подготовка аккаунта Cloudflare

1. **Регистрация и активация Zero Trust:**
   * Войдите или зарегистрируйтесь на [dash.cloudflare.com](https://dash.cloudflare.com/).
   * В левом меню откройте **Protect & connect → Zero Trust** (или перейдите напрямую на [one.dash.cloudflare.com](https://one.dash.cloudflare.com/)).
   * Задайте имя команды (любое, например `my-home-dns`) и выберите бесплатный тариф **Zero Trust Free** ($0/мес).
   * **Важно:** для активации даже бесплатного тарифа **Zero Trust Free** Cloudflare требует привязать **иностранную банковскую карту** (российские карты не принимаются; средства за тариф $0 не списываются).

2. **Получение Account ID:**
   * Нажмите на иконку профиля (человечка) в правом верхнем углу дашборда Cloudflare и выберите **Copy account ID** *(или скопируйте 32-значный идентификатор из адресной строки браузера: `https://dash.cloudflare.com/<ACCOUNT_ID>/...`)*.

3. **Создание API Token:**
   * В левом меню внизу нажмите **Manage account → Settings**.
   * Перейдите в **Account settings → Account API tokens** (либо **User settings → API credentials → API tokens**) и нажмите **+ Create token**.
   * Укажите любое имя токена (**Token name**), например `Gateway DNS Setup`.
   * В разделе **Policies** выберите **Start from scratch** (*Custom*) → **Start with an Account policy**.
   * Раскройте категорию **Cloudflare One / Zero Trust**, найдите строку **Zero Trust** и установите право **Edit** (именно `Edit`, не `Read`).
   * Нажмите **Continue to summary → Create Token** и скопируйте сгенерированный токен.

---

## Шаг 2. Запуск настройки

### Вариант А: Готовый исполняемый файл для Windows (без установки Python)
1. Скачайте `CloudflareDNS_Setup.exe` со страницы релизов:  
   [Скачать CloudflareDNS_Setup.exe](https://github.com/xcxpellx/cf-zero-trust-dns/releases/latest/download/CloudflareDNS_Setup.exe)
2. Запустите файл, введите **Account ID** и **API Token** (при желании сохраните их локально) и выберите **1. Быстрая настройка**.
3. Скопируйте выданные персональные адреса **DoH** (`https://<id>.cloudflare-gateway.com/dns-query`) и **DoT** (`<id>.cloudflare-gateway.com`).

### Вариант Б: Запуск из исходного кода (Windows / macOS / Linux)
Скрипт использует только стандартную библиотеку Python 3 и не требует установки сторонних пакетов:
```bash
python3 setup_cf_dns.py
```

---

## Шаг 3. Подключение на устройствах

* **Браузеры (Chrome, Edge, Яндекс Браузер, Brave, Firefox, Opera):**  
  *Настройки → Конфиденциальность и безопасность → Безопасность → Использовать безопасный DNS → Свой поставщик* — вставьте ваш **DoH-адрес**.
* **Android (9 и новее):**  
  *Настройки → Сеть и интернет → Персональный DNS-сервер (Private DNS) → Имя хоста провайдера* — вставьте ваш **DoT-хост** (`<id>.cloudflare-gateway.com`).
* **iOS / macOS:**  
  Установите профиль DNS-over-HTTPS с вашим **DoH-адресом** (или через приложение Cloudflare One / профиль `.mobileconfig`). Для корректной работы на iPhone отключите *«Частный узел iCloud» (Private Relay)* и *«Ограничение трекинга IP-адреса»* в свойствах Wi-Fi.
* **Роутеры (Keenetic, OpenWrt, Asuswrt-Merlin):**  
  Добавьте ваш **DoH-адрес** в разделе DNS-шифрования (DNS-over-HTTPS) в веб-интерфейсе роутера.

---

## Приватность и безопасность

* **Сквозное шифрование (TLS):** весь трафик до сайтов шифруется по HTTPS напрямую между вашим устройством и сервером целевого сервиса. SNI-прокси видит только имя запрашиваемого домена (SNI) для маршрутизации пакета, но не имеет доступа к содержимому переписок, токенам или паролям.
* **Локальное хранение ключей:** если вы выбрали «Запомнить Account ID и API Token», они сохраняются исключительно на вашем устройстве в `~/.cloudflare_dns_setup/config.json` (удалить можно через пункт меню *Профиль*).

---

## Решение проблем: ошибки 401 и 403

### 1. Ошибка возникает в консоли при запуске скрипта
* **Ошибка `401 (Unauthorized)`:** неверный API Token или при копировании попали лишние пробелы/переносы строк. Создайте новый токен и обновите его в пункте меню *Профиль*.
* **Ошибка `403 (Forbidden)`:**
  1. Не активирован бесплатный тариф **Zero Trust Free** на [one.dash.cloudflare.com](https://one.dash.cloudflare.com/) (для активации нужна привязка иностранной банковской карты).
  2. Токену выданы права **Read** вместо **Edit** в разделе *Zero Trust*.
  3. Указан неверный **Account ID** (проверьте через *иконку профиля в правом верхнем углу → Copy account ID*).

### 2. Ошибка `403` или `401` возникает в браузере при открытии сайта
* **Кэш старого DNS / IPv6:** перезапустите браузер или очистите кэш DNS (`chrome://net-internals/#dns` → *Clear host cache* и в командной строке Windows: `ipconfig /flushdns`).
* **Старые cookies / сессия:** откройте сайт в режиме инкогнито или очистите cookies для проблемного домена.
* **Проверка и замена Relay IP:** запустите в утилите **пункт 4 (Живая диагностика)** — если какой-то узел перестал отвечать, его можно сразу поменять в **пункте 3 (Редактирование Relay IP)** или проверить вручную:
  ```bash
  curl -I --resolve example.com:443:<IP_ПРОКСИ> https://example.com
  ```
