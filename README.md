# Cloudflare Zero Trust AI DNS Setup 🚀

Автоматическая настройка персонального шифрованного DNS (**DNS-over-HTTPS / DNS-over-TLS**) на базе **Cloudflare Zero Trust** для доступа к зарубежным ИИ-сервисам (ChatGPT, Claude, Google Gemini, AI Studio, Grok, Cursor и др.), а также опциональных правил для **Spotify** и **SoundCloud** **без использования VPN**.

---

## 💡 Как это работает?

Вместо постоянно включённого VPN, который пропускает через себя весь трафик и расходует заряд батареи:

1. Вы подключаете **персональный шифрованный DNS** от Cloudflare (DoH или DoT).
2. Для обычных сайтов (Яндекс, ВК, банки, локальные сервисы и т.д.) DNS возвращает их стандартные IP — трафик идёт **напрямую** через вашего провайдера.
3. При обращении к сервисам из списка (ChatGPT, Claude, Gemini и др.) Cloudflare Gateway блокирует утечку по IPv6 (`AAAA`) и применяет правило **DNS Override**, отдавая IP зарубежного **SNI-прокси**.
4. Трафик до этих сервисов перенаправляется через прокси без установки VPN-клиента.

```
[Ваше устройство (ПК / Телефон / Роутер)]
             │  (DNS-запрос через DoH / DoT)
             ▼
[Cloudflare Gateway (Ваш личный DNS)]
   ├── Обычные сайты ─────────────────────────► Стандартные IP (напрямую)
   └── ChatGPT / Claude / Gemini / Grok ──────► DNS Override (SNI-прокси) ──► Доступ без VPN
```

---

## 🌟 Поддерживаемые сервисы

### Включены по умолчанию:
- **OpenAI:** `chatgpt.com`, `openai.com`, `api.openai.com`, `auth.openai.com`, `oaistatic.com`, `oaiusercontent.com`
- **Anthropic:** `claude.ai`, `claude.com`, `anthropic.com`, `claudeusercontent.com`
- **Grok (xAI):** `grok.com`, `grok.x.com`, `assets.grok.com`, `x.ai`, `accounts.x.ai`, `console.x.ai`, `api.x.ai`
- **Google Gemini & AI Studio:** `gemini.google.com`, `geminiweb-pa.clients6.google.com`, `aistudio.google.com`, `alkalimakersuite-pa.clients6.google.com`, `webchannel-alkalimakersuite-pa.clients6.google.com`, `generativelanguage.googleapis.com`, `makersuite.google.com`, `deepmind.com`
- **Разработка и ИИ:** `cursor.com`, `cursor.sh`, `cursorapi.com`, `perplexity.ai`, `v0.dev`, `sora.com`, `copilot.microsoft.com`, `midjourney.com`, `civitai.com`, `elevenlabs.io`
- **Продуктивность и инструменты:** `deepl.com`, `notion.so`, `notion.site`, `canva.com`, `ntc.party`

### Опциональные правила (выключены по умолчанию):
В панели **Cloudflare Zero Trust** (*Gateway → Firewall Policies → DNS*) создаются дополнительные правила с выключенным тумблером — их можно включить в один клик:
- **Spotify:** `spotify.com`, `scdn.co`, `spotifycdn.com`, `spotifycdn.net`, `spotify.design`, `spotify.link` (SNI-прокси)
- **SoundCloud:** `soundcloud.com`, `sndcdn.com` (переопределение на рабочий IP Amazon CloudFront)

---

## ⚡ Быстрый старт

