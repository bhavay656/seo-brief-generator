import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai

st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")
st.title("SEO Content Brief Generator")

def scrape_bing_search(keyword):
    search_url = f"https://www.bing.com/search?q={keyword.replace(' ', '+')}&count=20"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    urls = []
    for result in soup.select('li.b_algo h2 a'):
        href = result.get('href')
        if href and 'bing.com' not in href:
            urls.append(href)

    return urls[:10]

def scrape_page_content(url, scraperapi_key):
    scraperapi_url = f"https://api.scraperapi.com/?api_key={scraperapi_key}&url={url}&render=true"
    try:
        response = requests.get(scraperapi_url, timeout=60)
        soup = BeautifulSoup(response.text, 'html.parser')

        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p')]
        headings = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3', 'h4'])]

        content_text = "\n".join(paragraphs)
        headings_text = "\n".join(headings)

        return content_text, headings_text

    except Exception as e:
        return "", ""

def generate_summary(api_key, content_text, headings_text):
    if not content_text.strip():
        return "No content found to summarize."

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional SEO content strategist."},
            {"role": "user", "content": f"Summarize the following article content for SEO writers. Also show the heading structure separately.\n\nContent:\n{content_text}\n\nHeadings:\n{headings_text}"}
        ],
        temperature=0.3,
        max_tokens=2000
    )

    return response.choices[0].message.content

# User Inputs
openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key:", type="password")
company_name = st.text_input("Enter your Company Name:")
company_website = st.text_input("Enter your Company Website URL:")
keyword = st.text_input("Enter your Keyword (Example: Supply Chain Visibility Software):")

if st.button("Scrape SERP Results and Generate Brief"):
    if not openai_api_key or not scraperapi_key or not company_name or not company_website or not keyword:
        st.warning("Please fill all fields before proceeding.")
    else:
        with st.spinner("Scraping Bing SERPs..."):
            urls = scrape_bing_search(keyword)

        if not urls:
            st.error("No URLs found. Try another keyword.")
        else:
            st.success(f"Scraping Successful. {len(urls)} URLs found:")
            for url in urls:
                st.markdown(f"- {url}")

            st.header("Scraping and Summarizing Articles...")

            all_summaries = []

            for idx, url in enumerate(urls, 1):
                with st.spinner(f"Scraping and summarizing URL {idx}/{len(urls)}: {url}"):
                    content_text, headings_text = scrape_page_content(url, scraperapi_key)

                    if content_text.strip():
                        summary = generate_summary(openai_api_key, content_text, headings_text)
                        all_summaries.append(f"{idx}. {url}\n\nSummary:\n{summary}\n\n")
                        st.success(f"URL {idx} summarized successfully.")
                    else:
                        all_summaries.append(f"{idx}. {url}\n\nSummary: No content found.\n\n")
                        st.warning(f"URL {idx} - No content found.")

            if all_summaries:
                st.header("SEO Content Brief")
                final_brief = "\n".join(all_summaries)
                st.text_area("SEO Content Brief", final_brief, height=500)
