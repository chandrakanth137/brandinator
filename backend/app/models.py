"""Data models for Brand Identity JSON schema."""
from typing import List, Optional
from pydantic import BaseModel, Field


class ColorInfo(BaseModel):
    """Color information with name and hex code."""
    name: str = Field(default="", description="Color name")
    hex: str = Field(default="", description="Hex color code")


class ColorPalette(BaseModel):
    """Brand color palette."""
    primary: ColorInfo = Field(default_factory=lambda: ColorInfo())
    secondary: ColorInfo = Field(default_factory=lambda: ColorInfo())
    support_1: ColorInfo = Field(default_factory=lambda: ColorInfo())
    support_2: ColorInfo = Field(default_factory=lambda: ColorInfo())
    support_3: ColorInfo = Field(default_factory=lambda: ColorInfo())
    positive: ColorInfo = Field(default_factory=lambda: ColorInfo())
    background: ColorInfo = Field(default_factory=lambda: ColorInfo())


class ImageStyle(BaseModel):
    """Image style specifications."""
    style: str = Field(default="", description="Overall style description")
    keywords: List[str] = Field(default_factory=list, description="Style keywords")
    temperature: str = Field(default="warm", description="Color temperature (warm/cool/neutral)")
    people_ethnicity: str = Field(default="", description="People ethnicity representation")
    occupation: List[str] = Field(default_factory=list, description="Occupations to represent")
    props: List[str] = Field(default_factory=list, description="Props to include")
    environment: List[str] = Field(default_factory=list, description="Environment settings")
    color_palette: ColorPalette = Field(default_factory=lambda: ColorPalette())


class BrandDetails(BaseModel):
    """Brand identity details."""
    brand_name: str = Field(default="", description="Brand name")
    brand_mission: str = Field(default="", description="Brand mission statement")
    brand_vision: str = Field(default="", description="Brand vision statement")
    brand_personality: List[str] = Field(default_factory=list, description="Brand personality traits")


class SourcePage(BaseModel):
    """Source page metadata."""
    url: str = Field(description="Source URL")
    used_for: List[str] = Field(default_factory=list, description="What this page was used for")


class Metadata(BaseModel):
    """Metadata about brand extraction."""
    source_pages: List[SourcePage] = Field(default_factory=list, description="Source pages used")


class BrandIdentity(BaseModel):
    """Complete Brand Identity JSON structure."""
    brand_details: BrandDetails = Field(default_factory=lambda: BrandDetails())
    image_style: ImageStyle = Field(default_factory=lambda: ImageStyle())
    metadata: Metadata = Field(default_factory=lambda: Metadata(), alias="_metadata", serialization_alias="_metadata")

    model_config = {"populate_by_name": True}


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

