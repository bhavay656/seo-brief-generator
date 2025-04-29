import streamlit as st
import requests
import aiohttp
import asyncio
import openai
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time

st.set_page_config(page_title="SEO Brief Generator", layout="wide")
st.title("SEO Content Brief Generator")
st.caption("Generate structured, search-intent-aligned briefs from live SERPs")

openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (e.g., yourcompany.com)")
sitemap_urls = st.text_input("Enter Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

def fetch_bing_urls(keyword):
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = []
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
        return urls[:10]
    except Exception:
        return []

async def scrape_url(session, url, scraperapi_key):
    try:
        final_url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url={url}&render=true"
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
            if 'BlogPosting' in html:
                schemas.append("BlogPosting")
            if 'WebPage' in html:
                schemas.append("WebPage")
            return {
                "url": url, "title": title, "meta": meta,
                "headings": headings, "schemas": schemas, "raw_html": html
            }
    except:
        return {"url": url, "error": "Scraping failed"}

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

def generate_detailed_prompt(keyword, results, sitemap_urls, company_name, company_url):
    detail_sections = ""
    for r in results:
        if 'error' in r:
            continue
        headings = "\\n".join(r['headings'])
        schemas = ', '.join(r['schemas']) if r['schemas'] else "None"
        detail_sections += f"""
URL: {r['url']}
Title: {r['title']}
Meta: {r['meta']}
Schemas: {schemas}
Headings:
{headings}

TLDR: [Summarize what this page is about]
Context for Writer: [Summarize what each section is covering]
Unique Angle: [If something stands out or differs from others]

---
"""

    prompt = f'''
You are an expert SEO content strategist.

Keyword: {keyword}
Company: {company_name}
Website: {company_url}
Sitemap: {sitemap_urls}

Here are full details from top-ranking URLs:
{detail_sections}

Now write a complete SEO content brief.

Include:
- Primary Keyword
- Secondary Keywords
- NLP/Semantic Suggestions
- Search-Intent-Aligned Keyword Clusters
- Heading Structure (H1, H2, H3s) based on majority SERP flow
- Under each heading: a brief "Context for Writer"
- Internal Linking Suggestions from sitemap
- External Link Search Suggestions (but not direct competitors)
- Schema Suggestions
- No fluff. No markdown.
- Structure by awareness–consideration–decision if present in SERP

Avoid generic suggestions. Focus on intent. If SERP is transactional, begin directly from consideration/decision-level.
'''

    return prompt

def call_openai_brief(prompt, openai_api_key):
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
                st.error("Less than 5 valid results.")
                st.stop()
            st.success(f"Fetched {len(urls)} URLs.")
            for i, u in enumerate(urls):
                st.write(f"{i+1}. [{u}]({u})")

        with st.spinner("Scraping URLs..."):
            results = asyncio.run(scrape_all(urls, scraperapi_key))

        st.subheader("Scraped URL Insights")
        all_obs = ""
        for r in results:
            if 'error' in r:
                continue
            all_obs += f"\nSource URL: {r['url']}\nTitle: {r['title']}\nMeta: {r['meta']}\nSchemas Detected: {', '.join(r['schemas']) or 'None'}\n"
            all_obs += "\nHeadings Observed:\n"
            for h in r['headings']:
                all_obs += f"- {h}\n"
            all_obs += "\nTLDR: \nContext for Writer: \nUnique Angle: \n\n---\n\n"
        st.text_area("Full Observations", all_obs, height=500)

        with st.spinner("Generating Final SEO Brief..."):
            prompt = generate_detailed_prompt(keyword, results, sitemap_urls, company_name, company_url)
            brief = call_openai_brief(prompt, openai_api_key)

        st.subheader("Generated Final SEO Brief")
        st.text_area("SEO Brief", brief, height=800)
    else:
        st.error("Please fill all fields.")
