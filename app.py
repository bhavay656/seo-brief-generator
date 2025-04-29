import streamlit as st
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from openai import OpenAI
import graphviz
import time
import random

st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")

st.title("SEO Content Brief Generator")
st.markdown(
    "This app scrapes top-ranking pages for your keyword, extracts real heading flow with context instructions, identifies schemas, "
    "suggests internal links, builds NLP/semantic clusters, and generates a skim-friendly, mindmap-visual SEO content brief."
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
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return r.text
        except:
            time.sleep(random.uniform(1, 2))
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
        if tag.string:
            try:
                import json
                data = json.loads(tag.string)
                if isinstance(data, dict) and "@type" in data:
                    if isinstance(data["@type"], list):
                        schemas.extend(data["@type"])
                    else:
                        schemas.append(data["@type"])
                if isinstance(data, list):
                    for item in data:
                        if "@type" in item:
                            schemas.append(item["@type"])
            except:
                continue
    return list(set(schemas))

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

def generate_mindmap_graphviz(flow):
    dot = graphviz.Digraph()
    last_tag = "H1"
    main_node = "Main"
    dot.node(main_node, label="Main Topic", shape="rectangle")
    counter = 0
    for tag, text in flow:
        counter += 1
        current = f"node{counter}"
        dot.node(current, label=text)
        if tag == "H1":
            dot.edge(main_node, current)
            last_tag = current
        elif tag == "H2":
            dot.edge(main_node, current)
            last_tag = current
        else:
            dot.edge(last_tag, current)
    return dot

def generate_brief(openai_api_key, keyword, headings_data, internal_links, domain, schemas, serp_summary):
    client = OpenAI(api_key=openai_api_key)
    prompt = f"""You are an expert SEO strategist. Create a detailed, skim-friendly content brief for the keyword "{keyword}".\n\nInclude:\n
- Primary and secondary keywords\n
- NLP/semantic keyword suggestions\n
- Keyword clusters\n
- Heading structure as per flow (Heading → context)\n
- Internal link suggestions from domain {domain}\n
- External neutral linking ideas\n
- Summarize detected schema types: {schemas}\n
- Summarize SERP differentiation themes: {serp_summary}\n
Make it engaging, bullet points, skim friendly.
Headings scraped:\n{headings_data}
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )
    return response.choices[0].message.content

if st.button("Generate SEO Brief"):
    if not all([openai_api_key, scraperapi_key, company_name, company_domain, target_keyword]):
        st.error("All fields are required.")
    else:
        with st.spinner("Fetching Bing URLs..."):
            urls = get_top_bing_urls(target_keyword)
            st.success(f"Fetched {len(urls)} URLs.")

        headings_all = []
        combined_data = ""
        failed_urls = []

        for url in urls:
            html = fetch_html(url)
            if not html:
                failed_urls.append(url)
                continue
            title, meta = extract_meta(html)
            flow = extract_headings_flow(html)
            schemas = extract_schemas(html)

            st.markdown("---")
            st.markdown(f"### Scraped URL: [{url}]({url})")
            st.write(f"Page Title: {title}")
            st.write(f"Meta Description: {meta}")
            st.write(f"Schemas Detected: {', '.join(schemas) if schemas else 'None'}")

            st.write("#### Heading Flow (with Context):")
            for tag, text in flow:
                st.write(f"**{tag}**: {text}")
                st.caption("Context: Short instruction for this heading.")

            combined_data += f"URL: {url}\nTitle: {title}\nMeta: {meta}\nSchemas: {schemas}\nHeadings:\n" +                              "\n".join([f"{tag}: {text}" for tag, text in flow]) + "\n"
            headings_all.append(flow)

        serp_themes = ", ".join(list(set([txt for flow in headings_all for _, txt in flow][:6])))

        st.subheader("SERP Differentiation Themes")
        st.write(serp_themes)

        st.subheader("Suggested Internal Links")
        internal_links = get_internal_links(sitemap_urls, target_keyword)
        if internal_links:
            for link in internal_links:
                st.write(link)
        else:
            st.warning("No relevant internal links found.")

        st.subheader("Generated Full SEO Content Brief")
        final_brief = generate_brief(openai_api_key, target_keyword, combined_data, internal_links, company_domain, schemas, serp_themes)
        st.code(final_brief)

        st.subheader("Mindmap of Heading Flow (Auto Visualized)")
        dot = generate_mindmap_graphviz([item for sublist in headings_all for item in sublist])
        st.graphviz_chart(dot)

        if failed_urls:
            st.error(f"Failed to scrape {len(failed_urls)} URLs after retries.")
            for url in failed_urls:
                st.write(url)
