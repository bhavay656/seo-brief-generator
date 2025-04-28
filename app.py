import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai
import time

# Streamlit app settings
st.set_page_config(page_title="SEO Content Brief Generator", layout="wide")

# User inputs
st.title("SEO Content Brief Generator")
openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key:", type="password")
company_name = st.text_input("Enter your Company Name:")
company_website = st.text_input("Enter your Company Website URL:")
keyword = st.text_input("Enter your Keyword (Example: Supply Chain Visibility Software):")

# Functions
def scrape_bing_search(keyword):
    url = f"https://api.scraperapi.com/?api_key={scraperapi_key}&url=https://www.bing.com/search?q={keyword.replace(' ', '+')}&hl=en&gl=us"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    result_links = []
    for item in soup.select('li.b_algo h2 a'):
        link = item.get('href')
        if link and link.startswith('http') and 'bing.com' not in link:
            result_links.append(link)
        if len(result_links) == 10:
            break
    return result_links

def scrape_article_content(url):
    try:
        full_url = f"https://api.scraperapi.com/?api_key={scraperapi_key}&render=true&url={url}"
        response = requests.get(full_url, timeout=60)
        soup = BeautifulSoup(response.text, 'html.parser')
        text = ' '.join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4'])])
        headings = [h.get_text() for h in soup.find_all(['h1', 'h2', 'h3', 'h4'])]
        return text, headings
    except Exception as e:
        return '', []

def summarize_article(openai_api_key, article_text, headings):
    if not article_text:
        return "No content found to summarize.", []
    prompt = f"""
You are a senior SEO content strategist.

Here is the article content:
"""
{article_text}
"""
Summarize this article briefly.
Also, list out the heading structure clearly.
    """
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a senior SEO strategist."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=1500
    )
    summary = response.choices[0].message.content
    return summary

def generate_final_brief(openai_api_key, company_name, company_website, keyword, summaries, headings_list):
    prompt = f"""
You are an SEO content strategist for {company_name} ({company_website}).

Target Keyword: {keyword}

Based on the following competitors' summaries and heading structures:
"""
    for i, (summary, headings) in enumerate(zip(summaries, headings_list), 1):
        prompt += f"\n\n{i}. Summary: {summary}\nHeadings: {headings}"

    prompt += """

Now, create a complete SEO Content Brief that:
- Matches the search intent
- Follows a heading structure aligned to the SERP
- Suggests contextual internal linking opportunities from {company_website}
- Suggests external authoritative links
- Adds People Also Ask questions seen
- Uses a human and clear writing style

Start with a TL;DR summary.
    """
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a senior SEO strategist."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=2500
    )
    return response.choices[0].message.content

# Main execution
if st.button("Scrape SERP Results and Generate Brief"):
    if not openai_api_key or not scraperapi_key or not keyword:
        st.warning("Please fill in all the fields!")
    else:
        st.subheader("Scraping SERP Results...")
        urls = scrape_bing_search(keyword)
        if urls:
            st.success(f"Scraping Successful. {len(urls)} URLs found:")
            for link in urls:
                st.write(link)

            summaries = []
            headings_all = []
            st.subheader("Scraping and Summarizing Articles...")

            BATCH_SIZE = 3
            for i in range(0, len(urls), BATCH_SIZE):
                batch = urls[i:i+BATCH_SIZE]
                for idx, url in enumerate(batch, start=i+1):
                    st.info(f"Scraping and summarizing URL {idx}/{len(urls)}: {url}")
                    text, headings = scrape_article_content(url)
                    summary = summarize_article(openai_api_key, text, headings)
                    summaries.append(summary)
                    headings_all.append(headings)
                    st.success(f"URL {idx} summarized successfully.")
                    time.sleep(1)

            st.subheader("SEO Content Brief")
            final_brief = generate_final_brief(openai_api_key, company_name, company_website, keyword, summaries, headings_all)
            st.markdown(final_brief)
        else:
            st.error("No URLs found. Please try again with another keyword or check your ScraperAPI key.")
