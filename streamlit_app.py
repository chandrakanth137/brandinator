"""Streamlit app combining frontend and backend for Brand Extraction Agent."""
import streamlit as st
import json
import base64
import os
from datetime import datetime
from typing import Optional

# Set API key from Streamlit secrets or environment variables
# Hugging Face Spaces uses environment variables, Streamlit Cloud uses st.secrets
# Backend modules use os.getenv, so we ensure the env var is set
if 'GEMINI_API_KEY' not in os.environ:
    # Try Streamlit secrets first (Streamlit Cloud)
    try:
        if 'GEMINI_API_KEY' in st.secrets:
            os.environ['GEMINI_API_KEY'] = st.secrets['GEMINI_API_KEY']
        elif 'GOOGLE_API_KEY' in st.secrets:
            os.environ['GOOGLE_API_KEY'] = st.secrets['GOOGLE_API_KEY']
    except:
        # If st.secrets is not available (e.g., Hugging Face Spaces), 
        # environment variables should already be set by the platform
        pass

# Import backend modules
try:
    from backend.agents.brand_extractor import BrandExtractionAgent
    from backend.app.image_generator import ImageGenerator
    from backend.app.models import BrandIdentity
    BACKEND_AVAILABLE = True
except ImportError as e:
    BACKEND_AVAILABLE = False
    st.error(f"Error importing backend modules: {e}")
    st.stop()

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
st.markdown('<div class="main-header">🎨 Brandinator</div>', unsafe_allow_html=True)

# Initialize session state
if 'brand_identity' not in st.session_state:
    st.session_state.brand_identity = None
if 'source_urls' not in st.session_state:
    st.session_state.source_urls = []
if 'generated_image_url' not in st.session_state:
    st.session_state.generated_image_url = None
if 'brand_extractor' not in st.session_state:
    st.session_state.brand_extractor = None
if 'image_generator' not in st.session_state:
    st.session_state.image_generator = None

# Initialize agents (cached to avoid reinitializing on every rerun)
@st.cache_resource
def get_brand_extractor():
    """Get or create BrandExtractionAgent instance."""
    return BrandExtractionAgent()

@st.cache_resource
def get_image_generator():
    """Get or create ImageGenerator instance."""
    return ImageGenerator()

# Initialize agents
if BACKEND_AVAILABLE:
    try:
        st.session_state.brand_extractor = get_brand_extractor()
        st.session_state.image_generator = get_image_generator()
    except Exception as e:
        st.error(f"Error initializing agents: {e}")
        st.stop()

