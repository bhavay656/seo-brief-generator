import streamlit as st
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup, SoupStrainer
import xml.etree.ElementTree as ET
import openai
import time

st.set_page_config(page_title="SEO Content Brief Generator")

st.title("SEO Content Brief Generator")
st.markdown(
    "This app generates a detailed SEO content brief by scraping top-ranking pages from Bing for your target keyword. "
    "It extracts heading hierarchy (H1-H4), identifies schemas present, analyzes competitor differentiation, suggests internal links from your sitemap, "
    "and builds a complete writing guide with primary and secondary keywords."
)

openai_api_key = st.text_input("Enter your OpenAI API Key (Required)", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key (Required)", type="password")
company_name = st.text_input("Enter your Company Name (Required)")
company_domain = st.text_input("Enter your Company Website URL (example: yourwebsite.com)")
sitemap_urls = st.text_input("Enter one or multiple Sitemap URLs (comma-separated)")
target_keyword = st.text_input("Enter the Target Keyword (Required)")

def clean_bing_url(url):
    if url.startswith("https://www.bing.com/"):
        return ""
    return url.split("&")[0]

def get_top_bing_urls(keyword):
    headers = {"User-Agent": "Mozilla/5.0"}
    forbidden_domains = [
        "bing.com", "youtube.com", "wikipedia.org", "linkedin.com", "facebook.com",
        "instagram.com", "twitter.com", "webcache.googleusercontent.com"
    ]
    forbidden_paths = [
        "/podcast/", "/video/", "/videos/", "/search/", "/directory/", "/categories/", "/tag/", "/topic/"
    ]
    urls = []
    seen_domains = set()

    for offset in range(0, 50, 10):
        params = {"q": keyword, "first": offset, "count": "10", "setLang": "EN", "cc": "US"}
        try:
            response = requests.get("https://www.bing.com/search", params=params, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser", parse_only=SoupStrainer('li'))
            for li in soup.select('li.b_algo'):
                h2 = li.find('h2')
                if not h2 or not h2.find('a'):
                    continue
                href = h2.find('a').get('href')
                if not href:
                    continue
                clean_url = clean_bing_url(href)
                parsed = urlparse(clean_url)
                domain = parsed.netloc.lower()
                if parsed.scheme not in ["http", "https"]:
                    continue
                if any(bad in domain for bad in forbidden_domains):
                    continue
                if parsed.path == "/" or any(fp in parsed.path for fp in forbidden_paths):
                    continue
                if domain not in seen_domains:
                    seen_domains.add(domain)
                    urls.append(clean_url)
                if len(urls) == 10:
                    break
        except:
            continue
        if len(urls) == 10:
            break
    return urls

def fetch_html_content(url, retries=3):
    for _ in range(retries):
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.text
        except:
            time.sleep(1)
    return ""

def extract_headings(html):
    soup = BeautifulSoup(html, "html.parser")
    headings = []
    for level in range(1, 5):
        for tag in soup.find_all(f'h{level}'):
            text = tag.get_text(strip=True)
            if text:
                headings.append((level, text))
    return headings

def display_heading_structure(headings):
    current_h2 = None
    current_h3 = None
    for level, text in headings:
        if level == 1:
            st.write(f"H1: {text}")
        elif level == 2:
            current_h2 = text
            st.write(f"    H2: {text}")
        elif level == 3:
            st.write(f"        H3: {text}")
        elif level == 4:
            st.write(f"            H4: {text}")
        else:
            st.write(f"H{level}: {text}")

def extract_meta_details(html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title else "N/A"
    meta_desc = ""
    if soup.find("meta", attrs={"name": "description"}):
        meta_desc = soup.find("meta", attrs={"name": "description"}).get("content", "")
    elif soup.find("meta", attrs={"property": "og:description"}):
        meta_desc = soup.find("meta", attrs={"property": "og:description"}).get("content", "")
    return title, meta_desc

def extract_schema_types(html):
    soup = BeautifulSoup(html, "html.parser")
    schemas = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            content = tag.string
            if content:
                parsed = eval(content) if content.strip().startswith("{") else None
                if parsed and "@type" in parsed:
                    schemas.append(parsed["@type"])
        except:
            continue
    return list(set(schemas))

def get_internal_links_from_sitemap(sitemap_urls, keyword):
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

def generate_serp_diff_analysis(headings_list):
    flat = [t.lower() for h in headings_list for _, t in h]
    return f"The top ranking articles consistently cover these themes: {', '.join(set(flat[:5]))}. Consider adding unique examples, visual comparisons, or updated trends to differentiate."

def generate_content_brief(openai_api_key, keyword, competitor_data, domain, internal_links):
    openai.api_key = openai_api_key
    prompt = f"""
You are an expert SEO strategist. Create a detailed content brief for the keyword "{keyword}" based on the competitor data below. Include:

1. Primary and secondary keywords
2. Suggested H1, H2, H3 structure (clean nested)
3. Context/direction for each heading
4. Internal linking suggestions from this domain: {domain}
5. Neutral external link ideas
6. SERP differentiation advice
7. Schemas detected in competitors

Competitor Pages:
{competitor_data}
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        return str(e)

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

        full_competitor_data = []
        all_headings = []
        for url in urls:
            st.markdown("---")
            st.subheader(f"Scraped URL: [{url}]({url})")
            html = fetch_html_content(url)
            title, meta_desc = extract_meta_details(html)
            headings = extract_headings(html)
            schemas = extract_schema_types(html)

            st.write("Page Title:", title)
            st.write("Meta Description:", meta_desc)
            st.write("Heading Structure:")
            display_heading_structure(headings)
            st.write("Schemas Detected:", ", ".join(schemas) if schemas else "None")

            flat_headings = "\\n".join([f"H{lvl}: {txt}" for lvl, txt in headings])
            full_competitor_data.append(f"URL: {url}\\nTitle: {title}\\nHeadings:\\n{flat_headings}\\nSchemas: {schemas}")
            all_headings.append(headings)

        diff_summary = generate_serp_diff_analysis(all_headings)
        st.subheader("SERP Differentiation Summary")
        st.write(diff_summary)

        internal_links = get_internal_links_from_sitemap(sitemap_urls, target_keyword)
        st.subheader("Suggested Internal Links")
        for link in internal_links:
            st.write(link)

        st.subheader("Generated SEO Content Brief")
        brief = generate_content_brief(openai_api_key, target_keyword, "\\n\\n".join(full_competitor_data), company_domain, internal_links)
        st.code(brief)
