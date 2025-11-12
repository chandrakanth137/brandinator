"""Streamlit frontend for Brand Extraction Agent."""
import streamlit as st
import requests
import json
from typing import Optional

# Backend API URL
BACKEND_URL = "http://localhost:8000"

# Page configuration
st.set_page_config(
    page_title="Brand Extraction Agent",
    page_icon="🎨",
    layout="wide"
)

# Custom CSS for better UI
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2c3e50;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #3498db;
    }
    .brand-json {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #dee2e6;
        max-height: 500px;
        overflow-y: auto;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">🎨 Brand Extraction Agent + On-Brand Image Generation</div>', unsafe_allow_html=True)

# Initialize session state
if 'brand_identity' not in st.session_state:
    st.session_state.brand_identity = None
if 'source_urls' not in st.session_state:
    st.session_state.source_urls = []


def check_backend_health() -> bool:
    """Check if backend is running."""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


# Check backend connection
if not check_backend_health():
    st.error("⚠️ Backend API is not running. Please start it with: `uv run backend/app/main.py`")
    st.stop()

# Main layout
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown('<div class="section-header">📊 Brand Information Extraction</div>', unsafe_allow_html=True)
    
    # URL input
    url_input = st.text_input(
        "Website URL",
        placeholder="https://example.com",
        help="Enter the website URL to extract brand identity from"
    )
    
    extract_button = st.button("🔍 Extract Brand", type="primary", use_container_width=True)
    
    if extract_button:
        if not url_input:
            st.error("Please enter a website URL")
        else:
            with st.spinner("Extracting brand identity... This may take a moment."):
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/extract",
                        json={"url": url_input},
                        timeout=60
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    st.session_state.brand_identity = data.get("brand_identity")
                    st.session_state.source_urls = data.get("source_urls", [])
                    
                    st.success("✅ Brand identity extracted successfully!")
                except requests.exceptions.RequestException as e:
                    st.error(f"Error extracting brand: {str(e)}")
    
    # Display extracted brand identity
    if st.session_state.brand_identity:
        st.markdown("### Extracted Brand Identity")
        
        # Pretty print JSON
        brand_json_str = json.dumps(st.session_state.brand_identity, indent=2, default=str)
        st.markdown(f'<div class="brand-json"><pre>{brand_json_str}</pre></div>', unsafe_allow_html=True)
        
        # Show source URLs
        if st.session_state.source_urls:
            with st.expander("📎 Source URLs"):
                for url in st.session_state.source_urls:
                    st.markdown(f"- {url}")

with col2:
    st.markdown('<div class="section-header">🖼️ Image Generation</div>', unsafe_allow_html=True)
    
    if not st.session_state.brand_identity:
        st.info("👈 First extract a brand identity from the left panel to generate images.")
    else:
        # User prompt input
        user_prompt = st.text_area(
            "Image Prompt",
            placeholder="A professional team working together in a modern office",
            help="Describe the image you want to generate based on the extracted brand identity",
            height=100
        )
        
        generate_button = st.button("✨ Generate Image", type="primary", use_container_width=True)
        
        if generate_button:
            if not user_prompt:
                st.error("Please enter an image prompt")
            else:
                with st.spinner("Generating image... This may take a moment."):
                    try:
                        response = requests.post(
                            f"{BACKEND_URL}/generate",
                            json={
                                "brand_json": st.session_state.brand_identity,
                                "user_prompt": user_prompt
                            },
                            timeout=60
                        )
                        response.raise_for_status()
                        data = response.json()
                        
                        image_url = data.get("image_url")
                        
                        if image_url:
                            st.success("✅ Image generated successfully!")
                            st.image(image_url, caption="Generated Image", use_container_width=True)
                            
                            # Download button
                            st.markdown(f"[🔗 View Full Image]({image_url})")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Error generating image: {str(e)}")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #7f8c8d;'>Brand Extraction Agent v0.1.0</div>",
    unsafe_allow_html=True
)

