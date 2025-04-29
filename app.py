
import streamlit as st
import asyncio
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import openai

openai_api_key = st.secrets["OPENAI_API_KEY"]
scraperapi_key = st.secrets["SCRAPERAPI_KEY"]

st.title("SEO Brief & Content Generator")

company_url = st.text_input("Enter your website URL")
company_name = st.text_input("Enter your brand name")
sitemap_urls = st.text_input("Enter Sitemap URLs (comma-separated)")
keyword = st.text_input("Enter the Target Keyword")

@st.cache_data(show_spinner=False)
def fetch_bing_urls(query):
    headers = {"Ocp-Apim-Subscription-Key": st.secrets["BING_API_KEY"]}
    params = {"q": query, "count": 10}
    response = requests.get("https://api.bing.microsoft.com/v7.0/search", headers=headers, params=params)
    urls = [item["url"] for item in response.json().get("webPages", {}).get("value", [])]
    return urls

@st.cache_data(show_spinner=False)
def scrape_url(url):
    api_url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url={url}"
    res = requests.get(api_url)
    if res.status_code != 200:
        return {"error": f"Failed to fetch {url}"}
    soup = BeautifulSoup(res.text, "html.parser")
    title = soup.title.string if soup.title else ""
    meta = soup.find("meta", {"name": "description"}) or soup.find("meta", {"property": "og:description"})
    meta_desc = meta["content"] if meta else ""
    headings = [f"{tag.name.upper()}: {tag.get_text(strip=True)}" for tag in soup.find_all(["h1", "h2", "h3", "h4"])]
    schemas = []
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        schemas.append("Detected")
    return {
        "url": url,
        "title": title,
        "meta": meta_desc,
        "headings": headings,
        "schemas": schemas
    }

async def scrape_all(urls):
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, scrape_url, url) for url in urls]
    return await asyncio.gather(*tasks)

def generate_brief(keyword, sources, sitemap_urls, company_name, company_url):
    summary_prompt = f"""
You are a top-tier SEO strategist. Based on these page observations:
{sources}

Generate a full SEO content brief for {company_name}'s website {company_url} targeting keyword "{keyword}".

Requirements:
- Begin with Primary, Secondary, NLP, Semantic SEO suggestions.
- Then create the H1 → H2 → H3 structure.
- Under each heading, add:
  - Context: What to write under that heading.
  - Unique Angle: Only add if there is a brand-based insight from {company_url}'s offerings.
- Internal link suggestions (from sitemap_urls) must return 200 OK. Do not add 404s.
- Avoid fluff and do not use words like "embrace", "ever-changing", etc.

Output Format:
Primary Keyword: ...
Secondary Keywords: ...
NLP/Entity Keywords: ...
Semantic Suggestions: ...

SEO Content Brief for {company_name}'s "{keyword}"

Outline:
H1: ...
  - Context: ...
  - Unique Angle: ...

H2: ...
  - Context: ...
  - Unique Angle: ...
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            api_key=openai_api_key,
            messages=[
                {"role": "system", "content": "You are a top-tier SEO strategist."},
                {"role": "user", "content": summary_prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI Error: {str(e)}"

if st.button("Generate SEO Brief"):
    if openai_api_key and scraperapi_key and keyword and company_url:
        with st.spinner("Fetching top Bing URLs..."):
            urls = fetch_bing_urls(keyword)
            st.success(f"Fetched {len(urls)} URLs.")
            for i, u in enumerate(urls):
                st.write(f"{i+1}. {u}")

        with st.spinner("Scraping URL content..."):
            results = asyncio.run(scrape_all(urls))
        
        source_insights = ""
        for r in results:
            if 'error' not in r:
                source_insights += (
                    f"\nSource URL: {r['url']}\n"
                    f"Title: {r['title']}\n"
                    f"Meta: {r['meta']}\n"
                    f"Schemas Detected: {', '.join(r['schemas']) if r['schemas'] else 'None'}\n"
                    f"Headings Observed:\n"
                )
                for h in r['headings']:
                    source_insights += f"- {h}\n"
                source_insights += "\nTLDR: [Detailed summary]\nContext for Writer: [Heading goals]\nUnique Angle: [Difference vs others]\n---\n"

        st.subheader("Scraped URL Insights")
        st.text_area("Full Observations", value=source_insights, height=400)

        with st.spinner("Generating Final SEO Brief..."):
            final_brief = generate_brief(keyword, source_insights, sitemap_urls, company_name, company_url)

        st.subheader("Generated Full SEO Content Brief")
        st.text_area("SEO Content Brief", final_brief, height=800)

        st.write("### What would you like to do next?")
        action = st.radio("Choose an option", ["Download Brief", "Get Going with Content Creation"])

        if action == "Download Brief":
            st.download_button("Download Brief", final_brief, file_name=f"{keyword}_SEO_Brief.txt")

        if action == "Get Going with Content Creation":
            st.markdown("### Edit or Confirm Your Outline")
            default_outline = final_brief.split("Outline:")[-1].strip()
            user_outline = st.text_area("Paste and Edit Outline (Use H1:, H2:, etc.)", default_outline, height=400)

            if st.button("Generate Article Content"):
                article_prompt = f"""
You are a professional SEO writer. Use the following outline to generate a complete blog post that aligns with {company_name}'s offering at {company_url}.

Requirements:
- Follow the exact outline provided (H1, H2, H3).
- No fluff. No use of terms like 'embrace', 'ever-changing', etc.
- Make it useful, practical, and dominant for SERP ranking.
- Avoid generic intros. Dive straight into the intent.
- Make it naturally engaging without sounding like an AI.

Outline:
{user_outline}
"""
                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-4",
                        api_key=openai_api_key,
                        messages=[
                            {"role": "system", "content": "You are an expert blog writer."},
                            {"role": "user", "content": article_prompt}
                        ]
                    )
                    content = response.choices[0].message.content
                    st.subheader("Generated Article Content")
                    st.text_area("SEO Blog", content, height=800)
                except Exception as e:
                    st.error(f"OpenAI Error: {str(e)}")
