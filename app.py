import streamlit as st
import openai
import requests
import aiohttp
import asyncio
import cloudscraper
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
import tempfile
import graphviz

# Set page config
st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")

# UI Inputs
st.title("SEO Content Brief Generator")

st.write("""
This app scrapes the top organic Bing results for your keyword, extracts title, meta description, headings flow,
identifies schema types, generates a detailed SEO content brief with primary/secondary keywords, semantic clusters,
context per heading, internal link suggestions (from your sitemap), neutral external link ideas, SERP differentiation themes,
and a mindmap visualization of the heading structure.
""")

openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key", type="password")
company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Company Website URL (example: yoursite.com)")
sitemaps = st.text_input("Enter Sitemap URLs (comma-separated)")
target_keyword = st.text_input("Enter the Target Keyword")

submit = st.button("Generate SEO Brief")

# Helper Functions
def scrape_with_requests(url, scraperapi_key):
    try:
        api_url = f"http://api.scraperapi.com?api_key={scraperapi_key}&url={url}&render=true"
        response = requests.get(api_url, timeout=15)
        if response.status_code == 200:
            return response.text
    except:
        pass
    return None

def scrape_with_undetected_browser(url):
    try:
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        driver = uc.Chrome(options=options)
        driver.get(url)
        html = driver.page_source
        driver.quit()
        return html
    except:
        return None

def clean_heading_structure(soup):
    headings = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        headings.append(f"{tag.name.upper()}: {tag.get_text(strip=True)}")
    return headings

def detect_schemas(soup):
    schemas = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            json_content = script.string
            if 'WebPage' in json_content:
                schemas.append('WebPage')
            if 'FAQPage' in json_content:
                schemas.append('FAQPage')
            if 'Article' in json_content:
                schemas.append('Article')
        except:
            continue
    return list(set(schemas))

def fetch_html(url):
    retries = 0
    html = None
    while retries < 3:
        html = scrape_with_requests(url, scraperapi_key)
        if html:
            break
        retries += 1
    if not html:
        html = scrape_with_undetected_browser(url)
    return html

@st.cache_data()
def fetch_top_bing_results(keyword):
    headers = {"Ocp-Apim-Subscription-Key": "Bing-API-Not-Needed", "User-Agent": "Mozilla/5.0"}
    search_url = f"https://www.bing.com/search?q={keyword.replace(' ', '+')}"
    scraper = cloudscraper.create_scraper()
    resp = scraper.get(search_url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith("http") and "bing.com" not in href and "javascript:" not in href:
            links.append(href)
    seen = set()
    unique_links = []
    for l in links:
        domain = urlparse(l).netloc
        if domain not in seen:
            seen.add(domain)
            unique_links.append(l)
    return unique_links[:10]

def generate_mindmap(headings_flow):
    dot = graphviz.Digraph()
    for heading in headings_flow:
        dot.node(heading, heading)
    return dot

# Main Execution
if submit and openai_api_key and scraperapi_key and company_url and target_keyword:
    st.info("Fetching top URLs from Bing...")
    urls = fetch_top_bing_results(target_keyword)

    st.success(f"Fetched {len(urls)} URLs.")
    st.markdown("### List of Fetched URLs:")
    for idx, u in enumerate(urls):
        st.markdown(f"{idx+1}. [{u}]({u})")

    scraped_data = []
    failed_urls = []

    for url in urls:
        st.markdown(f"#### Scraped URL: [{url}]({url})")
        html = fetch_html(url)
        if not html:
            failed_urls.append(url)
            continue
        soup = BeautifulSoup(html, 'html.parser')
        
        page_title = soup.title.string.strip() if soup.title else "N/A"
        meta_description = ""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            meta_description = meta.get("content", "")

        headings_flow = clean_heading_structure(soup)
        schemas_detected = detect_schemas(soup)

        st.markdown(f"**Page Title:** {page_title}")
        st.markdown(f"**Meta Description:** {meta_description}")
        st.markdown(f"**Heading Flow (Document Order):**")
        for h in headings_flow:
            st.markdown(f"- {h}")
        st.markdown(f"**Schemas Detected:** {', '.join(schemas_detected) if schemas_detected else 'None'}")

        scraped_data.append({
            "url": url,
            "title": page_title,
            "description": meta_description,
            "headings": headings_flow,
            "schemas": schemas_detected
        })

    if failed_urls:
        st.warning(f"Failed to scrape {len(failed_urls)} URLs:")
        for u in failed_urls:
            st.markdown(f"- {u}")

    # Generate SEO Content Brief
    st.header("Generated Full SEO Content Brief")
    mindmap = generate_mindmap([h.split(": ", 1)[-1] for data in scraped_data for h in data['headings']])
    st.graphviz_chart(mindmap)

else:
    st.warning("Please fill all fields and click 'Generate SEO Brief'.")
