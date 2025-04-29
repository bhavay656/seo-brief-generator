import streamlit as st
import requests
import aiohttp
import asyncio
import openai
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time

st.set_page_config(page_title="SEO Brief Generator", layout="wide")
st.title("SEO Brief Generator")

openai_api_key = st.text_input("Enter OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter ScraperAPI Key", type="password")
company_name = st.text_input("Company Name")
company_url = st.text_input("Company URL")
sitemap_urls = st.text_input("Sitemap URLs (comma-separated)")
keyword = st.text_input("Target Keyword")

# Fetch Bing URLs
def fetch_bing_urls(keyword):
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = []
    try:
        search_url = f"https://www.bing.com/search?q={'+'.join(keyword.split())}&count=20"
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup.select("li.b_algo h2 a"):
            href = tag.get("href")
            if href and "bing.com" not in href:
                urls.append(href)
    except:
        pass
    return urls[:10]

# Async scrape
async def scrape_url(session, url, api_key):
    try:
        final_url = f"http://api.scraperapi.com/?api_key={api_key}&url={url}&render=true"
        async with session.get(final_url, timeout=30) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            title = soup.title.string.strip() if soup.title else ""
            meta = ""
            for tag in soup.find_all("meta"):
                if tag.get("name") == "description" or tag.get("property") == "og:description":
                    meta = tag.get("content", "")
                    break
            headings = [f"{tag.name.upper()}: {tag.get_text(strip=True)}" for tag in soup.find_all(["h1", "h2", "h3", "h4"])]
            schemas = []
            for tag in ["FAQPage", "WebPage", "ItemList", "BlogPosting", "QAPage"]:
                if tag in html:
                    schemas.append(tag)
            return {"url": url, "title": title, "meta": meta, "headings": headings, "schemas": schemas}
    except:
        return {"url": url, "error": "Scrape Failed"}

async def scrape_all(urls, key):
    results = []
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(urls), 3):
            batch = urls[i:i+3]
            tasks = [scrape_url(session, u, key) for u in batch]
            results.extend(await asyncio.gather(*tasks))
            st.success(f"Scraped {len(results)} URLs so far...")
    return results

# Step 1: Get Competitor Observations
def get_observations(results):
    observations = ""
    for r in results:
        if 'error' in r:
            continue
        observations += f"\nSource URL: {r['url']}\nTitle: {r['title']}\nMeta: {r['meta']}\nSchemas: {', '.join(r['schemas'])}\n"
        observations += "Headings Observed:\n" + "\n".join(f"- {h}" for h in r['headings'])
        # Add prompt to generate insight
        context_prompt = f"""
Below are the extracted meta and headings from a webpage:
META: {r['meta']}
HEADINGS:
{r['headings']}

TLDR: Provide a 1-line summary of this URL
Context for Writer: What does this page primarily try to address?
Unique Angle: What makes this different or helpful compared to others?

Return in this format:
TLDR: ...
Context for Writer: ...
Unique Angle: ...
        """.strip()
        openai_client = openai.OpenAI(api_key=openai_api_key)
        insight = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": context_prompt}]
        ).choices[0].message.content.strip()
        observations += f"\n{insight}\n{'-'*60}\n"
    return observations

# Step 2: Final Brief Generator
def generate_brief(keyword, observations, sitemap_urls, company_name, company_url):
    prompt = f"""
You're an expert SEO strategist. Using the below SERP observations, generate a clear, fluff-free SEO brief that is aligned with dominant search intent.

Primary Keyword: {keyword}
Sitemap URLs: {sitemap_urls}
Company: {company_name}, URL: {company_url}

Observations from Top URLs:
{observations}

Include:
- Primary & Secondary Keywords
- NLP & Semantic Suggestions
- Keyword Clusters
- Heading Structure (H1, H2, H3)
- Context under each heading (for writers)
- Internal Link suggestions from sitemap URLs
- External Link types (not competitors)
- SERP Differentiation Ideas
- Don't use markdown or emojis
- Structure it for clear skimmability in the Streamlit output
    """.strip()

    client = openai.OpenAI(api_key=openai_api_key)
    result = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return result.choices[0].message.content.strip()

# MAIN FLOW
if st.button("Generate SEO Brief"):
    if not all([openai_api_key, scraperapi_key, keyword, company_url]):
        st.error("Please fill all required fields.")
        st.stop()

    with st.spinner("Fetching Top 10 Bing URLs..."):
        urls = fetch_bing_urls(keyword)
        if len(urls) < 5:
            st.error("Failed to fetch enough URLs.")
            st.stop()
        st.success(f"Fetched {len(urls)} URLs.")
        for idx, url in enumerate(urls):
            st.markdown(f"{idx+1}. [{url}]({url})")

    with st.spinner("Scraping URLs..."):
        results = asyncio.run(scrape_all(urls, scraperapi_key))

    with st.spinner("Generating SERP Observations..."):
        insight_text = get_observations(results)
        st.subheader("Scraped URL Insights")
        st.text_area("Full Observations", value=insight_text, height=600)

    with st.spinner("Generating Final SEO Brief..."):
        final = generate_brief(keyword, insight_text, sitemap_urls, company_name, company_url)
        st.subheader("Generated Full SEO Content Brief")
        st.text_area("SEO Content Brief", value=final, height=800)
