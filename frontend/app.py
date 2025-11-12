"""Streamlit frontend for Brand Extraction Agent."""
import streamlit as st
import requests
import json
import base64
import io
from typing import Optional
from urllib.parse import urlparse

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
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #dee2e6;
        max-height: 500px;
        overflow-y: auto;
    }
    .brand-json pre {
        color: #000000 !important;
        font-family: 'Courier New', monospace;
        margin: 0;
        background-color: #ffffff;
    }
    .stMarkdown pre {
        color: #000000 !important;
        background-color: #ffffff !important;
    }
    .stMarkdown code {
        color: #000000 !important;
        background-color: #f8f9fa !important;
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
if 'generated_image_url' not in st.session_state:
    st.session_state.generated_image_url = None


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
    
    extract_button = st.button("🔍 Extract Brand", type="primary", width='stretch')
    
    if extract_button:
        if not url_input:
            st.error("Please enter a website URL")
        else:
            with st.spinner("Extracting brand identity... This may take a moment."):
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/extract",
                        json={"url": url_input},
                        timeout=120  # Increased timeout for LLM processing
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
        
        # Pretty print JSON with proper styling
        brand_json_str = json.dumps(st.session_state.brand_identity, indent=2, default=str)
        # Use st.code for better JSON display with syntax highlighting
        st.code(brand_json_str, language='json')
        
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
        
        generate_button = st.button("✨ Generate Image", type="primary", width='stretch')
        
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
                            timeout=120  # Increased timeout for image generation
                        )
                        response.raise_for_status()
                        data = response.json()
                        
                        image_url = data.get("image_url")
                        
                        if image_url:
                            # Verify the image is accessible before showing success
                            # For data URLs, they're immediately available
                            # For regular URLs, verify they're accessible
                            image_ready = False
                            
                            if image_url.startswith('data:'):
                                # Data URLs are immediately available
                                image_ready = True
                            else:
                                # For regular URLs, verify they're accessible
                                try:
                                    img_check = requests.head(image_url, timeout=10, allow_redirects=True)
                                    if img_check.status_code == 200:
                                        image_ready = True
                                    else:
                                        # Try GET as fallback (some servers don't support HEAD)
                                        img_check = requests.get(image_url, timeout=10, stream=True)
                                        if img_check.status_code == 200:
                                            image_ready = True
                                except:
                                    # If verification fails, still store it and let display handle it
                                    image_ready = True  # Assume it's ready, display will handle errors
                            
                            if image_ready:
                                # Store in session state so it persists
                                st.session_state.generated_image_url = image_url
                                st.session_state.image_generation_status = "success"
                            else:
                                st.error("Image URL returned but image is not accessible yet")
                                st.session_state.generated_image_url = None
                                st.session_state.image_generation_status = None
                        else:
                            st.error("No image URL returned from the API")
                            st.session_state.generated_image_url = None
                            st.session_state.image_generation_status = None
                    except requests.exceptions.RequestException as e:
                        st.error(f"Error generating image: {str(e)}")
                        st.session_state.generated_image_url = None
                        st.session_state.image_generation_status = None
        
        # Display generated image if available
        if st.session_state.generated_image_url:
            image_url = st.session_state.generated_image_url
            
            # Show success message only when image is actually displayed
            if st.session_state.get("image_generation_status") == "success":
                st.success("✅ Image generated successfully!")
                st.session_state.image_generation_status = "displayed"  # Prevent duplicate messages
            
            st.markdown("### Generated Image")
            
            # Display the image
            try:
                st.image(image_url, caption="Generated Image", width='stretch')
            except Exception as e:
                st.error(f"Error displaying image: {str(e)}")
                st.info("The image URL was generated but could not be displayed. Check the URL below.")
            
            # Download button - Handle both data URLs and regular URLs
            if image_url.startswith('data:'):
                # Data URL - extract base64 data
                try:
                    # Format: data:image/png;base64,<data>
                    header, data = image_url.split(',', 1)
                    mime_type = header.split(';')[0].split(':')[1]
                    file_extension = mime_type.split('/')[1] if '/' in mime_type else 'png'
                    
                    # Fix base64 padding if needed (base64 strings must be multiples of 4)
                    missing_padding = len(data) % 4
                    if missing_padding:
                        data += '=' * (4 - missing_padding)
                    
                    # Decode base64 to bytes
                    try:
                        image_bytes = base64.b64decode(data, validate=True)
                    except Exception as decode_error:
                        # If validation fails, try without validation
                        image_bytes = base64.b64decode(data)
                    
                    # Ensure we have bytes, not string
                    if isinstance(image_bytes, str):
                        image_bytes = image_bytes.encode('utf-8')
                    
                    # Use BytesIO to ensure proper byte handling
                    image_buffer = io.BytesIO(image_bytes)
                    image_buffer.seek(0)
                    
                    # Create download button with bytes from buffer
                    st.download_button(
                        label="📥 Download Image",
                        data=image_buffer.getvalue(),
                        file_name=f"generated_image.{file_extension}",
                        mime=mime_type,
                        width='stretch'
                    )
                except Exception as e:
                    # Fallback: provide download link using HTML (more reliable for data URLs)
                    # Create a download link using HTML with JavaScript for better compatibility
                    st.markdown(
                        f'''
                        <a href="{image_url}" download="generated_image.{file_extension}" 
                           style="display: inline-block; padding: 0.5rem 1rem; background-color: #1f77b4; color: white; text-decoration: none; border-radius: 0.25rem; cursor: pointer;">
                           📥 Download Image
                        </a>
                        ''',
                        unsafe_allow_html=True
                    )
            else:
                # Regular URL - provide download link
                try:
                    # Try to fetch the image and provide download
                    img_response = requests.get(image_url, timeout=10)
                    if img_response.status_code == 200:
                        # Determine file extension from URL or content type
                        content_type = img_response.headers.get('content-type', 'image/png')
                        file_extension = content_type.split('/')[1] if '/' in content_type else 'png'
                        
                        st.download_button(
                            label="📥 Download Image",
                            data=img_response.content,
                            file_name=f"generated_image.{file_extension}",
                            mime=content_type,
                            width='stretch'
                        )
                    else:
                        st.markdown(f"[🔗 View Full Image]({image_url})")
                except Exception as e:
                    # If we can't fetch, just provide the link
                    st.markdown(f"[🔗 View Full Image]({image_url})")
            
            # Also show the URL for reference
            with st.expander("🔗 Image URL"):
                st.code(image_url, language=None)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #7f8c8d;'>Brand Extraction Agent v0.1.0</div>",
    unsafe_allow_html=True
)

