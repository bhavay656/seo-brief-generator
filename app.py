
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

def fetch_bing_urls(query, min_domains=5):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(f"https://www.bing.com/search?q={query}", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        links = []
        domains = set()
        for a in soup.select("li.b_algo h2 a"):
            href = a["href"]
            domain = urlparse(href).netloc
            if href.startswith("http") and domain not in domains:
                links.append(href)
                domains.add(domain)
            if len(links) >= 10:
                break
        return links
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

def get_serp_insight(page):
    title = page.get("title", "").strip()
    meta = page.get("meta", "").strip()
    headings = page.get("headings", [])

    if not title and not meta and not headings:
        return {"tldr": "❌ Not enough usable content."}

    prompt = f'''
You are an SEO strategist.

Analyze the following page and give:
1. TLDR (1–2 lines)
2. Context (What this page covers and how)
3. Unique hook or angle

Title: {title}
Meta: {meta}
Headings:
{chr(10).join(headings)}
'''
    try:
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        raw = res.choices[0].message.content.strip()
        return {"tldr": raw}
    except Exception as e:
        return {"tldr": f"❌ OpenAI error: {e}"}

if query and company_name and company_url:
    if "urls" not in st.session_state:
        scraped_urls = fetch_bing_urls(query)
        if len(scraped_urls) < 5:
            st.warning("Bing scraping failed or gave <5 unique domains. Please paste at least 10 manual URLs below.")
            st.stop()
        elif 5 <= len(scraped_urls) < 10:
            st.info("✅ Bing scraping gave 5-9 URLs. You can optionally add more below.")
        st.session_state["urls"] = scraped_urls + [url.strip() for url in manual_urls.split(",") if url.strip()]

    st.markdown("### 🔗 Top SERP + Reference URLs")
    for u in st.session_state["urls"]:
        st.markdown(f"- [{u}]({u})")

    confirmed = st.checkbox("✅ I've reviewed the URLs. Proceed to scrape content.")
    if confirmed and "scraped" not in st.session_state:
        with st.spinner("🔍 Scraping all pages in parallel..."):
            st.session_state["scraped"] = batch_scrape(st.session_state["urls"])

    scraped = st.session_state.get("scraped", [])
    sitemap_topics = parse_sitemap_topics(sitemap_url) if sitemap_url else []

    if scraped and "insights" not in st.session_state:
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

    if "insights" in st.session_state:
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
                from_insights = st.session_state["insights"]
                extracted = ""
                for p in from_insights:
                    extracted += f'''URL: {p['url']}
Title: {p['title']}
Meta: {p['meta']}
Headings:
{chr(10).join(p['headings'])}
Context: {p['tldr']}
---
'''
                internal_line = f"Internal linking topics: {', '.join(sitemap_topics)}." if sitemap_topics else ""
                prompt = f'''
You are an expert SEO strategist.

Generate a complete SEO content brief for:

Topic: {query}
Company: {company_name} ({company_url})

Based only on:
{extracted}

Include:
- Primary keyword
- Secondary keywords
- NLP & semantic keywords
- Search intent
- Unique angle
- Structured H1, H2, H3, H4 with context under each
- Add FAQ section (mandatory)
- {internal_line}
Minimum article word count: 2000+
Strict rules:
- No fluff, filler, or generic AI tone
- No banned phrases or robotic transitions
- Avoid all LLM-like expressions provided in earlier prompt
- Follow keyword density rule (max 3%)
- No internal links on primary keyword
'''
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
            content_prompt = f'''
Write a clear, human-written article for {company_name}, based on this outline:

{outline_input}

Rules:
- Minimum 2000 words
- Add a hook in the intro (2 short paras max)
- Add FAQ section (mandatory)
- Follow keyword rules: Max 3% density, no stuffing, natural tone
- Avoid LLM-like phrases and robotic transitions
- Avoid generic SEO phrasing (as listed)
- Make content sound personal, direct, and human

Output only the article.
'''
            res = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": content_prompt}]
            )
            article = res.choices[0].message.content.strip()
            st.session_state["article"] = article

    if "article" in st.session_state:
        st.subheader("📝 Generated Article")
        st.text_area("SEO Article", st.session_state["article"], height=800)
        st.download_button("📥 Download Article", st.session_state["article"], file_name=f"{query.replace(' ', '_')}_article.txt")
        feedback = st.text_area("✍️ Suggest edits to improve content")
        if st.button("🔄 Apply Feedback"):
            revision_prompt = f'''
Revise the article below based on this feedback: {feedback}

Apply these rules:
- Minimum 2000 words
- Add a hook to the intro
- Add FAQ section if missing
- Remove LLM-like phrases or transitions
- Follow keyword and tone rules from earlier brief

Article:
{st.session_state["article"]}
'''
            res = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": revision_prompt}]
            )
            revised_article = res.choices[0].message.content.strip()
            st.session_state["article"] = revised_article
            st.markdown("### 🔁 Revised Article")
            st.text_area("Updated Article", revised_article, height=800)
