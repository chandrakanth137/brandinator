"""Image generation service using Google Gemini Nano Banana API."""
import os
import json
import base64
from typing import Dict, Any, Optional
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


class ImageGenerator:
    """Generate on-brand images using brand identity."""
    
    def __init__(self):
        # Use separate API key for image generation
        api_key = os.getenv('GEMINI_IMAGE_API_KEY', '') or os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_API_KEY', '')
        
        # Create downloads directory
        self.downloads_dir = Path("generated_images")
        self.downloads_dir.mkdir(exist_ok=True)
        logger.info(f"Images will be saved to: {self.downloads_dir.absolute()}")
        
        if api_key and genai:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel(model_name="gemini-2.5-flash-image")
                self.enabled = True
                logger.info("Gemini image generation enabled")
            except Exception as e:
                logger.error(f"Error initializing Google AI: {e}")
                self.enabled = False
        else:
            self.enabled = False
            if not api_key:
                logger.warning("GEMINI_IMAGE_API_KEY not found, image generation will be mocked")
    
    def generate(
        self,
        brand_identity: BrandIdentity,
        user_prompt: str
    ) -> str:
        """Generate an image based on brand identity and user prompt."""
        
        # Build prompt with brand style cues
        style_prompt = self._build_style_prompt(brand_identity, user_prompt)
        
        if self.enabled:
            try:
                # Use Google Gemini Nano Banana for image generation
                logger.info(f"Generating image with prompt: {style_prompt[:500]}...")
                logger.debug(f"Full prompt: {style_prompt}")
                response = self.model.generate_content(style_prompt)
                
                # Process the response to extract image data
                image_url = self._process_response(response)
                if image_url:
                    logger.info("Image generated successfully")
                    return image_url
                else:
                    logger.warning("Could not extract image from response, using mock")
                    logger.debug(f"Raw API response (if available): {response}")
                    return self._mock_generate(style_prompt)
            except Exception as e:
                logger.error(f"Error generating image: {e}", exc_info=True)
                return self._mock_generate(style_prompt)
        else:
            # Return mock image URL
            return self._mock_generate(style_prompt)
    
    def _build_style_prompt(
        self,
        brand_identity: BrandIdentity,
        user_prompt: str
    ) -> str:
        """Build a detailed prompt incorporating brand identity and style."""
        brand = brand_identity.brand_details
        style = brand_identity.image_style
        
        # Start with the user's prompt as the core request
        prompt_parts = [f"Create an image: {user_prompt}"]
        
        # Incorporate brand identity context
        if brand.brand_name:
            prompt_parts.append(f"Brand: {brand.brand_name}")
        
        if brand.brand_mission:
            prompt_parts.append(f"Brand mission: {brand.brand_mission}")
        
        if brand.brand_vision:
            prompt_parts.append(f"Brand vision: {brand.brand_vision}")
        
        if brand.brand_personality:
            prompt_parts.append(f"Brand personality: {', '.join(brand.brand_personality)}")
        
        # Add visual style specifications
        if style.style:
            prompt_parts.append(f"Visual style: {style.style}")
        
        if style.keywords:
            prompt_parts.append(f"Style keywords: {', '.join(style.keywords)}")
        
        if style.temperature:
            prompt_parts.append(f"Color temperature: {style.temperature}")
        
        # Add color palette - prioritize primary and secondary, include all available colors
        color_descriptions = []
        if style.color_palette.primary.hex:
            color_descriptions.append(f"primary color {style.color_palette.primary.hex}")
        if style.color_palette.secondary.hex:
            color_descriptions.append(f"secondary color {style.color_palette.secondary.hex}")
        if style.color_palette.support_1.hex:
            color_descriptions.append(f"accent color {style.color_palette.support_1.hex}")
        if style.color_palette.support_2.hex:
            color_descriptions.append(f"accent color {style.color_palette.support_2.hex}")
        if style.color_palette.support_3.hex:
            color_descriptions.append(f"accent color {style.color_palette.support_3.hex}")
        if style.color_palette.positive.hex:
            color_descriptions.append(f"positive accent {style.color_palette.positive.hex}")
        if style.color_palette.background.hex:
            color_descriptions.append(f"background color {style.color_palette.background.hex}")
        
        if color_descriptions:
            prompt_parts.append(f"Use brand colors: {', '.join(color_descriptions)}")
        
        # Add specific visual elements
        if style.occupation:
            prompt_parts.append(f"Represent occupations: {', '.join(style.occupation)}")
        
        if style.props:
            prompt_parts.append(f"Include props: {', '.join(style.props)}")
        
        if style.environment:
            prompt_parts.append(f"Environment setting: {', '.join(style.environment)}")
        
        if style.people_ethnicity:
            prompt_parts.append(f"People representation: {style.people_ethnicity}")
        
        # Combine into a cohesive prompt
        full_prompt = ". ".join(prompt_parts)
        
        # Add instruction to ensure brand consistency
        full_prompt += ". Ensure the image reflects the brand's identity, mission, and visual style consistently."
        
        return full_prompt
    
    def _process_response(self, response) -> Optional[str]:
        """Process the Gemini API response to extract image data and save locally."""
        try:
            image_bytes = None
            mime_type = "image/png"
            image_data_b64 = None
            
            # The response structure may vary, try different ways to extract image
            # Check if response has image data
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                logger.debug(f"Processing candidate: {type(candidate)}")
                
                # Check for image in content
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    logger.debug(f"Found {len(candidate.content.parts)} parts in content")
                    for idx, part in enumerate(candidate.content.parts):
                        logger.debug(f"Part {idx}: {type(part)}, attributes: {[attr for attr in dir(part) if not attr.startswith('_')]}")
                        
                        # Check if part contains image data
                        if hasattr(part, 'inline_data'):
                            inline_data = part.inline_data
                            logger.debug(f"Found inline_data: {type(inline_data)}")
                            
                            # Image is base64 encoded
                            if hasattr(inline_data, 'data'):
                                image_data_raw = inline_data.data
                                logger.debug(f"Raw image data type: {type(image_data_raw)}, length: {len(image_data_raw) if image_data_raw else 0}")
                                
                                # Get MIME type first
                                if hasattr(inline_data, 'mime_type'):
                                    mime_type = inline_data.mime_type or "image/png"
                                else:
                                    mime_type = "image/png"
                                logger.info(f"MIME type: {mime_type}")
                                
                                # Handle different data formats
                                image_data_b64 = None
                                image_bytes = None
                                
                                if isinstance(image_data_raw, bytes):
                                    # Check if it's already raw image bytes (starts with image header)
                                    if len(image_data_raw) > 0:
                                        # PNG header: 0x89 0x50 0x4E 0x47
                                        # JPEG header: 0xFF 0xD8
                                        if image_data_raw[:2] == b'\x89\x50' or image_data_raw[:2] == b'\xff\xd8':
                                            # It's already raw image bytes, not base64
                                            logger.info(f"Found raw image bytes: {len(image_data_raw)} bytes")
                                            image_bytes = image_data_raw
                                        else:
                                            # Try to decode as base64-encoded string (base64 is ASCII-compatible)
                                            try:
                                                # Decode bytes to ASCII string (base64 uses ASCII characters)
                                                image_data_b64 = image_data_raw.decode('ascii')
                                                logger.debug("Decoded bytes to base64 string (ASCII)")
                                            except (UnicodeDecodeError, AttributeError):
                                                # If it's not ASCII, try decoding the bytes directly as base64
                                                logger.debug("Attempting to decode bytes directly as base64")
                                                try:
                                                    image_bytes = base64.b64decode(image_data_raw, validate=True)
                                                    logger.info(f"Successfully decoded image from base64 bytes: {len(image_bytes)} bytes")
                                                    # Re-encode to base64 string for data URL
                                                    image_data_b64 = base64.b64encode(image_bytes).decode('ascii')
                                                except Exception as e:
                                                    logger.error(f"Failed to decode as base64: {e}")
                                                    continue
                                    else:
                                        logger.warning("Empty image data")
                                        continue
                                elif isinstance(image_data_raw, str):
                                    # Already a string (base64)
                                    image_data_b64 = image_data_raw
                                    logger.debug("Image data is already a string")
                                else:
                                    logger.warning(f"Unexpected image data type: {type(image_data_raw)}")
                                    continue
                                
                                # Process the image data
                                if image_bytes is not None:
                                    # Already have raw image bytes
                                    logger.info(f"Using raw image bytes: {len(image_bytes)} bytes")
                                elif image_data_b64:
                                    # Need to decode base64 string
                                    try:
                                        # Fix padding if needed (base64 strings must be multiples of 4)
                                        missing_padding = len(image_data_b64) % 4
                                        if missing_padding:
                                            image_data_b64 += '=' * (4 - missing_padding)
                                        
                                        image_bytes = base64.b64decode(image_data_b64, validate=True)
                                        logger.info(f"Successfully decoded base64 to image: {len(image_bytes)} bytes")
                                    except Exception as decode_error:
                                        logger.error(f"Error decoding base64 image data: {decode_error}", exc_info=True)
                                        continue
                                else:
                                    logger.warning("No image data to process")
                                    continue
                                
                                # Validate it's actually an image by checking headers
                                if len(image_bytes) < 10:
                                    logger.warning("Image data too small")
                                    continue
                                
                                # Check for valid image headers
                                is_valid_image = (
                                    image_bytes[:8] == b'\x89PNG\r\n\x1a\n' or  # PNG
                                    image_bytes[:2] == b'\xff\xd8' or  # JPEG
                                    image_bytes[:4] == b'RIFF' or  # WebP
                                    image_bytes[:6] == b'GIF87a' or image_bytes[:6] == b'GIF89a'  # GIF
                                )
                                
                                if not is_valid_image:
                                    logger.warning(f"Image data doesn't have valid image headers. First bytes: {image_bytes[:20]}")
                                    # Continue anyway - might still be valid
                                
                                # Save image locally
                                file_path = self._save_image(image_bytes, mime_type)
                                logger.info(f"Image saved to: {file_path}")
                                
                                # Create data URL - use existing base64 or encode from bytes
                                if image_data_b64:
                                    data_url = f"data:{mime_type};base64,{image_data_b64}"
                                else:
                                    # Re-encode to base64 for data URL
                                    image_data_b64 = base64.b64encode(image_bytes).decode('ascii')
                                    data_url = f"data:{mime_type};base64,{image_data_b64}"
                                
                                logger.info(f"Returning data URL (length: {len(data_url)} chars)")
                                return data_url
                            else:
                                logger.warning("inline_data has no 'data' attribute")
                                continue
                        elif hasattr(part, 'text'):
                            # Sometimes the response might contain a URL or reference
                            text = part.text
                            if text and text.startswith('http'):
                                logger.info(f"Received image URL: {text}")
                                return text
            
            # Alternative: check if response has direct image data
            # Only try to access response.text if we haven't found inline_data
            # (accessing text when there's inline_data raises an error)
            try:
                if hasattr(response, 'text'):
                    response_text = response.text
                    # If response.text contains a URL
                    if response_text and response_text.startswith('http'):
                        logger.info(f"Received image URL from response.text: {response_text}")
                        return response_text
            except (ValueError, AttributeError) as e:
                # This is expected when response contains inline_data instead of text
                logger.debug(f"Response.text not available (likely has inline_data): {e}")
                pass
            
            # If we can't extract image, return None to use mock
            logger.warning("Could not extract image from API response")
            logger.debug(f"Response structure: {type(response)}")
            if hasattr(response, '__dict__'):
                logger.debug(f"Response attributes: {list(response.__dict__.keys())}")
            
            # Try to log more details about the response
            try:
                if hasattr(response, 'candidates'):
                    logger.debug(f"Candidates: {len(response.candidates)}")
                    if response.candidates:
                        candidate = response.candidates[0]
                        logger.debug(f"Candidate attributes: {[attr for attr in dir(candidate) if not attr.startswith('_')]}")
                        if hasattr(candidate, 'content'):
                            logger.debug(f"Content attributes: {[attr for attr in dir(candidate.content) if not attr.startswith('_')]}")
            except Exception as e:
                logger.debug(f"Error logging response details: {e}")
            
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
        return "https://via.placeholder.com/800x600/4A90E2/FFFFFF?text=Generated+Image"

