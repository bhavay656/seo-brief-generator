import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai

# Bing Scraper Function
def scrape_bing(keyword):
    try:
        url = f"https://www.bing.com/search?q={keyword.replace(' ', '+')}&cc=us"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, "html.parser")
        
        results = []
        for item in soup.select("li.b_algo"):
            link_tag = item.find("a")
            title_tag = item.find("h2")
            snippet_tag = item.find("p")

            if link_tag and title_tag:
                results.append({
                    "title": title_tag.get_text(strip=True),
                    "link": link_tag["href"],
                    "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "No snippet available"
                })

            if len(results) >= 10:
                break

        return results
    except Exception as e:
        print("Error during Bing scraping:", e)
        return []

# OpenAI Brief Generator
def generate_seo_brief(openai_api_key, company_name, company_website, keyword, scraped_results):
    client = openai.OpenAI(api_key=openai_api_key)
    links_summary = "\n".join([f"- {item['title']}: {item['link']}" for item in scraped_results])

    final_prompt = f"""
You are a senior SEO strategist at {company_name} ({company_website}).

Create a highly detailed SEO content brief for **{keyword}** using the real SERP structure and extracted content from these links:
{links_summary}

---
2. Context Summary
- Identify dominant search intent.
- List if it's a listicle, solution guide, use case, etc.
- Summarize common topics.

---
3. Suggested H1/H2/H3 Outline
- Follow SERP patterns.
- Under each heading: Writer instructions, Stats/examples, Unique angles.

---
4. People Also Ask
- Suggest PAA questions and placement.

---
5. Internal Linking Suggestions
- Pick 3–5 related internal pages from {company_website} sitemap.
- Give anchor text + placement logic.

---
6. External Linking Suggestions
- Link to authoritative sources (gov, Gartner, etc.)

---
7. Unique Stats/Angles
- Suggest quotes, analogies, use cases.

---
8. Writer Guidelines
- Audience: B2B buyers, supply chain heads
- Tone: Professional, confident
- Formatting: Subheads, short paras, bullets
- Reminder: Stay aligned with real search intent and SERP structure.
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a senior SEO strategist at GoComet.com."},
            {"role": "user", "content": final_prompt}
        ],
        temperature=0.7,
        max_tokens=2500
    )

    seo_brief = response.choices[0].message.content
    return seo_brief

# Streamlit App Interface
st.set_page_config(page_title="SEO Content Brief Generator", page_icon="🚀")

st.title("🚀 SEO Content Brief Generator")

openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")
company_name = st.text_input("Enter your Company Name:")
company_website = st.text_input("Enter your Company Website URL:")
keyword = st.text_input("Enter your Keyword (Example: Supply Chain Visibility Software):")

if st.button("Scrape SERP Results and Generate Brief"):
    if not openai_api_key or not company_name or not company_website or not keyword:
        st.warning("Please fill all the fields first.")
    else:
        with st.spinner("🔍 Scraping Bing SERPs... (this can take 10–20 seconds)"):
            scraped_results = scrape_bing(keyword)

        if scraped_results:
            st.success("✅ Scraping Successful. Now generating SEO Content Brief...")

            with st.spinner("✍️ Generating SEO Content Brief using OpenAI..."):
                brief = generate_seo_brief(openai_api_key, company_name, company_website, keyword, scraped_results)
                st.markdown('## 📋 SEO Content Brief')
                st.markdown(brief)
        else:
            st.error("❌ No links found. Please try another keyword.")
            
