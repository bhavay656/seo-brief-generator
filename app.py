import streamlit as st
import requests
import aiohttp
import asyncio
import openai
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from collections import defaultdict
import time
import graphviz

st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")

st.title("SEO Content Brief Generator")
st.caption("Generate detailed SEO briefs based on real SERPs, heading flows, schemas, and keyword clustering.")

openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (e.g., yourcompany.com)")
sitemap_urls = st.text_input("Enter one or multiple Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

# ------------------ URL Fetcher ------------------ #
def fetch_bing_urls(keyword):
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = []
    retries = 3
    for attempt in range(retries):
        try:
            search_url = f"https://www.bing.com/search?q={'+'.join(keyword.split())}&count=20"
            response = requests.get(search_url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")
            seen = set()
            for tag in soup.select("li.b_algo h2 a"):
                href = tag.get("href")
                domain = urlparse(href).netloc
                if domain and domain not in seen and 'bing.com' not in href:
                    seen.add(domain)
                    urls.append(href)
            if len(urls) >= 5:
                return urls[:10]
        except Exception:
            time.sleep(2)
    return urls[:10]

# ------------------ Async Scraper ------------------ #
async def scrape_url(session, url, scraperapi_key, fallback=False):
    try:
        final_url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url={url}&render=true" if fallback else url
        async with session.get(final_url, timeout=60) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            title = soup.title.string.strip() if soup.title else "N/A"
            meta = ""
            for tag in soup.find_all("meta"):
                if tag.get("name") == "description" or tag.get("property") == "og:description":
                    meta = tag.get("content", "")
                    break
            headings = [f"{tag.name.upper()}: {tag.get_text(strip=True)}" for tag in soup.find_all(["h1", "h2", "h3", "h4"])]
            schemas = []
            if 'FAQPage' in html:
                schemas.append("FAQPage")
            if 'WebPage' in html:
                schemas.append("WebPage")
            if 'ItemList' in html:
                schemas.append("ItemList")
            if 'BlogPosting' in html:
                schemas.append("BlogPosting")
            if 'QAPage' in html:
                schemas.append("QAPage")
            return {"url": url, "title": title, "meta": meta, "headings": headings, "schemas": schemas}
    except:
        if not fallback:
            return await scrape_url(session, url, scraperapi_key, fallback=True)
        return {"url": url, "error": "Failed after retries"}

async def scrape_all(urls, scraperapi_key):
    results = []
    batch_size = 3
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            tasks = [scrape_url(session, url, scraperapi_key) for url in batch]
            results.extend(await asyncio.gather(*tasks))
            st.success(f"Scraped {len(results)} URLs so far...")
            time.sleep(2)
    return results

# ------------------ Brief Generator ------------------ #
def generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url):
    prompt = f"""
You are an expert SEO content strategist.

Input Keyword: "{keyword}"
Company Name: "{company_name}"
Company URL: "{company_url}"
Sitemap URLs: "{sitemap_urls}"

Below are SERP competitor details extracted (titles, meta descriptions, headings, schemas):

{headings_all}

Return the final response in this exact format:
1. For each URL: show
   - URL
   - Page Title
   - Meta Description
   - Heading Flow (document order)
   - Schemas Detected
   - Summary for Writer (what this page covers and unique angle)
2. After all URLs, give:
   - Primary & Secondary Keywords
   - NLP/Semantic Keyword Suggestions
   - Keyword Clusters (organized thematically)
   - Suggested Heading Structure in document flow (H1 > H2 > H3)
   - Under each heading: a short writer instruction
   - Internal Linking Suggestions from sitemap domain
   - External Neutral Linking Ideas
   - Schema Types with explanation
   - SERP Differentiation Suggestions
   - Visual Mindmap (use text-based structure with bullets/sub-bullets, not Mermaid or code block)

Formatting Rules:
- No markdown or emojis
- Use white background visual style (no `st.code`, `st.markdown` with backticks)
- All sections should be skim-friendly, use bullet lists and spacing
- Each URL detail block must be clearly separated from brief
"""
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# ------------------ App Logic ------------------ #
if st.button("Generate SEO Brief"):
    if openai_api_key and scraperapi_key and company_url and keyword:
        with st.spinner("Fetching Top 10 Organic URLs from Bing..."):
            bing_urls = fetch_bing_urls(keyword)
            if len(bing_urls) < 5:
                st.error("Failed to fetch minimum 5 organic URLs. Try again.")
                st.stop()
            st.success(f"Fetched {len(bing_urls)} URLs.")
            for idx, link in enumerate(bing_urls):
                st.markdown(f"{idx+1}. [{link}]({link})")

        with st.spinner("Scraping URLs content..."):
            results = asyncio.run(scrape_all(bing_urls, scraperapi_key))

        headings_all = ""
        failed = []
        for res in results:
            if 'error' not in res:
                headings_all += f"\nURL: {res['url']}\nTitle: {res['title']}\nMeta: {res['meta']}\nSchemas: {', '.join(res['schemas'])}\n"
                for h in res['headings']:
                    headings_all += f"- {h}\n"
                headings_all += "\n"
            else:
                failed.append(res['url'])

        with st.spinner("Generating Brief using OpenAI..."):
            full_brief = generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url)

        st.subheader("Generated Full SEO Content Brief")
        st.markdown(full_brief)

        if failed:
            st.error("Some URLs failed:")
            for url in failed:
                st.markdown(f"- {url}")
    else:
        st.error("Please fill all required fields!")
