# Updated app.py for Async Scraping (ScraperAPI + Aiohttp)

import streamlit as st
import aiohttp
import asyncio
import openai
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Set page config
st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")

# ScraperAPI Key Input
scraperapi_key = st.text_input("Enter your ScraperAPI Key:", type="password")

# OpenAI Key Input
openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")

# Company Info
company_name = st.text_input("Enter your Company Name:")
company_website = st.text_input("Enter your Company Website URL:")

# Keyword Input
keyword = st.text_input("Enter your Keyword (Example: Supply Chain Visibility Software):")

# Async Scraping Function\async def fetch_html(session, url):
    try:
        async with session.get(url, timeout=60) as response:
            return await response.text()
    except Exception as e:
        print(f"Failed to fetch {url}", e)
        return None

async def scrape_urls_bing(keyword, scraperapi_key):
    search_query = keyword.replace(" ", "+")
    bing_url = f"https://www.bing.com/search?q={search_query}&setlang=en"
    api_url = f"https://api.scraperapi.com/?api_key={scraperapi_key}&render=true&url={bing_url}"

    async with aiohttp.ClientSession() as session:
        html = await fetch_html(session, api_url)

    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    urls = []
    for a_tag in soup.select('li.b_algo h2 a'):
        href = a_tag.get('href')
        if href and 'bing.com' not in href:
            urls.append(href)

    return list(dict.fromkeys(urls))[:10]

async def scrape_and_summarize(session, url, scraperapi_key, openai_api_key):
    api_url = f"https://api.scraperapi.com/?api_key={scraperapi_key}&render=true&url={url}"
    html = await fetch_html(session, api_url)

    if not html:
        return None, None, None

    soup = BeautifulSoup(html, 'html.parser')

    # Extract headings
    headings = [tag.get_text(strip=True) for tag in soup.find_all(['h1', 'h2', 'h3'])]

    # Extract main content
    paragraphs = [p.get_text(strip=True) for p in soup.find_all('p')]
    content = ' '.join(paragraphs[:15])

    if not content.strip():
        return url, "No content found.", headings

    # Generate Summary from GPT-4
    openai.api_key = openai_api_key
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Summarize the given content in under 100 words. Then, separately list the top 5 key points for a content writer to understand the article's context."},
                {"role": "user", "content": content}
            ],
            temperature=0.2,
            max_tokens=500,
        )
        summary = response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI summarization failed for {url}", e)
        summary = "Summary generation failed."

    return url, summary, headings

async def scrape_multiple(urls, scraperapi_key, openai_api_key):
    results = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in urls:
            tasks.append(scrape_and_summarize(session, url, scraperapi_key, openai_api_key))
        scraped = await asyncio.gather(*tasks)
        for result in scraped:
            if result:
                results.append(result)
    return results

# Main Button
if st.button("Scrape SERP Results and Generate Brief"):
    if not (scraperapi_key and openai_api_key and company_name and company_website and keyword):
        st.error("Please fill all fields.")
    else:
        with st.spinner("Scraping Bing SERP..."):
            urls = asyncio.run(scrape_urls_bing(keyword, scraperapi_key))

        if not urls:
            st.error("No URLs found.")
        else:
            st.success(f"Scraping Successful. {len(urls)} URLs found:")
            for u in urls:
                st.write(u)

            st.header("Scraping and Summarizing Articles...")
            scraped_data = asyncio.run(scrape_multiple(urls, scraperapi_key, openai_api_key))

            # Display all summaries
            for idx, (url, summary, headings) in enumerate(scraped_data, start=1):
                st.markdown(f"**{idx}. [{url}]({url})**")
                st.markdown("**Summary:**")
                st.write(summary)
                st.markdown("**Heading Structure:**")
                for heading in headings:
                    st.write(f"- {heading}")

            # After All Summaries: Generate SEO Content Brief
            all_contents = "\n".join([summary for _, summary, _ in scraped_data if summary])

            st.header("SEO Content Brief")
            prompt = f"""
You are an SEO strategist.
Based on the following summaries:

{all_contents}

And for the company {company_name} with website {company_website}, draft a complete SEO content brief.
Focus on:
- Matching the search intent seen in SERP.
- Suggest clear title and H1.
- Give a strong outline.
- Suggest internal links from {company_website}.
- Suggest 3 external authority links.
- Suggest 5 real People Also Ask questions based on Bing.
"""

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "system", "content": "Act as an SEO strategist."}, {"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500,
            )

            final_brief = response.choices[0].message.content
            st.text_area("SEO Content Brief", final_brief, height=600)

            st.success("SEO Content Brief generated successfully!")
