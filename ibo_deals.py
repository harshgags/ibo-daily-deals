from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

PINCODE = "560048"

URLS = [
    "https://ibo.com",
    "https://ibo.com",
    "https://ibo.com",
    "https://ibo.com"
]

def set_pincode(page, pincode, debug_info):
    try:
        # Click the 'Deliver to' location selector in the header
        deliver_btn = page.locator("text=/Deliver to|Change Location|560/i").first
        if deliver_btn.is_visible(timeout=5000):
            deliver_btn.click()
            page.wait_for_timeout(1500)
            
            # Fill the 6-digit pincode input box
            pin_input = page.locator("input[placeholder*='pin' i], input[maxlength='6'], input[type='tel']").first
            if pin_input.is_visible(timeout=4000):
                pin_input.fill(pincode)
                page.wait_for_timeout(1000)
                
                # Click Apply/Check or press Enter
                apply_btn = page.locator("button:has-text('Apply'), button:has-text('Check'), button:has-text('Submit')").first
                if apply_btn.is_visible(timeout=2000):
                    apply_btn.click()
                else:
                    pin_input.press("Enter")
                page.wait_for_timeout(3000)
                debug_info.append(f"Pincode set to **{pincode}**")
                return
        debug_info.append("Pincode prompt not found or already set")
    except Exception as e:
        debug_info.append(f"Pincode setup note: {e}")

def fetch_top_deals():
    deals = []
    debug_info = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata"
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            page.goto("https://ibo.com", timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            set_pincode(page, PINCODE, debug_info)
        except Exception as e:
            debug_info.append(f"Home error: {e}")

        for url in URLS:
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(7000)
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(2000)

                title_tag = page.title()
                links = page.query_selector_all("a[href*='/p/']")
                debug_info.append(f"`{url.split('.com')[1]}` → Title: *{title_tag}* | Products found: {len(links)}")

                for link_el in links[:15]:
                    href = link_el.get_attribute("href")
                    card_text = link_el.evaluate("""el => {
                        let p = el;
                        for (let i = 0; i < 4; i++) {
                            if (p.parentElement && p.parentElement.innerText.includes('%')) {
                                p = p.parentElement;
                                break;
                            }
                            if (p.parentElement) p = p.parentElement;
                        }
                        return p.innerText;
                    }""")

                    if "%" in card_text:
                        lines = [l.strip() for l in card_text.split("\n") if l.strip()]
                        discount_line = next((l for l in lines if "%" in l), "0%")
                        digits = ''.join(filter(str.isdigit, discount_line.split("%")[0]))
                        pct = int(digits) if digits else 0
                        text_lines = [l for l in lines if "%" not in l and not l.startswith("₹")]
                        prod_name = max(text_lines, key=len) if text_lines else "IBO Product"
                        full_link = f"https://ibo.com{href}" if href.startswith("/") else href
                        if pct > 0:
                            deals.append((pct, prod_name, discount_line, full_link))
            except Exception as e:
                debug_info.append(f"Error on {url}: {e}")

        browser.close()

    unique_deals = {d[3]: d for d in deals}.values()
    top_5 = sorted(unique_deals, key=lambda x: x[0], reverse=True)[:5]
    return top_5, debug_info

def update_readme(deals, debug_info):
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist).strftime("%d %b %Y, %I:%M %p IST")

    md = f"# 🔥 Daily Top 5 IBO Deals (Pincode: {PINCODE})\n\n*Last updated: {now}*\n\n"
    if not deals:
        md += "No high-discount deals found today.\n"
    else:
        md += "| # | Discount | Product | Link |\n|---|---|---|---|\n"
        for i, (pct, title, disc, link) in enumerate(deals, 1):
            clean_title = title.replace("|", "-")
            md += f"| {i} | **{disc}** | {clean_title} | [View on IBO]({link}) |\n"

    md += "\n---\n### Run Diagnostics\n" + "\n".join(f"- {d}" for d in debug_info) + "\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(md)

if __name__ == "__main__":
    top_deals, logs = fetch_top_deals()
    update_readme(top_deals, logs)
