# IMRAN TOPUP BOT — Vercel deployment package

This package is based on the user's original `main (3).py`.
The existing bot handlers, product data, payment flow, images-path logic,
owner actions, and local polling mode are preserved. Only the deployment
layer needed for Vercel was added/adjusted.

## Project files
- `main.py` — full bot code with Vercel webhook support
- `requirements.txt` — dependencies
- `README_VERCEL.txt` — deployment notes

## Images
The original code expects an `images/` folder next to `main.py` and references:
- imran.jpg
- pubg.jpg
- uc.jpg
- growth.jpg
- prime.jpeg
- mythic.jpg
- Rp.jpg
- freefire.jpg
- TikTok.jpg
- delta.jpg
- telegram.jpg
- blood.jpg
- Fortnite.jpg

The uploaded ZIP available in this chat contains only `main.py` and
`requirements.txt`; it does not contain the actual image assets. Therefore
this package does not invent or replace those images. If your GitHub repository
already contains the `images/` folder, keep it there. If you deploy this ZIP
directly, copy your existing `images/` folder into the project root first.

## Vercel environment variables

Required:
- `BOT_TOKEN` = your Telegram BotFather token
- `CHAT_ID` = your owner Telegram numeric user ID

Recommended:
- `WEBHOOK_SECRET` = a private random secret
- `WEBHOOK_BASE_URL` = optional; normally leave blank so Vercel's `VERCEL_URL` is used
- `REDIS_URL` = optional; use a Redis service if you need FSM state to survive
  across serverless instances

Optional:
- `CUSTOM_EMOJI_ID`
- `CUSTOM_EMOJI_IDS`
- `DB_PATH`

## Webhook setup

After the Vercel deployment succeeds, open:

https://YOUR-PROJECT.vercel.app/setup-webhook

This calls Telegram's webhook setup and points Telegram to:

https://YOUR-PROJECT.vercel.app/webhook

## Important storage note

The original bot uses SQLite. Vercel's deployed filesystem is not a durable
database, so on Vercel this package defaults the SQLite path to `/tmp/bot.db`.
That lets the bot initialize and write during an instance lifetime, but the
database is not guaranteed to survive a new serverless instance.

For reliable production orders/products, use a persistent external database.

The bot's FSM storage remains the original in-memory storage unless
`REDIS_URL` is supplied. For multi-step conversations that must survive
serverless cold starts, configure Redis.

## Vercel settings

- Framework / Application Preset: Flask
- Root Directory: `./`
- Build Command: None
- Output Directory: N/A
- Install Command: `pip install -r requirements.txt`
