
import streamlit as st
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from openai import OpenAI
import concurrent.futures
import time
import re

client = OpenAI(api_key=st.secrets["openai_api_key"])
scraperapi_key = st.secrets["scraperapi_key"]

st.set_page_config(page_title="SEO Brief Generator", layout="wide")
st.title("SEO Brief Generator")

keyword = st.text_input("Target Keyword (optional)")
topic = st.text_input("Content Topic (optional)")
company_name = st.text_input("Company name")
company_url = st.text_input("Website URL (for internal links)")
sitemap_url = st.text_input("Sitemap.xml URL (for topic suggestions)")
manual_urls = st.text_area("Add reference URLs manually (optional, comma-separated)")

query = keyword or topic
if not query:
    st.warning("Please enter either a keyword or content topic.")
    st.stop()

def fetch_bing_urls(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(f"https://www.bing.com/search?q={query}", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        links = [a["href"] for a in soup.select("li.b_algo h2 a") if a["href"].startswith("http")]
        return links[:10]
    except:
        st.error("❌ SERP scraping failed. Bing may be blocking requests. Please enter reference URLs manually.")
        return []

def scrape_with_scraperapi(url, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            full_url = f"http://api.scraperapi.com?api_key={scraperapi_key}&url={url}"
            r = requests.get(full_url, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            title = soup.title.string.strip() if soup.title else ""
            meta = soup.find("meta", attrs={"name": "description"})
            meta_desc = meta["content"].strip() if meta and "content" in meta.attrs else ""
            headings = []
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                text = tag.get_text(strip=True)
                if text:
                    text = re.sub(r'[:\-]', '', text)
                    headings.append(f"{tag.name.upper()}: {text}")
            return {"url": url, "title": title, "meta": meta_desc, "headings": headings}
        except:
            attempt += 1
            time.sleep(2)
    return None

def batch_scrape(urls):
    scraped_pages = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_url = {executor.submit(scrape_with_scraperapi, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if result:
                scraped_pages.append(result)
    return scraped_pages

def parse_sitemap_topics(sitemap_url):
    try:
        r = requests.get(sitemap_url, timeout=10)
        tree = ET.fromstring(r.content)
        urls = [elem[0].text for elem in tree.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")]
        topics = [urlparse(url).path.strip("/").replace("-", " ").title() for url in urls if url]
        return list(set(topics))[:15]
    except:
        return []

def get_serp_insight(page):
    title = page.get("title", "").strip()
    meta = page.get("meta", "").strip()
    headings = page.get("headings", [])

    if not title and not meta and not headings:
        return {"tldr": "❌ Not enough usable content."}

    prompt = f"""
You are an SEO strategist.

Analyze the following page and give:
1. TLDR (1–2 lines)
2. Context (What this page covers and how)
3. Unique hook or angle

Title: {title}
Meta: {meta}
Headings:
{chr(10).join(headings)}
"""

    try:
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        raw = res.choices[0].message.content.strip()
        return {"tldr": raw}
    except Exception as e:
        return {"tldr": f"❌ OpenAI error: {e}"}

# --- Execution Logic ---

if query and company_name and company_url:
    if "urls" not in st.session_state:
        scraped_urls = fetch_bing_urls(query)
        if manual_urls:
            scraped_urls += [url.strip() for url in manual_urls.split(",") if url.strip()]
        scraped_urls = list(dict.fromkeys(scraped_urls))  # remove duplicates
        st.session_state["urls"] = scraped_urls

    if st.session_state["urls"]:
        st.markdown("### 🔗 Top SERP + Reference URLs")
        for u in st.session_state["urls"]:
            st.markdown(f"- [{u}]({u})")

        confirmed = st.checkbox("✅ I’ve reviewed the URLs. Proceed to scrape content.", key="confirm_urls")

        if confirmed and "scraped" not in st.session_state:
            with st.spinner("🔍 Scraping all pages in parallel..."):
                st.session_state["scraped"] = batch_scrape(st.session_state["urls"])

    scraped = st.session_state.get("scraped", [])
    sitemap_topics = parse_sitemap_topics(sitemap_url) if sitemap_url else []

    if scraped and "insights" not in st.session_state:
        with st.spinner("📊 Generating insights from scraped content..."):
            st.session_state["insights"] = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(get_serp_insight, p): p for p in scraped}
                for future in concurrent.futures.as_completed(futures):
                    page = futures[future]
                    insight = future.result()
                    st.session_state["insights"].append({
                        "url": page["url"],
                        "title": page["title"],
                        "meta": page["meta"],
                        "headings": page["headings"],
                        "tldr": insight.get("tldr", "")
                    })

    if "insights" in st.session_state:
        st.markdown("### 🔍 SERP Insights")
        for p in st.session_state["insights"]:
            st.markdown(f"**URL:** [{p['url']}]({p['url']})")
            st.markdown(f"**Title:** {p['title']}")
            st.markdown(f"**Meta:** {p['meta']}")
            st.markdown("**Headings (Document Flow):**")
            for h in p["headings"]:
                indent = "  " if h.startswith("H4") else " " if h.startswith("H3") else ""
                st.markdown(f"{indent}- {h}")
            st.markdown(f"**Insight:** {p['tldr']}")
            st.markdown("---")
