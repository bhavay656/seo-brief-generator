import streamlit as st
import asyncio
import datetime
from openai import OpenAI
from scraper import scrape_all
from mindmap_generator import generate_mindmap

openai_api_key = st.secrets["openai_api_key"]
scraperapi_key = st.secrets["scraperapi_key"]

st.set_page_config(page_title="SEO Brief Generator", layout="wide")
st.title("🔍 SEO Brief Generator")

keyword = st.text_input("Enter the Target Keyword")
company_name = st.text_input("Your Brand or Website Name (e.g., GoComet)")
company_url = st.text_input("Website URL (e.g., https://www.gocomet.com)")
sitemap_urls = st.text_input("Enter Sitemap URLs (comma-separated)")

if st.button("Generate SEO Brief"):
    if not keyword or not company_name or not company_url:
        st.warning("Please fill in all fields.")
    else:
        urls = sitemap_urls.split(",") if sitemap_urls else []

        st.success(f"Fetched {len(urls)} URLs.")

        with st.spinner("Scraping URL content..."):
            results = asyncio.run(scrape_all(urls, scraperapi_key))

        source_insights = ""
        detailed_insights = []
        current_year = datetime.datetime.now().year

        for r in results:
            if "error" not in r:
                headings = r["headings"]
                structured = {
                    "url": r["url"],
                    "title": r["title"],
                    "meta": r["meta"],
                    "schemas": r.get("schemas", []),
                    "headings": headings
                }

                # Format headings clearly with tag info
                formatted_headings = "\n".join([f"- {h}" for h in headings])
                insight_block = (
                    f"Source URL: {r['url']}\n"
                    f"Title: {r['title']}\n"
                    f"Meta: {r['meta']}\n"
                    f"Schemas Detected: {', '.join(r['schemas']) if r['schemas'] else 'None'}\n"
                    f"Headings Observed:\n{formatted_headings}\n"
                )

                # Call OpenAI to extract TLDR, Context, and Unique Angle
                summary_prompt = f"""
You are an expert SEO analyst. Based on the data below, give:
1. TLDR (a crisp 1-line summary of page goal)
2. Context for Writer (what this article is trying to cover, from a content POV)
3. Unique Angle (what stands out or differs from similar pages)

Title: {r['title']}
Meta: {r['meta']}
Headings: {', '.join(headings)}

Respond ONLY in this format:
TLDR: ...
Context for Writer: ...
Unique Angle: ...
                """.strip()

                try:
                    client = OpenAI(api_key=openai_api_key)
                    response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are a top-tier SEO content strategist."},
                            {"role": "user", "content": summary_prompt}
                        ]
                    )
                    summary = response.choices[0].message.content
                    insight_block += f"\n{summary}\n\n---\n"
                except Exception as e:
                    insight_block += f"\nTLDR: Error from OpenAI - {str(e)}\n\n---\n"

                detailed_insights.append(insight_block)

        st.subheader("Scraped URL Insights")
        full_insight_block = "\n".join(detailed_insights)
        st.text_area("Full Observations", value=full_insight_block, height=600)

        # Generate final brief
        with st.spinner("Generating Final SEO Brief..."):
            brief_prompt = f"""
You are an SEO strategist writing an SEO content brief for the keyword: {keyword}.
Here are full observations from top 10 ranking URLs: \n\n{full_insight_block}

Please now generate:
1. SEO Outline with proper H1, H2, H3
2. For each heading, write:
   - Context (for the writer)
   - Unique angle (if any, esp. for {company_name})
3. Suggest:
   - Primary keyword
   - Secondary keywords
   - NLP & semantic keyword suggestions
   - Internal linking ideas (valid URLs only with 200 status on {company_url})
   - External resource prompts
   - Updated year to {current_year}, unless the article is historic
   - Avoid fluff, hype or overused LLM phrases (embrace, ever-changing, game-changer etc.)

End the output with a clearly structured visual mindmap-style flow of H1 > H2 > H3 topics.
            """

            final_response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a battle-tested SEO strategist."},
                    {"role": "user", "content": brief_prompt}
                ]
            )
            final_brief = final_response.choices[0].message.content

        st.subheader("Generated Full SEO Content Brief")
        st.text_area("SEO Content Brief", final_brief, height=1000)

        # Offer CTA for next steps
        st.subheader("What would you like to do next?")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("⬇️ Download Brief", final_brief, file_name=f"{keyword}_SEO_Brief.txt")

        with col2:
            if st.button("📝 Get Going with Content Creation"):
                st.session_state["brief"] = final_brief

# Content Generation Flow
if "brief" in st.session_state:
    st.subheader("✏️ Confirm Your Article Outline")

    default_outline = "\n".join([line for line in st.session_state["brief"].splitlines() if line.startswith("H")])
    outline = st.text_area("Edit your article structure (H1:, H2:, etc.)", value=default_outline, height=400)

    if st.button("✅ Confirm & Create Content"):
        content_prompt = f"""
You are a professional B2B content writer.

Here is the article outline:\n\n{outline}

Write fresh, 2025-relevant, fluff-free SEO content.
Avoid any generic terms like "embrace", "ever-changing", "landscape", etc.
Use real-world phrasing, break down concepts simply.
The tone should be clear, professional, and optimized for conversions.
Target keyword: {keyword}
Brand: {company_name}
Site: {company_url}

Start writing now.
        """

        with st.spinner("Creating high-quality content..."):
            content = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a highly experienced SEO content writer."},
                    {"role": "user", "content": content_prompt}
                ]
            ).choices[0].message.content

        st.subheader("📄 Final Content")
        st.text_area("Your SEO Blog", content, height=1000)
        st.download_button("📥 Download Article", content, file_name=f"{keyword}_SEO_Article.txt")
