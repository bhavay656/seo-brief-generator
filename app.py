import streamlit as st
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from openai import OpenAI
import time
import concurrent.futures

# --- Initialize OpenAI ---
client = OpenAI(api_key=st.secrets["openai_api_key"])
scraperapi_key = st.secrets["scraperapi_key"]

st.set_page_config(page_title="SEO Brief Generator", layout="wide")
st.title("SEO Brief Generator")

# --- User Inputs ---
st.markdown("Enter either a target **keyword** or a content **topic**. One is mandatory.")
keyword = st.text_input("Target Keyword (optional)")
topic = st.text_input("Content Topic (optional)")
company_name = st.text_input("Company name")
company_url = st.text_input("Website URL (for internal links)")
sitemap_url = st.text_input("Sitemap.xml URL (for topic suggestions)")

# Check one of topic or keyword is provided
if not keyword and not topic:
    st.warning("Please enter either a keyword or topic.")
    st.stop()

# --- Bing Search ---
def fetch_bing_urls(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    for _ in range(3):
        try:
            r = requests.get(f"https://www.bing.com/search?q={query}", headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            links = [a["href"] for a in soup.select("li.b_algo h2 a") if a["href"].startswith("http")]
            if links:
                return links[:10]
        except Exception:
            time.sleep(1)
    return []

# --- Scrape with ScraperAPI ---
def scrape_with_scraperapi(url):
    try:
        full_url = f"http://api.scraperapi.com?api_key={scraperapi_key}&url={url}"
        r = requests.get(full_url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string.strip() if soup.title else ""
        meta = soup.find("meta", attrs={"name": "description"})
        meta_desc = meta["content"].strip() if meta and "content" in meta.attrs else ""
        h1 = [h.get_text(strip=True) for h in soup.find_all("h1")]
        h2 = [h.get_text(strip=True) for h in soup.find_all("h2")]
        h3 = [h.get_text(strip=True) for h in soup.find_all("h3")]
        h4 = [h.get_text(strip=True) for h in soup.find_all("h4")]
        return {"url": url, "title": title, "meta": meta_desc, "headings": h1 + h2 + h3 + h4}
    except Exception:
        return None

def batch_scrape(urls):
    scraped_pages = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_url = {executor.submit(scrape_with_scraperapi, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                if result:
                    scraped_pages.append(result)
            except Exception as e:
                st.warning(f"Failed to scrape {url}: {e}")
    return scraped_pages

# --- Sitemap Parsing for Topic Suggestions ---
def parse_sitemap_topics(sitemap_url):
    try:
        r = requests.get(sitemap_url, timeout=10)
        tree = ET.fromstring(r.content)
        urls = [elem[0].text for elem in tree.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")]
        topics = [urlparse(url).path.strip("/").replace("-", " ").title() for url in urls if url]
        return list(set(topics))[:10]  # Limit to 10 unique ones
    except Exception:
        return []

# --- Insight Generator per Page ---
def get_serp_insight(page):
    prompt = f"""
Given the following data from a web page:
Title: {page['title']}
Meta: {page['meta']}
Headings: {page['headings']}

Return:
- TLDR summary (1–2 lines)
- Writer-friendly context
- Unique insight or angle

Output in clean bullet points.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except:
        return "❌ Error generating insight."

# --- Brief Generator ---
def generate_brief(pages, keyword, topic, company_name, company_url, sitemap_topics):
    extracted = ""
    for p in pages:
        title = p.get("title", "")
        meta = p.get("meta", "")
        headings = "\n".join(p.get("headings", []))
        extracted += f"URL: {p['url']}\nTitle: {title}\nMeta: {meta}\nHeadings:\n{headings}\n---\n"

    prompt = f"""
You are an advanced SEO strategist. Based on SERP data and sitemap clusters, create an SEO content brief.

Topic: {topic or keyword}
Company: {company_name} ({company_url})
Sitemap Clusters: {', '.join(sitemap_topics)}

SERP Data:
{extracted}

Instructions:
- Only use insights based on SERP content.
- Suggest H1, H2, H3 structure with writer context.
- Suggest internal linking **topics** only (from sitemap or SERP), not actual URLs.
- Suggest external reference **topics**, not URLs.
- No AI-sounding words like "paradigm", "delve", etc.
- Use {time.strftime('%Y')} in place of any outdated years.

Return the full brief in a clean, structured format.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Error generating brief: {e}"

# --- Article Generator ---
def generate_article(company_name, company_url, outline):
    prompt = f"""
Write an article from this outline. No fluff. Use natural, clear language.

Company: {company_name}
URL: {company_url}
Outline:
{outline}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except:
        return "❌ Error generating article."

# --- Run the App Logic ---
query = keyword or topic
if query and company_name and company_url:
    with st.spinner("Fetching SERP results..."):
        urls = fetch_bing_urls(query)

    if urls:
        st.markdown("### 🔗 Top SERP URLs")
        for u in urls:
            st.markdown(f"- [{u}]({u})")

        with st.spinner("Scraping URLs..."):
            scraped = batch_scrape(urls)

        if scraped:
            st.markdown("### 🔍 SERP Insights (TLDR, Context, Unique Angle)")
            for page in scraped:
                with st.spinner(f"Analyzing: {page['url']}"):
                    insight = get_serp_insight(page)
                st.markdown(f"**URL**: {page['url']}")
                st.markdown(insight)
                st.markdown("---")

            sitemap_topics = parse_sitemap_topics(sitemap_url) if sitemap_url else []

            if st.button("✅ Generate SEO Brief"):
                with st.spinner("Generating brief..."):
                    brief = generate_brief(scraped, keyword, topic, company_name, company_url, sitemap_topics)

                st.subheader("📄 SEO Content Brief")
                st.markdown("✍️ *You can edit the brief before generating final content.*")
                st.text_area("SEO Brief", brief, height=600)
                st.download_button("📥 Download Brief", brief, file_name=f"{query.replace(' ', '_')}_brief.txt")

                # Extract outline lines from brief
                suggested_outline = "\n".join([line for line in brief.splitlines() if line.startswith("H1") or line.startswith("H2") or line.startswith("H3")])
                st.markdown("## ✏️ Generate Content from Outline")
                st.text_area("Edit or approve outline (format: H1:, H2:, H3:)", value=suggested_outline, key="outline_input")

                if st.button("🚀 Generate Article"):
                    outline = st.session_state.outline_input
                    with st.spinner("Generating article..."):
                        article = generate_article(company_name, company_url, outline)
                    st.subheader("📝 Generated Article")
                    st.text_area("SEO Article", article, height=800)
        else:
            st.error("❌ No data scraped. Try another topic or keyword.")
    else:
        st.error("❌ Bing search failed.")
