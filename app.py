
import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from openai import OpenAI
import re

client = OpenAI(api_key=st.secrets["openai_api_key"])
scraperapi_key = st.secrets["scraperapi_key"]

st.set_page_config(page_title="SEO Brief Generator", layout="wide")
st.title("SEO Brief Generator")

# ---- Inputs ----
keyword = st.text_input("Target Keyword (optional)")
topic = st.text_input("Content Topic (optional)")
company_name = st.text_input("Company name")
company_url = st.text_input("Website URL (for internal links)")
sitemap_url = st.text_input("Sitemap.xml URL (for topic suggestions)")

if not keyword and not topic:
    st.warning("Please enter either a keyword or content topic.")
    st.stop()

query = keyword or topic

# ---- Fetch SERP URLs ----
def fetch_serp_urls(query, retries=3):
    headers = {
        "User-Agent": "Mozilla/5.0",
    }
    query_encoded = quote(query)
    urls = []

    def resolve_redirected_url(url):
        try:
            r = requests.get(url, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            meta = soup.find("meta", attrs={"http-equiv": "refresh"})
            if meta and "url=" in meta.get("content", ""):
                return meta["content"].split("url=")[-1].strip()
            canonical = soup.find("link", rel="canonical")
            if canonical and canonical.get("href"):
                return canonical["href"]
            return r.url
        except:
            return url

    # 1. Try Bing direct
    try:
        r = requests.get(f"https://www.bing.com/search?q={query_encoded}", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        raw_links = [a["href"] for a in soup.select("li.b_algo h2 a") if a.get("href")]
        urls = [resolve_redirected_url(link) for link in raw_links if link.startswith("http")]
        urls = list(dict.fromkeys(urls))[:10]
        if urls:
            return urls
    except:
        pass

    # 2. Fallback to Bing via ScraperAPI
    try:
        r = requests.get(
            f"http://api.scraperapi.com?api_key={scraperapi_key}&url=https://www.bing.com/search?q={query_encoded}",
            timeout=10
        )
        soup = BeautifulSoup(r.text, "html.parser")
        raw_links = [a["href"] for a in soup.select("li.b_algo h2 a") if a.get("href")]
        urls = [resolve_redirected_url(link) for link in raw_links if link.startswith("http")]
        urls = list(dict.fromkeys(urls))[:10]
        if urls:
            return urls
    except:
        pass

    return []

# ---- Get Title, Meta, Headings ----
def get_title_meta_headings(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string.strip() if soup.title else ""
        meta = soup.find("meta", attrs={"name": "description"})
        meta_content = meta["content"].strip() if meta else ""
        headings = [h.get_text().strip() for h in soup.find_all(["h1", "h2", "h3", "h4"])]
        return {"url": url, "title": title, "meta": meta_content, "headings": headings}
    except:
        return {"url": url, "title": "", "meta": "", "headings": []}

def get_insight(title, meta, headings, url):
    prompt = f"""
You are an SEO content analyst. A user is researching the article at this URL: {url}
Here is the title: {title}
Meta description: {meta}
Headings: {headings}

Write a TLDR, key context, and unique angle a writer should follow for this article.
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return res.choices[0].message.content.strip()
    except:
        return "No insight generated."

# ---------- Streamlit Flow ----------
st.subheader("🔗 Top SERP URLs")
urls = fetch_serp_urls(query)
st.markdown("### 🔗 Top SERP URLs")
for u in urls:
    st.markdown(f"- [{u}]({u})")

scraped = [get_title_meta_headings(u) for u in urls]
st.session_state["insights"] = []
for page in scraped:
    page["insight"] = get_insight(page["title"], page["meta"], page["headings"], page["url"])
    st.session_state["insights"].append(page)

st.subheader("🔍 SERP Insights")
for page in st.session_state["insights"]:
    st.markdown(f"**{page['title']}**")
    st.markdown(page["insight"])
    st.markdown("---")

# Step 4: Generate Article
outline_lines = []
for page in scraped:
    outline_lines.extend([re.sub(r"[:\-]", "", line).strip() for line in page["headings"] if line.strip()])

default_outline = "\n".join(outline_lines)
st.markdown("## ✍️ Generate Content from Outline")
outline_input = st.text_area("Edit or approve outline", value=default_outline, height=300)

# Article Generation Function
def generate_article(company_name, company_url, outline_input, user_feedback=None):
    if user_feedback:
    prompt = f"""You are an SEO writer for {company_name} ({company_url}).

Write a clear, detailed, human-sounding article using the following outline:

{outline_input}

- Match SERP title (H1) to search intent
- Minimum word count: 1800
- Tone: Clean, natural, human
- Embed primary/secondary keywords and NLP terms
- Avoid exaggerated claims or AI generated language
- User feedback: {user_feedback}
"""
else:
    prompt = f"""You are an SEO writer for {company_name} ({company_url}).

Write a clear, detailed, human-sounding article using the following outline:

{outline_input}

- Match SERP title (H1) to search intent
- Minimum word count: 1800
- Tone: Clean, natural, human
- Embed primary/secondary keywords and NLP terms
- Avoid exaggerated claims or AI-generated language
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return res.choices[0].message.content.strip()
    except:
        return "Failed to generate."

if st.button("🚀 Generate SEO Brief"):
    article = generate_article(company_name, company_url, outline_input)
    st.session_state["article"] = article

if "article" in st.session_state:
    st.subheader("📝 Generated Article")
    st.text_area("SEO Article", st.session_state["article"], height=800)
    st.download_button("📥 Download Article", st.session_state["article"], file_name=f"{query.replace(' ', '_')}_article.txt")

    feedback = st.text_area("📝 Suggest edits to improve the article below", key="feedback")
    if st.button("🔄 Improve Article Based on Feedback"):
        improved = generate_article(company_name, company_url, outline_input, user_feedback=feedback)
        st.session_state["article"] = improved
