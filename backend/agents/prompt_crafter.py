"""Image Prompt Crafting Agent - Intelligently combines brand identity with user prompts."""
import json
import os
from typing import Dict, Any
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from backend.app.models import BrandIdentity
from backend.app.logger import logger


PROMPT_CRAFTING_TEMPLATE = """You are an expert image prompt engineer. Your task is to craft a comprehensive, detailed image generation prompt that intelligently combines a user's image request with a brand's visual identity.

USER'S IMAGE REQUEST:
{user_prompt}

BRAND IDENTITY:
{brand_json}

INSTRUCTIONS:
1. Analyze the user's image request to understand what they want to see
2. Select ONLY the most relevant brand elements that enhance the user's request
3. Do NOT include irrelevant brand information - be selective and intelligent
4. Craft a natural, flowing prompt that seamlessly blends brand style with user content
5. Focus on:
   - Colors that match the brand (incorporate naturally, don't force)
   - Visual aesthetic and style that reflects the brand
   - Composition and lighting preferences from the brand
   - Mood and atmosphere that aligns with brand personality
   - Environment/setting if relevant to the user's request
   - People representation guidelines if people are in the image

6. Structure your prompt as a natural description, not a rigid template
7. DO NOT include brand names, logos, or text in the image description
8. Make the prompt detailed enough for high-quality image generation

OUTPUT FORMAT:
Return ONLY the crafted image generation prompt as plain text. No markdown, no JSON, no explanations. Just the prompt itself.

The prompt should read naturally, like instructions to a professional photographer or illustrator, incorporating brand elements subtly and intelligently.

Example structure (adapt based on relevance):
"Create a [user's request] in a [brand aesthetic] style. Use [brand colors] as the primary color palette, with [secondary colors] for accents. The image should have [brand lighting] lighting, [brand composition] composition, and evoke a [brand mood] atmosphere. [Additional relevant brand elements if applicable]. High quality, professional, clean composition. DO NOT include any text, logos, or brand names."

Now craft the prompt:"""


