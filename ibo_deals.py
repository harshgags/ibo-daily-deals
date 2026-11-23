from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

URLS = [
    "https://ibo.com",
    "https://ibo.com",
    "https://ibo.com"
]

def fetch_top_deals():
    deals = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        for url in URLS:
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                
                cards = page.query_selector_all("a[href*='/p/']")
                for card in cards[:12]:
                    text = card.inner_text()
                    href = card.get_attribute("href")
                    if "%" in text:
                        lines = [line.strip() for line in text.split("\n") if line.strip()]
                        discount_line = next((l for l in lines if "%" in l), "0%")
                        pct = int(''.join(filter(str.isdigit, discount_line.split("%"))) or 0)
                        title = max(lines, key=len)
                        full_link = f"https://ibo.com{href}" if href.startswith("/") else href
                        if pct > 0:
                            deals.append((pct, title, discount_line, full_link))
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                    
        browser.close()

    unique_deals = {d: d for d in deals}.values()
    return sorted(unique_deals, key=lambda x: x, reverse=True)[:5]

def update_readme(deals):
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist).strftime("%d %b %Y, %I:%M %p IST")
    
    md = f"# 🔥 Daily Top 5 IBO Deals\n\n*Last updated: {now}*\n\n"
    if not deals:
        md += "No high-discount deals found today (or site blocked cloud request).\n"
    else:
        md += "| # | Discount | Product | Link |\n|---|---|---|---|\n"
        for i, (pct, title, disc, link) in enumerate(deals, 1):
            clean_title = title.replace("|", "-")
            md += f"| {i} | **{disc}** | {clean_title} | [View on IBO]({link}) |\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(md)

if __name__ == "__main__":
    update_readme(fetch_top_deals())
