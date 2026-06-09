import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.utils.db import get_db_connection
import re
import os
import json
import warnings

# 1. Page Configuration
st.set_page_config(
    page_title            = "TikTok Trend Analytics Dashboard",
    page_icon             = "🎵",
    layout                = "wide",
    initial_sidebar_state = "expanded"
)

# Custom Premium Dark/Modern Styling
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
        
        * {
            font-family: 'Plus Jakarta Sans', sans-serif;
        }
        
        /* Gradient Title */
        .title-gradient {
            background: linear-gradient(90deg, #FE2C55 0%, #25F4EE 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.8rem;
            font-weight: 800;
            margin-bottom: 0.2rem;
            padding-bottom: 0.5rem;
            text-shadow: 0 4px 30px rgba(0,0,0,0.1);
        }
        
        .subtitle-muted {
            color: #88888b;
            font-size: 1.1rem;
            margin-bottom: 2rem;
        }
        
        /* Metric Card Styling */
        .metric-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
            border-color: rgba(254, 44, 85, 0.3);
            box-shadow: 0 12px 40px 0 rgba(254, 44, 85, 0.15);
        }
        
        .metric-value {
            font-size: 2.2rem;
            font-weight: 700;
            color: #ffffff;
            margin: 0.5rem 0;
        }
        
        .metric-label {
            font-size: 0.9rem;
            font-weight: 500;
            color: #a0a0a5;
            text-transform: uppercase;
            letter-spacing: 1.2px;
        }
        
        /* Section Header */
        .section-header {
            font-size: 1.6rem;
            font-weight: 700;
            color: #ffffff;
            border-left: 5px solid #FE2C55;
            padding-left: 12px;
            margin-top: 2rem;
            margin-bottom: 1.5rem;
        }
    </style>
""", unsafe_allow_html=True)

# 2. Database Fetch Functions (Cached)
@st.cache_data(ttl=120)
def fetch_main_data():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public_analytics'
                AND   table_name   = 'fact_ad_performance'
                AND   column_name  = 'country_code'
            );
        """)
        fact_has_country_code = cur.fetchone()[0]

    join_condition = "da.ad_id = fp.ad_id AND da.country_code = fp.country_code" if fact_has_country_code else "da.ad_id = fp.ad_id"
    query = f"""
        SELECT 
            da.ad_id,
            da.ad_title,
            da.brand_name,
            da.industry_key,
            da.objective_key,
            da.country_code,
            da.video_id,
            da.video_duration,
            da.video_cover_url,
            da.video_width,
            da.video_height,
            da.video_url_1080p,
            da.video_url_720p,
            fp.crawled_date,
            fp.like_count,
            fp.ctr_rate,
            fp.cost_level,
            fp.is_favorite,
            fp.is_search
        FROM public_analytics.dim_ads da
        JOIN public_analytics.fact_ad_performance fp
          ON {join_condition}
        ORDER BY fp.crawled_date DESC, fp.like_count DESC;
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message  = "pandas only supports SQLAlchemy connectable",
            category = UserWarning,
        )
        df = pd.read_sql(query, conn)
    conn.close()
    return df

# Load dynamic mappings from official TikTok Creative Center filters data
CURRENT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
FILTERS_PATH = os.path.join(PROJECT_ROOT, "data", "tiktok_filters.json")

def load_filters():
    try:
        with open(FILTERS_PATH, "r", encoding="utf-8") as f:
            filters_data = json.load(f)
        
        industry_data  = filters_data.get("data", {}).get("industry", [])
        objective_data = filters_data.get("data", {}).get("objective", [])
        
        # Build maps from label to value (label is 'label_xxx' / 'campaign_objective_xxx', value is 'Consumer Electronics' / 'Traffic')
        industry_map  = {item["label"]: item["value"] for item in industry_data if "label" in item and "value" in item}
        objective_map = {item["label"]: item["value"] for item in objective_data if "label" in item and "value" in item}
        return industry_map, objective_map
    except Exception as e:
        return {}, {}

industry_map, objective_map = load_filters()

def clean_metadata(df):
    if 'industry_key' in df.columns:
        df['industry_key'] = df['industry_key'].apply(lambda x: industry_map.get(x, x.replace("label_", "Industry ").strip() if isinstance(x, str) else "N/A"))
    if 'objective_key' in df.columns:
        df['objective_key'] = df['objective_key'].apply(lambda x: objective_map.get(x, x.replace("campaign_objective_", "").title().replace("_", " ") if isinstance(x, str) else "N/A"))
    return df

try:
    df_raw = clean_metadata(fetch_main_data())
except Exception as e:
    st.error(f"⚠️ Could not connect to the database: {e}")
    st.stop()

# 3. Sidebar Filters
st.sidebar.markdown("""
    <div style='text-align: center; margin-bottom: 1.5rem;'>
        <img src='https://img.icons8.com/color/96/tiktok.png' width='60'/>
        <h3 style='margin-top: 0.5rem; font-weight: 700;'>Data Filters</h3>
    </div>
