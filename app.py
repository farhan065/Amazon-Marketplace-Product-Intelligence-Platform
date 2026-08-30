import streamlit as st


st.set_page_config(
    page_title="Amazon Marketplace Product Intelligence",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container {max-width: 1180px; padding-top: 2rem;}
        .home-hero {
            padding: 2.2rem 2.4rem;
            border-radius: 22px;
            background: linear-gradient(125deg, #172554, #1d4ed8 60%, #0f766e);
            color: white;
            margin-bottom: 1.6rem;
            box-shadow: 0 16px 45px rgba(30, 64, 175, .22);
        }
        .home-hero h1 {font-size: 2.45rem; margin: 0 0 .5rem;}
        .home-hero p {font-size: 1.05rem; margin: 0; opacity: .88;}
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 16px;
            background: rgba(120, 120, 120, .035);
        }
        .status-ready {color: #10b981; font-weight: 700;}
        .status-next {color: #f59e0b; font-weight: 700;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="home-hero">
        <h1>Amazon Marketplace Product Intelligence</h1>
        <p>
            One workspace for customer sentiment, product similarity,
            thumbnail intelligence and price-tier analysis.
        </p>
    </section>
    """,
    unsafe_allow_html=True,
)

st.subheader("Intelligence features")
st.caption(
    "Choose a feature below or use the sidebar. Some pages may need a few "
    "seconds to load their data or models; a loading message will be shown."
)

left, right = st.columns(2, gap="large")

with left:
    with st.container(border=True):
        st.markdown("### 📊 Sentiment Analysis")
        st.markdown('<span class="status-ready">● Ready</span>', unsafe_allow_html=True)
        st.write(
            "Explore marketplace sentiment, inspect individual products, "
            "compare collection keywords and classify a custom review."
        )
        st.page_link(
            "pages/1_Sentiment_Analysis.py",
            label="Open Sentiment Intelligence",
            icon="➡️",
        )

    with st.container(border=True):
        st.markdown("### 🖼️ Thumbnail Grouping")
        st.markdown('<span class="status-next">● Next feature</span>', unsafe_allow_html=True)
        st.write(
            "Group visually similar listing thumbnails without depending "
            "on Amazon category labels."
        )
        st.page_link(
            "pages/3_Thumbnail_Grouping.py",
            label="Open Thumbnail Grouping",
            icon="➡️",
        )

with right:
    with st.container(border=True):
        st.markdown("### 🔎 Similar Products")
        st.markdown('<span class="status-next">● In development</span>', unsafe_allow_html=True)
        st.write(
            "Find comparable marketplace products using product content "
            "and the recommendation pipeline."
        )
        st.page_link(
            "pages/2_Similar_Products.py",
            label="Open Similar Products",
            icon="➡️",
        )

    with st.container(border=True):
        st.markdown("### 💰 Price Tier")
        st.markdown('<span class="status-next">● In development</span>', unsafe_allow_html=True)
        st.write(
            "Analyze pricing positions and product tiers across the "
            "collected marketplace keywords."
        )
        st.page_link(
            "pages/4_Price_Tier.py",
            label="Open Price Tier",
            icon="➡️",
        )

st.divider()
st.caption(
    "Application modules are independent, so each remaining feature can be "
    "developed and connected without changing the sentiment pipeline."
)
