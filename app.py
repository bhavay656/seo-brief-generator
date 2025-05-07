
import streamlit as st
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import concurrent.futures
import time
import re
from openai import OpenAI

client = OpenAI(api_key=st.secrets["openai_api_key"])
scraperapi_key = st.secrets["scraperapi_key"]

st.set_page_config(page_title="SEO Brief Generator", layout="wide")
st.title("SEO Brief Generator")

keyword = st.text_input("Target Keyword (optional)")
topic = st.text_input("Content Topic (optional)")
company_name = st.text_input("Company name")
company_url = st.text_input("Website URL (for internal links)")
sitemap_url = st.text_input("Sitemap.xml URL (for topic suggestions)")
manual_urls = st.text_area("Add reference URLs manually (optional, comma-separated)")

query = keyword or topic
if not query:
    st.warning("Please enter either a keyword or content topic.")
    st.stop()

def fetch_unique_bing_urls(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(f"https://www.bing.com/search?q={query}", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        seen_domains = set()
        unique_links = []
        for a in soup.select("li.b_algo h2 a"):
            href = a.get("href")
            domain = urlparse(href).netloc
            if href.startswith("http") and domain not in seen_domains:
                unique_links.append(href)
                seen_domains.add(domain)
            if len(unique_links) == 10:
                break
        return unique_links
    except:
        return []

def scrape_with_scraperapi(url, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            full_url = f"http://api.scraperapi.com?api_key={scraperapi_key}&url={url}"
            r = requests.get(full_url, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            title = soup.title.string.strip() if soup.title else ""
            meta = soup.find("meta", attrs={"name": "description"})
            meta_desc = meta["content"].strip() if meta and "content" in meta.attrs else ""
            headings = []
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                text = tag.get_text(strip=True)
                if text:
                    text = re.sub(r'[:\-]', '', text)
                    headings.append(f"{tag.name.upper()}: {text}")
            return {"url": url, "title": title, "meta": meta_desc, "headings": headings}
        except:
            attempt += 1
            time.sleep(2)
    return None

def batch_scrape(urls):
    scraped_pages = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_url = {executor.submit(scrape_with_scraperapi, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if result:
                scraped_pages.append(result)
    return scraped_pages

def parse_sitemap_topics(sitemap_url):
    try:
        r = requests.get(sitemap_url, timeout=10)
        tree = ET.fromstring(r.content)
        urls = [elem[0].text for elem in tree.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")]
        topics = [urlparse(url).path.strip("/").replace("-", " ").title() for url in urls if url]
        return list(set(topics))[:15]
    except:
        return []

if "urls" not in st.session_state:
    bing_urls = fetch_unique_bing_urls(query)
    if len(bing_urls) < 10:
        st.warning("Bing scraping failed or gave <10 unique domains. Please paste at least 10 manual URLs below.")
        st.stop()
    st.session_state["urls"] = bing_urls

st.markdown("### 🔗 Top SERP + Reference URLs")
for u in st.session_state["urls"]:
    st.markdown(f"- [{u}]({u})")

confirmed = st.checkbox("✅ I've reviewed the URLs. Proceed to scrape content.")
if not confirmed:
    st.stop()

if "scraped" not in st.session_state:
    with st.spinner("🔍 Scraping all pages in parallel..."):
        st.session_state["scraped"] = batch_scrape(st.session_state["urls"])

scraped = st.session_state["scraped"]
sitemap_topics = parse_sitemap_topics(sitemap_url) if sitemap_url else []

def get_serp_insight(page):
    title = page.get("title", "").strip()
    meta = page.get("meta", "").strip()
    headings = page.get("headings", [])
    if not title and not meta and not headings:
        return {"tldr": "❌ Not enough usable content."}
    prompt = f"""
You are an SEO strategist.

Analyze the following page and give:
1. TLDR (1–2 lines)
2. Context (What this page covers and how)
3. Unique hook or angle

Title: {title}
Meta: {meta}
Headings:
{chr(10).join(headings)}
"""
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return {"tldr": res.choices[0].message.content.strip()}

if "insights" not in st.session_state:
    with st.spinner("📊 Generating insights from scraped content..."):
        st.session_state["insights"] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(get_serp_insight, p): p for p in scraped}
            for future in concurrent.futures.as_completed(futures):
                page = futures[future]
                insight = future.result()
                st.session_state["insights"].append({
                    "url": page["url"],
                    "title": page["title"],
                    "meta": page["meta"],
                    "headings": page["headings"],
                    "tldr": insight.get("tldr", "")
                })

st.markdown("### 🔍 SERP Insights")
for p in st.session_state["insights"]:
    st.markdown(f"**URL:** [{p['url']}]({p['url']})")
    st.markdown(f"**Title:** {p['title']}")
    st.markdown(f"**Meta:** {p['meta']}")
    st.markdown("**Headings (Document Flow):**")
    for h in p["headings"]:
        indent = "  " if h.startswith("H4") else " " if h.startswith("H3") else ""
        st.markdown(f"{indent}- {h}")
    st.markdown(f"**Insight:** {p['tldr']}")
    st.markdown("---")

if st.button("✅ Generate SEO Brief"):
    with st.spinner("✍️ Generating content brief..."):
        extracted = ""
        for p in st.session_state["insights"]:
            extracted += f"URL: {p['url']}\nTitle: {p['title']}\nMeta: {p['meta']}\nHeadings:\n{chr(10).join(p['headings'])}\nContext: {p['tldr']}\n---\n"
        internal_line = f"Internal linking topics: {', '.join(sitemap_topics)}." if sitemap_topics else ""
        prompt = f"""
You are an expert SEO strategist.

Generate a full SEO content brief for:

Topic: {query}
Company: {company_name} ({company_url})

Based on:
{extracted}

Include:
- H1, H2, H3, H4 headings with context under each
- Primary keyword, secondary and semantic keywords
- FAQs
- Unique angle, search intent
- {internal_line}
Rules:
- 2000+ words
- ≤ 3% keyword density
- No LLM-sounding phrases
- Sharp, fluff-free, no loops
"""
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        st.session_state["brief"] = res.choices[0].message.content.strip()

if "brief" in st.session_state:
    st.subheader("📄 SEO Content Brief")
    brief = st.text_area("Edit Brief", st.session_state["brief"], height=600)
    st.download_button("📥 Download Brief", brief, file_name=f"{query.replace(' ', '_')}_brief.txt")

    headings = [line for line in brief.splitlines() if line.strip().startswith(("H1", "H2", "H3", "H4"))]
    default_outline = "\n".join(headings)
    st.markdown("## ✏️ Generate Content from Outline")
    outline_input = st.text_area("Edit or approve outline", value=default_outline, height=300)

    if st.button("🚀 Generate Article"):
        prompt = f"""
Write a 2000+ word SEO article for {company_name} using the outline below.

Include:
- All H1–H4 headings
- FAQs
- Short intro (≤ 2 short paragraphs)
- ≤ 3% keyword density
- No AI-like phrasing
- Conversational tone

Outline:
{outline_input}
"""
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        st.session_state["article"] = res.choices[0].message.content.strip()

if "article" in st.session_state:
    st.subheader("📝 Generated Article")
    st.text_area("SEO Article", st.session_state["article"], height=800)
    st.download_button("📥 Download Article", st.session_state["article"], file_name=f"{query.replace(' ', '_')}_article.txt")

    feedback = st.text_area("✍️ Suggest edits to improve content")
    if st.button("🔄 Apply Feedback"):
        prompt = f"""
Revise the article based on this feedback: {feedback}

Maintain:
- 2000+ words
- Short intro
- ≤ 3% keyword density
- All H1–H4 used
- FAQs
- Avoid LLM-style phrasing

Article:
{st.session_state["article"]}
"""
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        updated = res.choices[0].message.content.strip()
        st.session_state["article"] = updated
        st.markdown("### 🔁 Updated Article with Feedback")
        st.text_area("Updated SEO Article", updated, height=800)
