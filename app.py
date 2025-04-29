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
st.caption("Create highly detailed, SERP-aligned SEO briefs based on scraped URLs.")

openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (e.g., yourcompany.com)")
sitemap_urls = st.text_input("Enter Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

# ----------------------- Get URLs ----------------------- #
def fetch_bing_urls(keyword):
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = []
    search_url = f"https://www.bing.com/search?q={'+'.join(keyword.split())}&count=20"
    response = requests.get(search_url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    seen = set()
    for tag in soup.select("li.b_algo h2 a"):
        href = tag.get("href")
        domain = urlparse(href).netloc
        if domain and domain not in seen and 'bing.com' not in href:
            seen.add(domain)
            urls.append(href)
    return urls[:10]

# ---------------------- Scraper ------------------------ #
async def scrape_url(session, url, scraperapi_key, fallback=False):
    try:
        fetch_url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url={url}&render=true" if fallback else url
        async with session.get(fetch_url, timeout=60) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.string.strip() if soup.title else ""
            meta = ""
            for tag in soup.find_all("meta"):
                if tag.get("name") == "description" or tag.get("property") == "og:description":
                    meta = tag.get("content", "")
                    break
            headings = [f"{tag.name.upper()}: {tag.get_text(strip=True)}" for tag in soup.find_all(["h1", "h2", "h3"])]
            schemas = []
            if 'FAQPage' in html:
                schemas.append("FAQPage")
            if 'ItemList' in html:
                schemas.append("ItemList")
            if 'WebPage' in html:
                schemas.append("WebPage")
            if 'BlogPosting' in html:
                schemas.append("BlogPosting")
            return {"url": url, "title": title, "meta": meta, "schemas": schemas, "headings": headings}
    except:
        if not fallback:
            return await scrape_url(session, url, scraperapi_key, fallback=True)
        return {"url": url, "error": "Failed"}

async def scrape_all(urls, scraperapi_key):
    results = []
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(urls), 3):
            batch = urls[i:i + 3]
            tasks = [scrape_url(session, u, scraperapi_key) for u in batch]
            results += await asyncio.gather(*tasks)
            st.success(f"Scraped {len(results)} URLs so far...")
            time.sleep(2)
    return results

# ------------------- Generate Brief -------------------- #
def generate_brief(keyword, all_sources, sitemap_urls, company_name, company_url):
    prompt = f"""
Act as an SEO strategist. Based ONLY on the SERP data below, generate a detailed SEO brief.

Keyword: {keyword}
Sitemap: {sitemap_urls}
Company: {company_name}, {company_url}

Here is all the SERP data:
{all_sources}

Return a detailed content brief with:
- Document Structure using H1, H2, H3 formatting
- For each heading: Context, TLDR, Unique Angle
- Internal Linking Suggestions from the sitemap domain (no random guessing)
- External Linking Suggestions: suggest *what to search*, not random URLs
- Schema Opportunities
Avoid assumptions. Rely only on input data.
"""
    client = openai.OpenAI(api_key=openai_api_key)
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content.strip()

# -------------------- Streamlit UI --------------------- #
if st.button("Generate SEO Brief"):
    if openai_api_key and scraperapi_key and company_url and keyword:
        with st.spinner("Fetching top Bing URLs..."):
            urls = fetch_bing_urls(keyword)
            if len(urls) < 5:
                st.error("Could not fetch enough URLs.")
                st.stop()
            st.success(f"Fetched {len(urls)} URLs.")
            for i, u in enumerate(urls):
                st.markdown(f"{i+1}. [{u}]({u})")

        with st.spinner("Scraping URL content..."):
            results = asyncio.run(scrape_all(urls, scraperapi_key))

        source_insights = ""
        for r in results:
            if 'error' not in r:
                source_insights += (
                    f"\nSource URL: {r['url']}\n"
                    f"Title: {r['title']}\n"
                    f"Meta: {r['meta']}\n"
                    f"Schemas: {', '.join(r['schemas']) if r['schemas'] else 'None'}\n"
                    f"Headings:\n"
                )
                for h in r['headings']:
                    source_insights += f"- {h}\n"
                source_insights += "\n"

        st.subheader("Scraped URL Insights")
        st.text_area("Full Observations", value=source_insights, height=400)

        with st.spinner("Generating Brief using OpenAI..."):
            full_brief = generate_brief(keyword, source_insights, sitemap_urls, company_name, company_url)

        st.subheader("Generated Full SEO Content Brief")
        st.text_area("SEO Content Brief", value=full_brief, height=800)
    else:
        st.error("Please fill in all fields.")
