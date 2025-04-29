
import streamlit as st
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from openai import OpenAI
import concurrent.futures
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

# ---- Bing Results ----
def fetch_bing_urls(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(f"https://www.bing.com/search?q={query}", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        links = [a["href"] for a in soup.select("li.b_algo h2 a") if a["href"].startswith("http")]
        return links[:10]
    except:
        return []

# ---- Scrape URLs ----
def scrape_with_scraperapi(url):
    try:
        r = requests.get(f"http://api.scraperapi.com?api_key={scraperapi_key}&url={url}", timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string.strip() if soup.title else "N/A"
        meta = soup.find("meta", attrs={"name": "description"})
        meta = meta["content"].strip() if meta and "content" in meta.attrs else "N/A"
        headings = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
            text = tag.get_text(strip=True)
            if text:
                headings.append(tag.name.upper() + " " + text)
        return {"url": url, "title": title, "meta": meta, "headings": headings}
    except Exception as e:
        return {"url": url, "title": "N/A", "meta": "N/A", "headings": [], "error": str(e)}

def batch_scrape(urls):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(scrape_with_scraperapi, url) for url in urls]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    return results

def get_serp_insight(title, meta, headings, url):
    prompt = f"""
You're an SEO content strategist.

URL: {url}
Title: {title}
Meta: {meta}
Headings: {headings}

Give me the following in less than 100 words each:
- TL;DR summary
- Writer-friendly context
- Unique angle (if any)

Avoid using banned phrases (e.g., 'comprehensive', 'delve', 'landscape', 'holistic', etc.) and sound human.
"""

    banned_words = ["delve", "landscape", "evolving", "context", "insight", "nuanced", "perspective",
                    "paradigm", "comprehensive", "supercharge", "framework", "facet", "dynamic",
                    "intricacies", "holistic", "iterative", "synergy", "confluence", "pivotal", "nuance",
                    "robust", "transformative", "underpinning", "spectrum", "trajectory", "in-depth",
                    "at the core of", "a myriad of", "on a broader scale", "in the context of", "from a holistic perspective",
                    "taking into account", "a dynamic interplay", "evolving over time", "a comprehensive overview",
                    "intricacies involved", "a pivotal role", "underpinning principles", "the spectrum of", "transformative impact"]

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "Error generating insight."

def parse_sitemap_topics(sitemap_url):
    topics = []
    try:
        r = requests.get(sitemap_url, timeout=10)
        root = ET.fromstring(r.content)
        for url in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            path = urlparse(url.text).path.strip("/")
            topics.append(path.split("/")[-1].replace("-", " ").title())
    except:
        pass
    return topics[:10]

def generate_brief(scraped, query, company_name, company_url, sitemap_topics):
    prompt = f"""
Act as a senior SEO content strategist.

You’ve reviewed these competitor pages:
{scraped}

Based on the heading structures, generate an SEO content brief for the topic: "{query}".

Use heading tags (H1, H2, H3). Keep H1 identical to the SERP intent. Do not use colons or dashes in any heading. Do not use AI-sounding or banned phrases. Add unique angle for each section wherever possible. Suggest internal linking topics using these:
{sitemap_topics if sitemap_topics else "User has not provided sitemap."}

Do not include external references.

End with a human-style note for writers.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "Brief generation failed."

def generate_article(company_name, company_url, outline, user_feedback=None):
    prompt = f"""
You’re a SaaS content writer for the company {company_name} ({company_url}).

Write a detailed SEO article based on this outline:
{outline}

Rules:
- Avoid banned phrases: no 'delve', 'comprehensive', 'landscape', etc.
- Word count must be at least 1800 words unless search intent is shallow.
- Use natural tone, don’t exaggerate.
- Use semantic SEO terms around the main topic.
- Mention primary & secondary keywords naturally.

{"User feedback: " + user_feedback if user_feedback else ""}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "Article generation failed."

# --- STREAMLIT MAIN FLOW ---

st.subheader("🔍 SERP Insights (TLDR, Context, Unique Angle)")

urls = fetch_bing_urls(query)
st.markdown("### 🔗 Top SERP URLs")
for u in urls:
    st.markdown(f"- [{u}]({u})")

scraped = batch_scrape(urls)
st.session_state["insights"] = []

for page in scraped:
    page["insight"] = get_serp_insight(page["title"], page["meta"], page["headings"], page["url"])
    st.session_state["insights"].append(page)

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

    # Clean heading structure
    outline_lines = [
        re.sub(r"[:\-]", "", line).strip()
        for line in brief_text.splitlines()
        if line.strip().startswith(("H1", "H2", "H3"))
    ]
    default_outline = "\n".join(outline_lines)
    st.markdown("## ✏️ Generate Content from Outline")
    st.markdown("*We've preserved the H1 and key structure from top SERPs. Feel free to edit, but avoid altering the search intent.*")
    outline_input = st.text_area("Edit or approve outline", value=default_outline, height=300)

    if st.button("🚀 Generate Article"):
        with st.spinner("Writing article..."):
            article = generate_article(company_name, company_url, outline_input)
            st.session_state["article"] = article

if "article" in st.session_state:
    st.subheader("📝 Generated Article")
    article = st.session_state["article"]
    st.text_area("SEO Article", article, height=800)
    st.download_button("📥 Download Article", article, file_name=f"{query.replace(' ', '_')}_article.txt")
    feedback = st.text_area("Want to improve the article? Describe what you'd like to change.")
    if st.button("🔄 Improve Article Based on Feedback"):
        with st.spinner("Regenerating..."):
            updated = generate_article(company_name, company_url, outline_input, feedback)
            st.session_state["article"] = updated
