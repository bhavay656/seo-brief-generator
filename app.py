import streamlit as st
import requests
import aiohttp
import asyncio
import openai
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time

st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")
st.title("SEO Content Brief Generator")

# Inputs
openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (example.com)")
sitemap_urls = st.text_input("Enter Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter Target Keyword")

# Fetch URLs from Bing
def fetch_bing_urls(keyword):
    headers = {"User-Agent": "Mozilla/5.0"}
    urls, seen = [], set()
    search_url = f"https://www.bing.com/search?q={'+'.join(keyword.split())}&count=20"
    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup.select("li.b_algo h2 a"):
            href = tag.get("href")
            domain = urlparse(href).netloc
            if domain and domain not in seen and "bing.com" not in href:
                seen.add(domain)
                urls.append(href)
            if len(urls) >= 10:
                break
    except Exception:
        pass
    return urls

# Async URL scraper
async def scrape_url(session, url, scraperapi_key, fallback=False):
    try:
        target_url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url={url}&render=true" if fallback else url
        async with session.get(target_url, timeout=60) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.string.strip() if soup.title else "N/A"
            meta = ""
            for tag in soup.find_all("meta"):
                if tag.get("name") == "description" or tag.get("property") == "og:description":
                    meta = tag.get("content", "")
                    break
            headings = [f"{tag.name.upper()}: {tag.get_text(strip=True)}" for tag in soup.find_all(["h1", "h2", "h3"])]
            schemas = []
            if "FAQPage" in html:
                schemas.append("FAQPage")
            if "ItemList" in html:
                schemas.append("ItemList")
            if "BlogPosting" in html:
                schemas.append("BlogPosting")
            if "WebPage" in html:
                schemas.append("WebPage")
            return {"url": url, "title": title, "meta": meta, "schemas": schemas, "headings": headings}
    except:
        if not fallback:
            return await scrape_url(session, url, scraperapi_key, fallback=True)
        return {"url": url, "error": "Failed after retries"}

async def scrape_all(urls, scraperapi_key):
    results = []
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(urls), 3):
            batch = urls[i:i+3]
            results.extend(await asyncio.gather(*[scrape_url(session, u, scraperapi_key) for u in batch]))
            st.success(f"Scraped {len(results)} URLs so far...")
            time.sleep(1)
    return results

# SEO Brief generation
def generate_brief(keyword, source_details, sitemap_urls, company_name, company_url):
    prompt = f"""
You are a senior SEO Content Strategist.

Primary Keyword: {keyword}
Sitemap: {sitemap_urls}
Company: {company_name} ({company_url})

Competitor Observations:
{source_details}

Prepare a full SEO content brief based ONLY on these observations:
- Primary Keyword
- Secondary Keywords (from real patterns)
- NLP / Semantic SEO Suggestions
- Keyword Clusters
- Structured Heading Flow (H1, H2, H3)
    - After each heading: add Writer Context, TLDR, and Unique Angle
- Internal Link Opportunities (only from sitemap URLs, matching context)
- External Linking (suggest what to search, don't list competitor URLs)
- Detected Schema Types
- NO markdown formatting, NO emojis
- NO dilution: match the exact Search Intent (transactional if needed)

The brief must be skimmable, prescriptive for writers, and reflect the SERP search intent strictly.
"""
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# Main app logic
if st.button("Generate SEO Brief"):
    if openai_api_key and scraperapi_key and company_url and keyword:
        with st.spinner("Fetching top Bing URLs..."):
            urls = fetch_bing_urls(keyword)
            if len(urls) < 5:
                st.error("Failed to fetch enough URLs. Try again.")
                st.stop()
            st.success(f"Fetched {len(urls)} URLs.")
            for i, url in enumerate(urls):
                st.write(f"{i+1}. {url}")

        with st.spinner("Scraping URLs content..."):
            results = asyncio.run(scrape_all(urls, scraperapi_key))

        source_insights = ""
        failed = []
        for r in results:
            if "error" not in r:
                source_insights += (
                    f"\nSource URL: {r['url']}\n"
                    f"Title: {r['title']}\n"
                    f"Meta: {r['meta']}\n"
                    f"Schemas Detected: {', '.join(r['schemas']) if r['schemas'] else 'None'}\n"
                    "Headings Observed:\n"
                )
                for h in r['headings']:
                    source_insights += f"- {h}\n"
                source_insights += (
                    "TLDR: [Short summary of page goal]\n"
                    "Context for Writer: [What is this page covering, based on headings]\n"
                    "Unique Angle: [Anything different or missing compared to typical results]\n\n"
                )
            else:
                failed.append(r["url"])

        st.subheader("Scraped URL Insights")
        st.text_area("Full Observations", value=source_insights, height=500)

        with st.spinner("Generating Final SEO Brief..."):
            final_brief = generate_brief(keyword, source_insights, sitemap_urls, company_name, company_url)

        st.subheader("Generated SEO Content Brief")
        st.text_area("SEO Content Brief", value=final_brief, height=1000)

        if failed:
            st.error("Some URLs failed to scrape:")
            for url in failed:
                st.markdown(f"- {url}")
    else:
        st.error("Please complete all fields before generating.")
