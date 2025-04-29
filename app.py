import streamlit as st
import requests
import asyncio
import aiohttp
import openai
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
from mindmap_generator import generate_mindmap_from_headings
import graphviz

# Set Streamlit Page Config
st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")

# Title and description
st.title("SEO Content Brief Generator")
st.caption("Generate detailed SEO briefs based on SERPs, headings, schemas, and keyword clustering.")

# Input Fields
openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (e.g., yourwebsite.com)")
sitemap_urls = st.text_input("Enter one or multiple Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

# Helper Functions

def fetch_bing_urls(keyword, scraperapi_key, max_urls=10):
    query = '+'.join(keyword.split())
    url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url=https://www.bing.com/search?q={query}&country_code=us"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    links = []
    for a_tag in soup.select("li.b_algo h2 a"):
        href = a_tag.get('href')
        if href and 'bing.com' not in href and 'microsoft.com' not in href:
            domain = urlparse(href).netloc
            if domain not in [urlparse(link).netloc for link in links]:
                links.append(href)
    return links[:max_urls]

async def scrape_url(session, url, scraperapi_key, retries=3):
    for attempt in range(retries):
        try:
            api_url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url={url}&render=true"
            async with session.get(api_url, timeout=60) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')

                title = soup.title.string.strip() if soup.title else "N/A"

                meta_desc = ""
                for tag in soup.find_all("meta"):
                    if tag.get("name") == "description" or tag.get("property") == "og:description":
                        meta_desc = tag.get("content", "")
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
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(10)
            else:
                return {"url": url, "error": str(e)}

async def scrape_all(urls, scraperapi_key):
    results = []
    async with aiohttp.ClientSession() as session:
        tasks = [scrape_url(session, url, scraperapi_key) for url in urls]
        results = await asyncio.gather(*tasks)
    return results

def generate_brief(openai_api_key, keyword, headings_all, sitemap_urls, company_name, company_url):
    prompt = f"""
You are an expert SEO content strategist.
Given the following details:

- Target keyword: {keyword}
- Headings from competitors:\n{headings_all}
- Company's sitemap URLs: {sitemap_urls}
- Company's name: {company_name}
- Company's website: {company_url}

Generate:
- Primary and secondary keywords
- NLP/semantic keyword suggestions
- Keyword clusters
- Suggested heading structure (document flow)
- Internal link ideas
- External neutral link ideas
- Schema types detected
- SERP differentiation ideas
- Final markdown format outline (easy to copy)

Respond cleanly in structured markdown format without extra text.
"""

    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Main Logic

if st.button("Generate SEO Brief"):
    if openai_api_key and scraperapi_key and company_url and keyword:
        with st.spinner("Fetching top URLs from Bing..."):
            fetched_urls = fetch_bing_urls(keyword, scraperapi_key)
            st.success(f"Fetched {len(fetched_urls)} URLs.")
            for i, link in enumerate(fetched_urls):
                st.markdown(f"{i+1}. [{link}]({link})")

        with st.spinner("Scraping URLs..."):
            results = asyncio.run(scrape_all(fetched_urls, scraperapi_key))

        headings_all = ""
        headings_all_list = []
        failed_urls = []

        for res in results:
            if 'error' not in res:
                headings_all += f"\n{res['title']}\n"
                for head in res['headings']:
                    headings_all += f"{head}\n"
                    headings_all_list.append(head)
            else:
                failed_urls.append(res['url'])

        with st.spinner("Generating brief using OpenAI..."):
            full_brief = generate_brief(openai_api_key, keyword, headings_all, sitemap_urls, company_name, company_url)

        st.subheader("Generated Full SEO Content Brief")
        st.markdown(full_brief, unsafe_allow_html=True)

        if failed_urls:
            st.error(f"Failed to scrape {len(failed_urls)} URLs after retries.")
            for link in failed_urls:
                st.markdown(f"- [{link}]({link})")

        if headings_all_list:
            st.subheader("Visualized Mindmap of Heading Structure")
            mindmap = generate_mindmap_from_headings(headings_all_list)
            st.graphviz_chart(mindmap)

    else:
        st.error("Please fill all required fields!")
