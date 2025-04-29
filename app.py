import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import openai
import time

# Load secrets
openai.api_key = st.secrets["openai_api_key"]
scraperapi_key = st.secrets["scraperapi_key"]

st.set_page_config(page_title="SEO Brief Generator", layout="wide")
st.title("SEO Brief Generator")

# --- User Inputs ---
keyword = st.text_input("Enter a keyword to generate a brief")
company_name = st.text_input("Company name")
company_url = st.text_input("Website URL (for internal links)")
sitemap_url = st.text_input("Optional: Sitemap URL (not used yet)")

# --- Bing Scraper ---
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

# --- ScraperAPI Extraction ---
def scrape_with_scraperapi(url):
    for _ in range(3):
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
            time.sleep(1)
    return None

# --- SEO Brief Generator ---
def generate_brief(keyword, pages, company_name, company_url):
    extracted = ""
    for p in pages:
        title = p.get("title", "")
        meta = p.get("meta", "")
        headings = "\n".join(p.get("headings", []))
        extracted += f"URL: {p['url']}\nTitle: {title}\nMeta: {meta}\nHeadings:\n{headings}\n---\n"

    prompt = f"""
You are an advanced SEO strategist. Given the data below from top-ranking pages, generate a smart SEO content brief.

Keyword: {keyword}
Company: {company_name} ({company_url})
SERP Data:
{extracted}

Brief must include:
- Search intent
- Primary keyword, secondary keywords, NLP/semantic terms
- Unique angle (linked to the company if relevant)
- Suggested H1, H2, H3 structure with writer-friendly context
- Internal link ideas only if status is 200 on {company_url}
- Valid external sources
- No generic or AI-sounding words like 'embrace', 'paradigm', 'landscape'
- Avoid outdated year suggestions (use {time.strftime('%Y')})

Give only clean, human-sounding output.
"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an SEO strategist generating conversion-focused briefs."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Error generating brief: {e}"

# --- Article Generator ---
def generate_article(company_name, company_url, outline):
    prompt = f"""
Write an article based on this outline. Avoid fluff and filler. Do not use overly formal or AI-sounding language.

Company: {company_name}
URL: {company_url}
Outline:
{outline}

Generate the article now:
"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You write clear, SEO-optimized articles without fluff."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Error generating article: {e}"

# --- Pipeline Execution ---
if keyword and company_name and company_url:
    with st.spinner("Fetching Bing results..."):
        urls = fetch_bing_urls(keyword)

    if urls:
        st.markdown("### Top SERP URLs")
        for u in urls:
            st.markdown(f"- [{u}]({u})")

        scraped = []
        for u in urls:
            with st.spinner(f"Scraping: {u}"):
                data = scrape_with_scraperapi(u)
                if data:
                    scraped.append(data)

        if scraped:
            with st.spinner("Generating brief..."):
                brief = generate_brief(keyword, scraped, company_name, company_url)

            st.subheader("Generated Brief")
            st.text_area("SEO Brief", brief, height=600)
            st.download_button("📥 Download Brief", brief, file_name=f"{keyword.replace(' ', '_')}_seo_brief.txt")

            # Step 2: Content Generation
            st.markdown("## ✍️ Generate Content from Outline")
            default_outline = "\n".join([f"H1: {keyword.title()}"])
            outline = st.text_area("Edit or approve outline (format: H1:, H2:, H3:)", value=default_outline)

            if st.button("Generate Article"):
                article = generate_article(company_name, company_url, outline)
                st.subheader("Generated Article")
                st.text_area("SEO Article", article, height=800)
        else:
            st.error("❌ Scraping failed for all URLs. Try another keyword or check your API key.")
    else:
        st.error("❌ No URLs fetched from Bing. Try again later or use a different keyword.")
