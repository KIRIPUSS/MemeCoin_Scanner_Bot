from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time


def scrape_solscan_holders(token_address):
    url = f"https://solscan.io/token/{token_address}#holders"
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    time.sleep(5)

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
    )

    table = driver.find_element(By.CSS_SELECTOR, "table")
    headers = [th.text.strip() for th in table.find_elements(By.TAG_NAME, "th")]
    print(f"\nHeaders: {headers}\n")

    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    holders = []

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        data = [col.text.strip() for col in cols]
        holders.append(data)

    print(f"Found {len(holders)} holders:\n")
    for holder in holders:
        print(holder)

    driver.quit()

    # Extract max percentage
    max_percent = 0.0
    for holder in holders:
        perc_str = holder[4]  # 'Percentage' column
        try:
            perc = float(perc_str.replace('%', '').replace(',', '').strip())
            if perc > max_percent:
                max_percent = perc
        except Exception:
            continue

    return max_percent if max_percent > 0 else None

