import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai

# Set Streamlit page config
st.set_page_config(page_title="SEO Content Brief Generator", page_icon="🚀")

# Streamlit Title
st.title("\ud83d\ude80 SEO Content Brief Generator")

# Input Fields
st.subheader("Enter Details")
openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key:", type="password")
company_name = st.text_input("Enter your Company Name:")
company_website = st.text_input("Enter your Company Website URL:")
keyword = st.text_input("Enter your Keyword (Example: Supply Chain Visibility Software):")

# Function to scrape Bing search results
def scrape_bing(keyword):
    query = keyword.replace(' ', '+')
    url = f"https://api.scraperapi.com/?api_key={scraperapi_key}&url=https://www.bing.com/search?q={query}&country_code=US"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    links = []
    for a_tag in soup.select('li.b_algo h2 a'):
        link = a_tag.get('href')
        if link and 'http' in link:
            links.append(link)
    return links[:10]

# Function to scrape article content and headings
def scrape_article(url):
    try:
        api_url = f"https://api.scraperapi.com/?api_key={scraperapi_key}&render=true&url={url}"
        response = requests.get(api_url, timeout=60)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract headings
        headings = []
        for tag in soup.find_all(['h1', 'h2', 'h3']):
            headings.append(f"{tag.name.upper()}: {tag.get_text(strip=True)}")

        # Extract paragraphs for summary
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p')]
        text_content = ' '.join(paragraphs)[:4000]  # limit to first 4000 characters

        return text_content, headings
    except Exception as e:
        return "", []

# Function to summarize article text with OpenAI
def summarize_text(text, openai_api_key):
    client = openai.OpenAI(api_key=openai_api_key)
    prompt = f"""
Summarize the following webpage content into a short 3-5 line TL;DR in simple language for SEO content writers:
{text}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a senior SEO strategist at GoComet.com."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "Summary generation failed."

# Main App
if st.button("Scrape SERP Results and Generate Brief"):
    if not openai_api_key or not scraperapi_key or not company_name or not company_website or not keyword:
        st.warning("\u26a0\ufe0f Please fill all the fields.")
    else:
        with st.spinner("\ud83d\udd0d Scraping Bing SERP for URLs..."):
            urls = scrape_bing(keyword)

        if urls:
            st.success("\u2705 Scraping Successful. URLs found:")
            for url in urls:
                st.markdown(f"- [{url}]({url})")

            summaries = []
            headings_all = []

            st.subheader("\ud83d\udcd1 Scraping and Summarizing Articles...")

            for idx, url in enumerate(urls):
                with st.spinner(f"Scraping and summarizing URL {idx+1}/{len(urls)}: {url}"):
                    article_text, headings = scrape_article(url)
                    summary = summarize_text(article_text, openai_api_key)
                    summaries.append((url, summary))
                    headings_all.append((url, headings))

            st.subheader("\ud83d\udd39 SEO Content Brief:")
            for idx, (url, summary) in enumerate(summaries):
                st.markdown(f"**{idx+1}. [{url}]({url})**")
                st.markdown(f"**Summary:** {summary}")
                heading_lines = headings_all[idx][1]
                if heading_lines:
                    st.markdown("**Heading Structure:**")
                    for head in heading_lines:
                        st.markdown(f"- {head}")
                st.markdown("---")

        else:
            st.error("\u274c No URLs found. Please try a different keyword.")
