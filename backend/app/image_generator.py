"""Image generation service using Gemini 2.5 Flash (Nano Banana)."""
import os
import base64
from typing import Optional
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from backend.app.models import BrandIdentity
from backend.app.logger import logger
from backend.agents.prompt_crafter import PromptCraftingAgent


class ImageGenerator:
    """Generate on-brand images using Gemini 2.5 Flash image generation."""
    
    def __init__(self):
        api_key = os.getenv('GEMINI_IMAGE_API_KEY', '') or os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_API_KEY', '')
        
        self.downloads_dir = Path("generated_images")
        self.downloads_dir.mkdir(exist_ok=True)
        
        self.prompt_crafter = PromptCraftingAgent()
        
        if api_key and genai:
            try:
                genai.configure(api_key=api_key)
                
                self.model = genai.GenerativeModel(
                    model_name='gemini-2.5-flash-image',
                    generation_config={
                        'response_modalities': ['IMAGE']
                    }
                )
                
                self.enabled = True
            except Exception as e:
                logger.error(f"✗ Error initializing Gemini: {e}", exc_info=True)
                logger.error("=" * 60)
                logger.error("GEMINI API KEY ISSUE")
                logger.error("=" * 60)
                logger.error("Set GEMINI_IMAGE_API_KEY or GEMINI_API_KEY in your .env file")
                logger.error("Get a key from: https://aistudio.google.com/app/apikey")
                logger.error("=" * 60)
                self.enabled = False
        else:
            self.enabled = False
            if not api_key:
                logger.warning("GEMINI_IMAGE_API_KEY not found, image generation will be mocked")
                logger.warning("Get a key from: https://aistudio.google.com/app/apikey")
            if not genai:
                logger.warning("google-generativeai library not found, image generation will be mocked")
    
    def generate(
        self,
        brand_identity: BrandIdentity,
        user_prompt: str
    ) -> str:
        """Generate an image based on brand identity and user prompt."""
        logger.info("Crafting image generation prompt with Prompt Crafting Agent...")
        style_prompt = self.prompt_crafter.craft_prompt(brand_identity, user_prompt)
        
        if self.enabled:
            try:
                logger.info(f"Generating image with Gemini 2.5 Flash...")
                logger.info("=" * 60)
                logger.info("IMAGE GENERATION PROMPT:")
                logger.info("=" * 60)
                logger.info(style_prompt)
                logger.info("=" * 60)
                
                # Generate image using Gemini
                response = self.model.generate_content(style_prompt)
                
                # Process the response to extract image data
                image_url = self._process_response(response)
                if image_url:
                    logger.info("✓ Image generated successfully")
                    return image_url
                else:
                    logger.warning("Could not extract image from response, using mock")
                    return self._mock_generate(style_prompt)
            
            except Exception as e:
                logger.error(f"✗ Error generating image: {e}", exc_info=True)
                logger.error("Check:")
                logger.error("  1. API key is valid")
                logger.error("  2. Model name is correct (gemini-2.5-flash-image)")
                logger.error("  3. Prompt is appropriate (no blocked content)")
                return self._mock_generate(style_prompt)
        else:
            # Return mock image URL
            return self._mock_generate(style_prompt)
    
    def _process_response(self, response) -> Optional[str]:
        """Process the Gemini API response to extract image data."""
        try:
            # Check if response has candidates
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                logger.debug(f"Processing candidate: {type(candidate)}")
                
                # Check for content parts
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    logger.debug(f"Found {len(candidate.content.parts)} parts in content")
                    
                    for idx, part in enumerate(candidate.content.parts):
                        logger.debug(f"Part {idx}: {type(part)}")
                        
                        # Check if part contains image data
                        if hasattr(part, 'inline_data'):
                            inline_data = part.inline_data
                            logger.debug(f"Found inline_data: {type(inline_data)}")
                            
                            if hasattr(inline_data, 'data'):
                                image_data = inline_data.data
                                mime_type = getattr(inline_data, 'mime_type', 'image/png')
                                
                                logger.info(f"Extracted image data: {len(image_data)} bytes, type: {mime_type}")
                                
                                # If data is bytes, convert to base64
                                if isinstance(image_data, bytes):
                                    image_bytes = image_data
                                    image_data_b64 = base64.b64encode(image_bytes).decode('ascii')
                                else:
                                    # Already base64
                                    image_data_b64 = image_data
                                    image_bytes = base64.b64decode(image_data_b64)
                                
                                # Save image locally
                                file_path = self._save_image(image_bytes, mime_type)
                                logger.info(f"Image saved to: {file_path}")
                                
                                # Return as data URL
                                return f"data:{mime_type};base64,{image_data_b64}"
            
            logger.warning("No image data found in response")
            return None
            
        except Exception as e:
            logger.error(f"Error processing response: {e}", exc_info=True)
            return None
    
    def _save_image(self, image_bytes: bytes, mime_type: str) -> Path:
        """Save image bytes to local file."""
        # Determine file extension from MIME type
        ext_map = {
            'image/png': 'png',
            'image/jpeg': 'jpg',
            'image/jpg': 'jpg',
            'image/webp': 'webp',
            'image/gif': 'gif'
        }
        extension = ext_map.get(mime_type, 'png')
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"generated_image_{timestamp}.{extension}"
        file_path = self.downloads_dir / filename
        
        # Save the image
        with open(file_path, 'wb') as f:
            f.write(image_bytes)
        
        return file_path
    
    def _mock_generate(self, prompt: str) -> str:
        """Return a mock image URL for development."""
        # Return a placeholder image URL when API is not available or fails
        return "https://via.placeholder.com/800x600/4A90E2/FFFFFF?text=Generated+Image+(Mock)"
