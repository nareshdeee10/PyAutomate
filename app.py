import streamlit as st
import pandas as pd
import asyncio
import sys
import concurrent.futures
from playwright.async_api import async_playwright

# Initialize session state variables
if 'running' not in st.session_state:
    st.session_state.running = False
if 'output_df' not in st.session_state:
    st.session_state.output_df = None
if 'status_msgs' not in st.session_state:
    st.session_state.status_msgs = []

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

UNICORN_URL = "https://www.rpasamples.com/findunicornname"

async def scrape_unicorn_names_async(df):
    """The actual async scraping logic — runs inside its own event loop"""
    results = []
    status_messages = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        await page.goto(UNICORN_URL, wait_until="networkidle")

        total_rows = len(df)
        for i, row in df.iterrows():
            try:
                progress = (i + 1) / total_rows
                status_messages.append(f"Processing row {i+1}/{total_rows}: {row.get('Name', 'N/A')}...")

                month_idx = int(row['Month']) - 1
                if not 0 <= month_idx <= 11:
                    raise ValueError("Month must be 1–12")
                month_name = MONTHS[month_idx]

                await page.get_by_placeholder("Enter your name").fill(str(row['Name']))
                await page.select_option('select', label=month_name)
                await page.get_by_role("button", name="Get Unicorn Name").click()

                result_locator = page.locator("#lblUnicornName")
                await result_locator.wait_for(state="visible", timeout=10000)

                name = await result_locator.inner_text()
                cleaned = name.strip().replace("\n", " ").replace("  ", " ")
                results.append(cleaned)

                status_messages.append(f"→ {cleaned}")

                await asyncio.sleep(0.7)  # polite delay

            except Exception as e:
                results.append(f"Error: {str(e)}")
                status_messages.append(f"Row {i+1} failed: {str(e)}")

        await browser.close()

    df["UnicornName"] = results
    return df, status_messages


def run_scraping_in_thread(df):
    """Helper that creates Proactor loop and runs the async function"""
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()

    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(scrape_unicorn_names_async(df))
        return result
    finally:
        loop.close()


# ────────────────────────────────────────────────
#                Streamlit UI
# ────────────────────────────────────────────────

st.set_page_config(
    page_title="Unicorn Name Generator",
    page_icon="🦄",
    layout="wide"
)

st.title("🦄 Batch Unicorn Name Generator")
st.markdown("Upload CSV with **Name** and **Month** (1–12) columns")

uploaded_file = st.file_uploader("Upload your CSV", type="csv")

if uploaded_file is not None:
    try:
        input_df = pd.read_csv(uploaded_file)

        required = {"Name", "Month"}
        if not required.issubset(input_df.columns):
            st.error(f"CSV must have columns: {', '.join(required)}")
            st.stop()

        st.subheader("Data Preview")
        st.dataframe(input_df.head(10))
        st.caption(f"Showing first 10 rows out of {len(input_df)} total.")

        # ────── The button with disabled state ──────
        if st.button(
            "🚀 Start Scraping",
            type="primary",
            disabled=st.session_state.running,
            key="start_scraping"
        ):
            st.session_state.running = True
            st.session_state.output_df = None
            st.session_state.status_msgs = []
            # Force immediate re-run so button disables right away
            st.rerun()

        # Show spinner + status only when running
        if st.session_state.running:
            with st.spinner("Scraping in background thread... Please wait"):
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_scraping_in_thread, input_df)
                    try:
                        # Wait for result (blocks UI thread, but spinner shows)
                        output_df, status_msgs = future.result(timeout=900)  # 15 min timeout
                        st.session_state.output_df = output_df
                        st.session_state.status_msgs = status_msgs
                        st.session_state.running = False
                        st.success("🎉 Scraping completed!")
                        st.rerun()  # Re-run to update UI (show results + re-enable button)
                    except concurrent.futures.TimeoutError:
                        st.error("Scraping timed out after 15 minutes.")
                        st.session_state.running = False
                        # st.rerun()
                    except Exception as ex:
                        st.error(f"Scraping failed: {ex}")
                        st.session_state.running = False
                        # st.rerun()

        # Show results only when available
        if st.session_state.output_df is not None:
            with st.expander("Processing log", expanded=False):
                for msg in st.session_state.status_msgs:
                    st.write(msg)

            st.subheader("Results")
            st.dataframe(st.session_state.output_df)

            csv = st.session_state.output_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Results CSV",
                data=csv,
                file_name="unicorn_names_results.csv",
                mime="text/csv"
            )

    except Exception as e:
        st.error(f"Error reading CSV: {e}")

st.markdown("---")
st.caption("Streamlit + Playwright • Button disabled during run • Thread-isolated • Windows compatible")
