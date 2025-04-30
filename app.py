# Streamlit SEO Brief Generator

import streamlit as st
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from openai import OpenAI
import concurrent.futures
import time
import re

client = OpenAI(api_key=st.secrets["openai_api_key"])
scraperapi_key = st.secrets["scraperapi_key"]

st.set_page_config(page_title="SEO Brief Generator", layout="wide")
st.title("SEO Brief Generator")

# --- Inputs ---
keyword = st.text_input("Target Keyword (optional)")
topic = st.text_input("Content Topic (optional)")
company_name = st.text_input("Company name")
company_url = st.text_input("Website URL (for internal links)")
sitemap_url = st.text_input("Sitemap.xml URL (for topic suggestions)")
manual_urls = st.text_area("Add reference URLs manually (optional, comma-separated)")

if not keyword and not topic:
    st.warning("Please enter either a keyword or content topic.")
    st.stop()

query = keyword or topic

# --- Fetch Bing Results ---
def fetch_bing_urls(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(f"https://www.bing.com/search?q={query}", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        links = [a["href"] for a in soup.select("li.b_algo h2 a") if a["href"].startswith("http")]
        return links[:10]
    except:
        st.error("❌ SERP scraping failed. Bing may be blocking requests. Please enter reference URLs manually.")
        return []

# --- ScraperAPI Scraping ---
def scrape_with_scraperapi(url, retries=3):
    for _ in range(retries):
        try:
            full_url = f"http://api.scraperapi.com?api_key={scraperapi_key}&url={url}"
            r = requests.get(full_url, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            title = soup.title.string.strip() if soup.title else ""
            meta = soup.find("meta", attrs={"name": "description"})
            meta_desc = meta["content"].strip() if meta and "content" in meta.attrs else ""
            headings = [f"{tag.name.upper()}: {re.sub(r'[:\-]', '', tag.get_text(strip=True))}"
                        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4']) if tag.get_text(strip=True)]
            return {"url": url, "title": title, "meta": meta_desc, "headings": headings}
        except:
            time.sleep(2)
    return None

def batch_scrape(urls):
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(scrape_with_scraperapi, url): url for url in urls}
        return [f.result() for f in concurrent.futures.as_completed(futures) if f.result()]

# --- Sitemap Topic Parser ---
def parse_sitemap_topics(sitemap_url):
    try:
        r = requests.get(sitemap_url, timeout=10)
        tree = ET.fromstring(r.content)
        urls = [elem[0].text for elem in tree.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")]
        topics = [urlparse(u).path.strip("/").replace("-", " ").title() for u in urls if u]
        return list(set(topics))[:15]
    except:
        return []

# --- Insight Generator ---
def get_serp_insight(page):
    if not (page.get("title") or page.get("meta") or page.get("headings")):
        return "❌ Not enough usable content to generate insight."

    prompt = f"""You are an SEO strategist.

Analyze the following page content and generate:
- TLDR summary (1–2 lines)
- Writer-friendly context
- Unique insight

Title: {page['title']}
Meta: {page['meta']}
Headings:
{chr(10).join(page['headings'])}
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ OpenAI error: {e}"

# --- Brief Generator ---
def generate_brief(pages, query, company_name, company_url, sitemap_topics):
    extracted = ""
    for p in pages:
        context = get_serp_insight(p)
        extracted += f"""URL: {p['url']}
Title: {p['title']}
Meta: {p['meta']}
Headings:
{chr(10).join(p['headings'])}
Context: {context}
---
"""
    internal_line = f"Internal linking topics: {', '.join(sitemap_topics)}." if sitemap_topics else ""

    prompt = f"""You are an expert SEO strategist.

Generate a complete SEO content brief for:
Topic: {query}
Company: {company_name} ({company_url})

Based only on:
{extracted}

Your output must include:
- Primary keyword
- Secondary keywords
- NLP/semantic keyword suggestions
- Search intent
- Unique content angle
- Outline with H1, H2, H3 (with context)
- {internal_line}
Minimum article length: 1800+ words.
Avoid generic AI tone or external linking.
"""
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content.strip()

# --- Article Writer ---
def generate_article(company_name, company_url, outline, feedback=None):
    prompt = f"""Write a detailed SEO article of at least 1800 words.

Company: {company_name}
URL: {company_url}
Outline:
{outline}
"""
    if feedback:
        prompt += f"\nUser Feedback: {feedback}"

    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content.strip()

# --- Execution ---
if query and company_name and company_url:
    if "urls" not in st.session_state:
        scraped_urls = fetch_bing_urls(query)
        if manual_urls:
            scraped_urls += [u.strip() for u in manual_urls.split(",") if u.strip()]
        if not scraped_urls:
            st.warning("No URLs to scrape. Please input manually.")
            st.stop()
        st.session_state["urls"] = list(dict.fromkeys(scraped_urls))

    st.markdown("### 🔗 Top SERP URLs")
    for u in st.session_state["urls"]:
        st.markdown(f"- [{u}]({u})")

    confirm = st.checkbox("✅ I’ve reviewed URLs. Proceed to scrape pages.")

    if confirm and "scraped" not in st.session_state:
        with st.spinner("🔍 Scraping in progress..."):
            st.session_state["scraped"] = batch_scrape(st.session_state["urls"])

    if confirm and "scraped" in st.session_state:
        sitemap_topics = parse_sitemap_topics(sitemap_url) if sitemap_url else []

        if "brief" not in st.session_state:
            if st.button("✅ Generate SEO Brief"):
                with st.spinner("🧠 Creating content brief..."):
                    brief = generate_brief(st.session_state["scraped"], query, company_name, company_url, sitemap_topics)
                    st.session_state["brief"] = brief

    if "brief" in st.session_state:
        st.subheader("📄 SEO Content Brief")
        brief_text = st.text_area("Edit Brief", st.session_state["brief"], height=600)
        st.download_button("📥 Download Brief", brief_text, file_name=f"{query.replace(' ', '_')}_brief.txt")

        outline = "\n".join([l for l in brief_text.splitlines() if l.strip().startswith(("H1", "H2", "H3"))])
        st.markdown("## ✏️ Generate Article")
        outline_input = st.text_area("Review outline", outline, height=300)

        if st.button("🚀 Generate Article"):
            with st.spinner("✍️ Writing content..."):
                article = generate_article(company_name, company_url, outline_input)
                st.session_state["article"] = article

    if "article" in st.session_state:
        st.subheader("📝 Generated Article")
        st.text_area("SEO Article", st.session_state["article"], height=800)
        st.download_button("📥 Download Article", st.session_state["article"], file_name=f"{query.replace(' ', '_')}_article.txt")
        feedback = st.text_area("✍️ Suggest changes")
        if st.button("🔄 Improve with Feedback"):
            with st.spinner("🔁 Improving..."):
                improved = generate_article(company_name, company_url, outline_input, feedback=feedback)
                st.session_state["article"] = improved
