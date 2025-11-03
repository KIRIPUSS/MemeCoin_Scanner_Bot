# MemeCoin Scanner

A small toolkit to scrape trending Solana token pairs from Dexscreener, check basic safety signals (liquidity lock, authorities, volume/liquidity/MC heuristics), and optionally deliver results via a Telegram bot.

## Features
- **Dexscreener scraping** (undetected-chromedriver + Selenium)
- **Token heuristics** via Dexscreener API + Solscan HTML scraping
- **Telegram bot** command `/start` to run a scan and return best candidates

## Prerequisites
- Python 3.10+
- Google Chrome installed
- Internet access (Dexscreener + Solscan)

## Setup
1. Create and activate a virtual environment
   - Windows PowerShell:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
2. Install dependencies
   ```bash
   pip install -r requirement.txt
   ```

## Configuration
- Telegram bot token: edit `bot.py` and replace the placeholder in `ApplicationBuilder().token("<YOUR_TOKEN>")` with your real token.
- The repo includes a `.env` file but the current code does not read from it. If you prefer using environment variables, you can add python-dotenv and load the token yourself, or keep the direct token string in `bot.py`.

## Usage
- Run full scanner pipeline (headful Chrome will open):
  ```bash
  python scanner.py
  ```
- Run Telegram bot:
  ```bash
  python bot.py
  ```
  Then, in Telegram, send `/start` to your bot to trigger a scan. The bot runs the same pipeline and replies with the top results.

## Notes
- Selenium/ChromeDriver: `undetected-chromedriver` manages a compatible driver automatically, but you still need Google Chrome installed and accessible on PATH.
- Scraping targets (Dexscreener/Solscan) may change their markup. If selectors break, update the CSS selectors in the scrapers.
- Heuristics are simplistic and can yield false positives/negatives. Do your own research before any action.

## Project Structure
- `scanner.py` — end-to-end pipeline: scrape trending pairs, analyze, print reports
- `dextools_scraper.py` — utility to detect liquidity lock and scrape pairs
- `slscanscrap.py` — Solscan holders page scraper (example)
- `bot.py` — Telegram bot entrypoint
- `requirement.txt` — Python dependencies
- `launcher_scraper.bat` — Windows helper script to launch scraper

## Troubleshooting
- Chrome not found: install Google Chrome and ensure it can be launched by Selenium.
- Bot not responding: verify token, ensure your machine can reach Telegram, check console logs.
- Timeouts/rate limits: increase waits, use retries, or slow the scraping cadence.
