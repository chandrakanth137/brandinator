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
        Build a comprehensive AI image generation prompt that incorporates brand identity.
        
        Creates a structured, detailed prompt that ensures the generated image:
        1. Matches the user's desired content
        2. Uses the brand's color palette
        3. Follows the brand's visual aesthetic
        4. Reflects brand personality and mood
        5. Adheres to composition and technical guidelines
        
        Args:
            brand_identity: Extracted brand identity with colors, style, personality
            user_prompt: What the user wants to see (e.g., "nurse teaching IV setup")
            
        Returns:
            A comprehensive, structured prompt for image generation
        """
        brand_core = brand_identity.brand_core
        visual = brand_identity.visual_identity
        image_guidelines = brand_identity.image_generation_guidelines
        voice = brand_identity.brand_voice
        
        # Extract components
        brand_name = brand_core.brand_name or "the brand"
        personality_traits = ", ".join(brand_core.brand_personality.traits) if brand_core.brand_personality and brand_core.brand_personality.traits else "professional"
        aesthetic = visual.design_style.overall_aesthetic or "modern"
        
        # Color palette
        color_palette = visual.color_palette
        primary_color = color_palette.primary.hex if (color_palette.primary and color_palette.primary.hex) else ""
        secondary_color = color_palette.secondary.hex if (color_palette.secondary and color_palette.secondary.hex) else ""
        accent_color = color_palette.accent.hex if (color_palette.accent and color_palette.accent.hex) else ""
        neutrals = [n.hex for n in color_palette.neutrals if n and n.hex] if color_palette.neutrals else []
        
        # Imagery style
        imagery = visual.imagery_style
        lighting = imagery.lighting or "natural"
        composition = imagery.composition or "balanced"
        color_treatment = imagery.color_treatment or "vibrant"
        whitespace = imagery.use_of_whitespace or "generous"
        
        # People representation
        people = image_guidelines.people_representation
        diversity = people.diversity_level or "high"
        authenticity = people.authenticity_level or "polished"
        age_groups = ", ".join(people.age_groups) if people.age_groups else ""
        
        # Environment and props
        environment = image_guidelines.environment
        settings = ", ".join(environment.primary_settings) if environment.primary_settings else "professional setting"
        
        props = image_guidelines.props_and_objects
        common_items = ", ".join(props.common_items) if props.common_items else ""
        
        # Mood and emotion
        mood = image_guidelines.mood_and_emotion
        feelings = ", ".join(mood.target_feelings) if mood.target_feelings else ""
        atmosphere = ", ".join(mood.atmosphere) if mood.atmosphere else ""
        energy = mood.energy_level or "moderate"
        
        # Technical specs
        technical = image_guidelines.technical_specs
        dof = technical.depth_of_field or "sharp focus on subject"
        color_temp = technical.color_temperature or "neutral"
        composition_rules = ", ".join(technical.composition_rules) if technical.composition_rules else "rule of thirds"
        
        formality = voice.formality_level or "professional"
        
        # Build comprehensive structured prompt
        prompt = f"""Create a professional photograph: {user_prompt}

BRAND IDENTITY CONTEXT:
Brand personality: {personality_traits}
Visual aesthetic: {aesthetic}

COLOR PALETTE (incorporate subtly and naturally):"""
        
        if primary_color:
            prompt += f"\n- Primary accent: {primary_color}"
        if secondary_color:
            prompt += f"\n- Secondary: {secondary_color}"
        if accent_color:
            prompt += f"\n- Accent highlights: {accent_color}"
        if neutrals:
            prompt += f"\n- Neutral tones: {', '.join(neutrals[:3])}"
        prompt += f"\n- Color treatment: {color_treatment}"
        
        prompt += f"""

VISUAL STYLE:
- Lighting: {lighting} lighting
- Composition: {composition}, following {composition_rules}
- Use of space: {whitespace} whitespace for clarity and focus
- Depth of field: {dof}
- Color temperature: {color_temp}"""
        
        if age_groups or authenticity != "polished":
            prompt += f"""

PEOPLE (if applicable):
- Diversity: {diversity} diversity level
- Style: {authenticity}, professional appearance"""
            if age_groups:
                prompt += f"\n- Age groups: {age_groups}"
        
        prompt += f"""

ENVIRONMENT & SETTING:
- Location: {settings}"""
        if common_items:
            prompt += f"\n- Props: {common_items}"
        if atmosphere:
            prompt += f"\n- Atmosphere: {atmosphere}"
        
        if feelings or energy != "moderate":
            prompt += f"""

MOOD & EMOTION:
- Energy level: {energy}"""
            if feelings:
                prompt += f"\n- Evoke feelings of: {feelings}"
        
        prompt += f"""

TECHNICAL REQUIREMENTS:
- High resolution, professional quality
- Clean, uncluttered composition
- Subject should be clearly visible and well-lit
- Maintain {aesthetic} aesthetic throughout

The image should feel {personality_traits.lower()} and align with a {formality} brand voice. DO NOT include any text, logos, or brand names in the image."""
        
        logger.debug(f"Generated comprehensive prompt for: {user_prompt}")
        logger.debug(f"  Brand aesthetic: {aesthetic}")
        logger.debug(f"  Primary color: {primary_color}")
        logger.debug(f"  Personality: {personality_traits}")
        
        return prompt
    
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
