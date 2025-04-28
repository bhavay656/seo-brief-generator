import streamlit as st
import requests
import aiohttp
import asyncio
import openai
from bs4 import BeautifulSoup

# OpenAI key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Streamlit Page Config
st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")
st.title("SEO Content Brief Generator")

# Input
keyword = st.text_input("Enter the Target Keyword (Required)", "")
urls_input = st.text_area("Enter URLs (maximum 10, one per line)", "")
your_domain = st.text_input("Your Website Domain for Internal Links (example: gocomet.com)", "")

submit = st.button("Generate SEO Brief")

# Async Scraping
async def fetch(session, url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with session.get(url, timeout=15) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")

            headings = []
            for tag in ["h1", "h2", "h3", "h4"]:
                for h in soup.find_all(tag):
                    headings.append(h.get_text(strip=True))

            paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
            text_content = " ".join(paragraphs)

            return {
                "url": url,
                "headings": headings,
                "content": text_content[:5000]
            }
    except Exception as e:
        return {
            "url": url,
            "headings": [],
            "content": f"Error fetching: {e}"
        }

async def scrape_all(urls):
    results = []
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(urls), 3):
            batch = urls[i:i+3]
            tasks = [fetch(session, url) for url in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
    return results

# Summarize a page
def summarize_page(headings, content):
    try:
        prompt = f"""
You are helping an SEO content writer.

Given these extracted headings and text content from a webpage, summarize what the page is about in 5-7 lines.

Be simple, clear, and use English only.

Headings:
{headings}

Content:
{content}
"""
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert content summarizer for SEO."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=400
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error summarizing: {e}"

# Generate the final SEO brief
def generate_brief(keyword, scraped_summaries, domain):
    try:
        prompt = f"""
You are an SEO strategist.

Keyword: {keyword}

Summaries of competing pages:
{scraped_summaries}

Instructions:
- Summarize the dominant search intent.
- Provide H1, H2, H3 structure.
- Suggest 15 FAQs.
- Suggest 3 internal links from {domain}.
- Suggest 3 external authoritative links.
- Give a TL;DR for the final blog.

Language: English only. Clear and simple.
"""

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert SEO strategist."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=4000
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error generating SEO brief: {e}"

# Main Execution
if submit:
    if not keyword or not urls_input:
        st.warning("Keyword and URLs are required fields.")
    else:
        urls = urls_input.strip().split("\n")
        if len(urls) > 10:
            st.error("Maximum 10 URLs allowed.")
        else:
            st.info("Scraping pages in batches of 3. Please wait.")

            scraped_results = asyncio.run(scrape_all(urls))

            scraped_summary_for_brief = ""

            for page in scraped_results:
                st.subheader(f"Data from: {page['url']}")
                st.write("Heading Structure:")
                for heading in page['headings']:
                    st.write(f"- {heading}")

                if page['content'].startswith("Error fetching"):
                    summary = page['content']
                else:
                    summary = summarize_page(page['headings'], page['content'])
                
                st.write("Page Summary:")
                st.write(summary)

                scraped_summary_for_brief += f"\n\nURL: {page['url']}\nSummary: {summary}"

            st.info("Generating SEO content brief.")

            seo_brief = generate_brief(keyword, scraped_summary_for_brief, your_domain)

            st.subheader("Generated SEO Content Brief")
            st.write(seo_brief)

            st.download_button("Download Brief as Text", data=seo_brief, file_name="seo_brief.txt")