""", unsafe_allow_html=True)

# Date filter
dates          = sorted(df_raw['crawled_date'].unique())
selected_dates = st.sidebar.multiselect(
    "Select Crawl Date",
    options = dates,
    default = []
)

# Filter raw dataframe by date first
if selected_dates:
    df_filtered_date = df_raw[df_raw['crawled_date'].isin(selected_dates)]
else:
    df_filtered_date = df_raw.copy()

# Country filter
countries = sorted(df_filtered_date['country_code'].dropna().unique())
selected_countries = st.sidebar.multiselect(
    "Select Country",
    options = countries,
    default = []
)

# Industry filter
df_filtered_country = df_filtered_date[df_filtered_date['country_code'].isin(selected_countries)] if selected_countries else df_filtered_date.copy()

industries          = sorted(df_filtered_country['industry_key'].dropna().unique())
selected_industries = st.sidebar.multiselect(
    "Select Industry",
    options = industries,
    default = []
)

# CTR filter slider
max_ctr      = float(df_filtered_country['ctr_rate'].max()) if not df_filtered_country.empty and pd.notna(df_filtered_country['ctr_rate'].max()) else 1.0
selected_ctr = st.sidebar.slider(
    "CTR Threshold (%)",
    min_value = 0.0,
    max_value = max_ctr,
    value     = (0.0, max_ctr),
    step      = 0.05
)

# Min Likes filter
max_likes      = int(df_filtered_country['like_count'].max()) if not df_filtered_country.empty and pd.notna(df_filtered_country['like_count'].max()) else 1000
selected_likes = st.sidebar.number_input(
    "Minimum Likes",
    min_value = 0,
    max_value = max_likes,
    value     = 0,
    step      = 100
)

# Search input
search_query = st.sidebar.text_input("Search Title / Brand")

# Apply filters
df = df_filtered_country.copy()
if selected_industries:
    df = df[df['industry_key'].isin(selected_industries)]
df = df[(df['ctr_rate'] >= selected_ctr[0]) & (df['ctr_rate'] <= selected_ctr[1])]
df = df[df['like_count'] >= selected_likes]

if search_query:
    df = df[
        df['ad_title'].str.contains(search_query, case=False, na=False) |
        df['brand_name'].str.contains(search_query, case=False, na=False)
    ]

# Header Title
st.markdown("<div class='title-gradient'>🎵 TikTok Top Ads Trend Analytics</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle-muted'>Automated analysis and visualization of TikTok Creative Center advertising trends</div>", unsafe_allow_html=True)

# 4. KPI Cards
if not df.empty:
    # Get values for selected dates
    latest_date_data = df[df['crawled_date'] == df['crawled_date'].max()] if not df.empty else df
    
    total_ads   = df[['ad_id', 'country_code']].drop_duplicates().shape[0]
    total_likes = latest_date_data['like_count'].sum()
    avg_ctr     = latest_date_data['ctr_rate'].mean()
    
    # Finding top industry
    top_industry_series = latest_date_data.groupby('industry_key')['like_count'].sum().sort_values(ascending=False)
    top_industry        = top_industry_series.index[0] if not top_industry_series.empty else "N/A"
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Total Ads</div>
                <div class='metric-value'>{total_ads:,}</div>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Total Likes (Latest Date)</div>
                <div class='metric-value'>{total_likes:,} ❤️</div>
            </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Average CTR</div>
                <div class='metric-value'>{avg_ctr:.2f}% 📈</div>
            </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Trending Industry</div>
                <div class='metric-value' style='font-size: 1.2rem; padding: 0.8rem 0;'>{top_industry}</div>
            </div>
        """, unsafe_allow_html=True)
