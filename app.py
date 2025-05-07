
import streamlit as st
import requests
import concurrent.futures
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

st.set_page_config(layout="wide")
st.title("SEO Brief Generator")

scraperapi_key = st.secrets["SCRAPERAPI_KEY"]
openai_key = st.secrets["OPENAI_API_KEY"]

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {openai_key}"
}

def fetch_bing_urls(query, max_urls=10):
    try:
        response = requests.get(f"https://www.bing.com/search?q={query}")
        soup = BeautifulSoup(response.text, "html.parser")
        links = []
        domains = set()
        for a in soup.find_all("a", href=True):
            url = a["href"]
            domain = urlparse(url).netloc
            if url.startswith("http") and domain not in domains and "bing.com" not in domain:
                domains.add(domain)
                links.append(url)
            if len(links) >= max_urls:
                break
        return links
    except Exception as e:
        st.error(f"Bing scrape failed: {e}")
        return []

def scrape_with_scraperapi(url, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            full_url = f"http://api.scraperapi.com?api_key={scraperapi_key}&url={url}"
            r = requests.get(full_url, timeout=10)
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

def batch_scrape(urls):
    scraped_pages = []
    for i in range(0, len(urls), 3):
        chunk = urls[i:i+3]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_url = {executor.submit(scrape_with_scraperapi, url): url for url in chunk}
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
        topics = [urlparse(url).path.strip("/").replace("-", " ").title() for url in urls if url]
        return list(set(topics))[:15]
    except:
        return []

# Input section
keyword = st.text_input("Target Keyword (optional)", "supply chain visibility")
topic = st.text_input("Content Topic (optional)", "what is supply chain visibility")
company_name = st.text_input("Company name", "")
company_url = st.text_input("Website URL (for internal links)", "")
sitemap_urls = st.text_input("Sitemap.xml URL (for topic suggestions)", "")
manual_urls = []

# Step 1: Scrape from Bing
if keyword and topic:
    st.subheader("🔗 Top SERP + Reference URLs")
    urls = fetch_bing_urls(topic)
    if len(urls) >= 5:
        for u in urls:
            st.markdown(f"- [{u}]({u})")
        st.info("You can optionally add more URLs below to improve coverage.")
        manual_input = st.text_area("Add reference URLs manually (comma-separated)")
        if manual_input:
            manual_urls = [u.strip() for u in manual_input.split(",") if u.strip()]
            urls.extend(manual_urls)
        confirm = st.checkbox("✅ I've reviewed the URLs. Proceed to scrape content.")
    else:
        st.warning("Bing scraping gave <5 unique domains. Please paste at least 10 manual URLs below.")
        manual_input = st.text_area("Add reference URLs manually (comma-separated)")
        if manual_input:
            urls = [u.strip() for u in manual_input.split(",") if u.strip()]
            confirm = st.checkbox("✅ I've reviewed the URLs. Proceed to scrape content.")
    if confirm and urls:
        scraped = batch_scrape(urls)
        st.session_state["scraped"] = scraped
        st.session_state["step"] = "brief"
        st.rerun()

# Step 2: Display brief insights
if st.session_state.get("step") == "brief":
    st.subheader("🧠 Insights from Competitor Pages")
    for item in st.session_state["scraped"]:
        st.markdown(f"**{item['title']}**")
        for h in item["headings"]:
            st.markdown(f"- {h}")
    default_brief = "\n\n".join([item["title"] + "\n" + "\n".join(item["headings"]) for item in st.session_state["scraped"]])
    updated_brief = st.text_area("✏️ Review or Edit the Outline before Content Generation", default_brief, height=300)
    if st.button("✍️ Generate SEO Article"):
        st.session_state["final_outline"] = updated_brief
        st.session_state["step"] = "content"
        st.rerun()

# Step 3: Generate content
if st.session_state.get("step") == "content":
    st.subheader("📄 SEO Article")
    prompt = f"""You're an expert SEO writer. Based on this outline and competitor insights, write a 2000+ word article.

Instructions:
- Must use H1, H2, H3, H4 format in proper flow
- Word count must exceed 2000
- Integrate FAQs naturally within the content
- Keep keyword density < 3% for '{keyword}'
- Avoid AI phrases: "delve", "landscape", "evolving", etc.
- No generic AI sentence templates. Use natural, human-like writing.

Outline:
{st.session_state["final_outline"]}

Company: {company_name}
Website: {company_url}
Keyword: {keyword}
Topic: {topic}
"""
    with st.spinner("Generating complete brief and content..."):
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "You're a senior SEO writer."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
            }
        )
        reply = r.json()["choices"][0]["message"]["content"]
        st.markdown(reply)
        st.download_button("📥 Download Article", reply, file_name="seo_article.txt")
