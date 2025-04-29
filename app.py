import streamlit as st
import requests
import aiohttp
import asyncio
import openai
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
import graphviz

# Set Streamlit page config
st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")

# ----------------- INPUTS -----------------
st.title("SEO Content Brief Generator")
st.caption("Generate detailed SEO briefs based on real SERPs, heading flows, schemas, and keyword clustering.")

openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (e.g., yourcompany.com)")
sitemap_urls = st.text_input("Enter one or multiple Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

# ----------------- FUNCTIONS -----------------

def fetch_bing_urls(keyword):
    query = '+'.join(keyword.split())
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    url = f"https://www.bing.com/search?q={query}&count=30"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")
        links = []
        for a_tag in soup.select("li.b_algo h2 a"):
            href = a_tag.get('href')
            if href and 'bing.com' not in href and 'microsoft.com' not in href:
                links.append(href)
        unique_links = {}
        for link in links:
            domain = urlparse(link).netloc
            if domain not in unique_links:
                unique_links[domain] = link
        return list(unique_links.values())[:10]
    except Exception as e:
        return []

async def scrape_url(session, url, scraperapi_key):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        async with session.get(url, headers=headers, timeout=15) as resp:
            html = await resp.text()
    except:
        # fallback to scraperapi
        api_url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url={url}&render=true"
        async with session.get(api_url, timeout=20) as resp:
            html = await resp.text()

    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.string.strip() if soup.title else "N/A"
    meta_desc = ""
    for tag in soup.find_all("meta"):
        if tag.get("name") == "description" or tag.get("property") == "og:description":
            meta_desc = tag.get("content")
            break
    headings = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        headings.append(f"{tag.name.upper()}: {tag.get_text(strip=True)}")
    schemas = []
    if 'FAQPage' in html:
        schemas.append('FAQPage')
    if 'WebPage' in html:
        schemas.append('WebPage')
    return {"url": url, "title": title, "meta": meta_desc, "headings": headings, "schemas": schemas}

async def scrape_all(urls, scraperapi_key):
    results = []
    async with aiohttp.ClientSession() as session:
        batches = [urls[i:i + 3] for i in range(0, len(urls), 3)]
        for batch in batches:
            tasks = [scrape_url(session, url, scraperapi_key) for url in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            st.success(f"Scraped {len(results)} URLs so far...")
    return results

def generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url):
    prompt = f"""
You are an expert SEO strategist.
Topic: {keyword}
Collected competitor headings:
{headings_all}

Generate:
- Primary keyword
- Secondary keywords
- NLP/semantic keyword suggestions
- Keyword clusters
- Clean suggested heading structure
- Content direction (brief context) for each heading
- Internal linking ideas (use this domain: {company_url})
- External neutral link ideas
- Schema types detected
- SERP differentiation ideas
- A visual mindmap code
Clean formatting. Do not use emojis.
"""
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# ----------------- APP LOGIC -----------------

if st.button("Generate SEO Brief"):
    if openai_api_key and company_url and keyword:
        with st.spinner("Fetching Top 10 Organic URLs from Bing..."):
            fetched_urls = fetch_bing_urls(keyword)
            if len(fetched_urls) < 5:
                st.error("Failed to fetch minimum 5 organic URLs. Try again.")
                st.stop()
            st.success(f"Fetched {len(fetched_urls)} URLs.")
            for i, link in enumerate(fetched_urls):
                st.markdown(f"{i+1}. [{link}]({link})")

        with st.spinner("Scraping URLs content..."):
            results = asyncio.run(scrape_all(fetched_urls, scraperapi_key))

        headings_all = ""
        for res in results:
            headings_all += f"\n{res['title']}\n"
            for head in res['headings']:
                headings_all += f"{head}\n"

        with st.spinner("Generating Full Brief using OpenAI..."):
            full_brief = generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url)

        st.header("Generated Full SEO Content Brief")
        st.markdown(full_brief)
    else:
        st.error("Please fill all required fields!")