else:
    st.warning("⚠️ No data matches the selected filters. Please change your filters in the sidebar.")
    st.stop()

# 5. Main Tab Layout
tab_leaderboard, tab_trend, tab_hashtag, tab_player = st.tabs([
    "Top Ads Leaderboard", 
    "Trend & Growth", 
    "Industry & Hashtags", 
    "Video Player & Deep Dive"
])

# ── TAB 1: LEADERBOARD ──────────────────────────────────────────────────
with tab_leaderboard:
    st.markdown("<div class='section-header'>Highest Engagement Ads Leaderboard</div>", unsafe_allow_html=True)
    
    # Display table using dataframe columns configuration for cover image and video url
    # Sort and pick top ads for the latest selected dates
    latest_date    = df['crawled_date'].max()
    df_leaderboard = df[df['crawled_date'] == latest_date].copy()
    
    df_display = df_leaderboard[[
        'video_cover_url', 'country_code', 'ad_title', 'brand_name', 'industry_key',
        'like_count', 'ctr_rate', 'video_duration', 'video_url_1080p'
    ]].rename(columns={
        'video_cover_url': 'Cover',
        'country_code'   : 'Country',
        'ad_title'       : 'Title',
        'brand_name'     : 'Brand',
        'industry_key'   : 'Industry',
        'like_count'     : 'Likes',
        'ctr_rate'       : 'CTR (%)',
        'video_duration' : 'Duration (s)',
        'video_url_1080p': 'Video Link'
    })
    
    st.dataframe(
        df_display,
        column_config={
            "Cover"     : st.column_config.ImageColumn("Cover", help="Ad video cover image", width="medium"),
            "Video Link": st.column_config.LinkColumn("Watch Video", display_text="Play Video 🔗"),
            "Likes"     : st.column_config.NumberColumn(format="%d ❤️"),
            "CTR (%)"   : st.column_config.NumberColumn(format="%.2f%%")
        },
        use_container_width=True,
        hide_index=True
    )

