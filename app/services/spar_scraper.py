# spar_parser_v2.py
# Outputs: category, subcategory, product_name, product_image, product_price
# Strategy:
# 1) Capture ALL JSON from network and merge fields across nested objects.
# 2) Auto-crawl category/subcategory pages and scrape visible product cards as fallback.

from playwright.sync_api import sync_playwright
import csv, json, os, re, hashlib, time
from urllib.parse import urlparse

OUTPUT_CSV = "spar_products.csv"
DEBUG_DIR = "debug_responses"

# Keys to look for (very broad)
NAME_KEYS = {"name","title","productName","product_name","caption","label","fullName","displayName"}
PRICE_KEYS = {"price","currentPrice","salePrice","unitPrice","priceValue","amount","value","finalPrice"}
IMAGE_KEYS = {"image","imageUrl","imageURL","img","thumbnail","picture","photo","imageurl","image_src"}
CATEGORY_KEYS = {"category","categoryName","category_name","group","groupName","categoryTitle"}
SUBCATEGORY_KEYS = {"subcategory","subCategory","subcategoryName","sub_category_name","subGroup","subgroupName","subCategoryTitle"}

os.makedirs(DEBUG_DIR, exist_ok=True)

class RowSink:
    def __init__(self, path):
        self.f = open(path, "w", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        self.w.writerow(["category","subcategory","product_name","product_image","product_price"])
        self.seen = set()
        self.count = 0
    def add(self, cat, sub, name, image, price):
        key = (str(cat or ""), str(sub or ""), str(name or ""), str(image or ""), "" if price is None else f"{price}")
        if key in self.seen: return
        self.seen.add(key)
        self.w.writerow([cat or "", sub or "", name or "", image or "", price if price is not None else ""])
        self.count += 1
    def close(self):
        try: self.f.close()
        except: pass

def sanitize_filename(s):
    h = hashlib.md5(s.encode("utf-8", errors="ignore")).hexdigest()[:10]
    parsed = urlparse(s)
    base = (parsed.path.rsplit("/",1)[-1] or "resp").split("?")[0]
    base = re.sub(r"[^a-zA-Z0-9_.-]+","_", base)[:40] or "resp"
    return f"{base}_{h}.json"

def as_price(v):
    if v is None: return None
    if isinstance(v, (int,float)): return float(v)
    s = str(v)
    m = re.search(r"([0-9]+(?:[.,][0-9]{1,2})?)", s)
    if not m: return None
    return float(m.group(1).replace(",", "."))

def first_non_empty(d, keys):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, "", [], {}):
            return d[k]
    return None

def extract_items_merged(node, ctx, sink, depth=0, max_depth=20):
    """Walks JSON; merges context so name/price/image can come from different nested levels."""
    if depth > max_depth: return
    if isinstance(node, dict):
        # Update context with whatever we find at this level
        new_ctx = dict(ctx)
        for kset, label in (
            (CATEGORY_KEYS, "cat"),
            (SUBCATEGORY_KEYS, "sub"),
            (NAME_KEYS, "name"),
            (PRICE_KEYS, "price"),
            (IMAGE_KEYS, "image"),
        ):
            val = first_non_empty(node, kset)
            if val is not None:
                new_ctx[label] = val

        # If it looks like a product, emit
        name = new_ctx.get("name")
        price = as_price(new_ctx.get("price"))
        image = new_ctx.get("image")
        if name and (price is not None or image):
            sink.add(new_ctx.get("cat"), new_ctx.get("sub"), str(name).strip(), str(image or "").strip(), price)

        # Recurse
        for v in node.values():
            extract_items_merged(v, new_ctx, sink, depth+1, max_depth)

    elif isinstance(node, list):
        for v in node:
            extract_items_merged(v, ctx, sink, depth+1, max_depth)

def get_candidate_category_links(page):
    # Grab links that look like categories
    hrefs = page.evaluate("""
    Array.from(document.querySelectorAll('a[href]'))
      .map(a=>a.href)
      .filter(h=>/category|catalog|categories/i.test(h))
    """)
    # Dedupe while preserving order
    seen, out = set(), []
    for h in hrefs:
        if h not in seen:
            seen.add(h); out.append(h)
    return out[:100]  # hard cap

def auto_scroll(page, max_steps=30, pause_ms=600):
    last_h = page.evaluate("document.body.scrollHeight")
    steps = 0
    while steps < max_steps:
        page.mouse.wheel(0, 8000)
        page.wait_for_timeout(pause_ms)
        new_h = page.evaluate("document.body.scrollHeight")
        if new_h <= last_h: break
        last_h = new_h
        steps += 1

