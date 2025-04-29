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

def generate_context_for_heading(heading_text, keyword):
    prompt = f"What should a writer cover under this heading in an article about '{keyword}'?\nHeading: {heading_text}"
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url):
    prompt = f'''
Act as a top-tier SEO content strategist.

Keyword: {keyword}
Sitemap URLs: {sitemap_urls}
Company: {company_name} | Website: {company_url}

Here are the extracted heading structures from top SERP competitors:
{headings_all}

Return the following:
- Primary & Secondary Keywords
- NLP/Semantic Suggestions
- Keyword Clusters
- Suggested Heading Structure (Document Flow)
- Writer-focused Content Direction below each heading
- Internal Link Ideas from the company\'s sitemap domain
- External Link Ideas from trusted neutral domains
- Schema Types Detected with interpretation
- SERP Differentiation Ideas
- Visual Mindmap summary as bullet points with sub-topics

Use clear formatting and no markdown. Do not use emojis or unicode. Everything should be writer-ready and skim-friendly.
'''
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

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

        st.subheader("Scraped SERP Details (Before Brief Generation)")
        headings_all = ""
        failed = []

        for res in results:
            if 'error' not in res:
                st.text(f"URL: {res['url']}")
                st.text(f"Title: {res['title']}")
                st.text(f"Meta: {res['meta']}")
                st.text(f"Schemas: {', '.join(res['schemas'])}")
                for h in res['headings']:
                    st.text(h)
                    context = generate_context_for_heading(h, keyword)
                    st.text("Context: " + context)
                headings_all += f"URL: {res['url']}\nTitle: {res['title']}\nMeta: {res['meta']}\nSchemas: {', '.join(res['schemas'])}\n"
                headings_all += "\n".join(res['headings']) + "\n"
            else:
                failed.append(res['url'])

        with st.spinner("Generating Full SEO Brief..."):
            full_brief = generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url)

        st.subheader("Generated Full SEO Content Brief")
        st.text(full_brief)

        if failed:
            st.error("Some URLs failed:")
            for url in failed:
                st.text(f"- {url}")
    else:
        st.error("Please fill all required fields!")
