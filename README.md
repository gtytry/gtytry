# AI Sales QA Agent for Telegram

Production-like Telegram bot + FastAPI backend that evaluates manager-client chat screenshots using OCR and OpenAI Vision.

## What It Does

- Accepts Telegram photos, PNG, JPG, JPEG and image albums.
- Groups screenshots into an analysis session.
- Extracts Russian/English OCR text with Tesseract.
- Sends OCR text plus original screenshots to OpenAI Vision.
- Scores sales quality from 0 to 100 across 10 criteria.
- Stores every evaluation in SQLite.
- Deletes uploaded screenshots after analysis by default.
- Provides `/stats` admin leaderboard: average score, top mistakes, best and worst manager.

## Project Structure

```text
app/          FastAPI app and logging
bot/          Telegram bot handlers
ai/           OpenAI client and response schemas
ocr/          OCR extraction and cleanup
services/     business services, sessions, formatting, rate limiting
database/     SQLAlchemy models, DB init, repositories
prompts/      Sales QA system prompt
config/       environment settings
data/         runtime uploads and SQLite database
```

## Requirements

- Python 3.12+
- Telegram bot token from BotFather
- OpenAI API key
- Tesseract OCR with Russian language pack

On Ubuntu/Debian:

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng
```

On Windows, install Tesseract and set `TESSERACT_CMD` in `.env`, for example:

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o
BOT_MODE=polling
ADMIN_USER_IDS=123456789
```

Run:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```text
http://localhost:8000/health
```

## Docker Setup

```bash
copy .env.example .env
docker compose up --build
```

The container installs Tesseract with Russian and English language packs. SQLite data is persisted in `./data`. Screenshots are temporary by default and are deleted after analysis with `DELETE_IMAGES_AFTER_ANALYSIS=true`.

## Free Cloud Deploy

For a no-PC setup, use Render webhook deployment:

```text
DEPLOY_RENDER.md
```

This project includes `render.yaml`, so Render can create a free Docker web service from the repository.

## Telegram Usage

- `/start` - help
- `/new` - start a manual screenshot session
- Send one or more screenshots
- `/done` - analyze accumulated screenshots
- `/cancel` - reset current session
- `/stats` - admin statistics

Albums are grouped automatically. Single screenshots are accumulated until `/done`, so managers can send several screens in order.

## Webhook Mode

Set:

```env
BOT_MODE=webhook
WEBHOOK_BASE_URL=https://your-domain.com
WEBHOOK_SECRET=long-random-secret
```

The webhook endpoint is:

```text
/telegram/webhook/{WEBHOOK_SECRET}
```

## Database

SQLite schema is created automatically on startup via SQLAlchemy metadata:

- `managers`
- `analyses`

To switch to Postgres/Supabase later, replace `DATABASE_URL` with an async SQLAlchemy URL and add the matching driver.

## Scoring

The AI returns strict JSON:

- overall score
- sale probability
- summary
- strengths
- mistakes
- missed opportunities
- recommendations
- 10 individual criteria scores

The prompt is located at `prompts/sales_qa_system.md` and is intentionally strict: politeness alone is not enough for a high score; missing needs discovery, weak objections handling, and no close-to-action are penalized heavily.

## Production Notes

- Use webhook mode behind HTTPS for production.
- Set `ADMIN_USER_IDS`; if empty, `/stats` is open for local convenience.
- Screenshots are not stored after analysis by default. If you set `DELETE_IMAGES_AFTER_ANALYSIS=false`, use protected storage because screenshots may contain customer PII.
- Add external rate limiting at the reverse proxy for public deployments.
- Rotate logs and avoid writing customer PII to logs.
