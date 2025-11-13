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
        """
        Build an AI image generation prompt that blends user input with brand visual style.
        
        This function creates a detailed prompt that:
        1. Starts with the user's desired content
        2. Applies the brand's color palette
        3. Adds the brand's visual aesthetic and style
        4. Maintains brand personality through visual descriptors
        
        The result is an image that matches what the user wants, styled in the brand's colors and aesthetic.
        
        Args:
            brand_identity: Extracted brand identity with colors, style, personality
            user_prompt: What the user wants to see (e.g., "nurse teaching IV setup")
            
        Returns:
            A comprehensive prompt for image generation
        """
        brand_core = brand_identity.brand_core
        visual_identity = brand_identity.visual_identity
        image_guidelines = brand_identity.image_generation_guidelines
        
        # === SECTION 1: CORE CONTENT (User's Request) ===
        # Start with what the user wants - this is the main subject
        prompt_parts = [f"Create a high-quality image: {user_prompt}"]
        
        # === SECTION 2: VISUAL PERSONALITY ===
        # Convert brand personality to visual/aesthetic descriptors
        if brand_core.brand_personality and brand_core.brand_personality.traits:
            visual_traits = self._personality_to_visual(brand_core.brand_personality.traits)
            if visual_traits:
                prompt_parts.append(f"Visual style: {', '.join(visual_traits)} aesthetic")
        
        # === SECTION 3: ARTISTIC STYLE ===
        # Overall artistic direction from the brand
        design_style = visual_identity.design_style
        if design_style.overall_aesthetic:
            prompt_parts.append(f"Art direction: {design_style.overall_aesthetic} style")
        
        # Visual keywords (filtered to remove brand-specific terms)
        if design_style.keywords:
            visual_keywords = [kw for kw in design_style.keywords 
                             if kw.lower() not in ['brand', 'logo', 'company', 'trademark']]
            if visual_keywords:
                prompt_parts.append(f"Visual theme: {', '.join(visual_keywords)}")
        
        # === SECTION 4: COLOR PALETTE (Most Important for Brand Matching) ===
        color_instruction = self._build_color_instruction(visual_identity.color_palette)
        if color_instruction:
            prompt_parts.append(color_instruction)
        
        # Color temperature for overall mood
        tech_specs = image_guidelines.technical_specs
        if tech_specs.color_temperature:
            temp_desc = {
                'warm': 'warm, inviting tones',
                'cool': 'cool, professional tones',
                'neutral': 'balanced, neutral tones'
            }.get(tech_specs.color_temperature.lower(), tech_specs.color_temperature)
            prompt_parts.append(f"Color mood: {temp_desc}")
        
        # === SECTION 5: COMPOSITION & ENVIRONMENT ===
        # Setting and environment
        env = image_guidelines.environment
        if env.primary_settings:
            prompt_parts.append(f"Environment: {', '.join(env.primary_settings)}")
        
        # Props and objects
        props = image_guidelines.props_and_objects
        if props.common_items:
            prompt_parts.append(f"Include elements: {', '.join(props.common_items)}")
        
        # === SECTION 6: PEOPLE REPRESENTATION ===
        people = image_guidelines.people_representation
        if people.featured_occupations:
            prompt_parts.append(f"Featuring: {', '.join(people.featured_occupations)}")
        
        if people.ethnicity_inclusion:
            prompt_parts.append(f"People: {', '.join(people.ethnicity_inclusion)}")
        
        # === SECTION 7: QUALITY & CONSISTENCY ===
        # Combine all parts into a cohesive prompt
        full_prompt = ". ".join(prompt_parts)
        
        # Add final instructions for quality and consistency
        full_prompt += (
            ". High quality, professional composition. "
            "Ensure all elements use the specified color palette consistently. "
            "Maintain visual harmony and cohesive aesthetic throughout."
        )
        
        logger.debug(f"Generated prompt template breakdown:")
        logger.debug(f"  User content: {user_prompt}")
        visual_traits_list = visual_traits if (brand_core.brand_personality and brand_core.brand_personality.traits) else []
        logger.debug(f"  Visual style: {visual_traits_list if visual_traits_list else 'none'}")
        logger.debug(f"  Color palette: {color_instruction}")
        
        return full_prompt
    
    def _personality_to_visual(self, personality_traits: list) -> list:
        """
        Convert brand personality traits to visual/aesthetic descriptors.
        
        Maps abstract brand personalities to concrete visual styles:
        - "professional" → "clean, polished, organized"
        - "innovative" → "cutting-edge, modern, forward-thinking"
        
        This ensures the image reflects the brand's character visually.
        """
        visual_traits = []
        
        # Mapping of personality traits to visual descriptors
        trait_map = {
            'professional': 'clean, polished, and well-organized',
            'modern': 'contemporary, sleek, and minimalist',
            'innovative': 'cutting-edge, creative, and forward-thinking',
            'friendly': 'warm, approachable, and inviting',
            'luxurious': 'elegant, premium, and sophisticated',
            'premium': 'high-end, refined, and exclusive',
            'playful': 'vibrant, energetic, and fun',
            'fun': 'lively, colorful, and dynamic',
            'trustworthy': 'solid, dependable, and stable',
            'reliable': 'consistent, professional, and steady',
            'creative': 'artistic, imaginative, and expressive',
            'bold': 'striking, confident, and impactful',
            'elegant': 'refined, graceful, and tasteful',
            'minimalist': 'simple, clean, and uncluttered',
            'traditional': 'classic, timeless, and established',
            'edgy': 'bold, unconventional, and distinctive',
            'corporate': 'professional, structured, and formal',
            'casual': 'relaxed, informal, and comfortable',
            'tech': 'digital, modern, and innovative',
            'eco': 'natural, sustainable, and organic',
            'youthful': 'fresh, energetic, and contemporary',
            'mature': 'sophisticated, established, and refined'
        }
        
        for trait in personality_traits:
            trait_lower = trait.lower().strip()
            
            # Try exact match first
            if trait_lower in trait_map:
                visual_traits.append(trait_map[trait_lower])
            else:
                # Try partial matches
                for key, value in trait_map.items():
                    if key in trait_lower:
                        visual_traits.append(value)
                        break
                else:
                    # Use the trait as-is if no mapping found
                    visual_traits.append(trait_lower)
        
        return visual_traits
    
    def _build_color_instruction(self, color_palette: any) -> str:
        """
        Build detailed color instructions from the brand's color palette.
        
        Creates natural language instructions like:
        "Use a color palette dominated by #0070F3 (primary) and #000000 (secondary),
         with #FFFFFF as accent, on a #FAFAFA background"
        
        This is the KEY element that makes generated images match the brand.
        Handles optional/null color fields gracefully.
        """
        colors = []
        
        # Primary color (most important)
        if hasattr(color_palette, 'primary') and color_palette.primary and hasattr(color_palette.primary, 'hex') and color_palette.primary.hex:
            colors.append(f"{color_palette.primary.hex} as the dominant primary color")
        
        # Secondary color
        if hasattr(color_palette, 'secondary') and color_palette.secondary and hasattr(color_palette.secondary, 'hex') and color_palette.secondary.hex:
            colors.append(f"{color_palette.secondary.hex} as the secondary color")
        
        # Support/accent colors
        accent_colors = []
        for attr in ['support_1', 'support_2', 'support_3']:
            if hasattr(color_palette, attr):
                color_obj = getattr(color_palette, attr)
                if color_obj and hasattr(color_obj, 'hex') and color_obj.hex:
                    accent_colors.append(color_obj.hex)
        
        if accent_colors:
            colors.append(f"{', '.join(accent_colors)} as accent colors")
        
        # Positive/highlight color
        if hasattr(color_palette, 'positive') and color_palette.positive and hasattr(color_palette.positive, 'hex') and color_palette.positive.hex:
            colors.append(f"{color_palette.positive.hex} for highlights")
        
        # Background color
        background = ""
        if hasattr(color_palette, 'background') and color_palette.background and hasattr(color_palette.background, 'hex') and color_palette.background.hex:
            background = f" on a {color_palette.background.hex} background"
        
        if colors:
            return f"Color palette: use {', '.join(colors)}{background}"
        
        return ""
    
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
