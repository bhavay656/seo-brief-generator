
import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from openai import OpenAI

client = OpenAI(api_key=st.secrets["openai_api_key"])
scraperapi_key = st.secrets["scraperapi_key"]

st.set_page_config(page_title="SEO Brief Generator", layout="wide")
st.title("SEO Brief Generator")

keyword = st.text_input("Target Keyword (optional)")
topic = st.text_input("Content Topic (optional)")
company_name = st.text_input("Company name")
company_url = st.text_input("Website URL (for internal links)")

query = keyword or topic
if not query:
    st.warning("Please enter a keyword or topic.")
    st.stop()

def fetch_serp_urls(q):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(f"https://www.bing.com/search?q={q}", headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        return [a["href"] for a in soup.select("li.b_algo h2 a") if a["href"].startswith("http")][:10]
    except:
        try:
            r = requests.get(f"http://api.scraperapi.com?api_key={scraperapi_key}&url=https://www.google.com/search?q={q}", timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            return [a["href"] for a in soup.select("a") if a.get("href", "").startswith("http")][:10]
        except:
            return []

def get_title_meta_headings(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string.strip() if soup.title else "No title"
        meta = soup.find("meta", attrs={"name": "description"})
        meta = meta["content"].strip() if meta else "No meta"
        headings = [tag.get_text(strip=True) for tag in soup.find_all(re.compile("^h[1-4]$"))]
        return title, meta, headings
    except:
        return "Error", "Error", []

def get_insight(title, meta, headings, url):
    prompt = f"""You are an SEO strategist.
URL: {url}
Title: {title}
Meta: {meta}
Headings: {headings}

Generate:
1. TLDR (1-line)
2. Context for content
3. Unique angle"""
    try:
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        return res.choices[0].message.content.strip()
    except:
        return "No insight generated."

# Step 1: Fetch SERP URLs
urls = fetch_serp_urls(query)

st.markdown("### 🔗 Top SERP URLs")
for u in urls:
    st.markdown(f"- [{u}]({u})")

# Step 2: Show insights
insights = []
st.subheader("🔍 SERP Insights")
for u in urls:
    title, meta, headings = get_title_meta_headings(u)
    insight = get_insight(title, meta, headings, u)
    insights.append({"url": u, "title": title, "meta": meta, "headings": headings, "insight": insight})
    st.markdown(f"**URL:** [{u}]({u})")
    st.markdown(f"**Title:** {title}")
    st.markdown(f"**Meta:** {meta}")
    st.markdown("**Headings:**")
    for h in headings:
        st.markdown(f"- {h}")
    st.markdown(f"**Insight:** {insight}")
    st.markdown("---")

# Step 3: Generate SEO Brief
if st.button("✅ Generate SEO Brief"):
    brief = []
    for idx, i in enumerate(insights):
        brief.append(f"H{idx+1}: {i['title']}")
        for h in i["headings"]:
            brief.append(f"- Context: {h}")
        brief.append(f"- Insight: {i['insight']}")
        brief.append("")
    brief_text = "\n".join(brief)
    st.session_state["brief"] = brief_text

if "brief" in st.session_state:
    st.subheader("📄 SEO Brief")
    st.markdown("*✏️ You can edit the brief before generating final content.*")
    brief_text = st.text_area("SEO Brief", st.session_state["brief"], height=600)
    st.download_button("📥 Download Brief", brief_text, file_name=f"{query.replace(' ', '_')}_brief.txt")

    # Step 4: Generate Article
    outline_lines = [re.sub(r"[:\-]", "", line).strip() for line in brief_text.splitlines() if line.strip().startswith("H")]
    default_outline = "\n".join(outline_lines)
    st.markdown("## ✏️ Generate Content from Outline")
    outline_input = st.text_area("Edit or approve outline", value=default_outline, height=300)

if user_feedback:
    prompt = f"""You are an SEO writer for {company_name} ({company_url}).

Write a clear, detailed, human-sounding article using the following outline:

{outline_input}

– Match SERP title (H1) to search intent  
– Minimum word count: 1800  
– Tone: Clean, natural, human  
– Embed primary/secondary keywords and NLP terms  
– Avoid exaggerated claims or AI-generated language  
– User feedback: {user_feedback}
"""
else:
    prompt = f"""You are an SEO writer for {company_name} ({company_url}).

Write a clear, detailed, human-sounding article using the following outline:

{outline_input}

– Match SERP title (H1) to search intent  
– Minimum word count: 1800  
– Tone: Clean, natural, human  
– Embed primary/secondary keywords and NLP terms  
– Avoid exaggerated claims or AI-generated language
"""

try:
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    st.session_state["article"] = res.choices[0].message.content.strip()
except:
    st.session_state["article"] = "Failed to generate."

if "article" in st.session_state:
    st.subheader("📝 Generated Article")
    st.text_area("SEO Article", st.session_state["article"], height=800)
    st.download_button("📥 Download Article", st.session_state["article"], file_name=f"{query.replace(' ', '_')}_article.txt")

    feedback = st.text_area("💬 Suggest edits to improve the article below", key="feedback")
    if st.button("🔄 Improve Article Based on Feedback"):
        feedback_prompt = (
            "Here is an article:\n"
            f"{st.session_state['article']}\n\n"
            "Improve it based on this feedback:\n"
            f"{feedback}"
        )
        try:
            res = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": feedback_prompt}],
                temperature=0.4
            )
            st.session_state["article"] = res.choices[0].message.content.strip()
        except:
            st.session_state["article"] = "Failed to improve."