### Способ 1: Готовый `.exe` (для Windows)
Не требует установки Python. Скачайте последнюю версию из раздела релизов: **[Скачать CloudflareDNS_Setup.exe](https://github.com/xcxpellx/cf-zero-trust-dns/releases/latest/download/CloudflareDNS_Setup.exe)** (или откройте все версии в **[Releases](../../releases)**) и запустите.

### Способ 2: Запуск скрипта Python (Windows / macOS / Linux)
Работает на стандартной библиотеке Python без установки сторонних пакетов:
```bash
git clone https://github.com/xcxpellx/cf-zero-trust-dns.git
cd cf-zero-trust-dns
python setup_cf_dns.py
```

---

## 📋 Инструкция по получению ключей Cloudflare

Для автоматической настройки потребуются **Account ID** и **API Token** от вашего аккаунта Cloudflare:

1. **Регистрация и активация Zero Trust:**  
   Зарегистрируйтесь на [dash.cloudflare.com](https://dash.cloudflare.com/). Затем перейдите в панель [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) и активируйте бесплатный тариф (**Zero Trust Free**), задав имя команды (Team Name). *Без этого шага API вернёт ошибку 403.*
2. **Account ID:**  
   Нажмите на иконку профиля (человечка) в правом верхнем углу дашборда Cloudflare и выберите **Copy account ID** *(или скопируйте 32-значный идентификатор из адресной строки браузера: `https://dash.cloudflare.com/<ACCOUNT_ID>/...`)*.
3. **API Token:**  
   - В левом меню внизу откройте **Manage account → Settings**.
   - В блоке **Account settings** выберите **Account API tokens** (либо в **User settings → API credentials → API tokens**) и нажмите **+ Create token**.
   - В поле **Token name** задайте имя (например, `Zero Trust DNS`).
   - В блоке **Policies** нажмите **Start from scratch** (*Custom*) → **Start with an Account policy**.
   - Раскройте категорию **Cloudflare One / Zero Trust**, найдите строку **Zero Trust** и отметьте галочку **Edit**.
   - Сохраните токен (**Continue to summary** → **Create Token**) и скопируйте созданный ключ.

Запустите утилиту, вставьте `Account ID` и `API Token` — настройка займёт несколько секунд.

---

## 📱 Как применить полученный DNS

После завершения скрипт выдаст ваши персональные адреса:
- **DoH (DNS-over-HTTPS):** `https://<subdomain>.cloudflare-gateway.com/dns-query`
- **DoT (DNS-over-TLS):** `<subdomain>.cloudflare-gateway.com`

### 🌐 В браузере (Chrome / Edge / Яндекс / Firefox / Opera):
1. Откройте **Настройки** → **Конфиденциальность и безопасность** → **Безопасность**.
2. Включите **Использовать безопасный DNS-сервер**.
3. Выберите **Свой** (*Custom*) и вставьте ваш **DoH-адрес**.

### 📱 На смартфоне (Android):
1. Откройте **Настройки** → **Сеть и интернет** (или *Подключения* → *Другие настройки*).
2. Выберите **Частный DNS-сервер** (*Private DNS*).
3. Укажите ваш **DoT-хост**: `<subdomain>.cloudflare-gateway.com` (без `https://` и `/dns-query`).

### 📡 На роутере (Keenetic / OpenWrt / Asus):
- **Keenetic:** *Сетевые правила* → *Интернет-фильтр* → добавьте сервер **DNS-over-HTTPS** с вашим DoH-адресом.
- **OpenWrt:** используйте пакеты `https-dns-proxy` или `stubby` с указанием вашего DoH/DoT-адреса.

---

## 🛠️ Решение проблем: ошибки 401 и 403

### 1. Ошибки при запуске скрипта (ответ от Cloudflare API)

* **401 Unauthorized (Ошибка авторизации):**
  * **Причина:** Неверный, отозванный или просроченный `API Token`, либо при копировании попали лишние пробелы/переносы строк.
  * **Решение:** Перепроверьте токен или перевыпустите его в разделе *API Tokens*.

* **403 Forbidden (Доступ запрещён):**
  * **Причина 1:** Не активирован тариф **Zero Trust Free** в панели `one.dash.cloudflare.com`.
  * **Причина 2:** У токена недостаточно прав (выбрано `Read` вместо `Edit`, либо указан не тот раздел).
  * **Причина 3:** Неверный `Account ID` или в настройках токена (*Account Resources*) не включён нужный аккаунт.
  * **Решение:** Убедитесь, что Zero Trust активирован, перепроверьте `Account ID` и права токена (`Account → Zero Trust → Edit`).

### 2. Ошибки при открытии сайтов в браузере (ChatGPT, Claude, Gemini и др.)

* **403 Forbidden (Доступ к сервису заблокирован):**
  * **Причина 1 (Кэш DNS):** Браузер или ОС всё ещё используют старый IP провайдера.
  * **Причина 2 (Лимиты SNI-прокси):** IP-адрес публичного SNI-прокси временно попал под ограничения (rate-limit) или блокировку со стороны самого сервиса (Cloudflare WAF / OpenAI / Anthropic).
  * **Решение:** Очистите DNS-кэш (`ipconfig /flushdns` на Windows), перезапустите браузер. Если проблема сохраняется — замените IP прокси в правиле Gateway.

* **401 Unauthorized (Ошибка входа на сайт / в API):**
  * **Причина:** Конфликт старой сессии (cookies) после смены IP/региона или истёкший токен авторизации.
  * **Решение:** Очистите cookies для проблемного сайта или откройте его в режиме инкогнито и войдите заново.

---

## 🔒 Безопасность и приватность

- Скрипт общается напрямую с официальным API Cloudflare по HTTPS; ваши ключи никуда не передаются и не сохраняются на сторонних серверах.
- Все правила создаются исключительно внутри вашего личного аккаунта Cloudflare.
- **Важно о SNI-прокси:** Трафик к ИИ-сервисам шифруется по протоколу TLS (HTTPS) напрямую между вашим устройством и сервером сервиса. SNI-прокси видит только доменное имя, к которому вы подключаетесь (SNI), но **не может** прочитать содержимое переписок, пароли или передаваемые данные.
