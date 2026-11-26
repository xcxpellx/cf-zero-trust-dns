# Cloudflare Zero Trust — Персональный шифрованный DNS для доступа к ИИ и зарубежным сервисам

Автоматическая настройка собственного шифрованного DNS-сервера (**DoH / DoT**) на базе бесплатного тарифа **Cloudflare Zero Trust Gateway** с правилами **DNS Override** через проверенные зарубежные SNI-прокси.

Обычные сайты (банки, Госуслуги, локальные сервисы, видеохостинги) продолжают открываться напрямую через вашего провайдера без потери скорости, а запросы к ИИ-платформам и геоблокированным ресурсам направляются через зарубежный узел.

---

## Что настраивается автоматически

Перед применением правил скрипт выводит интерактивное меню, где можно **включить или отключить любую из 9 групп** (невыбранные правила всё равно создаются в Cloudflare с выключенным тумблером — их можно переключить в панели в любой момент):

| # | Группа / Правило | Что входит | Статус по умолчанию |
| :---: | :--- | :--- | :--- |
| 1 | **Claude AI Override** (`Claude_Domains`) | `claude.ai`, `claude.com`, `anthropic.com`, `claudeusercontent.com` | Включено |
| 2 | **Grok & xAI Override** (`Grok_xAI_Domains`) | `grok.com`, `grok.x.com`, `grok.x.ai`, `assets.grok.com`, `x.ai`, `accounts.x.ai`, `console.x.ai`, `api.x.ai` | Включено |
| 3 | **OpenAI Backend Override** (`OpenAI_Domains`) | `chatgpt.com`, `openai.com`, `api.openai.com`, `auth.openai.com`, `oaistatic.com`, `oaiusercontent.com` | Включено |
| 4 | **Google Gemini Override** (`Gemini_Domains`) | `gemini.google.com`, `aistudio.google.com`, `notebooklm.google.com`, `labs.google`, API Google AI | Включено |
| 5 | **Other AI Services Override** (`Other_AI_Domains`) | `cursor.com`, `cursor.sh`, `windsurf.com`, `perplexity.ai`, `copilot.microsoft.com`, `elevenlabs.io`, `mistral.ai`, `openrouter.ai` и др. | Включено |
| 6 | **AI Media & Dev Override** (`AI_Media_Dev_Domains`) | `sora.com`, `midjourney.com`, `civitai.com`, `canva.com`, `figma.com`, `notion.*`, `jetbrains.*`, `docker.io`, `groq.com`, `replicate.com` | Включено |
| 7 | **Geo Blocked Services Override** (`Geo_Domains`) | `strava.com`, `deepl.com`, `miro.com`, `linear.app`, `atlassian.com`, `framer.com`, `tailscale.com`, `wise.com`, `deezer.com` и др. | Включено |
| 8 | **Spotify Override** (`Spotify_Domains`) | `spotify.com`, `scdn.co`, `spotifycdn.com` | Выключено (включается при выборе в скрипте или в панели) |
| 9 | **SoundCloud Override** (`SoundCloud_Domains`) | `soundcloud.com`, `sndcdn.com` *(быстрый Amazon CloudFront IP `108.156.22.80`)* | Выключено (включается при выборе в скрипте или в панели) |
| — | **Force IPv4 for Overridden Services** | Блокировка `AAAA`-запросов (IPv6) только для **активных** групп выше, чтобы IPv6 не обходил `DNS Override` | Включено автоматически при наличии активных групп |

> **Про SoundCloud:** публичные SNI-прокси не обслуживают `soundcloud.com` (сбрасывают TLS), поэтому правило использует быстрый рабочий Anycast IP **Amazon CloudFront** (`108.156.22.80`). Это решает блокировку или троттлинг отдельных подсетей CloudFront и работает в паре с обходом SNI DPI (`d2o` / Zapret). Если ваш провайдер режет `soundcloud.com` жёстко по SNI без DPI-обхода на роутере/ПК, одного DNS Override недостаточно.

> **При повторном запуске:** если на аккаунте уже есть DNS-правила или списки доменов, скрипт предложит выбор — оставить их и обновиться поверх или полностью очистить перед настройкой. Ваша точка DNS (`location`) и выданные адреса DoH/DoT при этом сохраняются.

---

## Шаг 1. Подготовка аккаунта Cloudflare

1. **Регистрация и активация Zero Trust:**
   * Войдите или зарегистрируйтесь на [dash.cloudflare.com](https://dash.cloudflare.com/).
   * В левом меню откройте **Protect & connect → Zero Trust** (или перейдите напрямую на [one.dash.cloudflare.com](https://one.dash.cloudflare.com/)).
   * Задайте имя команды (любое, например `my-home-dns`) и выберите бесплатный тариф **Zero Trust Free** ($0/мес — достаточно подтвердить бесплатный план).

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
1. Скачайте последний `CloudflareDNS_Setup.exe` со страницы релизов:  
   [Скачать CloudflareDNS_Setup.exe](https://github.com/xcxpellx/cf-zero-trust-dns/releases/latest/download/CloudflareDNS_Setup.exe)
2. Запустите файл, вставьте ваш **Account ID** и **API Token**, выберите нужные группы правил.
3. Скопируйте выданные персональные адреса **DoH** (`https://<id>.cloudflare-gateway.com/dns-query`) и **DoT** (`<id>.cloudflare-gateway.com`).

### Вариант Б: Запуск из исходного кода (Windows / macOS / Linux)
Скрипт использует только стандартную библиотеку Python 3 (`urllib`, `json`, `re`, `sys`) и не требует установки дополнительных пакетов:
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
* **Локальный трафик не затрагивается:** сайты вне списков обхода резолвятся стандартным образом через Cloudflare DNS без проксирования.

---

## Решение проблем: ошибки 401 и 403

### 1. Ошибка возникает в консоли при запуске скрипта
* **Ошибка `401 (Unauthorized)`:** неверный API Token или при копировании попали лишние пробелы/переносы строк. Создайте новый токен и вставьте его заново.
* **Ошибка `403 (Forbidden)`:**
  1. Не активирован бесплатный тариф **Zero Trust Free** на [one.dash.cloudflare.com](https://one.dash.cloudflare.com/).
  2. Токену выданы права **Read** вместо **Edit** в разделе *Zero Trust*.
  3. Указан неверный **Account ID** (проверьте через *иконку профиля в правом верхнем углу → Copy account ID*).

### 2. Ошибка `403` или `401` возникает в браузере при открытии сайта
* **Кэш старого DNS / IPv6:** перезапустите браузер или очистите кэш DNS (`chrome://net-internals/#dns` → *Clear host cache* и в командной строке Windows: `ipconfig /flushdns`).
* **Старые cookies / сессия:** откройте сайт в режиме инкогнито или очистите cookies для проблемного домена.
* **Проверка домена вручную:** любой домен и его совместимость с релеем можно проверить командой:
  ```bash
  curl -I --resolve example.com:443:31.58.216.201 https://example.com
  ```
  и при необходимости убрать или переключить проблемный список в панели Cloudflare Zero Trust (*Gateway → Firewall Policies → DNS*).
