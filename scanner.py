import time
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dextools_scraper import is_liquidity_locked

# === Cache ===
CACHE = {}
CACHE_TTL_SECONDS = 300
FREEZE_CACHE = {}
MINT_CACHE = {}

# === Validation adresse Solana ===
def is_valid_solana_address(addr):
    return bool(re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", addr))

# === Récupération JSON Dexscreener ===
def safe_get_json(url, max_retries=3, timeout=10):
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
        except requests.RequestException:
            pass
        time.sleep(1)
    return None

def get_dexscreener_data(token_address):
    url = f"https://api.dexscreener.com/latest/dex/search?q={token_address}"
    return safe_get_json(url)

# === Scraping Freeze Authority via BeautifulSoup ===
def scrape_freeze_authority(token_address):
    cached = FREEZE_CACHE.get(token_address)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    url = f"https://solscan.io/token/{token_address}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Failed to fetch Solscan page: status {resp.status_code}")
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        freeze_auth = None
        freeze_label_div = soup.find("div", string="Freeze Authority:")
        if freeze_label_div:
            parent_div = freeze_label_div.find_parent("div", class_="flex gap-1 flex-row items-center justify-start flex-wrap")
            if parent_div:
                children = parent_div.find_all("div", recursive=False)
                for i, child in enumerate(children):
                    if child == freeze_label_div and i + 1 < len(children):
                        text = children[i + 1].text.strip()
                        freeze_auth = text if text != "N/A" else None
                        break
        FREEZE_CACHE[token_address] = (time.time(), freeze_auth)
        return freeze_auth
    except Exception as e:
        print(f"❌ Exception during freeze authority scraping: {e}")
        return None

# === Scraping Mint Authority via BeautifulSoup ===
def scrape_mint_authority(token_address):
    cached = MINT_CACHE.get(token_address)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    url = f"https://solscan.io/token/{token_address}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Failed to fetch Solscan page: status {resp.status_code}")
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        mint_auth = None
        mint_label_div = soup.find("div", string="Mint Authority:")
        if mint_label_div:
            parent_div = mint_label_div.find_parent("div", class_="flex gap-1 flex-row items-center justify-start flex-wrap")
            if parent_div:
                children = parent_div.find_all("div", recursive=False)
                for i, child in enumerate(children):
                    if child == mint_label_div and i + 1 < len(children):
                        text = children[i + 1].text.strip()
                        mint_auth = text if text != "N/A" else None
                        break
        MINT_CACHE[token_address] = (time.time(), mint_auth)
        return mint_auth
    except Exception as e:
        print(f"❌ Exception during mint authority scraping: {e}")
        return None

# === Analyse du token ===
def analyze_token(token_address, liquidity_locked=False, return_data_only=False):
    token_address = token_address.strip()
    if not is_valid_solana_address(token_address):
        return None if return_data_only else "❌ Invalid address"

    cached = CACHE.get(token_address)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1] if not return_data_only else None

    dexs_data = get_dexscreener_data(token_address)
    if not dexs_data or not dexs_data.get("pairs"):
        return None if return_data_only else "❌ No Dexscreener data"

    freeze_auth = scrape_freeze_authority(token_address)
    mint_auth = scrape_mint_authority(token_address)

    pair = dexs_data["pairs"][0]
    name = pair.get("baseToken", {}).get("name", "Unknown")
    symbol = pair.get("baseToken", {}).get("symbol", "???")
    price_usd = float(pair.get("priceUsd", 0))
    market_cap = pair.get("fdv", 0)
    liquidity = pair.get("liquidity", {}).get("usd", 0)
    volume_24h = pair.get("volume", {}).get("h24", 0)
    txns = pair.get("txns", {}).get("h1", {})
    buys = txns.get("buys", 0)
    sells = txns.get("sells", 0)
    url = pair.get("url", "N/A")
    created_ts = pair.get("pairCreatedAt")

    buy_sell_ratio = buys / sells if sells > 0 else (buys if buys > 0 else 0)
    honeypot_suspected = buys > 10 and sells == 0

    age_days = (time.time() - created_ts / 1000) / 86400 if created_ts else None

    safe_entry = (

        market_cap and 10_000 <= market_cap <= 300_000 and
        liquidity and 10_000 <= liquidity <= 200_000 and
        volume_24h and volume_24h >= 5_000 
        and sells > 0 and
        not honeypot_suspected and
        (age_days or 0) <= (30 / 1440) and
        freeze_auth is None and
        mint_auth is None and
        liquidity_locked
    )

    if return_data_only:
        reason = []
        if not market_cap or market_cap < 5_000: reason.append("Low MC")
        if liquidity < 1000: reason.append("Low Liquidity")
        if volume_24h < 500: reason.append("Low Volume")
        if sells == 0: reason.append("No sells")
        if honeypot_suspected: reason.append("Possible honeypot")
        if age_days and age_days > (1 / 24): reason.append("Too old")
        if freeze_auth is not None: reason.append("Has freeze authority")
        if not liquidity_locked: reason.append("Liquidity not locked")

        return {
            "token": f"{name} ({symbol})",
            "safe": safe_entry,
            "reason": ", ".join(reason) if not safe_entry else None,
            "report": None
        }

    report = (
        f"📛 Token: {name} ({symbol})\n"
        f"💵 Price: ${price_usd:,.8f}\n"
        f"💰 Market Cap: ${market_cap:,.2f}\n"
        f"💧 Liquidity: ${liquidity:,.2f}\n"
        f"🔒 Liquidity Locked: {'Yes' if liquidity_locked else 'No'}\n"
        f"📊 Volume (24h): ${volume_24h:,.2f}\n"
        f"🛒 Buys: {buys} | 🏷️ Sells: {sells} | ⚖️ Ratio: {buy_sell_ratio:.2f}\n"
        f"🔐 Freeze Authority: {freeze_auth or 'N/A'}\n"
        f"🔑 Mint Authority: {mint_auth or 'N/A'}\n"
        f"🗓️ Age: {age_days:.2f} days\n"
        f"🔗 Trade link: {url}\n"
        f"⏰ Fetched: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"✅ Safe: {'for entry (no obvious scam flags)' if safe_entry else 'No'}"
    )

    CACHE[token_address] = (time.time(), report)
    return report

