
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
st.caption("Generate detailed SEO briefs strictly based on SERP observations: headings, TLDRs, angles, sitemap-based internal links.")

openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (e.g., yourcompany.com)")
sitemap_urls = st.text_input("Enter Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

def fetch_bing_urls(keyword):
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = []
    retries = 3
    for _ in range(retries):
        try:
            res = requests.get(f"https://www.bing.com/search?q={'+'.join(keyword.split())}&count=20", headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.select("li.b_algo h2 a"):
                href = a.get("href")
                if href and "bing.com" not in href and href not in urls:
                    urls.append(href)
            if len(urls) >= 5:
                return urls[:10]
        except:
            time.sleep(2)
    return urls[:10]

async def scrape_url(session, url, scraperapi_key):
    try:
        async with session.get(f"http://api.scraperapi.com/?api_key={scraperapi_key}&url={url}&render=true", timeout=60) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            title = soup.title.string.strip() if soup.title else "N/A"
            meta = ""
            for tag in soup.find_all("meta"):
                if tag.get("name") == "description" or tag.get("property") == "og:description":
                    meta = tag.get("content", "")
                    break
            headings = [tag.get_text(strip=True) for tag in soup.find_all(["h1", "h2", "h3", "h4"])][:10]
            schemas = []
            if 'FAQPage' in html: schemas.append("FAQPage")
            if 'WebPage' in html: schemas.append("WebPage")
            return {"url": url, "title": title, "meta": meta, "headings": headings, "schemas": schemas}
    except:
        return {"url": url, "error": "Failed to fetch"}

async def scrape_all(urls, scraperapi_key):
    results = []
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(urls), 3):
            tasks = [scrape_url(session, url, scraperapi_key) for url in urls[i:i+3]]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            st.success(f"Scraped {len(results)} URLs...")
            time.sleep(1)
    return results

def generate_brief(keyword, sources, sitemap_urls, company_name, company_url):
    prompt = f"""
Use the following SERP data to create a deeply structured SEO content brief strictly derived from observations.

Keyword: {keyword}
Company: {company_name}, Website: {company_url}
Sitemap XMLs: {sitemap_urls}

SERP-Based Insights:
{sources}

Instructions:
1. Create clear H1, H2, H3 document structure following SERP heading patterns.
2. Under each heading, include:
    - Context: What to cover based on SERP
    - TLDR: What this section aims to explain
    - Unique Angle: How competitors covered it or what stands out
3. Do NOT hallucinate. Only derive suggestions from scraped observations.
4. Internal linking ideas must be relevant pages from sitemap domain only.
5. For external resources, suggest search phrases—not direct competitors.
6. No markdown or emojis. Writer-focused format only.

End the brief with a visual mindmap flow in bullet points.

Strictly follow: NO st.markdown. NO filler text. NO markdown syntax.
"""

    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

if st.button("Generate SEO Brief"):
    if openai_api_key and scraperapi_key and keyword and company_url:
        with st.spinner("Fetching top Bing URLs..."):
            urls = fetch_bing_urls(keyword)
            if len(urls) < 5:
                st.error("Failed to fetch 5+ URLs.")
                st.stop()
            st.success(f"Fetched {len(urls)} URLs.")
            for i, u in enumerate(urls):
                st.write(f"{i+1}. {u}")

        with st.spinner("Scraping URL content..."):
            results = asyncio.run(scrape_all(urls, scraperapi_key))

        source_insights = ""
        for r in results:
            if 'error' not in r:
source_insights += f"Source URL: {r['url']}\n"
Title: {r['title']}
Meta: {r['meta']}
Schemas: {', '.join(r['schemas']) or 'None'}
"
                for h in r['headings']:
                    source_insights += f"- {h}
"
                source_insights += "
"

        st.subheader("Scraped URL Insights")
        st.text_area("Full Observations", value=source_insights, height=400)

        with st.spinner("Generating Brief using OpenAI..."):
            full_brief = generate_brief(keyword, source_insights, sitemap_urls, company_name, company_url)

        st.subheader("Generated Full SEO Content Brief")
        st.text_area("SEO Content Brief", full_brief, height=700)
    else:
        st.error("Fill all fields.")
