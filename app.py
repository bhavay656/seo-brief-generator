
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
st.caption("Generate detailed SEO briefs based on real SERPs, heading flows, schemas, and keyword clustering.")

openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (e.g., yourcompany.com)")
sitemap_urls = st.text_input("Enter one or multiple Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

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
            headings = [tag.get_text(strip=True) for tag in soup.find_all(["h1", "h2", "h3", "h4"])]
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

def generate_brief(keyword, scraped_data, sitemap_urls, company_name, company_url):
    source_insights = ""
    for res in scraped_data:
        if 'error' not in res:
            source_insights += f"
Source URL: {res['url']}
Title: {res['title']}
Meta: {res['meta']}
Schemas: {', '.join(res['schemas'])}
"
            source_insights += "Headings:
"
            for h in res['headings']:
                source_insights += f"- {h}
"
            source_insights += "
"

    prompt = f"""
You're a world-class SEO content strategist.

Keyword: {keyword}
Company: {company_name} | Website: {company_url}
Sitemap URLs: {sitemap_urls}

Extracted details from top-ranking pages for "{keyword}":

{source_insights}

Now based on SERP patterns and observed competitor content, generate a highly detailed, writer-focused SEO content brief. Include:

1. Primary & Secondary Keywords
2. NLP/Semantic Suggestions
3. Keyword Clusters
4. SERP-aligned Heading Structure
5. Under each heading, explain to a writer what should be written and why (based on competitor coverage)
6. Unique angles or gaps observed
7. Internal Linking Ideas from the provided sitemap domain
8. External Linking Ideas from neutral authority sources
9. Schema Types detected
10. SERP Differentiation Ideas
11. Visual Mindmap Plan (Bullet Format Only)

DO NOT use markdown. Keep it easy to read in plain text. Don't invent fluff – base all insights on scraped URLs. Don't say "You can" or "Consider writing" – be direct and prescriptive to the writer.
"""

    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

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

        st.subheader("Extracted SERP Data Summary")
        for res in results:
            if 'error' not in res:
                st.write(f"URL: {res['url']}")
                st.write(f"Title: {res['title']}")
                st.write(f"Meta: {res['meta']}")
                st.write(f"Schemas: {', '.join(res['schemas'])}")
                st.write("Headings:")
                for h in res['headings']:
                    st.write(f"- {h}")
                st.markdown("---")
            else:
                st.error(f"Failed to scrape: {res['url']}")

        with st.spinner("Generating Final SEO Brief using OpenAI..."):
            full_brief = generate_brief(keyword, results, sitemap_urls, company_name, company_url)

        st.subheader("Generated Full SEO Content Brief")
        st.text(full_brief)
    else:
        st.error("Please fill all required fields!")