# ── TAB 2: TREND ANALYSIS ──────────────────────────────────────────────
with tab_trend:
    st.markdown("<div class='section-header'>Metrics Trend by Crawl Date</div>", unsafe_allow_html=True)
    
    # Group data by date and country
    df_daily = df.groupby(['crawled_date', 'country_code']).agg(
        total_likes = ('like_count', 'sum'),
        avg_ctr     = ('ctr_rate', 'mean'),
        total_ads   = ('ad_id', 'count')
    ).reset_index()
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        fig_likes = px.line(
            df_daily, 
            x                  = 'crawled_date',
            y                  = 'total_likes',
            title              = 'Total Accumulated Likes Over Time',
            labels             = {'total_likes': 'Total Likes', 'crawled_date': 'Crawl Date'},
            color              = 'country_code',
            color_discrete_map = {
                'VN': '#FF0000',
                'CA': '#FF6666',
                'SG': '#FF007F',
                'US': '#00FFFF',
                'AU': '#0088FF',
                'NZ': '#0000FF',
                'PH': '#00FF00',
                'TH': '#00A86B',
                'MY': '#FFCC00',
                'ID': '#FF6600',
                'GB': '#FFFFFF',
                'TW': '#A020F0',
                'HK': '#FF00FF',
            },
            markers=True
        )
        fig_likes.update_traces(line_width=3, marker=dict(size=8))
        fig_likes.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_likes, use_container_width=True)
        
    with col_chart2:
        fig_ctr = px.line(
            df_daily, 
            x                  = 'crawled_date',
            y                  = 'avg_ctr',
            title              = 'Average CTR Over Time (%)',
            labels             = {'avg_ctr': 'CTR (%)', 'crawled_date': 'Crawl Date'},
            color              = 'country_code',
            color_discrete_map = {
                'VN': '#FF0000',
                'CA': '#FF6666',
                'SG': '#FF007F',
                'US': '#00FFFF',
                'AU': '#0088FF',
                'NZ': '#0000FF',
                'PH': '#00FF00',
                'TH': '#00A86B',
                'MY': '#FFCC00',
                'ID': '#FF6600',
                'GB': '#FFFFFF',
                'TW': '#A020F0',
                'HK': '#FF00FF',
            },
            markers=True
        )
        fig_ctr.update_traces(line_width=3, marker=dict(size=8))
        fig_ctr.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_ctr, use_container_width=True)

# ── TAB 3: INDUSTRY & HASHTAGS ─────────────────────────────────────────
with tab_hashtag:
    col_ind, col_hash = st.columns(2)
    
    with col_ind:
        st.markdown("<div class='section-header'>Likes by Industry</div>", unsafe_allow_html=True)
        # Industry grouping
        latest_date = df['crawled_date'].max()
        df_ind      = df[df['crawled_date'] == latest_date].groupby('industry_key')['like_count'].sum().reset_index()
        df_ind      = df_ind.sort_values(by='like_count', ascending=True).tail(10)                                     # Top 10
        
        fig_ind = px.bar(
            df_ind, 
            y           = 'industry_key',
            x           = 'like_count',
            orientation = 'h',
            title       = 'Top 10 Industries (by Likes)',
            labels      = {'like_count': 'Total Likes', 'industry_key': 'Industry'}
        )
        fig_ind.update_traces(marker_color='#25F4EE')
        fig_ind.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_ind, use_container_width=True)
        
    with col_hash:
        st.markdown("<div class='section-header'>Top Trending Hashtags</div>", unsafe_allow_html=True)
        
        # Extract hashtags from selected ads
        latest_date = df['crawled_date'].max()
        df_latest = df[df['crawled_date'] == latest_date]
        
        hashtags_list = []
        for idx, row in df_latest.iterrows():
            title = row['ad_title'] or ""
            likes = row['like_count'] or 0
            found = re.findall(r'#[a-zA-Z0-9_]+', title)
            for h in found:
                hashtags_list.append({'hashtag': h.lower(), 'likes': likes})
                
        if hashtags_list:
            df_hash     = pd.DataFrame(hashtags_list)
            df_hash_agg = df_hash.groupby('hashtag').agg(
                likes_sum = ('likes', 'sum'),
                count     = ('hashtag', 'count')
            ).reset_index()
            df_hash_agg = df_hash_agg.sort_values(by='likes_sum', ascending=True).tail(15)
            
            fig_hash = px.bar(
                df_hash_agg, 
                y           = 'hashtag',
                x           = 'likes_sum',
                orientation = 'h',
                title       = 'Top 15 Trending Hashtags (by Likes)',
                labels      = {'likes_sum': 'Total Likes', 'hashtag': 'Hashtag'}
            )
            fig_hash.update_traces(marker_color='#FE2C55')
            fig_hash.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_hash, use_container_width=True)
        else:
            st.info("No hashtags found in the titles of selected ads.")

