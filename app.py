import streamlit as st
import openai
import requests
import xml.etree.ElementTree as ET
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import datetime

openai.api_key = st.secrets["openai_api_key"]
scraperapi_key = st.secrets["scraperapi_key"]

def fetch_bing_urls(query):
    headers = {"Ocp-Apim-Subscription-Key": st.secrets["bing_api_key"]}
    endpoint = "https://api.bing.microsoft.com/v7.0/search"
    params = {"q": query, "count": 10}
    response = requests.get(endpoint, headers=headers, params=params)
    return [link["url"] for link in response.json().get("webPages", {}).get("value", [])]

async def scrape_url(session, url, key):
    api = f"https://api.scraperapi.com?api_key={key}&url={url}"
    try:
        async with session.get(api, timeout=30) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.string.strip() if soup.title else ""
            meta = soup.find("meta", attrs={"name": "description"})
            meta_desc = meta["content"] if meta else ""
            headings = [f"H{i}: {h.get_text(strip=True)}" for i in range(1, 5) for h in soup.find_all(f"h{i}")]
            schemas = list(set([s.get("itemtype") for s in soup.find_all(attrs={"itemscope": True}) if s.get("itemtype")]))
            return {"url": url, "title": title, "meta": meta_desc, "headings": headings, "schemas": schemas}
    except Exception as e:
        return {"url": url, "error": str(e)}

async def scrape_all(urls, key):
    async with aiohttp.ClientSession() as session:
        return await asyncio.gather(*(scrape_url(session, url, key) for url in urls))

def extract_from_sitemap(sitemap_url):
    try:
        resp = requests.get(sitemap_url)
        root = ET.fromstring(resp.content)
        return [url.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc").text for url in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url")]
    except:
        return []

def generate_outline_insight(r):
    prompt = f"""
You are an expert SEO content strategist.

Analyze the following web page content structure and summarize its positioning:

Title: {r['title']}
Meta Description: {r['meta']}
Headings: {' | '.join(r['headings'])}

Give me:
1. TLDR (brief 1-liner on the purpose of this page)
2. Context for Writer (what this page covers based on its headings)
3. Unique Angle (what stands out or differs from others)

Avoid generic templates.
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a top-tier SEO content analyst."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"TLDR: Error from OpenAI - {str(e)}"

def generate_brief(keyword, sources, sitemap_urls, company_name, company_url):
    year = datetime.datetime.now().year
    prompt = f"""
You are a senior SEO strategist helping {company_name} write a content brief to dominate SERPs.

Target keyword: {keyword}
Current Year: {year}
Reference SERP pages include:
{sources}

Instructions:
- Suggest Primary Keyword, Secondary Keywords, NLP/semantic suggestions
- Recommend content structure with clear H1, H2, H3 tags.
- Under each heading, give:
   - Context for writer
   - Unique angle based on GoComet’s site and what others lack
- Avoid LLM phrases like “embrace”, “ever-changing”, etc.
- Refresh any outdated references like 2024 to {year}.
- Suggest internal links based on these URLs: {', '.join(sitemap_urls[:5])}
- Final output should be clean, structured, and SERP-aligned.
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional SEO brief generator."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

# --- Streamlit UI ---

st.title("SEO Content Brief Generator")

company_name = st.text_input("Enter your Company Name")
company_url = st.text_input("Enter your Website URL")
sitemap_input = st.text_input("Enter Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

if st.button("Generate SEO Brief"):
    if openai.api_key and scraperapi_key and keyword and company_url:
        with st.spinner("Fetching top Bing URLs..."):
            urls = fetch_bing_urls(keyword)
            for u in urls:
                st.write(u)

        with st.spinner("Scraping URL content..."):
            results = asyncio.run(scrape_all(urls, scraperapi_key))

        source_insights = ""
        for r in results:
            if "error" not in r:
                source_insights += f"\nSource URL: {r['url']}\n"
                source_insights += f"Title: {r['title']}\n"
                source_insights += f"Meta: {r['meta']}\n"
                source_insights += f"Schemas Detected: {', '.join(r['schemas']) if r['schemas'] else 'None'}\n"
                source_insights += "Headings Observed:\n"
                for h in r['headings']:
                    source_insights += f"- {h}\n"
                insight = generate_outline_insight(r)
                source_insights += f"\n{insight}\n{'-'*50}\n"

        st.subheader("Scraped URL Insights")
        st.text_area("Full Observations", value=source_insights, height=400)

        with st.spinner("Generating Final SEO Brief..."):
            sitemap_urls = []
            for sm_url in sitemap_input.split(","):
                sitemap_urls.extend(extract_from_sitemap(sm_url.strip()))

            full_brief = generate_brief(keyword, source_insights, sitemap_urls, company_name, company_url)

        st.subheader("Generated Full SEO Content Brief")
        st.text_area("SEO Content Brief", full_brief, height=800)

        option = st.radio("Next Step:", ["Download Brief", "Generate Content"])

        if option == "Download Brief":
            st.download_button("Download as Text", data=full_brief, file_name="seo_content_brief.txt")

        elif option == "Generate Content":
            st.markdown("### Review & Edit the Outline (Format: H1:, H2:, H3:)")
            default_outline = "\n".join([line for line in full_brief.splitlines() if line.strip().startswith("H1:") or line.strip().startswith("H2:") or line.strip().startswith("H3:")])
            outline = st.text_area("Document Flow Outline", default_outline, height=400)

            if st.button("Confirm and Create Content"):
                with st.spinner("Creating content..."):
                    prompt = f"""
You are an SEO content writer. Write a complete, well-structured blog using the following outline.

Company: {company_name}
Year: {datetime.datetime.now().year}
Keyword: {keyword}

Instructions:
- Use heading tags as given (H1, H2, H3).
- Avoid generic fluff and LLM phrases like “embrace”, “landscape”, “ever-changing”.
- Ensure freshness by referencing the year {datetime.datetime.now().year}.
- Each section must provide value aligned with the search intent (awareness/consideration/transactional).

Outline:
{outline}

Generate content strictly based on this structure.
"""

                    content = openai.ChatCompletion.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are a clear, helpful SEO content writer."},
                            {"role": "user", "content": prompt}
                        ]
                    ).choices[0].message.content.strip()

                    st.subheader("Generated Article")
                    st.text_area("Full Article", content, height=1000)
