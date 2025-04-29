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
st.caption("Generate detailed SEO briefs based on real SERPs, heading flows, schemas, keyword clusters, and full URL insights — no markdown.")

# --- Inputs --- #
openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (e.g., yourcompany.com)")
sitemap_urls = st.text_input("Enter one or multiple Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

# --- Fetch top 10 Bing URLs --- #
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

# --- Scrape a single URL --- #
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

# --- Scrape all URLs in batches --- #
async def scrape_all(urls, scraperapi_key):
    results = []
    batch_size = 3
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            tasks = [scrape_url(session, url, scraperapi_key) for url in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            st.success(f"Scraped {len(results)} URLs so far...")
            time.sleep(2)
    return results

# --- Generate SEO Brief --- #
def generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url):
    prompt = (
        f"You are a senior SEO Content Strategist.\n"
        f"Keyword: {keyword}\n"
        f"Company: {company_name} | Website: {company_url}\n"
        f"Sitemap URLs: {sitemap_urls}\n"
        f"\n"
        f"Observed competitor content:\n{headings_all}\n\n"
        f"Based on these, prepare a 1000x detailed SEO content brief for writers:\n"
        f"- Title and Meta Suggestions\n"
        f"- Primary + Secondary Keywords\n"
        f"- NLP/Semantic Keywords\n"
        f"- Keyword Clusters\n"
        f"- Detailed Heading Structure (based on observed headings)\n"
        f"- Writer Content Directions under each H2/H3\n"
        f"- Internal Link Suggestions from company's sitemap domain\n"
        f"- External Link Suggestions from trusted domains\n"
        f"- Schema Types detected and to be used\n"
        f"- SERP Differentiation Opportunities\n"
        f"- Mindmap of topic\n"
        f"\nImportant Instructions:\n"
        f"- NO markdown formatting. Only clear readable text.\n"
        f"- Reflect actual search intent based on observed URLs.\n"
        f"- Highly detailed and practical writer notes. No placeholder suggestions.\n"
    )
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# --- App Logic --- #
if st.button("Generate SEO Brief"):
    if openai_api_key and scraperapi_key and company_url and keyword:
        with st.spinner("Fetching Top 10 Organic URLs from Bing..."):
            bing_urls = fetch_bing_urls(keyword)
            if len(bing_urls) < 5:
                st.error("Failed to fetch minimum 5 organic URLs. Try again.")
                st.stop()
            st.success(f"Fetched {len(bing_urls)} URLs.")
            for idx, link in enumerate(bing_urls):
                st.markdown(f"{idx+1}. {link}")

        with st.spinner("Scraping URLs content..."):
            results = asyncio.run(scrape_all(bing_urls, scraperapi_key))

        headings_all = ""
        failed = []
        for res in results:
            if 'error' not in res:
                headings_all += (
                    f"Source URL: {res['url']}\n"
                    f"Title: {res['title']}\n"
                    f"Meta Description: {res['meta']}\n"
                    f"Schemas Detected: {', '.join(res['schemas'])}\n"
                    f"Headings Observed:\n"
                )
                for h in res['headings']:
                    headings_all += f"- {h}\n"
                headings_all += "\n"
            else:
                failed.append(res['url'])

        st.subheader("Scraped URL Insights")
        st.text_area("Full Observations", headings_all, height=500)

        with st.spinner("Generating Full SEO Content Brief using OpenAI..."):
            full_brief = generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url)

        st.subheader("Generated Full SEO Content Brief")
        st.text_area("SEO Content Brief", full_brief, height=800)

        if failed:
            st.error("Some URLs failed to scrape:")
            for url in failed:
                st.markdown(f"- {url}")
    else:
        st.error("Please fill all required fields!")

