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
company_website = st.text_input("Enter your Company Website URL (example: gocomet.com)", "")
sitemap_url = st.text_input("Enter your Sitemap URL (example: https://gocomet.com/sitemap.xml)", "")
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
        params = {"q": keyword, "count": "10", "setLang": "EN", "cc": "US"}
        response = requests.get("https://www.bing.com/search", params=params, headers=headers, timeout=10)
        strain = SoupStrainer('li')
        soup = BeautifulSoup(response.text, "html.parser", parse_only=strain)

        urls = []
        for a in soup.select('li.b_algo h2 a'):
            href = a.get('href')
            if href:
                clean_url = clean_bing_url(href)
                if clean_url.startswith("http"):
                    urls.append(clean_url)
            if len(urls) == 10:
                break

        return urls
    except Exception as e:
        return []

# Scrape Sitemap and filter URLs
def fetch_valid_sitemap_urls(sitemap_url):
    try:
        response = requests.get(sitemap_url, timeout=15)
        urls = []
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for url in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                urls.append(url.text.strip())

        valid_urls = []
        for url in urls:
            try:
                check = requests.get(url, timeout=10)
                if check.status_code == 200:
                    valid_urls.append(url)
            except:
                continue
        return valid_urls
    except Exception as e:
        return []

# Async Scraping using ScraperAPI
async def fetch(session, url, scraperapi_key):
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
    except Exception as e:
        return {
            "url": url,
            "title": "Error",
            "meta_description": "Error",
            "headings": [],
            "content": f"Error fetching: {e}"
        }

async def scrape_and_display(urls, scraperapi_key):
    scraped_summary = ""
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(urls), 3):
            batch = urls[i:i+3]
            tasks = [fetch(session, url, scraperapi_key) for url in batch]
            batch_results = await asyncio.gather(*tasks)

            for page in batch_results:
                st.markdown(f"### Scraped URL: [{page['url']}]({page['url']})")

                st.markdown(f"**Page Title:** {page['title']}")
                st.markdown(f"*Meta Description:* {page['meta_description']}")

                st.markdown("**Heading Structure:**")
                for level, heading_text in page['headings']:
                    indent = "&nbsp;" * (level * 4)
                    st.markdown(f"{indent}&lt;H{level}&gt; {heading_text}", unsafe_allow_html=True)

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

Focus on providing a simple, clear overview for an SEO content writer.

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
    except Exception as e:
        return f"Error summarizing: {e}"

# Generate final SEO Brief
def generate_brief(company_name, company_website, keyword, sitemap_links, scraped_summaries):
    try:
        sitemap_urls = "\n".join(sitemap_links)
        prompt = f"""
You are an SEO strategist working for {company_name} ({company_website}).

Keyword: {keyword}

Summaries of competing pages:
{scraped_summaries}

Instructions:
- Identify dominant search intent.
- Suggest a detailed SEO content structure: H1 > H2 > H3 hierarchy.
- Under each major H2, write 3–4 lines of context describing what should be written.
- Suggest a strong blog Introduction strategy.
- Suggest a strong blog Conclusion strategy.
- Provide 1 Primary Keyword and 3–5 Secondary Keywords.
- Provide 8–10 NLP/LSI Keywords related to the topic.
- Suggest 4–6 Keyword Cluster Ideas (related blog topics).
- Suggest 15 FAQs that can be included.
- Recommend 3 internal links (only from these sitemap URLs):
{sitemap_urls}
- Recommend 3 external authoritative sources (industry reports, data research, no blog competitors).
- Provide a TL;DR.

Important:
- Keep the format structured and SEO-writer ready.
- Do not write a blog, just the detailed content brief.

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
    except Exception as e:
        return f"Error generating brief: {e}"

# Main Execution
if submit:
    if not user_openai_key or not scraperapi_key:
        st.error("Please enter your OpenAI API Key and ScraperAPI Key.")
    elif not company_name or not company_website or not target_keyword or not sitemap_url:
        st.error("Please fill Company Name, Company Website, Target Keyword, and Sitemap URL.")
    else:
        openai.api_key = user_openai_key

        st.info("Fetching top URLs from Bing...")
        urls = get_top_bing_urls(target_keyword)

        if not urls:
            st.error("Could not fetch URLs from Bing. Try a different keyword.")
        else:
            st.success(f"Fetched {len(urls)} URLs.")

            st.markdown("### List of Fetched URLs:")
            for idx, url in enumerate(urls, start=1):
                st.markdown(f"{idx}. [{url}]({url})")

            st.info("Scraping and summarizing each URL...")

            scraped_summary_for_brief = asyncio.run(scrape_and_display(urls, scraperapi_key))

            st.info("Fetching live valid internal links from sitemap...")

            sitemap_links = fetch_valid_sitemap_urls(sitemap_url)

            if not sitemap_links:
                st.warning("No valid internal URLs found in sitemap or sitemap not reachable.")

            st.info("Generating final SEO content brief...")

            seo_brief = generate_brief(company_name, company_website, target_keyword, sitemap_links, scraped_summary_for_brief)

            st.subheader("Generated SEO Content Brief")
            st.write(seo_brief)

            st.download_button("Download Brief as Text", data=seo_brief, file_name="seo_brief.txt")
