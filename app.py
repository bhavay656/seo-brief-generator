
import streamlit as st
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from openai import OpenAI
import time

st.set_page_config(page_title="SEO Content Brief Generator")

st.title("SEO Content Brief Generator")
st.markdown(
    "This app generates a detailed SEO content brief by scraping top-ranking pages from Bing for your target keyword. "
    "It extracts heading structure based on real document flow (not grouped by level), identifies schemas present, analyzes competitor differentiation, "
    "suggests internal links from your sitemap, and builds a complete writing guide with primary and secondary keywords."
)

openai_api_key = st.text_input("Enter your OpenAI API Key (Required)", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key (Required)", type="password")
company_name = st.text_input("Enter your Company Name (Required)")
company_domain = st.text_input("Enter your Company Website URL (example: yourwebsite.com)")
sitemap_urls = st.text_input("Enter one or multiple Sitemap URLs (comma-separated)")
target_keyword = st.text_input("Enter the Target Keyword (Required)")

def clean_bing_url(url):
    return url.split("&")[0]

def get_top_bing_urls(keyword):
    headers = {"User-Agent": "Mozilla/5.0"}
    forbidden_domains = [
        "bing.com", "youtube.com", "wikipedia.org", "linkedin.com", "facebook.com",
        "instagram.com", "twitter.com", "webcache.googleusercontent.com"
    ]
    urls = []
    seen_domains = set()
    for offset in range(0, 50, 10):
        params = {"q": keyword, "first": offset, "count": "10", "setLang": "EN", "cc": "US"}
        try:
            response = requests.get("https://www.bing.com/search", params=params, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            for li in soup.select("li.b_algo h2 a"):
                href = li.get("href")
                if not href:
                    continue
                parsed = urlparse(href)
                domain = parsed.netloc.lower()
                if parsed.scheme not in ["http", "https"]:
                    continue
                if any(bad in domain for bad in forbidden_domains):
                    continue
                if domain not in seen_domains:
                    seen_domains.add(domain)
                    urls.append(href)
                if len(urls) == 10:
                    break
        except:
            continue
        if len(urls) == 10:
            break
    return urls

def fetch_html(url, retries=3):
    for _ in range(retries):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return r.text
        except:
            time.sleep(1)
    return ""

def extract_headings_flow(html):
    soup = BeautifulSoup(html, "html.parser")
    flow = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        if tag.name and tag.get_text(strip=True):
            flow.append((tag.name.upper(), tag.get_text(strip=True)))
    return flow

def extract_meta(html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title else "N/A"
    desc = ""
    if soup.find("meta", attrs={"name": "description"}):
        desc = soup.find("meta", attrs={"name": "description"}).get("content", "")
    elif soup.find("meta", attrs={"property": "og:description"}):
        desc = soup.find("meta", attrs={"property": "og:description"}).get("content", "")
    return title, desc

def extract_schemas(html):
    soup = BeautifulSoup(html, "html.parser")
    schemas = []
    for tag in soup.find_all("script", type="application/ld+json"):
        if tag.string and '"@type":' in tag.string:
            schemas.append("Detected")
    return schemas

def show_headings_flow(flow):
    for tag, text in flow:
        indent = " " * (int(tag[1]) - 1) * 4
        st.write(f"{indent}{tag}: {text}")

def get_internal_links(sitemap_urls, keyword):
    internal_links = []
    for url in sitemap_urls.split(","):
        try:
            r = requests.get(url.strip(), timeout=10)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                for elem in root.iter():
                    if elem.tag.endswith("loc") and keyword.lower().replace(" ", "-") in elem.text.lower():
                        if requests.head(elem.text).status_code == 200:
                            internal_links.append(elem.text)
        except:
            continue
    return internal_links[:3]

def generate_serp_diff(headings_flow_all):
    all_lines = [txt.lower() for flow in headings_flow_all for _, txt in flow if len(txt) < 120]
    top_themes = list(set(all_lines[:6]))
    return f"The top ranking articles consistently cover these themes: {', '.join(top_themes)}. Consider adding unique angles or comparisons to differentiate."

def generate_brief(openai_api_key, keyword, competitor_data, domain, internal_links):
    client = OpenAI(api_key=openai_api_key)
    prompt = f"""You are an expert SEO strategist. Create a detailed content brief for the keyword "{keyword}" based on the competitor data below. Include:

1. Primary and secondary keywords
2. Suggested heading structure as per document flow
3. Context/direction for each heading
4. Internal linking suggestions from this domain: {domain}
5. Neutral external link ideas
6. SERP differentiation advice
7. Schemas detected in competitors

Competitor Pages:
{competitor_data}
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content

if st.button("Generate SEO Brief"):
    if not all([openai_api_key, scraperapi_key, company_name, company_domain, target_keyword]):
        st.error("All fields are required.")
    else:
        with st.spinner("Fetching top URLs from Bing..."):
            urls = get_top_bing_urls(target_keyword)
            st.success(f"Fetched {len(urls)} URLs.")

        st.subheader("List of Fetched URLs:")
        for i, url in enumerate(urls):
            st.markdown(f"{i+1}. [{url}]({url})")

        all_data = []
        all_headings = []
        for url in urls:
            st.markdown("---")
            st.subheader(f"Scraped URL: [{url}]({url})")
            html = fetch_html(url)
            title, meta = extract_meta(html)
            flow = extract_headings_flow(html)
            schemas = extract_schemas(html)

            st.write("Page Title:", title)
            st.write("Meta Description:", meta)
            st.write("Heading Flow (Document Order):")
            show_headings_flow(flow)
            st.write("Schemas Detected:", ", ".join(schemas) if schemas else "None")

            combined = f"URL: {url}\nTitle: {title}\nMeta: {meta}\nSchemas: {schemas}\nHeadings:\n" +                        "\n".join([f"{tag}: {text}" for tag, text in flow])
            all_data.append(combined)
            all_headings.append(flow)

        st.subheader("SERP Differentiation Summary")
        st.write(generate_serp_diff(all_headings))

        st.subheader("Suggested Internal Links")
        internal_links = get_internal_links(sitemap_urls, target_keyword)
        for link in internal_links:
            st.write(link)

        st.subheader("Generated SEO Content Brief")
        final_brief = generate_brief(openai_api_key, target_keyword, "\n\n".join(all_data), company_domain, internal_links)
        st.code(final_brief)
