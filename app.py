
import streamlit as st
import requests
from bs4 import BeautifulSoup
import concurrent.futures
import re
import time
import json
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

# --- Constants and API Keys ---
scraperapi_key = st.secrets["scraperapi_key"]
openai_api_key = st.secrets["openai_api_key"]

headers = {"Authorization": f"Bearer {openai_api_key}"}
openai_url = "https://api.openai.com/v1/chat/completions"

# --- Helper Functions ---

def fetch_bing_urls(query):
    try:
        url = f"https://api.scraperapi.com/?api_key={scraperapi_key}&url=https://www.bing.com/search?q={query}"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        links = [a["href"] for a in soup.select("li.b_algo h2 a[href]")]
        unique_domains = {}
        for link in links:
            domain = urlparse(link).netloc
            if domain not in unique_domains:
                unique_domains[domain] = link
            if len(unique_domains) >= 10:
                break
        return list(unique_domains.values())
    except Exception as e:
        return []

def scrape_with_scraperapi(url, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            full_url = f"http://api.scraperapi.com?api_key={scraperapi_key}&url={url}"
            r = requests.get(full_url, timeout=20)
            soup = BeautifulSoup(r.content, "html.parser")
            title = soup.title.string.strip() if soup.title else ""
            meta = soup.find("meta", attrs={"name": "description"})
            meta_desc = meta["content"].strip() if meta and "content" in meta.attrs else ""
            headings = []
            for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
                text = tag.get_text(strip=True)
                if text:
                    text = re.sub(r"[:\-]", "", text)
                    headings.append(f"{tag.name.upper()}: {text}")
            return {"url": url, "title": title, "meta": meta_desc, "headings": headings}
        except:
            attempt += 1
            time.sleep(2)
    return None

def batch_scrape(urls, batch_size=3):
    scraped_pages = []
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i + batch_size]
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
            future_to_url = {executor.submit(scrape_with_scraperapi, url): url for url in batch}
            for future in concurrent.futures.as_completed(future_to_url):
                result = future.result()
                if result:
                    scraped_pages.append(result)
    return scraped_pages

def parse_sitemap_topics(sitemap_url):
    try:
        r = requests.get(sitemap_url, timeout=10)
        tree = ET.fromstring(r.content)
        urls = [elem[0].text for elem in tree.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url")]
        topics = [urlparse(url).path.strip("/").replace("-", " ").title() for url in urls]
        return list(set(topics))[:15]
    except:
        return []

def get_serp_insight(page):
    headings = "\n".join(page["headings"])
    prompt = f"""You're an expert SEO writer. Based on these competitor insights and headings, create a brief followed by a 2000+ word article.

Requirements:
- Avoid LLM-like phrases: Delve, landscape, evolving, etc.
- Avoid common AI transitions like: "In fact", "Clearly", "To illustrate", etc.
- All headings (H1–H4) should be logically used.
- Add FAQs within the natural flow of the article.
- Word count MUST be 2000+.
- Keyword density should be below 3%. Do not link internally on the primary keyword.
- Avoid fluff, make introduction 2 short paragraphs max.
- Write in natural, conversational tone.
- CTA: Mention a call-to-action relevant to {company_name or 'your brand'} at the end.

Here are the insights from one competitor page:

Headings:
{headings}

Title: {page['title']}

Meta Description: {page['meta']}

URL: {page['url']}

Return ONLY the complete SEO brief first with proper outline (H1 to H4 structured).
"""
    response = requests.post(openai_url, headers=headers, json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": prompt}]
    })
    return response.json()["choices"][0]["message"]["content"]

# --- Streamlit UI ---

st.title("🧠 SEO Brief Generator")

keyword = st.text_input("Target Keyword (optional)")
topic = st.text_input("Content Topic (optional)")
company_name = st.text_input("Company name")
company_url = st.text_input("Website URL (for internal links)")
sitemap_url = st.text_input("Sitemap.xml URL (for topic suggestions)")

submitted = st.button("🔍 Start SERP Scraping")

manual_urls_input = ""
final_urls = []
scraped_insights = []

if submitted:
    with st.spinner("Fetching top SERP URLs..."):
        query = keyword or topic
        serp_urls = fetch_bing_urls(query)
        if len(serp_urls) >= 5:
            st.markdown("#### 🔗 Top SERP + Reference URLs")
            for url in serp_urls:
                st.markdown(f"- [{url}]({url})")
            st.info("You can optionally add more URLs below to improve coverage.")
            manual_urls_input = st.text_area("Add reference URLs manually (comma-separated)")
            if manual_urls_input:
                serp_urls += [url.strip() for url in manual_urls_input.split(",") if url.strip()]
            st.checkbox("✅ I've reviewed the URLs. Proceed to scrape content.", key="scrape_ready")
        else:
            st.warning("Bing scraping failed or gave <5 unique domains. Please paste at least 10 manual URLs below.")
            manual_urls_input = st.text_area("Add reference URLs manually (required)", key="manual_only")
            if manual_urls_input:
                serp_urls = [url.strip() for url in manual_urls_input.split(",") if url.strip()]
                st.checkbox("✅ I've reviewed the URLs. Proceed to scrape content.", key="manual_ready")

    if serp_urls:
        with st.spinner("Scraping competitor pages in batches..."):
            scraped_insights = batch_scrape(serp_urls)

        st.session_state["insights"] = scraped_insights

        st.markdown("### ✍️ Competitor Insights & Headings")
        for item in scraped_insights:
            st.markdown(f"**{item['title']}**  
{item['url']}")
            for h in item["headings"]:
                st.markdown(f"- {h}")

        if scraped_insights:
            st.markdown("### 💡 Generate Editable Brief")
            brief_prompt = get_serp_insight(scraped_insights[0])
            editable_brief = st.text_area("📋 Review and edit the outline/brief before generating content", value=brief_prompt, height=300)
            if st.button("✏️ Generate SEO Article"):
                with st.spinner("🧠 Generating content..."):
                    content_prompt = editable_brief + "\n\nNow generate the article based on this brief."
                    response = requests.post(openai_url, headers=headers, json={
                        "model": "gpt-4",
                        "messages": [{"role": "user", "content": content_prompt}]
                    })
                    article = response.json()["choices"][0]["message"]["content"]
                    st.markdown("## 📝 SEO Article")
                    st.markdown(article)
                    st.download_button("📥 Download Article", data=article, file_name="seo_article.txt")
