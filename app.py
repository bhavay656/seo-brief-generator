import streamlit as st
import requests
import aiohttp
import asyncio
import openai
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import graphviz

st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")

# Title and description
st.title("SEO Content Brief Generator")
st.caption("Generate detailed, real-world SEO briefs from SERP analysis, heading flows, schema detection, and keyword clustering. No fluff, only actionable briefs.")

# Inputs
openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (e.g., yourwebsite.com)")
sitemap_urls = st.text_input("Enter Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

# Functions
def fetch_bing_urls(keyword, scraperapi_key):
    query = '+'.join(keyword.split())
    url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url=https://www.bing.com/search?q={query}&country_code=us"
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
    return list(unique_links.values())[:10]

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
    return {"url": url, "error": "Failed after retries"}

async def scrape_all(urls, scraperapi_key):
    async with aiohttp.ClientSession() as session:
        tasks = [scrape_url(session, url, scraperapi_key) for url in urls]
        results = await asyncio.gather(*tasks)
    return results

def generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url):
    sitemap_list = sitemap_urls.split(",")
    prompt = f"""
You are an expert SEO strategist.

Topic: {keyword}

Here are the competitor heading structures:
{headings_all}

Based on this:

- Suggest a **Title**.
- Suggest **Primary** and **Secondary** keywords.
- Suggest **NLP/Semantic Keywords**.
- Create 3-4 **Keyword Clusters**.
- Suggest **Heading Structure** (document order, natural H1 > H2 > H3 flow).
- Under each heading, suggest **Content Direction** (1 line instruction).
- Suggest **Internal Links** from these sitemaps: {', '.join(sitemap_list)}
- Suggest 3 **External Links** (neutral sources, not competitors).
- Identify **Schema types** if any (FAQPage, WebPage etc.).
- Summarize **SERP Differentiation** in 3 points.
- Format cleanly in structured Markdown, easy to copy.

Strictly do not use emojis or unicode characters.
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        api_key=openai_api_key,
        messages=[{"role": "user", "content": prompt}]
    )
    return response['choices'][0]['message']['content']

def draw_mindmap(headings):
    dot = graphviz.Digraph()
    last_h2 = None
    last_h1 = None
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
        with st.spinner("Fetching top URLs from Bing..."):
            fetched_urls = fetch_bing_urls(keyword, scraperapi_key)
            st.success(f"Fetched {len(fetched_urls)} URLs.")
            for i, link in enumerate(fetched_urls):
                st.markdown(f"{i+1}. [{link}]({link})")

        with st.spinner("Scraping URLs..."):
            results = asyncio.run(scrape_all(fetched_urls, scraperapi_key))
        
        headings_all = ""
        failed_urls = []
        all_headings = []

        for res in results:
            if 'error' not in res:
                headings_all += f"\n{res['title']}\n"
                for head in res['headings']:
                    headings_all += f"{head}\n"
                all_headings.extend(res['headings'])
            else:
                failed_urls.append(res['url'])

        with st.spinner("Generating Brief using OpenAI..."):
            full_brief = generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url)
            st.subheader("Generated Full SEO Content Brief")
            st.markdown(full_brief)

        if failed_urls:
            st.warning(f"Failed to scrape {len(failed_urls)} URLs after retries.")
            for url in failed_urls:
                st.markdown(f"- [{url}]({url})")

        with st.spinner("Generating Mindmap..."):
            mindmap = draw_mindmap(all_headings)
            st.graphviz_chart(mindmap)

    else:
        st.error("Please fill all required fields!")
