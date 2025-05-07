
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

query = keyword or topic
if not query:
    st.warning("Please enter either a keyword or content topic.")
    st.stop()

def fetch_bing_unique_domains(query, max_urls=10):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(f"https://www.bing.com/search?q={query}", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        urls, seen_domains = [], set()
        for a in soup.select("li.b_algo h2 a"):
            href = a.get("href")
            domain = urlparse(href).netloc.replace("www.", "")
            if href and domain not in seen_domains:
                seen_domains.add(domain)
                urls.append(href)
            if len(urls) >= max_urls:
                break
        return urls
    except:
        return []

if "urls_fetched" not in st.session_state:
    st.session_state["urls_fetched"] = fetch_bing_unique_domains(query)

urls = st.session_state["urls_fetched"]

manual_urls = ""
if urls:
    st.markdown("### 🔗 Top SERP + Reference URLs")
    for u in urls:
        st.markdown(f"- [{u}]({u})")

    if len(urls) < 5:
        st.warning("Bing scraping gave <5 unique domains. Please paste at least 5 manual URLs below.")
    elif len(urls) < 10:
        st.info("You can optionally add more URLs below to improve coverage.")

    manual_urls = st.text_area("Add reference URLs manually (comma-separated)")
    confirmed = st.checkbox("✅ I've reviewed the URLs. Proceed to scrape content.")
else:
    st.warning("Bing scraping failed or gave no usable URLs. Please paste at least 5 manual URLs below.")
    manual_urls = st.text_area("Add reference URLs manually (comma-separated)")
    confirmed = st.checkbox("✅ I've added 5+ URLs. Proceed to scrape content.")

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

    try:
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        raw = res.choices[0].message.content.strip()
        return {"tldr": raw}
    except Exception as e:
        return {"tldr": f"❌ OpenAI error: {e}"}

sitemap_topics = parse_sitemap_topics(sitemap_url) if sitemap_url else []
urls_to_scrape = urls + [url.strip() for url in manual_urls.split(",") if url.strip()]
urls_to_scrape = list(dict.fromkeys(urls_to_scrape))  # Remove duplicates

if confirmed and urls_to_scrape:
    with st.spinner("🔍 Scraping all pages..."):
        scraped_pages = batch_scrape(urls_to_scrape)

    with st.spinner("📊 Generating insights..."):
        insights = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(get_serp_insight, p): p for p in scraped_pages}
            for future in concurrent.futures.as_completed(futures):
                page = futures[future]
                result = future.result()
                insights.append({
                    "url": page["url"],
                    "title": page["title"],
                    "meta": page["meta"],
                    "headings": page["headings"],
                    "tldr": result.get("tldr", "")
                })
        st.session_state["insights"] = insights

def generate_brief(insights, keyword, company_name, sitemap_topics):
    context = "\n\n".join([
        f"URL: {i['url']}\nTitle: {i['title']}\nMeta: {i['meta']}\nHeadings:\n" + "\n".join(i["headings"])
        for i in insights if i["headings"]
    ])
    prompt = f"""
Write a 2000+ word SEO article on "{keyword}" for {company_name} using the insights below.

Follow these rules:
1. Use all heading levels (H1–H4) wherever contextually needed.
2. Add a FAQs section at the end with at least 5 detailed questions and answers.
3. Avoid AI-like words and phrases like: "delve", "insight", "pivotal", etc.
4. Don’t say: "To sum up", "In conclusion", "Clearly", or use phrases like "Not only...but also..."
5. Do not use overused transitions like "Moreover", "Furthermore".
6. Start with a short, sharp intro (2 small paragraphs).
7. Keep keyword density for "{keyword}" under 3%.
8. Avoid fluff. Be direct and sharp.
9. Do not link the keyword itself.
10. Use a natural tone with occasional anecdotes.

INSIGHTS:
{context}

SITEMAP TOPICS:
{", ".join(sitemap_topics)}

Generate a clean, human-style article with formatting.
"""

    try:
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Error generating brief: {e}"

if "insights" in st.session_state:
    if st.button("✍ Generate SEO Article"):
        with st.spinner("Creating final article..."):
            article = generate_brief(st.session_state["insights"], keyword, company_name, sitemap_topics)
            st.session_state["article"] = article

if "article" in st.session_state:
    st.markdown(st.session_state["article"])
    st.download_button("📄 Download Article", st.session_state["article"], file_name="seo_article.md")

    feedback = st.text_area("✍ Suggest edits to improve content")
    if st.button("💬 Apply Feedback"):
        revised_prompt = f"""
Revise the below article based on this feedback: "{feedback}"

CONTENT:
{st.session_state["article"]}

Rules:
- Keep it sharp and human.
- Enforce keyword density <3%.
- Avoid AI-style fluff or repetitive phrasing.
- Rewrite only what’s needed.

Return final article only.
"""
        with st.spinner("Updating content..."):
            try:
                res = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": revised_prompt}]
                )
                st.session_state["article"] = res.choices[0].message.content.strip()
                st.markdown("---")
                st.markdown("### ✅ Updated Article")
                st.markdown(st.session_state["article"])
            except Exception as e:
                st.error(f"❌ Error applying feedback: {e}")
