
import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
import concurrent.futures
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import openai

openai.api_key = st.secrets["OPENAI_API_KEY"]
scraperapi_key = st.secrets["SCRAPERAPI_KEY"]

def fetch_bing_urls(query, max_results=10):
    headers = {"Ocp-Apim-Subscription-Key": st.secrets["BING_API_KEY"]}
    params = {"q": query, "count": 20}
    endpoint = "https://api.bing.microsoft.com/v7.0/search"
    domains = set()
    urls = []

    try:
        res = requests.get(endpoint, headers=headers, params=params).json()
        for item in res.get("webPages", {}).get("value", []):
            domain = urlparse(item["url"]).netloc
            if domain not in domains:
                domains.add(domain)
                urls.append(item["url"])
            if len(urls) >= max_results:
                break
    except Exception as e:
        st.warning(f"Bing scraping failed: {e}")
    return urls

def scrape_with_scraperapi(url, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            full_url = f"http://api.scraperapi.com?api_key={scraperapi_key}&url={url}"
            r = requests.get(full_url, timeout=15)
            soup = BeautifulSoup(r.content, "html.parser")
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

def batch_scrape(urls, batch_size=4):
    scraped = []
    for i in range(0, len(urls), batch_size):
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
            batch = urls[i:i+batch_size]
            future_to_url = {executor.submit(scrape_with_scraperapi, url): url for url in batch}
            for future in concurrent.futures.as_completed(future_to_url):
                result = future.result()
                if result:
                    scraped.append(result)
    return scraped

def get_serp_insight(scraped):
    insights = []
    for s in scraped:
        insight = {
            "url": s["url"],
            "title": s["title"],
            "meta": s["meta"],
            "tldr": s["meta"][:250],
            "headings": s["headings"][:10]
        }
        insights.append(insight)
    return insights

def generate_brief_and_content(insights, keyword, topic):
    heading_list = []
    for entry in insights:
        heading_list.extend(entry["headings"])

    prompt = (
        "You're an expert SEO writer. Based on these competitor insights and headings, create a brief followed by a 2000+ word article.

"
        f"- Topic: {topic}
"
        f"- Keyword: {keyword}
"
        "- Include all headings (H1–H4)
"
        "- Keep keyword density <3%
"
        "- Avoid AI-like phrases (delve, landscape, evolving, indeed, etc.)
"
        "- Add conversational FAQs within the flow
"
        "- Avoid fluffy intros, go straight to the point
"
        "- No keyword stuffing

"
        "Headings:
" + "
".join(heading_list) + "

" +
        "Insights:
" + "
".join(i['tldr'] for i in insights)
    )

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"]

# Streamlit UI
st.title("SEO Brief Generator")

keyword = st.text_input("Target Keyword (optional)")
topic = st.text_input("Content Topic (optional)")
company = st.text_input("Company name")
company_url = st.text_input("Website URL (for internal links)")
sitemap_url = st.text_input("Sitemap.xml URL (for topic suggestions)")

scraped_urls = []
if keyword or topic:
    with st.spinner("Scraping Bing for SERPs..."):
        scraped_urls = fetch_bing_urls(keyword or topic)

if scraped_urls and len(scraped_urls) >= 5:
    st.markdown("### 🔗 Top SERP + Reference URLs")
    for url in scraped_urls:
        st.markdown(f"- [{url}]({url})")

    if len(scraped_urls) < 10:
        st.info("You can optionally add more URLs below to improve coverage.")
    manual_urls = st.text_area("Add reference URLs manually (comma-separated)")
    url_list = scraped_urls + [u.strip() for u in manual_urls.split(",") if u.strip()]

    proceed = st.checkbox("✅ I've reviewed the URLs. Proceed to scrape content.")
    if proceed:
        with st.spinner("Scraping content..."):
            scraped = batch_scrape(url_list[:10])
            insights = get_serp_insight(scraped)
            st.markdown("### ✍️ Review the Brief Below")
            brief_draft = "\n\n".join(
                [f"**{i['title']}**\n{i['meta']}\n" + "\n".join(i['headings']) for i in insights]
            )
            updated_brief = st.text_area("Edit Brief if Needed:", brief_draft, height=300)
            if st.button("✍️ Generate SEO Article"):
                with st.spinner("🧠 Generating final content..."):
                    article = generate_brief_and_content(insights, keyword, topic)
                    st.markdown("### ✅ Final Article")
                    st.markdown(article)
else:
    st.warning("Bing scraping failed or returned <5 domains. Please enter at least 5 URLs manually.")
