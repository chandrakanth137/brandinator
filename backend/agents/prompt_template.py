"""Prompt template for comprehensive brand extraction."""
# This file contains the prompt template for the new comprehensive schema

COMPREHENSIVE_EXTRACTION_PROMPT = """You are an expert brand identity analyst. Analyze the provided website content from multiple pages and extract a COMPREHENSIVE brand identity JSON.

IMPORTANT: Infer and analyze brand characteristics from content, tone, messaging, and visual elements across ALL pages. Don't just look for explicit statements.

WEBSITE DATA:
Homepage Title: {homepage_title}
Homepage Description: {homepage_description}
Combined Content (from all pages): {combined_text}

Pages Crawled:
{page_summaries}

Additional Context:
Search Results: {search_results}
Extracted Colors: {colors}
Extracted Fonts: {fonts}
Style Analysis: {style_analysis}

EXTRACTION INSTRUCTIONS:

1. BRAND CORE:
   - brand_name: Clean name only (remove taglines, "|", "-")
   - tagline: Main tagline or slogan
   - industry: Industry sector (e.g., "Technology", "Healthcare", "E-commerce")
   - brand_mission: What problem they solve, who they serve, core purpose
   - brand_vision: Future aspirations, long-term goals, ideal future state
   - core_values: 3-5 core values (e.g., ["Innovation", "Quality", "Customer-first"])
   - brand_personality.traits: 3-5 personality traits (e.g., ["Professional", "Innovative", "Friendly"])
   - brand_personality.archetypes: Brand archetypes (e.g., ["The Creator", "The Sage"])
   - positioning: Brand positioning statement
   - unique_selling_propositions: List of USPs

2. TARGET AUDIENCE:
   - primary_demographics.age_range: Target age range
   - primary_demographics.professions: Target professions
   - primary_demographics.income_level: Income level
   - psychographics: Psychographic traits
   - pain_points_addressed: Problems they solve
   - aspirations: What audience aspires to

3. VISUAL IDENTITY:
   - design_style.overall_aesthetic: Overall aesthetic (e.g., "Modern minimalist", "Bold and vibrant")
   - design_style.keywords: Style keywords
   - design_style.influences: Design influences
   - color_palette.primary: Most prominent brand color (REQUIRED if found)
   - color_palette.secondary: Secondary brand color (optional)
   - color_palette.accent: Accent color (optional)
   - color_palette.neutrals: List of neutral colors
   - typography.primary_font: Primary font family (REQUIRED - use extracted fonts or infer from style)
   - typography.secondary_font: Secondary font family (if different from primary)
   - typography.font_personality: Font personality traits (e.g., ["Clean", "Modern", "Technical"])
   - imagery_style.primary_type: Image type (e.g., "photography", "illustration", "mixed", "3d", or descriptive terms)
   - imagery_style.photo_style: Photo style (e.g., "candid", "staged", "lifestyle", "product", "stylized", or descriptive terms)
   - imagery_style.lighting: Lighting style (e.g., "natural", "studio", "dramatic", "soft", or descriptive terms)
   - imagery_style.composition: Composition style (e.g., "minimal", "balanced", "dynamic", or descriptive terms)
   - imagery_style.color_treatment: Color treatment (e.g., "vibrant", "muted", "natural", "filtered", or descriptive terms)

4. BRAND VOICE:
   - tone_attributes: Tone descriptors (e.g., ["Friendly", "Professional", "Conversational"])
   - language_style: Language style description
   - formality_level: Formality level (e.g., "formal", "professional", "casual", "playful", or descriptive terms)
   - key_phrases: Recurring phrases
   - messaging_approach: How they communicate

5. IMAGE GENERATION GUIDELINES:
   - people_representation.diversity_level: Diversity level (e.g., "high", "moderate", "specific", or descriptive terms)
   - people_representation.featured_occupations: Occupations to feature
   - environment.primary_settings: Primary settings/environments
   - props_and_objects.common_items: Common props/objects
   - mood_and_emotion.target_feelings: Target emotions
   - mood_and_emotion.energy_level: Energy level (e.g., "high", "moderate", "calm", or descriptive terms)
   - technical_specs.color_temperature: Color temperature (e.g., "warm", "neutral", "cool", or descriptive terms)

6. CONTENT THEMES:
   - recurring_topics: Recurring content topics
   - storytelling_style: Storytelling approach
   - content_pillars: Main content pillars

CRITICAL COLOR RULES:
- PRIMARY COLOR IS REQUIRED - Extract the most prominent brand color (buttons, CTAs, links)
- If no colors found in extracted data, ANALYZE the website style and INFER likely brand colors
- For tech/modern brands: Often black, white, blue, or brand-specific accent colors
- Secondary, accent, neutrals are OPTIONAL but should be included if identifiable
- Background color should be included if clearly identifiable (often white or black)

CRITICAL TYPOGRAPHY RULES:
- PRIMARY_FONT IS REQUIRED - Use extracted fonts if available, otherwise INFER from style
- Modern tech brands often use: Inter, Roboto, Helvetica, Arial, system fonts
- SaaS platforms: Often Inter, SF Pro, or custom sans-serif fonts
- If extracted fonts exist, use them. If not, infer based on brand style.

Return ONLY valid JSON matching this structure:
{{
  "brand_core": {{
    "brand_name": "",
    "tagline": "",
    "industry": "",
    "brand_mission": "",
    "brand_vision": "",
    "core_values": [],
    "brand_personality": {{
      "traits": [],
      "archetypes": []
    }},
    "positioning": "",
    "unique_selling_propositions": []
  }},
  "target_audience": {{
    "primary_demographics": {{
      "age_range": "",
      "professions": [],
      "income_level": ""
    }},
    "psychographics": [],
    "pain_points_addressed": [],
    "aspirations": []
  }},
  "visual_identity": {{
    "design_style": {{
      "overall_aesthetic": "",
      "keywords": [],
      "influences": []
    }},
    "color_palette": {{
      "primary": {{"name": "", "hex": "", "usage": ""}} or null,
      "secondary": {{"name": "", "hex": "", "usage": ""}} or null,
      "accent": {{"name": "", "hex": "", "usage": ""}} or null,
      "neutrals": [{{"name": "", "hex": ""}}],
      "semantic_colors": {{
        "success": {{"hex": ""}},
        "warning": {{"hex": ""}},
        "error": {{"hex": ""}}
      }}
    }},
    "typography": {{
      "primary_font": "",
      "secondary_font": "",
      "font_personality": [],
      "hierarchy_style": ""
    }},
    "imagery_style": {{
      "primary_type": "",
      "photo_style": "",
      "lighting": "",
      "composition": "",
      "color_treatment": "",
      "subject_focus": [],
      "perspective_preference": [],
      "use_of_whitespace": ""
    }},
    "graphic_elements": {{
      "icon_style": "",
      "pattern_usage": "",
      "shape_preference": [],
      "texture_usage": ""
    }}
  }},
  "brand_voice": {{
    "tone_attributes": [],
    "language_style": "",
    "formality_level": "",
    "key_phrases": [],
    "vocabulary_preferences": [],
    "messaging_approach": ""
  }},
  "image_generation_guidelines": {{
    "people_representation": {{
      "diversity_level": "",
      "ethnicity_inclusion": [],
      "age_groups": [],
      "featured_occupations": [],
      "authenticity_level": ""
    }},
    "environment": {{
      "primary_settings": [],
      "indoor_outdoor_balance": "",
      "location_type": []
    }},
    "props_and_objects": {{
      "common_items": [],
      "technology_presence": "",
      "brand_specific_items": []
    }},
    "mood_and_emotion": {{
      "target_feelings": [],
      "energy_level": "",
      "atmosphere": []
    }},
    "technical_specs": {{
      "preferred_aspect_ratios": [],
      "composition_rules": [],
      "depth_of_field": "",
      "color_temperature": ""
    }}
  }},
  "content_themes": {{
    "recurring_topics": [],
    "storytelling_style": "",
    "content_pillars": []
  }}
}}

CRITICAL: Return ONLY valid JSON. No markdown, no explanations. Just the JSON object.
"""

