# X Trend Digest Automation

This automation checks X for currently talked-about posts in the requested niches, uses Gemini to turn the findings into content ideas, and emails the digest. Reddit is intentionally left out for now.

## Categories

- Personal Finance & Money Mindset for Gen Z
- Startup Breakdowns & High-Potential Business Ideas
- Upskilling, Tech Certifications & Freelancing
- Artificial Intelligence & Emerging Tech Updates

## Setup

1. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in real credentials:

   ```bash
   cp .env.example .env
   ```

3. Configure your SMTP settings. For Gmail, use an app password rather than your normal Google account password.

4. Confirm the ScrapperSOGS X posts endpoint path. If your account uses a different route, update `SCRAPPERSOGS_X_POSTS_PATH` in `.env`.

## Run

Preview without sending email:

```bash
python automations/trend_digest/trend_digest.py --dry-run
```

Send the email:

```bash
python automations/trend_digest/trend_digest.py
```

## Scheduling example

Run every weekday at 8 AM UTC with cron:

```cron
0 8 * * 1-5 cd /workspace/bh && /usr/bin/python3 automations/trend_digest/trend_digest.py >> trend_digest.log 2>&1
```

## Security notes

Do not commit real API keys or SMTP passwords. Keep them in `.env` or your deployment platform's secret manager.
