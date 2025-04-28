# app.py

import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai

st.set_page_config(page_title="SEO Content Brief Generator", page_icon="🚀", layout="wide")

# --- Input fields ---
st.title("\U0001F680 SEO Content Brief Generator")

openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")
company_name = st.text_input("Enter your Company Name:")
company_website = st.text_input("Enter your Company Website URL:")
keyword = st.text_input("Enter your Keyword (Example: Supply Chain Visibility Software):")
scraperapi_key = st.text_input("Enter your ScraperAPI Key:", type="password")


# --- Helper Functions ---
def scrape_bing_top_urls(keyword, num_results=10):
    search_url = f"https://www.bing.com/search?q={keyword.replace(' ', '+')}&count={num_results}&setLang=en"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    links = []
    for a_tag in soup.select('li.b_algo h2 a'):
        href = a_tag['href']
        if href.startswith('http'):
            links.append(href)
            if len(links) >= num_results:
                break
    return links


def scrape_page_summary(url, scraperapi_key):
    scraperapi_url = f"https://api.scraperapi.com/?api_key={scraperapi_key}&render=true&url={url}"
    try:
        response = requests.get(scraperapi_url, timeout=60)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Try to extract only meaningful article content
        main_content = soup.find('main')
        if not main_content:
            main_content = soup.body

        text_content = main_content.get_text(separator=" ", strip=True)
        text_content = text_content[:4000]  # Limit size for OpenAI

        headings = []
        for tag in soup.find_all(['h1', 'h2', 'h3']):
            headings.append(f"{tag.name.upper()}: {tag.get_text(strip=True)}")

        return text_content, headings

    except Exception as e:
        st.error(f"Failed to scrape {url}: {e}")
        return None, []


def summarize_article(openai_api_key, article_text):
    client = openai.OpenAI(api_key=openai_api_key)
    prompt = f"""
Summarize the main topic, content style (guide, listicle, use-case etc.), and focus points of this article below in 3–5 lines:
\n\n{article_text}
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an SEO strategist."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=300
    )
    return response.choices[0].message.content


def generate_final_brief(openai_api_key, company_name, company_website, keyword, url_summaries):
    summary_block = "\n\n".join([
        f"URL: {item['url']}\nSummary: {item['summary']}\nHeadings:\n" + "\n".join(item['headings'])
        for item in url_summaries
    ])

    full_prompt = f"""
You are a senior SEO strategist at {company_name} ({company_website}).
Create a highly detailed SEO content brief for the keyword **{keyword}** using the real search intent and structure from the following SERP summaries and headings.

{summary_block}

The structure of the brief should be:

2. Context Summary
3. Suggested H1/H2/H3 Outline
4. People Also Ask (suggest 5+ questions)
5. Internal Linking Suggestions (use {company_website}/sitemap.xml for links)
6. External Link Suggestions (gov, gartner, fourkites, project44 etc.)
7. Unique Stats or Angles
8. Writer Guidelines
"""

    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional SEO content strategist."},
            {"role": "user", "content": full_prompt}
        ],
        temperature=0.4,
        max_tokens=2500
    )
    return response.choices[0].message.content


# --- Main Workflow ---
if st.button("Scrape SERP Results and Generate Brief"):
    if not openai_api_key or not keyword or not company_name or not company_website or not scraperapi_key:
        st.warning("Please fill all fields!")
    else:
        with st.spinner('🔍 Scraping Bing SERPs for URLs...'):
            urls = scrape_bing_top_urls(keyword, num_results=10)

        if urls:
            st.success('✅ Scraping Successful. URLs found:')
            for url in urls:
                st.write(url)

            url_summaries = []

            for idx, url in enumerate(urls):
                with st.spinner(f'📄 Scraping and summarizing {url}...'):
                    article_text, headings = scrape_page_summary(url, scraperapi_key)
                    if article_text:
                        summary = summarize_article(openai_api_key, article_text)
                        url_summaries.append({
                            "url": url,
                            "summary": summary,
                            "headings": headings
                        })

            with st.spinner('✍️ Generating Final SEO Content Brief...'):
                final_brief = generate_final_brief(openai_api_key, company_name, company_website, keyword, url_summaries)

            st.markdown("## 📋 Final SEO Content Brief:")
            st.markdown(final_brief)

        else:
            st.error("❌ No URLs found. Try another keyword.")