# Helper function to convert BrandIdentity to dict for JSON display
def brand_identity_to_dict(brand_identity: BrandIdentity) -> dict:
    """Convert BrandIdentity Pydantic model to dictionary for JSON serialization."""
    if brand_identity is None:
        return {}
    return brand_identity.model_dump(mode='json', exclude_none=False)

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
            if not st.session_state.brand_extractor:
                st.error("Brand extractor not initialized. Please check your API keys in Streamlit secrets.")
            else:
                with st.spinner("Extracting brand identity... This may take a moment."):
                    try:
                        # Extract brand identity directly
                        brand_identity = st.session_state.brand_extractor.extract(url_input)
                        
                        # Store in session state
                        st.session_state.brand_identity = brand_identity
                        
                        # Collect source URLs
                        source_urls = [page.url for page in brand_identity.source_pages] if brand_identity.source_pages else []
                        st.session_state.source_urls = source_urls
                        
                        st.success("✅ Brand identity extracted successfully!")
                    except Exception as e:
                        st.error(f"Error extracting brand: {str(e)}")
                        st.exception(e)
    
    # Display extracted brand identity
    if st.session_state.brand_identity:
        st.markdown("### Extracted Brand Identity")
        
        # Convert to dict and pretty print JSON
        brand_dict = brand_identity_to_dict(st.session_state.brand_identity)
        brand_json_str = json.dumps(brand_dict, indent=2, default=str)
        
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
        
        generate_button = st.button("✨ Generate Image", type="primary", use_container_width=True)
        
        if generate_button:
            if not user_prompt:
                st.error("Please enter an image prompt")
            else:
                if not st.session_state.image_generator:
                    st.error("Image generator not initialized. Please check your API keys in Streamlit secrets.")
                else:
                    with st.spinner("Generating image... This may take a moment."):
                        try:
                            # Generate image directly
                            image_url = st.session_state.image_generator.generate(
                                brand_identity=st.session_state.brand_identity,
                                user_prompt=user_prompt
                            )
                            
                            if image_url:
                                st.session_state.generated_image_url = image_url
                                st.session_state.image_generation_status = "success"
                            else:
                                st.error("No image URL returned from the generator")
                                st.session_state.generated_image_url = None
                                st.session_state.image_generation_status = None
                        except Exception as e:
                            st.error(f"Error generating image: {str(e)}")
                            st.exception(e)
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
            
            # Display the image - handle both data URLs and regular URLs
            try:
                if image_url.startswith('data:'):
                    # For data URLs, decode and use st.image with bytes
                    try:
                        # Extract base64 data from data URL
                        header, data = image_url.split(',', 1)
                        
                        # Fix base64 padding if needed
                        missing_padding = len(data) % 4
                        if missing_padding:
                            data += '=' * (4 - missing_padding)
                        
                        # Decode base64 to bytes
                        try:
                            image_bytes = base64.b64decode(data, validate=True)
                        except:
                            # If validation fails, try without validation
                            image_bytes = base64.b64decode(data)
                        
                        # Validate that we have actual image data (check PNG/JPEG headers)
                        if len(image_bytes) < 10:
                            raise ValueError("Image data too small")
                        
                        # Check for valid image headers
                        is_valid = (
                            image_bytes[:8] == b'\x89PNG\r\n\x1a\n' or  # PNG
                            image_bytes[:2] == b'\xff\xd8' or  # JPEG
                            image_bytes[:4] == b'RIFF' or  # WebP
                            image_bytes[:6] == b'GIF87a' or image_bytes[:6] == b'GIF89a'  # GIF
                        )
                        
                        if not is_valid:
                            st.warning("⚠️ Image data may be corrupted. First bytes: " + str(image_bytes[:20]))
                        
                        # Use st.image with bytes (most reliable method)
                        st.image(image_bytes, caption="Generated Image", use_container_width=True)
                        
                        # Add download button for data URL images
                        st.download_button(
                            label="📥 Download Image",
                            data=image_bytes,
                            file_name=f"generated_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                            mime="image/png",
                            type="primary",
                            use_container_width=True
                        )
                    except Exception as decode_error:
                        st.error(f"Error decoding image: {str(decode_error)}")
                        st.info("Attempting fallback display method...")
                        # If decoding fails, try using st.image directly with the data URL
                        try:
                            st.image(image_url, caption="Generated Image", use_container_width=True)
                        except Exception as fallback_error:
                            st.error(f"Fallback also failed: {str(fallback_error)}")
                            st.info("The image URL was generated but could not be displayed.")
                else:
                    # For regular URLs, use st.image
                    st.image(image_url, caption="Generated Image", use_container_width=True)
                    
                    # Add download button for regular URLs
                    try:
                        import requests
                        # Fetch the image to get bytes for download
                        img_response = requests.get(image_url, timeout=10)
                        if img_response.status_code == 200:
                            st.download_button(
                                label="📥 Download Image",
                                data=img_response.content,
                                file_name=f"generated_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                                mime="image/png",
                                type="primary",
                                use_container_width=True
                            )
                    except Exception as download_error:
                        st.warning(f"Could not prepare download button: {str(download_error)}")
            except Exception as e:
                st.error(f"Error displaying image: {str(e)}")
                st.info("The image URL was generated but could not be displayed. Check the URL below.")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #7f8c8d;'>Brandinator</div>",
    unsafe_allow_html=True
)

