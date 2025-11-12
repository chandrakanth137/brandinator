"""Image generation service using Google Gemini Nano Banana API."""
import os
import json
import base64
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from backend.app.models import BrandIdentity


class ImageGenerator:
    """Generate on-brand images using brand identity."""
    
    def __init__(self):
        # Use separate API key for image generation
        api_key = os.getenv('GEMINI_IMAGE_API_KEY', '') or os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_API_KEY', '')
        if api_key and genai:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel(model_name="gemini-2.5-flash-image")
                self.enabled = True
                print("✓ Gemini image generation enabled")
            except Exception as e:
                print(f"Error initializing Google AI: {e}")
                self.enabled = False
        else:
            self.enabled = False
            if not api_key:
                print("GEMINI_IMAGE_API_KEY not found, image generation will be mocked")
    
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
                print(f"Generating image with prompt: {style_prompt[:100]}...")
                response = self.model.generate_content(style_prompt)
                
                # Process the response to extract image data
                image_url = self._process_response(response)
                if image_url:
                    return image_url
                else:
                    print("Could not extract image from response, using mock")
                    return self._mock_generate(style_prompt)
            except Exception as e:
                print(f"Error generating image: {e}")
                return self._mock_generate(style_prompt)
        else:
            # Return mock image URL
            return self._mock_generate(style_prompt)
    
    def _build_style_prompt(
        self,
        brand_identity: BrandIdentity,
        user_prompt: str
    ) -> str:
        """Build a detailed prompt incorporating brand style."""
        style = brand_identity.image_style
        
        prompt_parts = [
            f"Generate an image: {user_prompt}",
            f"Style: {style.style}",
            f"Keywords: {', '.join(style.keywords)}",
            f"Color temperature: {style.temperature}",
        ]
        
        if style.color_palette.primary.hex:
            prompt_parts.append(
                f"Primary color: {style.color_palette.primary.name} ({style.color_palette.primary.hex})"
            )
        if style.color_palette.secondary.hex:
            prompt_parts.append(
                f"Secondary color: {style.color_palette.secondary.name} ({style.color_palette.secondary.hex})"
            )
        
        if style.occupation:
            prompt_parts.append(f"Occupations: {', '.join(style.occupation)}")
        if style.props:
            prompt_parts.append(f"Props: {', '.join(style.props)}")
        if style.environment:
            prompt_parts.append(f"Environment: {', '.join(style.environment)}")
        
        return ". ".join(prompt_parts)
    
    def _process_response(self, response) -> str:
        """Process the Gemini API response to extract image data."""
        try:
            # The response structure may vary, try different ways to extract image
            # Check if response has image data
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                # Check for image in content
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        # Check if part contains image data
                        if hasattr(part, 'inline_data'):
                            # Image is base64 encoded
                            image_data = part.inline_data.data
                            image_mime_type = part.inline_data.mime_type
                            # Return as data URL
                            return f"data:{image_mime_type};base64,{image_data}"
                        elif hasattr(part, 'text'):
                            # Sometimes the response might contain a URL or reference
                            text = part.text
                            if text.startswith('http'):
                                return text
            
            # Alternative: check if response has direct image data
            if hasattr(response, 'text'):
                # If response.text contains a URL
                if response.text.startswith('http'):
                    return response.text
            
            # If we can't extract image, return None to use mock
            print("Warning: Could not extract image from API response")
            print(f"Response structure: {type(response)}")
            if hasattr(response, '__dict__'):
                print(f"Response attributes: {list(response.__dict__.keys())}")
            return None
            
        except Exception as e:
            print(f"Error processing response: {e}")
            return None
    
    def _mock_generate(self, prompt: str) -> str:
        """Return a mock image URL for development."""
        # Return a placeholder image URL when API is not available or fails
        return "https://via.placeholder.com/800x600/4A90E2/FFFFFF?text=Generated+Image"

