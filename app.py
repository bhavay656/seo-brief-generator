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

if not keyword and not topic:
    st.warning("Please enter either a keyword or content topic.")
    st.stop()

query = keyword or topic

# --- Bing Results ---
def fetch_bing_urls(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(f"https://www.bing.com/search?q={query}", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        links = [a["href"] for a in soup.select("li.b_algo h2 a") if a["href"].startswith("http")]
        return links[:10]
    except:
        return []

# --- ScraperAPI with Retry ---
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
                    # Remove colons and hyphens from headings
                    text = re.sub(r'[:\-]', '', text)
                    headings.append(f"{tag.name.upper()}: {text}")
            return {"url": url, "title": title, "meta": meta_desc, "headings": headings}
        except:
            attempt += 1
            time.sleep(2)
    return None

def batch_scrape(urls):
    scraped_pages = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_url = {executor.submit(scrape_with_scraperapi, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if result:
                scraped_pages.append(result)
    return scraped_pages

# --- Sitemap Parser ---
def parse_sitemap_topics(sitemap_url):
    try:
        r = requests.get(sitemap_url, timeout=10)
        tree = ET.fromstring(r.content)
        urls = [elem[0].text for elem in tree.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")]
        topics = [urlparse(url).path.strip("/").replace("-", " ").title() for url in urls if url]
        return list(set(topics))[:15]
    except:
        return []

# --- Insight Generator ---
def get_serp_insight(page):
    title = page.get("title", "").strip()
    meta = page.get("meta", "").strip()
    headings = page.get("headings", [])

    if not title and not meta and not headings:
        return "❌ Not enough usable content to generate insight."

    prompt = f"""
You are an SEO strategist.

Analyze the following page content and generate:
- TLDR summary (1–2 lines)
- Writer-friendly context of what this page covers
- Unique insight or hook

Title: {title}
Meta: {meta}
Headings (in order of appearance):
{chr(10).join(headings)}
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
        extracted += f"URL: {p['url']}\nTitle: {p['title']}\nMeta: {p['meta']}\nHeadings:\n{chr(10).join(p['headings'])}\n---\n"

    internal_topic_line = f"Internal linking topics: {', '.join(sitemap_topics)}." if sitemap_topics else ""

    prompt = f"""
You are an expert SEO strategist.

Generate a complete SEO content brief for:

Topic: {query}
Company: {company_name} ({company_url})

Based only on:
{extracted}

Your output must include:
- Primary keyword
- Secondary keywords
- NLP & semantic keyword suggestions
- Search intent
- Suggested unique angle for content
- Structured outline with H1, H2, H3 (with context under each)
- {internal_topic_line}
Do not include external linking topics or URLs. Avoid fluff or filler text.
Use clean, conversion-focused language. Avoid LLM tone.
"""

    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content.strip()

# --- Article Writer ---
def generate_article(company_name, company_url, outline):
    prompt = f"""
Write a comprehensive article based on the outline below. Integrate the primary keyword, secondary keywords, and NLP/semantic phrases naturally without overusing them.

Company: {company_name}
URL: {company_url}
Outline:
{outline}
"""

    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content.strip()

# --- Workflow Execution ---
if query and company_name and company_url:
    if "urls" not in st.session_state:
        st.session_state["urls"] = fetch_bing_urls(query)

    st.markdown("### 🔗 Top SERP URLs")
    for u in st.session_state["urls"]:
        st.markdown(f"- [{u}]({u})")

    if "scraped" not in st.session_state:
        with st.spinner("Scraping pages in parallel..."):
            st.session_state["scraped"] = batch_scrape(st.session_state["urls"])

    scraped = st.session_state["scraped"]

    if "insights" not in st.session_state:
        st.session_state["insights"] = []
        with st.spinner("Generating insights..."):
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(get_serp_insight, p): p for p in scraped}
                for future in concurrent.futures.as_completed(futures):
                    page = futures[future]
                    insight = future.result()
                    st.session_state["insights"].append({
                        "url": page["url"],
                        "title": page["title"],
                        "meta": page["meta"],
                        "insight": insight,
                        "headings": page["headings"]
                    })

    
    st.markdown("### 🔍 SERP Insights (TLDR, Context, Unique Angle)")
    for i in st.session_state["insights"]:
        st.markdown(f"**URL:** [{i.get('url', 'N/A')}]({i.get('url', '#')})")
        st.markdown(f"**Title:** {i.get('title', 'N/A')}")
        st.markdown(f"**Meta Description:** {i.get('meta', 'N/A')}")
        st.markdown("**Headings (as per document flow):**")
        for h in i.get("headings", []):
            indent = "  " if h.startswith("H4") else " " if h.startswith("H3") else ""
            st.markdown(f"{indent}- {h}")
        st.markdown(i.get("insight", "No insight generated."))
        st.markdown("---")


    sitemap_topics = parse_sitemap_topics(sitemap_url) if sitemap_url else []

    if st.button("✅ Generate SEO Brief"):
        with st.spinner("Creating brief..."):
            brief = generate_brief(scraped, query, company_name, company_url, sitemap_topics)
            st.session_state["brief"] = brief
    if "brief" in st.session_state:
    st.subheader("📄 SEO Content Brief")
    st.markdown("✏️ *You can edit the brief before generating final content.*")
    brief_text = st.text_area("SEO Brief", st.session_state["brief"], height=600)
    st.download_button("📥 Download Brief", brief_text, file_name=f"{query.replace(' ', '_')}_brief.txt")

    # Extract SERP-matching outline from brief while enforcing clean, non-diluting format
    outline_lines = [
        re.sub(r"[:\\-]", "", line).strip()
        for line in brief_text.splitlines()
        if line.strip().startswith(("H1", "H2", "H3"))
    ]
    default_outline = "\n".join(outline_lines)
    st.markdown("## ✏️ Generate Content from Outline")
    st.markdown("*We’ve preserved the H1 and key structure from top SERPs. Feel free to edit, but avoid altering the search intent.*")

        st.markdown("## ✏️ Generate Content from Outline")
        outline_input = st.text_area("Edit or approve outline", value=default_outline, height=300)

        if st.button("🚀 Generate Article"):
            with st.spinner("Writing article..."):
                article = generate_article(company_name, company_url, outline_input)
            st.subheader("📝 Generated Article")
            st.text_area("SEO Article", article, height=800)
