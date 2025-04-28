import streamlit as st
import openai
import httpx
from bs4 import BeautifulSoup
import asyncio

st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")

def scrape_bing_search_results(keyword):
    search_url = f"https://www.bing.com/search?q={keyword.replace(' ', '+')}&cc=us&setlang=en"
    try:
        response = httpx.get(search_url, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')

        urls = []
        for a_tag in soup.select('li.b_algo h2 a'):
            href = a_tag.get('href')
            if href and href.startswith('http'):
                urls.append(href)
            if len(urls) == 10:
                break

        return urls
    except Exception as e:
        st.error(f"Failed to scrape Bing: {e}")
        return []

async def fetch_page(client, url):
    try:
        response = await client.get(url, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')

        headings = []
        for tag in soup.find_all(['h1', 'h2', 'h3']):
            text = tag.get_text(strip=True)
            if text:
                headings.append(text)

        text_content = ' '.join([p.get_text(strip=True) for p in soup.find_all('p')])

        return {
            "url": url,
            "text": text_content,
            "headings": headings
        }
    except Exception as e:
        return {
            "url": url,
            "text": "",
            "headings": [],
            "error": str(e)
        }

async def scrape_multiple_pages(urls):
    async with httpx.AsyncClient() as client:
        tasks = [fetch_page(client, url) for url in urls]
        return await asyncio.gather(*tasks)

def generate_brief_with_openai(openai_api_key, company_name, company_website, keyword, page_summaries):
    openai_client = openai.OpenAI(api_key=openai_api_key)

    prompt = f"""
You are an expert SEO strategist.

Below are the summaries and heading structures of top ranking pages for the keyword "{keyword}":

"""

    for idx, page in enumerate(page_summaries, 1):
        prompt += f"""
Result {idx} URL: {page['url']}

Summary:
{page['text'][:1000]}  # Use only 1000 characters max per result.

Heading Structure:
{', '.join(page['headings'])}
"""

    prompt += f"""

Now, based on the above SERP analysis, and assuming you are writing for the website {company_website}, 
generate an SEO-optimized blog outline and writing strategy for the keyword "{keyword}". 
Keep strict focus on real user search intent. no assumptions, checked the scraped details.

Additionally:
- Suggest 5 internal linking opportunities from {company_website}.
- Suggest 3 external high-authority links.
- Give a short recommendation on tone, style, and structure.
"""

    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an SEO strategist helping content teams rank on Google."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens
