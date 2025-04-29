import streamlit as st
import requests
import aiohttp
import asyncio
import openai
import time
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import graphviz
from collections import defaultdict

# Streamlit Page Config
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
def fetch_bing_urls(keyword, scraperapi_key, retries=3):
    query = '+'.join(keyword.split())
    url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url=https://www.bing.com/search?q={query}&country_code=us"

    for attempt in range(retries):
        response = requests.get(url)
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
    return final_links

async def scrape_url(session, url, scraperapi_key, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            api_url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url={url}&render=true"
            async with session.get(api_url, timeout=40) as resp:
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
        except:
            attempt += 1
            time.sleep(10)
    return {"url": url, "error": "Failed after retries"}

async def scrape_all(urls, scraperapi_key):
    results = []
    async with aiohttp.ClientSession() as session:
        tasks = [scrape_url(session, url, scraperapi_key) for url in urls]
        results = await asyncio.gather(*tasks)
    return results

def generate_brief(openai_api_key, keyword, headings_all, sitemap_urls, company_name, company_url):
    system_prompt = f"""
You are an expert SEO content strategist.

Given the topic: {keyword}

Headings collected from competitors:

{headings_all}

Also, the internal sitemap(s): {sitemap_urls}

Company Name: {company_name}
Company URL: {company_url}

Generate a full SEO content brief including:

- Title
- Primary & Secondary Keywords
- NLP/Semantic Keyword Suggestions
- Keyword Clusters
- Suggested Heading Structure (in real document order)
- Short Content Direction for each Heading
- Internal Link Suggestions (from sitemap URLs given)
- External Neutral Linking Ideas
- Schema Types Detected
- SERP Differentiation Ideas
- Full Final Copyable Markdown at the end.

No emojis. No salesy words. Focus purely on SEO.
Answer in clean sections.

"""
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": system_prompt}]
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
        with st.spinner('Fetching Top Organic URLs from Bing...'):
            fetched_urls = fetch_bing_urls(keyword, scraperapi_key)
            if len(fetched_urls) < 10:
                st.error("Failed to fetch at least 10 organic URLs after retries. Please retry with another keyword.")
                st.stop()
            st.success(f"Fetched {len(fetched_urls)} URLs.")
            for i, link in enumerate(fetched_urls):
                st.markdown(f"{i+1}. [{link}]({link})")
        
        with st.spinner('Scraping URL Details...'):
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

        with st.spinner('Generating Final Brief using OpenAI...'):
            full_brief = generate_brief(openai_api_key, keyword, headings_all, sitemap_urls, company_name, company_url)

        st.header("Generated Full SEO Content Brief")
        st.markdown(full_brief, unsafe_allow_html=True)

        if failed_urls:
            st.warning("Failed to scrape the following URLs after retries:")
            for link in failed_urls:
                st.markdown(f"- {link}")

        with st.spinner('Drawing Mindmap...'):
            mindmap = draw_mindmap([head for res in results if 'headings' in res for head in res['headings']])
            st.subheader("Mindmap of Heading Flow")
            st.graphviz_chart(mindmap)

    else:
        st.error("Please fill all fields properly!")

