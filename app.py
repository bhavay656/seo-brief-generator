import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai
import time

st.set_page_config(page_title="SEO Content Brief Generator", page_icon="🚀", layout="wide")

st.title("🚀 SEO Content Brief Generator")

# Input fields
openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key:", type="password")
company_name = st.text_input("Enter your Company Name:")
company_website = st.text_input("Enter your Company Website URL:")
keyword = st.text_input("Enter your Keyword (Example: Supply Chain Visibility Software):")

# Function to scrape SERP using ScraperAPI
def scrape_google_scraperapi(keyword, scraperapi_key):
    try:
        search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}&hl=en&gl=us"
        scraperapi_url = f"https://api.scraperapi.com/?api_key={scraperapi_key}&render=true&url={search_url}"
        response = requests.get(scraperapi_url, timeout=120)
        soup = BeautifulSoup(response.text, 'html.parser')

        organic_results = []
        for g in soup.select('div.g'):
            link_tag = g.find('a', href=True)
            title_tag = g.find('h3')
            snippet_tag = g.find('span', class_='aCOpRe')

            if link_tag and title_tag:
                organic_results.append({
                    "title": title_tag.get_text(strip=True),
                    "link": link_tag['href'],
                    "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "No snippet available"
                })

            if len(organic_results) >= 5:  # scraping first 5 URLs
                break

        return organic_results

    except Exception as e:
        st.error(f"Error during scraping: {e}")
        return []

# Function to generate SEO Brief using OpenAI
def generate_seo_brief(openai_api_key, company_name, company_website, keyword, scraped_results):
    openai.api_key = openai_api_key

    urls_block = ""
    for idx, result in enumerate(scraped_results, 1):
        urls_block += f"{idx}. {result['title']}\n{result['link']}\nSummary: {result['snippet']}\n\n"

    prompt = f"""
You are a senior SEO strategist at {company_name} ({company_website}).

Create a highly detailed SEO content brief for **{keyword}** using the **SERP structure**, **scraped headings**, and **real search intent**.

Avoid assumptions. Follow top-ranking patterns.

---

### 1. Scraped URLs and Quick Notes
{urls_block}

---

### 2. Context Summary
- Identify the dominant **search intent**.
- State if it's a listicle, solution guide, or use-case-led.
- Summarize common topics across competitors.

---

### 3. Suggested H1/H2/H3 Outline
- Match format of top pages (e.g. if they’re listicles, use listicles).
- Under each heading, add:
  - **Writer instructions** (what to cover, what to avoid)
  - **Stats/examples** to include
  - **Unique ideas** to differentiate

---

### 4. People Also Ask
Add PAA questions and suggest where to place them.

---

### 5. Internal Linking Suggestions
Pick 3–5 semantically related pages from {company_website}.
Suggest anchor text, destination URL, and placement logic.

---

### 6. External Link Suggestions
Suggest live links from Gartner, FourKites, Project44, or gov sources.

---

### 7. Unique Stats or Angles
Suggest real quotes, analogies, or use-cases to enrich.

---

### 8. Writer Guidelines
- Tone: Professional, confident
- Audience: B2B buyers, supply chain heads
- Formatting: Subheads, short paras, bullets
- Reminder: Stay aligned with real search intent and SERP structure.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a senior SEO content strategist."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2500
    )

    return response.choices[0].message.content

# Button to scrape and generate
if st.button("Scrape SERP Results and Generate Brief"):
    if not openai_api_key or not scraperapi_key or not company_name or not company_website or not keyword:
        st.warning("Please fill all the fields first.")
    else:
        with st.spinner('🔍 Scraping Google SERPs... (this can take 10-20 seconds)'):
            scraped_results = scrape_google_scraperapi(keyword, scraperapi_key)
        
        if scraped_results:
            st.success("✅ Scraping Successful. Now generating SEO Content Brief...")

            with st.spinner('✍️ Generating SEO Content Brief using OpenAI...'):
                brief = generate_seo_brief(openai_api_key, company_name, company_website, keyword, scraped_results)

            st.markdown("## 📋 SEO Content Brief")
            st.markdown(brief)
        else:
            st.error("❌ Failed to scrape results. Please check your ScraperAPI key or try a different keyword.")
