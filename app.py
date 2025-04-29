import streamlit as st
import requests
import aiohttp
import asyncio
import openai
import time
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import graphviz

st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")

# Title & Description
st.title("SEO Content Brief Generator")
st.caption("Generate detailed SEO briefs based on real SERPs, heading flows, schemas, and keyword clustering.")

# Inputs
openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (e.g., yourcompany.com)")
sitemap_urls = st.text_input("Enter one or multiple Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

# Functions
def fetch_bing_urls(keyword, retries=3):
    query = '+'.join(keyword.split())
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    url = f"https://www.bing.com/search?q={query}&cc=us"

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            soup = BeautifulSoup(response.content, "html.parser")
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
            final_links = list(unique_links.values())
            if len(final_links) >= 10:
                return final_links[:10]
            else:
                time.sleep(10)
        except Exception as e:
            time.sleep(10)
    return []

async def scrape_url(session, url, scraperapi_key, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            api_url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url={url}&render=true"
            async with session.get(api_url, timeout=50) as resp:
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
        except Exception:
            attempt += 1
            time.sleep(10)
    return {"url": url, "error": "Failed after retries"}

async def scrape_all(urls, scraperapi_key):
    async with aiohttp.ClientSession() as session:
        tasks = [scrape_url(session, url, scraperapi_key) for url in urls]
        results = await asyncio.gather(*tasks)
    return results

def generate_brief(openai_api_key, keyword, headings_all, sitemap_urls, company_name, company_url):
    system_prompt = f"""
You are an expert SEO strategist.

Topic: {keyword}

Here are competitor headings:\n{headings_all}

Sitemaps to pull internal links from: {sitemap_urls}

Company: {company_name}
Company Website: {company_url}

Generate:
- Title
- Primary and Secondary Keywords
- NLP/Semantic Keyword Suggestions
- Keyword Clusters
- Suggested Heading Structure (document order)
- Content Direction under each Heading
- Internal Link Suggestions
- External Neutral Link Ideas
- Schema Types Detected
- SERP Differentiation Summary

Format everything in clean markdown. No emojis.
"""
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": system_prompt}]
    )
    return response.choices[0].message.content

def draw_mindmap(headings):
    dot = graphviz.Digraph()
    last_h1, last_h2 = None, None
    for head in headings:
        if head.startswith("H1"):
            last_h1 = head
            dot.node(head, head)
        elif head.startswith("H2") and last_h1:
            last_h2 = head
            dot.node(head, head)
            dot.edge(last_h1, head)
        elif head.startswith("H3") and last_h2:
            dot.node(head, head)
            dot.edge(last_h2, head)
        elif head.startswith("H4") and last_h2:
            dot.node(head, head)
            dot.edge(last_h2, head)
    return dot

# App Logic
if st.button("Generate SEO Brief"):
    if openai_api_key and scraperapi_key and company_url and keyword:
        with st.spinner('Fetching Top 10 Organic URLs from Bing...'):
            fetched_urls = fetch_bing_urls(keyword)
            if len(fetched_urls) < 10:
                st.error("Failed to fetch minimum 10 organic URLs. Try again.")
                st.stop()
            st.success(f"Fetched {len(fetched_urls)} URLs.")
            for i, link in enumerate(fetched_urls):
                st.markdown(f"{i+1}. [{link}]({link})")
        
        with st.spinner('Scraping Website Details...'):
            results = asyncio.run(scrape_all(fetched_urls, scraperapi_key))

        headings_all = ""
        failed_urls = []
        for res in results:
            if 'error' not in res:
                headings_all += f"\n{res['title']}\n"
                for head in res['headings']:
                    headings_all += f"{head}\n"
            else:
                failed_urls.append(res['url'])

        with st.spinner('Generating SEO Content Brief using OpenAI...'):
            full_brief = generate_brief(openai_api_key, keyword, headings_all, sitemap_urls, company_name, company_url)

        st.subheader("Generated Full SEO Content Brief")
        st.markdown(full_brief, unsafe_allow_html=True)

        if failed_urls:
            st.warning("Failed to scrape the following URLs:")
            for link in failed_urls:
                st.markdown(f"- {link}")

        with st.spinner('Drawing Mindmap from Headings...'):
            mindmap = draw_mindmap([head for res in results if 'headings' in res for head in res['headings']])
            st.subheader("Heading Mindmap")
            st.graphviz_chart(mindmap)

    else:
        st.error("Please fill all required fields correctly!")