class PromptCraftingAgent:
    """Agent that intelligently crafts image generation prompts by combining brand identity with user requests."""
    
    def __init__(self):
        self.llm = self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize LLM with Google Gemini."""
        if GOOGLE_AVAILABLE:
            api_key = os.getenv('GEMINI_ANALYSIS_API_KEY', '') or os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_API_KEY', '')
            if api_key:
                try:
                    llm = ChatGoogleGenerativeAI(
                        model="gemini-2.5-flash",
                        temperature=0.8,
                        google_api_key=api_key
                    )
                    logger.info("✓ Prompt Crafting Agent: Google Gemini LLM (gemini-2.5-flash) initialized")
                    return llm
                except Exception as e:
                    logger.warning(f"⚠ Google Gemini LLM failed: {e}")
        
        logger.warning("⚠ Prompt Crafting Agent: No LLM available - will use rule-based prompt crafting")
        return None
    
    def craft_prompt(
        self,
        brand_identity: BrandIdentity,
        user_prompt: str
    ) -> str:
        """
        Craft an intelligent image generation prompt by combining brand identity with user request.
        
        Args:
            brand_identity: The extracted brand identity
            user_prompt: The user's image request (e.g., "nurse teaching IV setup")
            
        Returns:
            A well-crafted image generation prompt
        """
        if self.llm:
            try:
                # Convert brand identity to JSON for LLM context
                brand_json = self._brand_identity_to_dict(brand_identity)
                
                # Create the prompt
                prompt = PROMPT_CRAFTING_TEMPLATE.format(
                    user_prompt=user_prompt,
                    brand_json=json.dumps(brand_json, indent=2)
                )
                
                logger.info("Crafting image prompt with LLM...")
                logger.debug(f"User prompt: {user_prompt}")
                
                # Get LLM response
                response = self.llm.invoke([HumanMessage(content=prompt)])
                
                # Extract the crafted prompt
                if hasattr(response, 'content'):
                    crafted_prompt = response.content.strip()
                else:
                    crafted_prompt = str(response).strip()
                
                # Clean up any markdown formatting that might have been added
                crafted_prompt = self._clean_prompt(crafted_prompt)
                
                logger.info("✓ Image prompt crafted successfully by LLM")
                logger.debug(f"Crafted prompt length: {len(crafted_prompt)} characters")
                
                return crafted_prompt
                
            except Exception as e:
                logger.error(f"✗ Error crafting prompt with LLM: {e}", exc_info=True)
                logger.warning("Falling back to rule-based prompt crafting...")
                return self._fallback_craft_prompt(brand_identity, user_prompt)
        else:
            # No LLM available, use rule-based approach
            logger.info("Using rule-based prompt crafting (no LLM available)")
            return self._fallback_craft_prompt(brand_identity, user_prompt)
    
    def _brand_identity_to_dict(self, brand_identity: BrandIdentity) -> Dict[str, Any]:
        """Convert BrandIdentity Pydantic model to dictionary for JSON serialization."""
        brand_dict = brand_identity.model_dump(mode='json', exclude_none=False)
        
        def clean_dict(d):
            if isinstance(d, dict):
                return {k: clean_dict(v) for k, v in d.items() if v is not None and v != "" and v != []}
            elif isinstance(d, list):
                return [clean_dict(item) for item in d if item is not None and item != ""]
            else:
                return d
        
        return clean_dict(brand_dict)
    
    def _clean_prompt(self, prompt: str) -> str:
        """Clean up the LLM-generated prompt (remove markdown, extra formatting)."""
        if prompt.startswith("```"):
            lines = prompt.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            prompt = "\n".join(lines)
        
        prompt = prompt.strip()
        if prompt.startswith('"') and prompt.endswith('"'):
            prompt = prompt[1:-1]
        if prompt.startswith("'") and prompt.endswith("'"):
            prompt = prompt[1:-1]
        
        return prompt.strip()
    
    def _fallback_craft_prompt(
        self,
        brand_identity: BrandIdentity,
        user_prompt: str
    ) -> str:
        """Fallback rule-based prompt crafting when LLM is not available."""
        brand_core = brand_identity.brand_core
        visual = brand_identity.visual_identity
        image_guidelines = brand_identity.image_generation_guidelines
        voice = brand_identity.brand_voice
        
        personality_traits = ", ".join(brand_core.brand_personality.traits) if brand_core.brand_personality and brand_core.brand_personality.traits else "professional"
        aesthetic = visual.design_style.overall_aesthetic or "modern"
        
        color_palette = visual.color_palette
        primary_color = color_palette.primary.hex if (color_palette.primary and color_palette.primary.hex) else ""
        secondary_color = color_palette.secondary.hex if (color_palette.secondary and color_palette.secondary.hex) else ""
        neutrals = [n.hex for n in color_palette.neutrals if n and n.hex] if color_palette.neutrals else []
        
        imagery = visual.imagery_style
        lighting = imagery.lighting or "natural"
        composition = imagery.composition or "balanced"
        color_treatment = imagery.color_treatment or "vibrant"
        
        prompt_parts = [f"Create a professional image: {user_prompt}"]
        
        if aesthetic:
            prompt_parts.append(f"Style: {aesthetic}")
        
        if primary_color:
            color_desc = f"Use {primary_color} as the primary color"
            if secondary_color:
                color_desc += f", with {secondary_color} as secondary"
            if neutrals:
                color_desc += f", and {', '.join(neutrals[:2])} as neutral tones"
            prompt_parts.append(color_desc)
        
        prompt_parts.append(f"{lighting} lighting, {composition} composition, {color_treatment} color treatment")
        
        if personality_traits:
            prompt_parts.append(f"Evoke a {personality_traits.lower()} feeling")
        
        prompt_parts.append("High quality, professional, clean composition. DO NOT include any text, logos, or brand names.")
        
        return ". ".join(prompt_parts)

