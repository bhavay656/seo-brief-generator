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

# ------------------ INPUTS ------------------ #
st.title("SEO Content Brief Generator")
st.caption("Generate detailed SEO briefs based on SERPs, headings, schemas, and keyword clustering.")

openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (e.g., yourwebsite.com)")
sitemap_urls = st.text_input("Enter one or multiple Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

# ------------------ FUNCTIONS ------------------ #

def fetch_bing_urls(keyword, scraperapi_key):
    query = '+'.join(keyword.split())
    retries = 0
    while retries < 3:
        try:
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
            final_links = list(unique_links.values())
            if len(final_links) >= 10:
                return final_links[:10]
            else:
                retries += 1
                time.sleep(10)
        except:
            retries += 1
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
        except:
            attempt += 1
            time.sleep(10)
    return {"url": url, "error": "Failed after retries"}

async def scrape_all(urls, scraperapi_key):
    async with aiohttp.ClientSession() as session:
        tasks = [scrape_url(session, url, scraperapi_key) for url in urls]
        results = await asyncio.gather(*tasks)
    return results

def generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url):
    prompt = f"""
You are an SEO strategist.
Topic: {keyword}

Collected headings:
{headings_all}

Company: {company_name}
Website: {company_url}

Based on this, generate:
- Primary keyword
- Secondary keywords
- NLP/semantic suggestions
- Keyword clusters
- Suggested heading structure (document flow)
- Content direction for each heading
- Internal link ideas from {company_url}
- External neutral link ideas
- Schema types if detected
- SERP Differentiation Themes

Format cleanly without any coding block.
"""
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def draw_mindmap(headings):
    dot = graphviz.Digraph()
    last_h2 = None
    if headings:
        for head in headings:
            if head.startswith("H1"):
                dot.node(head, head)
            elif head.startswith("H2"):
                last_h2 = head
                dot.node(head, head)
                dot.edge("H1" if "H1" in dot.source else list(dot.body)[0], head)
            elif head.startswith("H3") and last_h2:
                dot.node(head, head)
                dot.edge(last_h2, head)
    else:
        dot.node("H1: Main Idea")
        dot.node("H2: Subtopic 1")
        dot.edge("H1: Main Idea", "H2: Subtopic 1")
    return dot

# ------------------ APP LOGIC ------------------ #

if st.button("Generate SEO Brief"):
    if openai_api_key and scraperapi_key and company_url and keyword:
        with st.spinner('Fetching top URLs from Bing...'):
            fetched_urls = fetch_bing_urls(keyword, scraperapi_key)
            if not fetched_urls:
                st.error("Failed to fetch 10 organic URLs from Bing after retries.")
                st.stop()
            st.success(f"Fetched {len(fetched_urls)} URLs.")
            for i, link in enumerate(fetched_urls):
                st.markdown(f"{i+1}. [{link}]({link})")

        with st.spinner('Scraping URLs...'):
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

        with st.spinner('Generating Brief using OpenAI...'):
            full_brief = generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url)

        st.header("Generated Full SEO Content Brief")
        st.markdown(full_brief, unsafe_allow_html=True)

        if failed_urls:
            st.warning(f"Failed to scrape {len(failed_urls)} URLs after retries.")
            for link in failed_urls:
                st.markdown(f"- [{link}]({link})")

        with st.spinner("Generating Mindmap..."):
            mindmap = draw_mindmap([head for res in results if 'headings' in res for head in res['headings']])
            st.graphviz_chart(mindmap)
    else:
        st.error("Please fill all required fields!")
