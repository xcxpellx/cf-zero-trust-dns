# Cloudflare Zero Trust AI DNS Setup 🚀

Автоматическая настройка персонального безопасного DNS-сервера (**DNS-over-HTTPS / DNS-over-TLS**) на базе **Cloudflare Zero Trust** со встроенным обходом блокировок зарубежных ИИ-сервисов (ChatGPT, Claude, Google Gemini, Cursor и др.) **без VPN**.

---

## 💡 Как это работает?

Вместо того чтобы держать постоянно включённый VPN, тратить заряд батареи и снижать скорость интернета:

1. Вы используете **персональный защищённый DNS** от Cloudflare.
2. Для обычных сайтов (Яндекс, YouTube, ВК, банки и т.д.) DNS отдаёт их стандартные адреса.
3. При запросе к заблокированным ИИ-сервисам (ChatGPT, Claude, Gemini и т.д.) ваш Cloudflare Gateway автоматически подменяет IP на проверенный зарубежный Anycast-релей (**SNI Override**).
4. Сервисы открываются **напрямую на полной скорости вашего провайдера**.

```
[Ваше устройство (ПК / Телефон / Роутер)]
             │  (DNS-запрос через DoH / DoT)
             ▼
[Cloudflare Gateway (Ваш личный DNS)]
   ├── Обычные сайты  ──► Стандартные IP (напрямую)
   └── ChatGPT / Claude / Gemini ──► SNI Override IP ──► Доступ без VPN!
```

---

## 🌟 Поддерживаемые сервисы

* **OpenAI:** `chatgpt.com`, `openai.com`, `api.openai.com`, `auth.openai.com`
* **Anthropic:** `claude.ai`, `claude.com`, `anthropic.com`
* **Google AI:** `gemini.google.com`, `aistudio.google.com`, `makersuite.google.com`, `deepmind.com`
* **Разработка и ИИ:** `cursor.com`, `cursor.sh`, `perplexity.ai`, `v0.dev`, `sora.com`, `copilot.microsoft.com`, `midjourney.com`, `civitai.com`
* **Другие сервисы:** `canva.com`, `spotify.com`, `ntc.party`

---

## ⚡ Быстрый старт

### Способ 1: Готовый `.exe` (для Windows)
Не требует установки Python! Скачайте готовый файл из раздела **[Releases](../../releases)** и запустите.

### Способ 2: Запуск скрипта Python (любая ОС)
Работает на Windows, macOS и Linux без установки дополнительных библиотек:
```bash
git clone https://github.com/xcxpellx/cf-zero-trust-dns.git
cd cloudflare-ai-dns
python setup_cf_dns.py
```

---

## 📋 Инструкция по получению ключей Cloudflare

Для развёртывания настроек утилите потребуются **Account ID** и **API Token** из вашего личного кабинета Cloudflare (всё на 100% бесплатно):

1. **Регистрация:**  
   Зарегистрируйтесь на сайте [dash.cloudflare.com](https://dash.cloudflare.com/).
2. **Account ID:**  
   На главной странице дашборда в правой колонке найдите строку **Account ID** и скопируйте значение (32-значный хэш).
3. **API Token:**  
   * Перейдите в раздел [API Tokens](https://dash.cloudflare.com/profile/api-tokens) $\rightarrow$ нажмите **Create Token**.
   * Прокрутите страницу вниз и нажмите **Create Custom Token** (Создать свой токен).
   * Задайте имя токена (например, `Zero Trust DNS`).
   * В блоке **Permissions** выберите:  
     `Account` $\rightarrow$ `Zero Trust` $\rightarrow$ `Edit`
   * Нажмите **Continue to summary** $\rightarrow$ **Create Token** и скопируйте созданный ключ.

Запустите программу, вставьте скопированные данные — через 3 секунды всё будет готово!

---

## 📱 Как применить полученный DNS

После завершения скрипт выдаст ваш личный **DoH-адрес** вида:  
`https://<subdomain>.cloudflare-gateway.com/dns-query`  
и **DoT-хост** вида: `<subdomain>.cloudflare-gateway.com`.

### 🌐 В браузере (Chrome / Edge / Яндекс / Firefox / Opera):
1. Откройте **Настройки** $\rightarrow$ **Конфиденциальность и безопасность** $\rightarrow$ **Безопасность**.
2. Включите **Использовать безопасный DNS-сервер**.
3. Выберите **Свой** (или *Custom*) и вставьте ваш DoH-адрес.

### 📱 На смартфоне (Android):
1. Откройте **Настройки** $\rightarrow$ **Сеть и интернет** (или *Подключения*).
2. Выберите **Частный DNS-сервер** (Private DNS).
3. Укажите имя хоста провайдера частного DNS: `<subdomain>.cloudflare-gateway.com`.

### 📡 На роутере (Keenetic / OpenWrt):
* В Keenetic: **Сетевые правила** $\rightarrow$ **Интернет-фильтр** $\rightarrow$ добавьте сервер DNS-over-HTTPS с вашим адресом.

---

## 🔒 Безопасность
* Программа работает напрямую с официальным API Cloudflare по HTTPS.
* Ваши токены и ключи никуда не отправляются и не сохраняются на сторонних серверах.
* Все правила создаются исключительно внутри вашего изолированного аккаунта.
