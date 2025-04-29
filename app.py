import streamlit as st
import requests
import aiohttp
import asyncio
import openai
import time
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import graphviz

# -------------- PAGE CONFIG ---------------- #
st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")

st.title("SEO Content Brief Generator")
st.caption("Generate detailed SEO briefs based on SERPs, heading flows, schemas, and keyword clustering.")

# -------------- USER INPUTS ---------------- #
openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (e.g., yourcompany.com)")
sitemap_urls = st.text_input("Enter one or multiple Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

# -------------- FUNCTIONS ---------------- #

def fetch_bing_urls(keyword, retries=3):
    query = '+'.join(keyword.split())
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    url = f"https://www.bing.com/search?q={query}&cc=us"

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=5)
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

            if len(final_links) >= 5:
                return final_links[:10]
            else:
                time.sleep(2)
        except Exception:
            time.sleep(2)

    return []

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
            await asyncio.sleep(2)
    return {"url": url, "error": "Failed after retries"}

async def scrape_all(urls, scraperapi_key):
    async with aiohttp.ClientSession() as session:
        tasks = [scrape_url(session, url, scraperapi_key) for url in urls]
        results = await asyncio.gather(*tasks)
    return results

def generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url):
    sitemap_urls_str = sitemap_urls if sitemap_urls else "None provided"
    prompt = f"""
You are an expert SEO strategist.

Given the topic: {keyword}

And collected headings:

{headings_all}

And company info:
- Company Name: {company_name}
- Company URL: {company_url}
- Sitemap URLs: {sitemap_urls_str}

Generate:
- Primary and Secondary keywords
- NLP/semantic keyword suggestions
- Keyword clusters
- Suggested heading structure (document flow)
- Content directions for each heading
- Internal linking suggestions
- External neutral linking ideas
- Schema types if detected
- SERP differentiation summary
- Provide the entire output in simple white background, no grey box.
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
    return dot

# -------------- MAIN APP LOGIC ---------------- #

if st.button("Generate SEO Brief"):
    if openai_api_key and scraperapi_key and company_url and keyword:
        with st.spinner('Fetching Top 10 Organic URLs from Bing...'):
            fetched_urls = fetch_bing_urls(keyword)
            if len(fetched_urls) < 5:
                st.error("Failed to fetch minimum 5 organic URLs. Try again.")
                st.stop()
            else:
                st.success(f"Fetched {len(fetched_urls)} URLs.")
                for i, link in enumerate(fetched_urls):
                    st.markdown(f"{i+1}. [{link}]({link})")
        
        with st.spinner('Scraping URLs content...'):
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

        with st.spinner('Generating Full SEO Brief using OpenAI...'):
            full_brief = generate_brief(keyword, headings_all, sitemap_urls, company_name, company_url)

        st.markdown("## Generated Full SEO Content Brief")
        st.markdown(full_brief, unsafe_allow_html=True)

        if failed_urls:
            st.warning(f"Some URLs failed to scrape after retries:")
            for link in failed_urls:
                st.markdown(f"- [{link}]({link})")

        with st.spinner("Generating Mindmap from Headings..."):
            all_headings = [head for res in results if 'headings' in res for head in res['headings']]
            if all_headings:
                mindmap = draw_mindmap(all_headings)
                st.graphviz_chart(mindmap)
            else:
                st.warning("No headings found to generate mindmap.")

    else:
        st.error("Please fill all required fields correctly.")

