import streamlit as st
import asyncio
import aiohttp
import time
import openai
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import graphviz

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
    query = '+'.join(keyword.split())
    url = f"https://www.bing.com/search?q={query}&count=50"
    headers = {"User-Agent": "Mozilla/5.0"}
    links = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        for a_tag in soup.select("li.b_algo h2 a"):
            href = a_tag.get('href')
            if href and 'bing.com' not in href and 'microsoft.com' not in href:
                links.append(href)
    except:
        pass
    unique_links = {}
    for link in links:
        domain = urlparse(link).netloc
        if domain not in unique_links:
            unique_links[domain] = link
    return list(unique_links.values())[:15]

async def scrape_url(session, url, scraperapi_key):
    for attempt in range(3):
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
            await asyncio.sleep(2 * (attempt + 1))
    return {"url": url, "error": "Failed after retries"}

async def scrape_all(urls, scraperapi_key):
    results = []
    async with aiohttp.ClientSession() as session:
        batches = [urls[i:i+2] for i in range(0, len(urls), 2)]
        for batch in batches:
            batch_tasks = [scrape_url(session, url, scraperapi_key) for url in batch]
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)
            st.success(f"Scraped {len(results)} URLs so far...")
            time.sleep(1)
    return results

def generate_brief(openai_api_key, keyword, headings_all, sitemap_urls, company_name, company_url):
    prompt = f"""
You are an expert SEO strategist.
Given the keyword: {keyword}
Given the headings from competitors:
{headings_all}

Create an SEO brief including:
- Primary keyword and secondary keywords
- NLP/semantic keyword suggestions
- Keyword clusters
- Heading structure
- Content direction under each heading
- Internal linking ideas from sitemap URLs: {sitemap_urls}
- External linking ideas
- Schema types detected
- SERP differentiation summary
Use clean white background, no emojis, no unicode artifacts, mature tone.
"""
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload
    )
    return response.json()["choices"][0]["message"]["content"]

def draw_mindmap(headings):
    dot = graphviz.Digraph()
    last_h2 = None
    last_h3 = None
    for head in headings:
        if head.startswith("H1"):
            dot.node(head, head)
        elif head.startswith("H2"):
            last_h2 = head
            dot.node(head, head)
            dot.edge("H1" if "H1" in dot.source else list(dot.body)[0], head)
        elif head.startswith("H3") and last_h2:
            last_h3 = head
            dot.node(head, head)
            dot.edge(last_h2, head)
        elif head.startswith("H4") and last_h3:
            dot.node(head, head)
            dot.edge(last_h3, head)
    return dot

if st.button("Generate SEO Brief"):
    if openai_api_key and scraperapi_key and company_url and keyword:
        with st.spinner("Fetching Top URLs from Bing..."):
            fetched_urls = fetch_bing_urls(keyword)
        
        if len(fetched_urls) < 5:
            st.error("Failed to fetch minimum 5 organic URLs. Try again.")
            st.stop()
        
        st.success(f"Fetched {len(fetched_urls)} URLs.")
        for idx, link in enumerate(fetched_urls):
            st.markdown(f"{idx+1}. [{link}]({link})")
        
        with st.spinner("Scraping URLs content..."):
            results = asyncio.run(scrape_all(fetched_urls[:10], scraperapi_key))
        
        headings_all = ""
        failed_urls = []
        for res in results:
            if 'error' not in res:
                headings_all += f"\n{res['title']}\n"
                for head in res['headings']:
                    headings_all += f"{head}\n"
            else:
                failed_urls.append(res['url'])
        
        with st.spinner("Generating Full SEO Content Brief..."):
            full_brief = generate_brief(openai_api_key, keyword, headings_all, sitemap_urls, company_name, company_url)
        
        st.subheader("Generated Full SEO Content Brief")
        st.markdown(full_brief)

        if failed_urls:
            st.error(f"Failed to scrape {len(failed_urls)} URLs after retries:")
            for link in failed_urls:
                st.markdown(f"- [{link}]({link})")
        
        st.subheader("Mindmap of Heading Structure")
        mindmap = draw_mindmap([head for res in results if 'headings' in res for head in res['headings']])
        st.graphviz_chart(mindmap)
        
    else:
        st.error("Please fill all fields properly.")
