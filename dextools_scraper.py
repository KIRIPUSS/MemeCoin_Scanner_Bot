import time
import re
import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


CACHE = {}
CACHE_TTL_SECONDS = 300


def is_liquidity_locked(driver):
    try:
        return bool(driver.find_elements(By.CSS_SELECTOR, ".custom-f1j64i svg"))
    except Exception:
        return False


def scrape_dexscreener_pair_urls(max_tokens=10):
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    
    wait = WebDriverWait(driver, 20)
    base_url = "https://dexscreener.com"
    trending_url = "https://dexscreener.com/solana?rankBy=pairAge&order=asc"

    addresses = []
    seen = set()

    try:
        driver.get(trending_url)
        time.sleep(5)

        # Instead of storing token_links once, fetch fresh inside the loop
        token_urls = []
        for i in range(max_tokens):
            try:
                token_links = wait.until(EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "a.ds-dex-table-row")
                ))
                link = token_links[i]
                href = link.get_attribute("href")
                if href:
                    full_url = base_url + href if href.startswith("/") else href
                    token_urls.append(full_url)
            except Exception as e:
                print(f"⚠️ Skipping link {i+1} due to error or index out of range: {e}")
                break

        print(f"🔗 {len(token_urls)} token URLs collected")

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
                        print(f"✅ Mint Address Found: {address}")
                    else:
                        print("⚠️ Duplicate Address")
                else:
                    print("❌ No Mint Address Found on Page")

                time.sleep(2)

            except Exception as e:
                print(f"❌ Error scraping {token_url}: {e}")
                continue

    finally:
        driver.quit()

    print(f"\n🎯 Total unique mint addresses: {len(addresses)}")
    return addresses


def scrape_freeze_authority(token_address):
    cached = CACHE.get(token_address)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    url = f"https://solscan.io/token/{token_address}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"❌ Solscan HTTP {response.status_code} for {token_address}")
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        freeze_auth = "N/A"
        freeze_label_div = soup.find("div", string="Freeze Authority:")
        if freeze_label_div:
            parent_div = freeze_label_div.find_parent("div", class_="flex gap-1 flex-row items-center justify-start flex-wrap")
            if parent_div:
                children = parent_div.find_all("div", recursive=False)
                for i, child in enumerate(children):
                    if child == freeze_label_div and i + 1 < len(children):
                        freeze_auth = children[i + 1].text.strip()
                        break
        CACHE[token_address] = (time.time(), freeze_auth)
        return freeze_auth
    except Exception as e:
        print(f"❌ Error scraping Freeze Authority for {token_address}: {e}")
        return None


# === MAIN ===
if __name__ == "__main__":
    max_tokens_to_scrape = 10
    mint_addresses = scrape_dexscreener_pair_urls(max_tokens=max_tokens_to_scrape)

    print("\n🧾 Fetching Freeze Authorities:\n")
    for token_info in mint_addresses:
        address = token_info["address"]
        locked = token_info["locked"]
        freeze_auth = scrape_freeze_authority(address)
        print(f"Token: {address} | Liquidity Locked: {'Yes' if locked else 'No'} | Freeze Authority: {freeze_auth}")
