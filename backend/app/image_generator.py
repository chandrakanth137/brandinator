"""Image generation service using Vertex AI Imagen."""
import os
import base64
from typing import Optional
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    # Vertex AI Imagen library (using stable version, not preview)
    import vertexai
    from vertexai.vision_models import ImageGenerationModel
except ImportError as e:
    # If stable version not available, try preview version as fallback
    try:
        from vertexai.preview.vision_models import ImageGenerationModel
    except ImportError:
        vertexai = None
        ImageGenerationModel = None

from backend.app.models import BrandIdentity
from backend.app.logger import logger


class ImageGenerator:
    """Generate on-brand images using Vertex AI Imagen."""
    
    def __init__(self):
        # Vertex AI requires a Project ID and Location
        self.project_id = os.getenv('GOOGLE_PROJECT_ID')
        self.location = os.getenv('GOOGLE_LOCATION', 'us-central1')  # e.g., 'us-central1'
        
        # Create downloads directory
        self.downloads_dir = Path("generated_images")
        self.downloads_dir.mkdir(exist_ok=True)
        logger.info(f"Images will be saved to: {self.downloads_dir.absolute()}")
        
        if self.project_id and vertexai and ImageGenerationModel:
            try:
                logger.info(f"Initializing Vertex AI with project: {self.project_id}, location: {self.location}")
                # Initialize Vertex AI
                vertexai.init(project=self.project_id, location=self.location)
                
                logger.info("Loading Imagen model: imagegeneration@006")
                # Load the pre-trained Imagen model
                self.model = ImageGenerationModel.from_pretrained("imagegeneration@006")
                
                self.enabled = True
                logger.info("✓ Vertex AI Imagen generation enabled successfully")
            except Exception as e:
                error_str = str(e)
                logger.error(f"✗ Error initializing Vertex AI: {error_str}", exc_info=True)
                
                # Provide specific guidance based on error type
                if "credentials were not found" in error_str or "DefaultCredentialsError" in error_str:
                    logger.error("=" * 60)
                    logger.error("AUTHENTICATION REQUIRED")
                    logger.error("=" * 60)
                    logger.error("Run this command to authenticate:")
                    logger.error("  gcloud auth application-default login")
                    logger.error("")
                    logger.error("This will open a browser to sign in with your Google account.")
                    logger.error("Make sure you use the same account that has access to project: " + str(self.project_id))
                    logger.error("=" * 60)
                else:
                    logger.error("Common issues:")
                    logger.error("  1. Vertex AI API not enabled in Google Cloud Console")
                    logger.error("  2. Billing not enabled for the project")
                    logger.error("  3. Authentication failed - run: gcloud auth application-default login")
                    logger.error("  4. Missing IAM permissions - need 'Vertex AI User' role")
                self.enabled = False
        else:
            self.enabled = False
            if not self.project_id:
                logger.warning("GOOGLE_PROJECT_ID not found in environment variables, image generation will be mocked")
            if not vertexai:
                logger.warning("vertexai library not found, image generation will be mocked")
    
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
                logger.info(f"Generating image with prompt: {style_prompt[:500]}...")
                logger.debug(f"Full prompt: {style_prompt}")
                
                # Use Vertex AI Imagen to generate images
                response = self.model.generate_images(
                    prompt=style_prompt,
                    number_of_images=1,
                    # Optional parameters:
                    # aspect_ratio="1:1",
                    # safety_filter_level="block_few",
                )
                
                # Process the response to extract image data
                if response.images:
                    # Get the raw image bytes from the first image
                    image_bytes = response.images[0]._image_bytes
                    
                    logger.info(f"Successfully generated image: {len(image_bytes)} bytes")
                    
                    # Save the image locally
                    file_path = self._save_image(image_bytes, "image/png")
                    logger.info(f"Image saved to: {file_path}")
                    
                    # Convert bytes to base64 data URL to send to frontend
                    image_data_b64 = base64.b64encode(image_bytes).decode('ascii')
                    data_url = f"data:image/png;base64,{image_data_b64}"
                    
                    logger.info("Image generated successfully")
                    return data_url
                else:
                    logger.warning("API response did not contain images, using mock")
                    logger.debug(f"Raw API response: {response}")
                    return self._mock_generate(style_prompt)
            
            except Exception as e:
                logger.error(f"✗ Error generating image: {e}", exc_info=True)
                logger.error("This error occurred during image generation. Check:")
                logger.error("  1. Vertex AI API is enabled")
                logger.error("  2. Billing is enabled")
                logger.error("  3. Authentication is valid: gcloud auth application-default login")
                logger.error("  4. IAM permissions include 'Vertex AI User' role")
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
