"""Data models for Brand Identity JSON schema."""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ============================================================================
# COLOR MODELS
# ============================================================================

class ColorInfo(BaseModel):
    """Color information with name and hex code."""
    name: str = Field(default="", description="Color name")
    hex: str = Field(default="", description="Hex color code")
    usage: Optional[str] = Field(default="", description="How this color is used")


class ColorPalette(BaseModel):
    """Brand color palette."""
    primary: Optional[ColorInfo] = Field(default=None, description="Primary brand color")
    secondary: Optional[ColorInfo] = Field(default=None, description="Secondary brand color")
    accent: Optional[ColorInfo] = Field(default=None, description="Accent color")
    neutrals: List[ColorInfo] = Field(default_factory=list, description="Neutral colors")
    semantic_colors: Optional[dict] = Field(default_factory=lambda: {
        "success": {"hex": ""},
        "warning": {"hex": ""},
        "error": {"hex": ""}
    }, description="Semantic colors (success, warning, error)")


# ============================================================================
# BRAND CORE MODELS
# ============================================================================

class BrandPersonality(BaseModel):
    """Brand personality traits and archetypes."""
    traits: List[str] = Field(default_factory=list, description="Personality traits")
    archetypes: List[str] = Field(default_factory=list, description="Brand archetypes")


class BrandCore(BaseModel):
    """Core brand information."""
    brand_name: str = Field(default="", description="Brand name")
    tagline: str = Field(default="", description="Brand tagline")
    industry: str = Field(default="", description="Industry sector")
    brand_mission: str = Field(default="", description="Brand mission statement")
    brand_vision: str = Field(default="", description="Brand vision statement")
    core_values: List[str] = Field(default_factory=list, description="Core brand values")
    brand_personality: BrandPersonality = Field(default_factory=lambda: BrandPersonality())
    positioning: str = Field(default="", description="Brand positioning statement")
    unique_selling_propositions: List[str] = Field(default_factory=list, description="USPs")


# ============================================================================
# TARGET AUDIENCE MODELS
# ============================================================================

class PrimaryDemographics(BaseModel):
    """Primary demographic information."""
    age_range: str = Field(default="", description="Target age range")
    professions: List[str] = Field(default_factory=list, description="Target professions")
    income_level: str = Field(default="", description="Income level")


class TargetAudience(BaseModel):
    """Target audience information."""
    primary_demographics: PrimaryDemographics = Field(default_factory=lambda: PrimaryDemographics())
    psychographics: List[str] = Field(default_factory=list, description="Psychographic traits")
    pain_points_addressed: List[str] = Field(default_factory=list, description="Pain points")
    aspirations: List[str] = Field(default_factory=list, description="Aspirations")


# ============================================================================
# VISUAL IDENTITY MODELS
# ============================================================================

class DesignStyle(BaseModel):
    """Design style specifications."""
    overall_aesthetic: str = Field(default="", description="Overall aesthetic")
    keywords: List[str] = Field(default_factory=list, description="Style keywords")
    influences: List[str] = Field(default_factory=list, description="Design influences")


class Typography(BaseModel):
    """Typography specifications."""
    primary_font: str = Field(default="", description="Primary font family")
    secondary_font: str = Field(default="", description="Secondary font family")
    font_personality: List[str] = Field(default_factory=list, description="Font personality traits")
    hierarchy_style: str = Field(default="", description="Typography hierarchy style")


class ImageryStyle(BaseModel):
    """Imagery style specifications."""
    primary_type: str = Field(default="", description="Primary image type (e.g., photography, illustration, mixed, 3d)")
    photo_style: str = Field(default="", description="Photo style (e.g., candid, staged, lifestyle, product, stylized)")
    lighting: str = Field(default="", description="Lighting style (e.g., natural, studio, dramatic, soft)")
    composition: str = Field(default="", description="Composition style (e.g., minimal, balanced, dynamic)")
    color_treatment: str = Field(default="", description="Color treatment (e.g., vibrant, muted, natural, filtered)")
    subject_focus: List[str] = Field(default_factory=list, description="Subject focus areas")
    perspective_preference: List[str] = Field(default_factory=list, description="Perspective preferences")
    use_of_whitespace: str = Field(default="", description="Whitespace usage")


class GraphicElements(BaseModel):
    """Graphic elements specifications."""
    icon_style: str = Field(default="", description="Icon style")
    pattern_usage: str = Field(default="", description="Pattern usage")
    shape_preference: List[str] = Field(default_factory=list, description="Shape preferences")
    texture_usage: str = Field(default="", description="Texture usage")


class VisualIdentity(BaseModel):
    """Complete visual identity."""
    design_style: DesignStyle = Field(default_factory=lambda: DesignStyle())
    color_palette: ColorPalette = Field(default_factory=lambda: ColorPalette())
    typography: Typography = Field(default_factory=lambda: Typography())
    imagery_style: ImageryStyle = Field(default_factory=lambda: ImageryStyle())
    graphic_elements: GraphicElements = Field(default_factory=lambda: GraphicElements())


# ============================================================================
# BRAND VOICE MODELS
# ============================================================================

