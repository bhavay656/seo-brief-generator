import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai

# -------------------- SETTINGS --------------------
BING_SEARCH_URL = "https://www.bing.com/search?q={query}&setlang=en-us"

# -------------------- SCRAPE BING ORGANIC RESULTS --------------------
def scrape_bing_organic(query, max_results=10):
    search_url = BING_SEARCH_URL.format(query=query.replace(' ', '+'))
    response = requests.get(search_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    organic_links = []
    for item in soup.select('li.b_algo'):
        a_tag = item.find('a', href=True)
        if a_tag:
            link = a_tag['href']
            if link.startswith('http') and 'bing.com' not in link:
                organic_links.append(link)
            if len(organic_links) >= max_results:
                break

    return list(dict.fromkeys(organic_links))  # remove duplicates

# -------------------- SCRAPE EACH URL AND SUMMARIZE --------------------
def scrape_and_summarize(url, scraperapi_key):
    try:
        api_url = f"http://api.scraperapi.com/?api_key={scraperapi_key}&url={url}&render=true"
        response = requests.get(api_url, timeout=60)
        soup = BeautifulSoup(response.text, 'html.parser')

        headings = [tag.get_text(strip=True) for tag in soup.find_all(['h1', 'h2', 'h3'])]
        paras = ' '.join([p.get_text(strip=True) for p in soup.find_all('p')])

        if len(paras) > 4000:
            paras = paras[:4000]  # limit to 4000 chars

        return {
            'url': url,
            'headings': headings,
            'content_excerpt': paras
        }

    except Exception as e:
        return {
            'url': url,
            'headings': [],
            'content_excerpt': f"Failed to fetch: {str(e)}"
        }

# -------------------- GENERATE SEO CONTENT BRIEF --------------------
def generate_seo_brief(openai_api_key, company_name, company_website, keyword, summaries):
    client = openai.OpenAI(api_key=openai_api_key)

    urls_info = "\n\n".join([
        f"URL: {s['url']}\nHeadings: {s['headings']}\nSummary: {s['content_excerpt'][:500]}..."
        for s in summaries
    ])

    final_prompt = f"""
You are a senior SEO strategist at {company_name}.

Create a highly detailed SEO content brief for the keyword **{keyword}** using the following context:

- Summaries of top-ranked articles
- Heading structures from each URL
- Real search intent reflected in current SERPs
- Company website: {company_website}

Data:
{urls_info}

Your brief must follow this structure:
---

### 2. Context Summary
- Dominant search intent
- Common content patterns

### 3. Suggested H1/H2/H3 Outline
- Include writer instructions under each heading

### 4. People Also Ask Questions (suggested)
- Suggest 5-7 PAA Questions

### 5. Internal Linking Suggestions (3-5 from company website)
- ✅ Anchor text, ✅ Destination URL, ✅ Placement logic

### 6. External Links (Gov, Gartner, industry sources)
- ✅ Anchor text, ✅ Destination URL, ✅ Relevance

### 7. Unique Stats/Examples
- Suggest stats, quotes, case studies

### 8. Writer Guidelines
- Tone: Professional and confident
- Audience: B2B buyers, supply chain heads
- Formatting: Bulleted where needed, short paragraphs

---
Only use the data from the URLs. Do not assume anything not shown.
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a senior SEO strategist at GoComet.com."},
            {"role": "user", "content": final_prompt},
        ],
        temperature=0.7,
        max_tokens=2500
    )

    return response.choices[0].message.content

# -------------------- STREAMLIT APP --------------------
st.set_page_config(page_title="SEO Content Brief Generator", page_icon="🚀")
st.title("\ud83d\ude80 SEO Content Brief Generator")

openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")
scraperapi_key = st.text_input("Enter your ScraperAPI Key:", type="password")
company_name = st.text_input("Enter your Company Name:")
company_website = st.text_input("Enter your Company Website URL:")
keyword = st.text_input("Enter your Keyword (Example: Supply Chain Visibility Software):")

if st.button("Scrape SERP Results and Generate Brief"):
    if not openai_api_key or not scraperapi_key or not company_name or not company_website or not keyword:
        st.warning("Please fill all the fields.")
    else:
        with st.spinner("\ud83d\udd0d Scraping Bing SERPs for keyword..."):
            urls = scrape_bing_organic(keyword)

        if urls:
            st.success("\u2705 Scraping Successful. URLs found:")
            for url in urls:
                st.write(f"[{url}]({url})")

            summaries = []
            for idx, url in enumerate(urls):
                with st.spinner(f"\ud83d\udcc3 Scraping and summarizing {url}..."):
                    summary = scrape_and_summarize(url, scraperapi_key)
                    summaries.append(summary)

            with st.spinner("\ud83d\udd8a\ufe0f Generating SEO Content Brief using OpenAI..."):
                seo_brief = generate_seo_brief(openai_api_key, company_name, company_website, keyword, summaries)

            st.markdown("## \ud83d\udcc4 SEO Content Brief")
            st.markdown(seo_brief)

        else:
            st.error("\u274c No valid organic links found. Try another keyword!")
