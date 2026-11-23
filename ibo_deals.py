import re
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

PINCODE = "560048"
MIN_PRICE = 40  # Ignore items selling below ₹50

TARGET_CATEGORIES = [
    "Power Tools",
    "Hand Tools",
    "Drill Driver",
    "Small Domestic Appliances",
    "LED Bulb",
    "Switches and Sockets"
]

def set_pincode(page, pincode, debug_info):
    try:
        clicked = page.evaluate("""() => {
            const els = Array.from(document.querySelectorAll('div, span, button, a'));
            const target = els.find(e => e.innerText && (e.innerText.includes('Change Location') || e.innerText.includes('Deliver to')) && e.innerText.length < 40);
            if (target) { target.click(); return true; }
            return false;
        }""")
        if clicked:
            page.wait_for_timeout(2000)
            pin_input = page.locator("input:visible").first
            if pin_input.is_visible(timeout=4000):
                pin_input.fill(pincode)
                page.wait_for_timeout(1500)
                pin_input.press("Enter")
                page.wait_for_timeout(2000)
                btn = page.locator("button:has-text('Apply'), button:has-text('Check'), button:has-text('Save'), button:has-text('Confirm')").first
                if btn.is_visible(timeout=1500):
                    btn.click()
                page.wait_for_timeout(3000)
                debug_info.append(f"Pincode set to **{pincode}**")
                return
        debug_info.append("Pincode using default catalog")
    except Exception as e:
        debug_info.append(f"Pincode note: {e}")

def sort_by_discount(page):
    try:
        sort_el = page.locator("text=/Sort by|Popularity|Relevance|Featured/i").first
        if sort_el.is_visible(timeout=3000):
            sort_el.click()
            page.wait_for_timeout(1200)
            disc_opt = page.locator("text=/Discount.*High|High to Low/i").first
            if disc_opt.is_visible(timeout=3000):
                disc_opt.click()
                page.wait_for_timeout(4000)
                return True
    except Exception:
        pass
    return False

def parse_prices_and_discount(card_text):
    pct_match = re.search(r'(\d{1,2})\s*%', card_text)
    explicit_pct = int(pct_match.group(1)) if pct_match else 0

    raw_nums = re.findall(r'₹\s*([\d,]+(?:\.\d+)?)', card_text)
    nums = [float(n.replace(',', '')) for n in raw_nums if float(n.replace(',', '')) > 0]

    calc_pct = 0
    sell_price = 0
    price_str = "-"
    if len(nums) >= 2:
        sell_price, mrp = min(nums), max(nums)
        if mrp > sell_price:
            calc_pct = round(((mrp - sell_price) / mrp) * 100)
            price_str = f"₹{int(sell_price):,} (MRP ₹{int(mrp):,})"
        else:
            price_str = f"₹{int(sell_price):,}"
    elif len(nums) == 1:
        sell_price = nums[0]
        price_str = f"₹{int(sell_price):,}"

    return max(explicit_pct, calc_pct), sell_price, price_str

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

        page.goto("https://ibo.com", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        set_pincode(page, PINCODE, debug_info)

        category_urls = []
        for cat in TARGET_CATEGORIES:
            # Exact text match skips parent menus like "Power & Hand Tools"
            link = page.locator(f"a >> text='{cat}'").first
            if link.count() == 0:
                link = page.locator(f"a:has-text('{cat}')").first
            href = link.get_attribute("href") if link.count() > 0 else None
            if href:
                full = f"https://ibo.com{href}" if href.startswith("/") else href
                category_urls.append((cat, full))

        for cat_name, url in category_urls:
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                sorted_ok = sort_by_discount(page)
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(2000)

                links = page.query_selector_all("a[href*='/p/']")
                debug_info.append(f"**{cat_name}** → Sorted: {sorted_ok} | Scanned: {len(links)}")

                for link_el in links[:20]:
                    href = link_el.get_attribute("href")
                    card_text = link_el.evaluate("""el => {
                        let p = el;
                        for (let i = 0; i < 6; i++) {
                            if (p.parentElement) {
                                const txt = p.parentElement.innerText || '';
                                if (txt.length > 500) break;
                                p = p.parentElement;
                                if (txt.includes('₹')) break;
                            }
                        }
                        return p.innerText;
                    }""")

                    pct, sell_price, price_str = parse_prices_and_discount(card_text)
                    lines = [l.strip() for l in card_text.split("\n") if l.strip()]
                    text_lines = [
                        l for l in lines
                        if "%" not in l and "₹" not in l and "add to cart" not in l.lower() and len(l) > 8
                    ]
                    prod_name = max(text_lines, key=len) if text_lines else "IBO Product"
                    full_link = f"https://ibo.com{href}" if href.startswith("/") else href

                    if 10 <= pct <= 95 and sell_price >= MIN_PRICE:
                        deals.append((pct, prod_name, f"{pct}% OFF", price_str, full_link))
            except Exception as e:
                debug_info.append(f"Error on {cat_name}: {e}")

        browser.close()

    unique_deals = {d[4]: d for d in deals}.values()
    top_5 = sorted(unique_deals, key=lambda x: x[0], reverse=True)[:5]
    return top_5, debug_info

def update_readme(deals, debug_info):
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist).strftime("%d %b %Y, %I:%M %p IST")

    md = f"# 🔥 Daily Top 5 IBO Deals (Pincode: {PINCODE} | Min ₹{MIN_PRICE})\n\n*Last updated: {now}*\n\n"
    if not deals:
        md += f"No high-discount deals above ₹{MIN_PRICE} found today.\n"
    else:
        md += "| # | Discount | Product | Price | Link |\n|---|---|---|---|---|\n"
        for i, (pct, title, disc, price, link) in enumerate(deals, 1):
            clean_title = title.replace("|", "-")
            md += f"| {i} | **{disc}** | {clean_title} | {price} | [View on IBO]({link}) |\n"

    md += "\n---\n### Run Diagnostics\n" + "\n".join(f"- {d}" for d in debug_info) + "\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(md)

if __name__ == "__main__":
    top_deals, logs = fetch_top_deals()
    update_readme(top_deals, logs)
