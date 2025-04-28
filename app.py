import streamlit as st
import requests
import aiohttp
import asyncio
import openai
from bs4 import BeautifulSoup, SoupStrainer
from urllib.parse import urlparse, parse_qs, unquote
import xml.etree.ElementTree as ET

# Streamlit Config
st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")
st.title("SEO Content Brief Generator")

# Input Fields
user_openai_key = st.text_input("Enter your OpenAI API Key (Required)", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key (Required)", type="password")
company_name = st.text_input("Enter your Company Name (Required)", "")
company_website = st.text_input("Enter your Company Website URL (example: yourwebsite.com)", "")
sitemap_urls_input = st.text_input("Enter one or multiple Sitemap URLs (comma-separated)", "")
target_keyword = st.text_input("Enter the Target Keyword (Required)", "")

submit = st.button("Generate SEO Brief")

# Setup OpenAI client
client = None
if user_openai_key:
    client = openai.OpenAI(api_key=user_openai_key)

# Clean Bing URL
def clean_bing_url(bing_url):
    if bing_url.startswith("https://www.bing.com/ck/a?"):
        parsed = urlparse(bing_url)
        query = parse_qs(parsed.query)
        if "url" in query:
            actual_url = query["url"][0]
            return unquote(actual_url)
    return bing_url

# Fetch top 10 Bing URLs
def get_top_bing_urls(keyword):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        forbidden_domains = [
            "bing.com", "youtube.com", "wikipedia.org", "linkedin.com", "facebook.com",
            "instagram.com", "twitter.com", "webcache.googleusercontent.com"
        ]
        forbidden_paths = [
            "/podcast/", "/video/", "/videos/", "/search/", "/directory/", "/categories/", "/tag/", "/topic/"
        ]

        urls = []
        seen_domains = set()

        for offset in range(0, 50, 10):  # page 1 to 5
            params = {
                "q": keyword,
                "first": offset,
                "count": "10",
                "setLang": "EN",
                "cc": "US"
            }
            response = requests.get("https://www.bing.com/search", params=params, headers=headers, timeout=10)
            strain = SoupStrainer('li')
            soup = BeautifulSoup(response.text, "html.parser", parse_only=strain)

            for li in soup.select('li.b_algo'):
                h2 = li.find('h2')
                if not h2:
                    continue
                a_tag = h2.find('a')
                if not a_tag:
                    continue

                href = a_tag.get('href')
                if href:
                    clean_url = clean_bing_url(href)
                    parsed = urlparse(clean_url)

                    if parsed.scheme not in ["http", "https"]:
                        continue

                    domain = parsed.netloc.lower()

                    # Forbidden domain or path
                    if any(bad in domain for bad in forbidden_domains):
                        continue
                    if any(forbidden in parsed.path for forbidden in forbidden_paths):
                        continue

                    # Skip homepage
                    if parsed.path == "/":
                        continue

                    # Only one URL per domain
                    if domain not in seen_domains:
                        seen_domains.add(domain)
                        urls.append(clean_url)

                if len(urls) == 10:
                    break

            if len(urls) == 10:
                break

        return urls
    except Exception:
        return []

# Fetch multiple sitemap URLs
def fetch_valid_sitemap_urls(sitemap_urls):
    valid_urls = []
    try:
        sitemaps = [url.strip() for url in sitemap_urls.split(",") if url.strip()]
        for sitemap_url in sitemaps:
            response = requests.get(sitemap_url, timeout=15)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                for url in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                    loc = url.text.strip()
                    try:
                        check = requests.get(loc, timeout=10)
                        if check.status_code == 200:
                            valid_urls.append(loc)
                    except:
                        continue
    except Exception:
        pass
    return valid_urls

# Async Scraping with retry
async def fetch(session, url, scraperapi_key):
    retries = 3
    for attempt in range(retries):
        try:
            scraperapi_url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url={url}"
            async with session.get(scraperapi_url, timeout=20) as response:
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                title = soup.title.string.strip() if soup.title else "No Title Found"

                meta_description = ""
                meta = soup.find("meta", attrs={"name": "description"})
                if meta and meta.get("content"):
                    meta_description = meta["content"].strip()

                headings = []
                for level in range(1, 11):
                    for tag in soup.find_all(f"h{level}"):
                        headings.append((level, tag.get_text(strip=True)))

                return {
                    "url": url,
                    "title": title,
                    "meta_description": meta_description,
                    "headings": headings,
                    "content": " ".join([p.get_text(strip=True) for p in soup.find_all("p")])[:5000]
                }
        except Exception:
            if attempt == retries - 1:
                return {
                    "url": url,
                    "title": "Error",
                    "meta_description": "Error",
                    "headings": [],
                    "content": f"Error fetching after {retries} retries."
                }
            await asyncio.sleep(1)

async def scrape_and_display(urls, scraperapi_key):
    scraped_summary = ""
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(urls), 3):
            batch = urls[i:i+3]
            tasks = [fetch(session, url, scraperapi_key) for url in batch]
            batch_results = await asyncio.gather(*tasks)

            for page in batch_results:
                st.markdown(f"### Scraped URL: [{page['url']}]({page['url']})")

                st.markdown("**Page Title:**")
                st.write(page['title'])

                st.markdown("**Meta Description:**")
                st.write(page['meta_description'])

                st.markdown("**Heading Structure:**")
                last_h2 = None
                for level, heading_text in page['headings']:
                    if level == 1:
                        st.write(f"H1: {heading_text}")
                    elif level == 2:
                        last_h2 = heading_text
                        st.write(f"H2: {heading_text}")
                    elif level == 3:
                        if last_h2:
                            st.write(f"    H3: {heading_text}")
                        else:
                            st.write(f"H3: {heading_text}")
                    else:
                        st.write(f"H{level}: {heading_text}")

                if page['content'].startswith("Error fetching"):
                    summary = page['content']
                else:
                    summary = summarize_page(page['headings'], page['content'])

                st.markdown("**Page Summary:**")
                st.write(summary)

                scraped_summary += f"\n\nURL: {page['url']}\nSummary: {summary}"

    return scraped_summary

