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


class ImageGenerator:
    """Generate on-brand images using Gemini 2.5 Flash image generation."""
    
    def __init__(self):
        # Use Gemini API key (simpler than Vertex AI)
        api_key = os.getenv('GEMINI_IMAGE_API_KEY', '') or os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_API_KEY', '')
        
        # Create downloads directory
        self.downloads_dir = Path("generated_images")
        self.downloads_dir.mkdir(exist_ok=True)
        logger.info(f"Images will be saved to: {self.downloads_dir.absolute()}")
        
        if api_key and genai:
            try:
                # Configure Gemini API
                genai.configure(api_key=api_key)
                
                # Initialize Gemini 2.5 Flash model with image generation capability
                self.model = genai.GenerativeModel(
                    model_name='gemini-2.5-flash-image',
                    generation_config={
                        'response_modalities': ['IMAGE']  # Only generate images
                    }
                )
                
                self.enabled = True
                logger.info("✓ Gemini 2.5 Flash image generation enabled (Nano Banana)")
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
        
        # Build prompt with brand style cues
        style_prompt = self._build_style_prompt(brand_identity, user_prompt)
        
        if self.enabled:
            try:
                logger.info(f"Generating image with Gemini 2.5 Flash...")
                logger.info(f"Prompt: {style_prompt[:200]}...")
                logger.debug(f"Full prompt: {style_prompt}")
                
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
    
    def _build_style_prompt(
        self,
        brand_identity: BrandIdentity,
        user_prompt: str
    ) -> str:
        """Build a prompt with visual style transfer - colors and aesthetic only, no brand text."""
        brand = brand_identity.brand_details
        style = brand_identity.image_style
        
        # Start with the user's prompt as the core content
        prompt_parts = [user_prompt]
        
        # Extract personality traits as visual adjectives (not branded)
        if brand.brand_personality:
            # Convert personality to visual descriptors
            visual_traits = []
            for trait in brand.brand_personality:
                trait_lower = trait.lower()
                if 'professional' in trait_lower:
                    visual_traits.append('clean and polished')
                elif 'modern' in trait_lower:
                    visual_traits.append('contemporary and sleek')
                elif 'innovative' in trait_lower:
                    visual_traits.append('cutting-edge and forward-thinking')
                elif 'friendly' in trait_lower:
                    visual_traits.append('warm and approachable')
                elif 'luxurious' in trait_lower or 'premium' in trait_lower:
                    visual_traits.append('elegant and high-end')
                elif 'playful' in trait_lower or 'fun' in trait_lower:
                    visual_traits.append('vibrant and energetic')
                elif 'trustworthy' in trait_lower or 'reliable' in trait_lower:
                    visual_traits.append('solid and dependable')
                elif 'creative' in trait_lower:
                    visual_traits.append('artistic and imaginative')
                else:
                    visual_traits.append(trait_lower)
            
            if visual_traits:
                prompt_parts.append(f"Style: {', '.join(visual_traits)}")
        
        # Add visual style specifications
        if style.style:
            prompt_parts.append(f"Aesthetic: {style.style}")
        
        if style.keywords:
            # Filter out brand-specific keywords, keep visual ones
            visual_keywords = [kw for kw in style.keywords if kw.lower() not in ['brand', 'logo', 'company']]
            if visual_keywords:
                prompt_parts.append(f"Visual elements: {', '.join(visual_keywords)}")
        
        if style.temperature:
            prompt_parts.append(f"Color temperature: {style.temperature}")
        
        # Color palette - the key element for style transfer
        color_palette = []
        if style.color_palette.primary.hex:
            color_palette.append(style.color_palette.primary.hex)
        if style.color_palette.secondary.hex:
            color_palette.append(style.color_palette.secondary.hex)
        if style.color_palette.support_1.hex:
            color_palette.append(style.color_palette.support_1.hex)
        if style.color_palette.support_2.hex:
            color_palette.append(style.color_palette.support_2.hex)
        if style.color_palette.support_3.hex:
            color_palette.append(style.color_palette.support_3.hex)
        
        if color_palette:
            # Describe the color scheme in a natural way
            if len(color_palette) >= 2:
                prompt_parts.append(f"Color scheme: dominant colors {color_palette[0]} and {color_palette[1]}")
                if len(color_palette) > 2:
                    other_colors = ', '.join(color_palette[2:])
                    prompt_parts.append(f"with accent colors {other_colors}")
            else:
                prompt_parts.append(f"Dominant color: {color_palette[0]}")
        
        # Add background color if specified
        if style.color_palette.background.hex:
            prompt_parts.append(f"Background tone: {style.color_palette.background.hex}")
        
        # Add environment/setting details
        if style.environment:
            prompt_parts.append(f"Setting: {', '.join(style.environment)}")
        
        if style.props:
            prompt_parts.append(f"Props/elements: {', '.join(style.props)}")
        
        if style.people_ethnicity:
            prompt_parts.append(f"People: {style.people_ethnicity}")
        
        if style.occupation:
            prompt_parts.append(f"Featuring: {', '.join(style.occupation)}")
        
        # Combine into a cohesive prompt
        full_prompt = ". ".join(prompt_parts)
        
        # Add instruction for style consistency (visual only)
        full_prompt += ". Maintain consistent visual style, color harmony, and aesthetic throughout the image."
        
        return full_prompt
    
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