# === Scraping Dexscreener ===
def scrape_dexscreener_token_addresses(max_tokens=10):
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options)
    wait = WebDriverWait(driver, 15)
    base_url = "https://dexscreener.com"
    trending_url = "https://dexscreener.com/solana/raydium?rankBy=pairAge&order=asc"

    addresses = []
    seen = set()

    try:
        driver.get(trending_url)
        time.sleep(5)

        token_links = wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "a.ds-dex-table-row.ds-dex-table-row-new, a.ds-dex-table-row.ds-dex-table-row-top")
        ))

        token_urls = []
        for link in token_links[:max_tokens]:
            href = link.get_attribute("href")
            full_url = base_url + href if href.startswith("/") else href
            token_urls.append(full_url)

        print(f"🔗 {len(token_urls)} liens de tokens extraits")

        for i, token_url in enumerate(token_urls):
            try:
                print(f"\n➡️ Scraping token {i+1}: {token_url}")
                driver.get(token_url)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[title='Copy']")))

                locked = is_liquidity_locked(driver)
                print(f"🔒 Liquidity Locked: {locked}")

                page_html = driver.page_source
                match = re.search(r"[1-9A-HJ-NP-Za-km-z]{32,44}", page_html)
                if match:
                    address = match.group(0)
                    if address not in seen:
                        seen.add(address)
                        addresses.append({"address": address, "locked": locked})
                        print(f"✅ Adresse mint trouvée: {address}")
                    else:
                        print("⚠️ Adresse dupliquée")
                else:
                    print("❌ Aucune adresse mint trouvée sur la page")

                time.sleep(2)

            except Exception as e:
                print(f"❌ Erreur avec {token_url}: {e}")
                continue

    finally:
        driver.quit()

    print(f"\n🎯 Total: {len(addresses)} adresses uniques récupérées")
    return addresses

# === Pipeline complet : scrape + analyse ===
def run_full_pipeline(max_scrape=10, max_results=5):
    addresses_info = scrape_dexscreener_token_addresses(max_scrape)
    results = []

    print("\n🔎 Analyse des tokens extraits...\n")

    for idx, info in enumerate(addresses_info, 1):
        addr = info["address"]
        locked = info["locked"]

        try:
            analysis = analyze_token(addr, liquidity_locked=locked, return_data_only=True)
            if analysis and analysis["safe"]:
                print(f"✅ {idx}. {analysis['token']} → SAFE (Locked: {locked})")
                full_report = analyze_token(addr, liquidity_locked=locked)
                results.append({"address": addr, "token": analysis["token"], "report": full_report})
            else:
                reason = analysis["reason"] if analysis else "Pas d'infos"
                print(f"❌ {idx}. {addr} → Non safe — {reason}")
        except Exception as e:
            print(f"⚠️ Erreur analyse {addr}: {e}")

        if len(results) >= max_results:
            break

    print(f"\n✅ Tokens safe trouvés: {len(results)}")
    return results

# === Main ===
if __name__ == "__main__":
    safe_tokens = run_full_pipeline(max_scrape=10, max_results=5)

    print("\n📋 Rapports finaux des tokens safe:")
    for token in safe_tokens:
        print("\n" + "=" * 60)
        print(token["report"])