# Summarize each page
def summarize_page(headings, content):
    try:
        headings_text = "\n".join([f"H{level}: {text}" for level, text in headings])
        prompt = f"""
Given these extracted headings and page content, summarize what this webpage is about in 5-7 lines.

Headings:
{headings_text}

Content:
{content}
"""
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert SEO content summarizer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=400
        )
        return response.choices[0].message.content
    except Exception:
        return "Error summarizing."

# Generate SEO Brief
def generate_brief(company_name, company_website, keyword, sitemap_links, scraped_summaries):
    try:
        sitemap_urls = "\n".join(sitemap_links)
        prompt = f"""
You are an SEO strategist working for {company_name} ({company_website}).

Keyword: {keyword}

Summaries of competing pages:
{scraped_summaries}

Instructions:
- Suggest a full SEO content structure (H1 > H2 > H3).
- Write 3–4 lines of context under each H2.
- Suggest blog Introduction and blog Ending strategies.
- List 1 Primary Keyword and 3–5 Secondary Keywords.
- Suggest 8–10 NLP/LSI keywords.
- Recommend 4–6 related blog topic ideas (keyword clusters).
- List 15 FAQs to include.
- Recommend 3 internal links from:
{sitemap_urls}
- Recommend 3 external authoritative sources (no blogs or competitors).
- Provide a TL;DR at the end.

Language: English only.
"""
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert SEO strategist."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=4000
        )
        return response.choices[0].message.content
    except Exception:
        return "Error generating SEO brief."

# Main execution
if submit:
    if not user_openai_key or not scraperapi_key:
        st.error("Please enter your OpenAI API Key and ScraperAPI Key.")
    elif not company_name or not company_website or not target_keyword or not sitemap_urls_input:
        st.error("Please fill all fields.")
    else:
        openai.api_key = user_openai_key

        st.info("Fetching top URLs from Bing...")
        urls = get_top_bing_urls(target_keyword)

        if not urls:
            st.error("Could not fetch URLs from Bing. Try again.")
        else:
            st.success(f"Fetched {len(urls)} URLs.")
            st.markdown("### List of Fetched URLs:")
            for idx, url in enumerate(urls, start=1):
                st.markdown(f"{idx}. [{url}]({url})")

            st.info("Scraping URLs...")
            scraped_summary_for_brief = asyncio.run(scrape_and_display(urls, scraperapi_key))

            st.info("Fetching sitemap URLs...")
            sitemap_links = fetch_valid_sitemap_urls(sitemap_urls_input)

            if not sitemap_links:
                st.warning("No valid URLs found in sitemap.")

            st.info("Generating SEO Content Brief...")
            seo_brief = generate_brief(company_name, company_website, target_keyword, sitemap_links, scraped_summary_for_brief)

            st.subheader("Generated SEO Content Brief")
            st.write(seo_brief)

            st.download_button("Download SEO Brief", data=seo_brief, file_name="seo_content_brief.txt")