class BrandVoice(BaseModel):
    """Brand voice and tone."""
    tone_attributes: List[str] = Field(default_factory=list, description="Tone attributes")
    language_style: str = Field(default="", description="Language style")
    formality_level: str = Field(default="", description="Formality level (e.g., formal, professional, casual, playful)")
    key_phrases: List[str] = Field(default_factory=list, description="Key phrases")
    vocabulary_preferences: List[str] = Field(default_factory=list, description="Vocabulary preferences")
    messaging_approach: str = Field(default="", description="Messaging approach")


# ============================================================================
# IMAGE GENERATION GUIDELINES MODELS
# ============================================================================

class PeopleRepresentation(BaseModel):
    """People representation guidelines."""
    diversity_level: str = Field(default="", description="Diversity level (e.g., high, moderate, specific)")
    ethnicity_inclusion: List[str] = Field(default_factory=list, description="Ethnicity inclusion")
    age_groups: List[str] = Field(default_factory=list, description="Age groups")
    featured_occupations: List[str] = Field(default_factory=list, description="Featured occupations")
    authenticity_level: str = Field(default="", description="Authenticity level (e.g., candid, natural, polished)")


class Environment(BaseModel):
    """Environment guidelines."""
    primary_settings: List[str] = Field(default_factory=list, description="Primary settings")
    indoor_outdoor_balance: str = Field(default="", description="Indoor/outdoor balance")
    location_type: List[str] = Field(default_factory=list, description="Location types")


class PropsAndObjects(BaseModel):
    """Props and objects guidelines."""
    common_items: List[str] = Field(default_factory=list, description="Common items")
    technology_presence: str = Field(default="", description="Technology presence (e.g., high, moderate, minimal)")
    brand_specific_items: List[str] = Field(default_factory=list, description="Brand-specific items")


class MoodAndEmotion(BaseModel):
    """Mood and emotion guidelines."""
    target_feelings: List[str] = Field(default_factory=list, description="Target feelings")
    energy_level: str = Field(default="", description="Energy level (e.g., high, moderate, calm)")
    atmosphere: List[str] = Field(default_factory=list, description="Atmosphere descriptors")


class TechnicalSpecs(BaseModel):
    """Technical specifications."""
    preferred_aspect_ratios: List[str] = Field(default_factory=list, description="Preferred aspect ratios")
    composition_rules: List[str] = Field(default_factory=list, description="Composition rules")
    depth_of_field: str = Field(default="", description="Depth of field preference")
    color_temperature: str = Field(default="", description="Color temperature (e.g., warm, neutral, cool)")


class ImageGenerationGuidelines(BaseModel):
    """Image generation guidelines."""
    people_representation: PeopleRepresentation = Field(default_factory=lambda: PeopleRepresentation())
    environment: Environment = Field(default_factory=lambda: Environment())
    props_and_objects: PropsAndObjects = Field(default_factory=lambda: PropsAndObjects())
    mood_and_emotion: MoodAndEmotion = Field(default_factory=lambda: MoodAndEmotion())
    technical_specs: TechnicalSpecs = Field(default_factory=lambda: TechnicalSpecs())


# ============================================================================
# CONTENT THEMES MODELS
# ============================================================================

class ContentThemes(BaseModel):
    """Content themes and storytelling."""
    recurring_topics: List[str] = Field(default_factory=list, description="Recurring topics")
    storytelling_style: str = Field(default="", description="Storytelling style")
    content_pillars: List[str] = Field(default_factory=list, description="Content pillars")


# ============================================================================
# SOURCE PAGES MODELS
# ============================================================================

class SourcePage(BaseModel):
    """Source page metadata."""
    url: str = Field(description="Source URL")
    page_type: Literal["homepage", "about", "products", "blog", "other", ""] = Field(default="", description="Page type")


# ============================================================================
# MAIN BRAND IDENTITY MODEL
# ============================================================================

class BrandIdentity(BaseModel):
    """Complete Brand Identity JSON structure."""
    brand_core: BrandCore = Field(default_factory=lambda: BrandCore())
    target_audience: TargetAudience = Field(default_factory=lambda: TargetAudience())
    visual_identity: VisualIdentity = Field(default_factory=lambda: VisualIdentity())
    brand_voice: BrandVoice = Field(default_factory=lambda: BrandVoice())
    image_generation_guidelines: ImageGenerationGuidelines = Field(default_factory=lambda: ImageGenerationGuidelines())
    content_themes: ContentThemes = Field(default_factory=lambda: ContentThemes())
    source_pages: List[SourcePage] = Field(default_factory=list, description="Source pages used")

    model_config = {"populate_by_name": True}


# ============================================================================
# API REQUEST/RESPONSE MODELS
# ============================================================================

class ExtractRequest(BaseModel):
    """Request model for brand extraction."""
    url: str = Field(description="Website URL to extract brand from")


class ExtractResponse(BaseModel):
    """Response model for brand extraction."""
    brand_identity: BrandIdentity
    source_urls: List[str] = Field(default_factory=list, description="Source URLs used")


class GenerateRequest(BaseModel):
    """Request model for image generation."""
    brand_json: BrandIdentity
    user_prompt: str = Field(description="User prompt for image generation")


class GenerateResponse(BaseModel):
    """Response model for image generation."""
    image_url: str = Field(description="URL of the generated image")