def dom_scrape_products(page, sink):
    # Try to read breadcrumbs for category/subcategory
    crumbs = page.evaluate("""
    (()=>{
      const parts = [];
      document.querySelectorAll('nav a, .breadcrumb a, [class*="crumb"] a, nav li, .breadcrumb li')
        .forEach(el=>{ const t=(el.textContent||'').trim(); if(t) parts.push(t); });
      return parts.filter(Boolean).slice(0,5);
    })()
    """)
    url = page.url
    segments = [s for s in urlparse(url).path.split("/") if s]
    cat_guess = (crumbs[1] if len(crumbs)>1 else None) or (segments[1] if len(segments)>1 else None)
    sub_guess = (crumbs[2] if len(crumbs)>2 else None) or (segments[2] if len(segments)>2 else None)

    items = page.evaluate(r"""
    (()=>{
      const seen = new Set();
      function getText(el){ return (el && (el.textContent||'').replace(/\s+/g,' ').trim()) || ''; }

      // Find candidate product containers by presence of a price (₾) in text
      const candidates = new Set();
      document.querySelectorAll('div,li,article,section').forEach(el=>{
        const txt = getText(el);
        if(/\d(?:[.,]\d{1,2})?\s*₾/.test(txt)){
          // also require an image or a title-ish element to reduce noise
          const img = el.querySelector('img');
          const titleEl = el.querySelector('[class*="name"],[class*="title"],h3,h4,.name,.title,[itemprop="name"]');
          if(img || titleEl){ candidates.add(el); }
        }
      });

      const out = [];
      candidates.forEach(el=>{
        // nearest image
        const imgEl = el.querySelector('img');
        let image = null;
        if(imgEl){
          image = imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || imgEl.getAttribute('srcset') || '';
          if(!image && imgEl.currentSrc) image = imgEl.currentSrc;
        }

        // name
        let nameEl = el.querySelector('[class*="name"],[class*="title"],h3,h4,.name,.title,[itemprop="name"]');
        let name = nameEl ? getText(nameEl) : (imgEl && imgEl.alt ? imgEl.alt.trim() : '');

        // price
        const txt = getText(el);
        const m = txt.match(/([0-9]+(?:[.,][0-9]{1,2})?)\s*₾/);
        let price = m ? m[1].replace(',', '.') : '';

        if(name && (price || image)){
          const key = name + '|' + image + '|' + price;
          if(!seen.has(key)){
            seen.add(key);
            out.push({name, image, price});
          }
        }
      });
      return out;
    })()
    """)
    for it in items:
        price = as_price(it.get("price"))
        sink.add(cat_guess, sub_guess, it.get("name"), it.get("image"), price)

def run():
    sink = RowSink(OUTPUT_CSV)
    captured_urls = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()

        def on_response(resp):
            try:
                ct = (resp.headers.get("content-type") or "").lower()
                url = resp.url
                # We try to parse ANY JSON-ish content
                if "json" in ct or "graphql" in ct or "application/vnd" in ct:
                    body = resp.body()
                    if not body: return
                    text = body.decode("utf-8", errors="ignore").strip()
                    if not text.startswith("{") and not text.startswith("["):
                        return
                    # Save for debugging
                    if url not in captured_urls:
                        captured_urls.add(url)
                        fname = os.path.join(DEBUG_DIR, sanitize_filename(url))
                        with open(fname, "w", encoding="utf-8") as f:
                            f.write(text)
                    data = json.loads(text)
                    extract_items_merged(data, {}, sink)
            except Exception:
                pass

        page.on("response", on_response)

        page.goto("https://sparonline.ge/", wait_until="domcontentloaded")
        print("\n==== Steps ====")
        print("1) In the opened browser, choose a deliverable address so the catalog appears.")
        print("2) Then come back here and press Enter. The script will crawl categories automatically.")
        print("===============")
        try: input("Press Enter when the address is set...")
        except KeyboardInterrupt: pass

        # Discover category links from the homepage (after address)
        cat_links = get_candidate_category_links(page)
        if not cat_links:
            # try clicking 'Catalog' button if present
            try:
                page.click("text=Catalog", timeout=2000)
                time.sleep(1)
                cat_links = get_candidate_category_links(page)
            except Exception:
                pass

        if not cat_links:
            print("No category links detected from the homepage. Scraping current page only as fallback...")
            auto_scroll(page)
            dom_scrape_products(page, sink)
        else:
            print(f"Found {len(cat_links)} category-like links. Crawling...")
            for i, link in enumerate(cat_links, 1):
                try:
                    print(f"Visiting [{i}/{len(cat_links)}]: {link}")
                    page.goto(link, wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    continue
                # Scroll to load items (and trigger network)
                auto_scroll(page)
                # DOM fallback on this page too
                dom_scrape_products(page, sink)
                print(f"[{i}/{len(cat_links)}] {page.url} → total rows: {sink.count}")

        ctx.close()
        browser.close()
        sink.close()

    print(f"\nSaved: {OUTPUT_CSV}  (rows: {sink.count})")
    print(f"Debug JSON saved under: {DEBUG_DIR}/  (share a sample if mapping still misses)")

if __name__ == "__main__":
    run()
