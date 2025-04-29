import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai

# Load API keys securely
openai.api_key = st.secrets["openai_api_key"]

# Basic Streamlit UI
st.title("SEO Brief Generator")
query = st.text_input("Enter a keyword to generate a brief")

# Helper to scrape Bing SERP
def fetch_top_results(query, num_results=3):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    results = []
    response = requests.get(
        f"https://www.bing.com/search?q={query}",
        headers=headers
    )
    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.select("li.b_algo h2 a")[:num_results]
    for link in links:
        href = link.get("href")
        text = link.get_text()
        results.append((text, href))
    return results

# Helper to generate SEO brief
def generate_brief(query, urls):
    prompt = f"""You are an SEO content strategist. Write a detailed SEO content brief for the keyword: "{query}" based on the following top search result URLs:\n\n"""

    for title, url in urls:
        prompt += f"- {title}: {url}\n"

    prompt += """
Include:
1. Recommended blog structure (H1, H2, H3).
2. Target audience.
3. Search intent.
4. Recommended word count.
5. Internal linking suggestions (for a B2B SaaS company).
6. Important stats or quotes (even hypothetical).
7. Bonus section ideas for added value.

Make the brief practical and human-friendly.
"""

    completion = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an SEO expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return completion.choices[0].message.content.strip()

# Main logic
if query:
    with st.spinner("Fetching top search results..."):
        top_urls = fetch_top_results(query)

    st.subheader("Top SERP URLs")
    for title, url in top_urls:
        st.markdown(f"- [{title}]({url})")

    with st.spinner("Generating SEO brief..."):
        brief = generate_brief(query, top_urls)

    st.subheader("Generated SEO Content Brief")
    st.markdown(brief)