# ── TAB 4: VIDEO PLAYER & DEEP DIVE ────────────────────────────────────
with tab_player:
    st.markdown("<div class='section-header'>Video Player & Historical Analytics</div>", unsafe_allow_html=True)
    
    # Let user select an ad from the list
    latest_date = df['crawled_date'].max()
    df_latest = df[df['crawled_date'] == latest_date].copy()
    
    if not df_latest.empty:
        # Create a select options string
        df_latest['select_label'] = df_latest['country_code'].fillna('N/A') + " - " + df_latest['brand_name'].fillna('No Brand') + " - " + df_latest['ad_title'].str.slice(0, 50) + " (" + df_latest['ad_id'].astype(str) + ")"
        
        selected_ad_label = st.selectbox(
            "Select Ad to View Details & Play Video",
            options=df_latest['select_label'].tolist()
        )
        
        # Get selected ad row
        selected_row          = df_latest[df_latest['select_label'] == selected_ad_label].iloc[0]
        selected_ad_id        = selected_row['ad_id']
        selected_country_code = selected_row['country_code']
        ad_row                = df_latest[
            (df_latest['ad_id'] == selected_ad_id) &
            (df_latest['country_code'] == selected_country_code)
        ].iloc[0]
        
        col_video, col_details = st.columns([3, 2])
        
        with col_video:
            # Check video url availability
            video_url = ad_row['video_url_1080p'] or ad_row['video_url_720p']
            if isinstance(video_url, str) and video_url.strip() and video_url.startswith("http"):
                st.video(video_url)
            else:
                st.warning("Live video link not found (It might have expired or been blocked by TikTok).")
                cover_url = ad_row['video_cover_url']
                if isinstance(cover_url, str) and cover_url.strip() and cover_url.startswith("http"):
                    st.image(cover_url, caption="Ad cover image")
                    
        with col_details:
            st.markdown(f"### {ad_row['ad_title']}")
            st.markdown(f"**Country:** {ad_row['country_code'] or 'N/A'}")
            st.markdown(f"**Brand:** {ad_row['brand_name'] or 'N/A'}")
            st.markdown(f"**Industry:** {ad_row['industry_key'] or 'N/A'}")
            st.markdown(f"**Campaign Objective:** {ad_row['objective_key'] or 'N/A'}")
            st.markdown(f"**Duration:** {ad_row['video_duration']} seconds" if pd.notna(ad_row['video_duration']) else "**Duration:** N/A")
            
            width   = ad_row['video_width']
            height  = ad_row['video_height']
            res_str = f"{int(width)}x{int(height)}" if pd.notna(width) and pd.notna(height) else "N/A"
            st.markdown(f"**Resolution:** {res_str}")
            
            likes     = ad_row['like_count']
            likes_str = f"{int(likes):,}" if pd.notna(likes) else "0"
            st.markdown(f"**Likes:** {likes_str}")
            
            ctr     = ad_row['ctr_rate']
            ctr_str = f"{ctr:.2f}%" if pd.notna(ctr) else "N/A"
            st.markdown(f"**CTR:** {ctr_str}")
            
            # Historical trend for this specific ad (if crawled in multiple days)
            df_history = df_raw[
                (df_raw['ad_id'] == selected_ad_id) &
                (df_raw['country_code'] == selected_country_code)
            ].sort_values(by='crawled_date')
            if len(df_history) > 1:
                st.markdown("---")
                st.markdown("**Interaction History for this Ad:**")
                fig_hist = go.Figure()
                fig_hist.add_trace(go.Scatter(
                    x=df_history['crawled_date'], y=df_history['like_count'],
                    mode='lines+markers', name='Likes', line=dict(color='#FE2C55', width=2)
                ))
                fig_hist.update_layout(
                    height=200, margin=dict(l=0, r=0, t=10, b=0),
                    template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_hist, use_container_width=True)
            else:
                st.info("This ad is newly crawled. No historical data available.")
    else:
        st.info("No ads found.")
