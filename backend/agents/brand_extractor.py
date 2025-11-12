"""Brand Extraction Agent using LangChain."""
import json
import os
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from backend.agents.tools import (
    WebScraper,
    GoogleSearchTool,
    ColorPaletteExtractor,
    VisionStyleAnalyzer
)
from backend.app.models import BrandIdentity, BrandDetails, ImageStyle, ColorPalette, ColorInfo, Metadata, SourcePage


class BrandExtractionAgent:
    """LangChain-based agent for extracting brand identity from websites."""
    
    def __init__(self):
        self.web_scraper = WebScraper()
        self.search_tool = GoogleSearchTool()
        self.color_extractor = ColorPaletteExtractor()
        self.vision_analyzer = VisionStyleAnalyzer()
        
        # Initialize LLM (use OpenAI or fallback to mock)
        api_key = os.getenv('OPENAI_API_KEY', '')
        if api_key:
            self.llm = ChatOpenAI(
                model="gpt-4-turbo-preview",
                temperature=0.7,
                api_key=api_key
            )
        else:
            # Use a mock LLM if no API key
            self.llm = None
    
    def extract(self, url: str) -> BrandIdentity:
        """Extract brand identity from a website URL."""
        source_pages = []
        
        # Step 1: Scrape the main website
        print(f"Scraping website: {url}")
        scraped_data = self.web_scraper.scrape(url)
        source_pages.append(SourcePage(
            url=url,
            used_for=["mission", "vision", "palette", "style"]
        ))
        
        # Step 2: Extract color palette from images
        print("Extracting color palette...")
        colors = []
        if scraped_data.get('images'):
            # Try to extract colors from first few images
            for img in scraped_data['images'][:3]:
                try:
                    img_colors = self.color_extractor.extract_from_url(img['url'])
                    colors.extend(img_colors)
                except Exception as e:
                    print(f"Error extracting colors from {img['url']}: {e}")
        
        # Step 3: Analyze visual style
        print("Analyzing visual style...")
        image_urls = [img['url'] for img in scraped_data.get('images', [])[:5]]
        style_analysis = self.vision_analyzer.analyze(image_urls)
        
        # Step 4: Search for additional brand information
        print("Searching for additional brand info...")
        brand_name = scraped_data.get('title', '').split('|')[0].split('-')[0].strip()
        if brand_name:
            search_results = self.search_tool.search(f"{brand_name} brand mission vision")
        else:
            search_results = []
        
        # Step 5: Use LLM to generate structured brand identity
        print("Generating brand identity JSON...")
        brand_identity = self._generate_brand_identity(
            scraped_data=scraped_data,
            search_results=search_results,
            colors=colors,
            style_analysis=style_analysis
        )
        
        # Add metadata
        brand_identity.metadata.source_pages = source_pages
        
        return brand_identity
    
    def _generate_brand_identity(
        self,
        scraped_data: Dict[str, Any],
        search_results: List[Dict[str, str]],
        colors: List[Dict[str, str]],
        style_analysis: Dict[str, Any]
    ) -> BrandIdentity:
        """Generate Brand Identity JSON using LLM reasoning."""
        
        # Prepare context for LLM
        context = {
            'website_title': scraped_data.get('title', ''),
            'website_description': scraped_data.get('description', ''),
            'website_text': scraped_data.get('text', '')[:2000],  # Limit text
            'search_results': search_results[:3],
            'colors': colors[:7],
            'style_analysis': style_analysis
        }
        
        # Create prompt for LLM
        prompt = self._create_extraction_prompt(context)
        
        if self.llm:
            # Use real LLM
            try:
                response = self.llm.invoke([HumanMessage(content=prompt)])
                brand_json = self._parse_llm_response(response.content)
            except Exception as e:
                print(f"LLM error: {e}, using fallback")
                brand_json = self._fallback_extraction(context)
        else:
            # Use fallback extraction
            brand_json = self._fallback_extraction(context)
        
        return brand_json
    
    def _create_extraction_prompt(self, context: Dict[str, Any]) -> str:
        """Create prompt for brand extraction."""
        return f"""You are a brand identity extraction expert. Analyze the following website data and extract a comprehensive brand identity.

Website Title: {context['website_title']}
Website Description: {context['website_description']}
Website Text (excerpt): {context['website_text']}

Search Results:
{json.dumps(context['search_results'], indent=2)}

Color Palette:
{json.dumps(context['colors'], indent=2)}

Style Analysis:
{json.dumps(context['style_analysis'], indent=2)}

Extract and return a complete Brand Identity JSON with the following structure:
{{
  "brand_details": {{
    "brand_name": "extracted brand name",
    "brand_mission": "mission statement",
    "brand_vision": "vision statement",
    "brand_personality": ["trait1", "trait2", "trait3"]
  }},
  "image_style": {{
    "style": "visual style description",
    "keywords": ["keyword1", "keyword2"],
    "temperature": "warm|cool|neutral",
    "people_ethnicity": "diverse representation",
    "occupation": ["occupation1", "occupation2"],
    "props": ["prop1", "prop2"],
    "environment": ["env1", "env2"],
    "color_palette": {{
      "primary": {{"name": "color name", "hex": "#hexcode"}},
      "secondary": {{"name": "color name", "hex": "#hexcode"}},
      "support_1": {{"name": "color name", "hex": "#hexcode"}},
      "support_2": {{"name": "color name", "hex": "#hexcode"}},
      "support_3": {{"name": "color name", "hex": "#hexcode"}},
      "positive": {{"name": "color name", "hex": "#hexcode"}},
      "background": {{"name": "color name", "hex": "#hexcode"}}
    }}
  }}
}}

Return ONLY valid JSON, no additional text."""

    def _parse_llm_response(self, response: str) -> BrandIdentity:
        """Parse LLM response into BrandIdentity model."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            response = response.strip()
            if response.startswith('```'):
                # Remove markdown code blocks
                response = response.split('```')[1]
                if response.startswith('json'):
                    response = response[4:]
                response = response.strip()
            elif response.startswith('```json'):
                response = response[7:].strip().rstrip('```').strip()
            
            data = json.loads(response)
            return BrandIdentity(**data)
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            return self._fallback_extraction({})
    
    def _fallback_extraction(self, context: Dict[str, Any]) -> BrandIdentity:
        """Fallback extraction when LLM is not available."""
        # Extract brand name - try multiple methods
        website_title = context.get('website_title', '')
        website_text = context.get('website_text', '')
        website_description = context.get('website_description', '')
        
        # Try to extract brand name from title
        brand_name = website_title.split('|')[0].split('-')[0].split('—')[0].strip()
        
        # If title extraction failed, try to get from first words of description or text
        if not brand_name or brand_name.lower() in ['home', 'welcome', 'index']:
            # Try to extract from description
            if website_description:
                brand_name = website_description.split('.')[0].split(',')[0].strip()[:50]
            # Or from first sentence of text
            elif website_text:
                first_sentence = website_text.split('.')[0].strip()
                # Get first few words
                words = first_sentence.split()[:3]
                brand_name = ' '.join(words) if words else "Unknown Brand"
        
        if not brand_name or len(brand_name) < 2:
            brand_name = "Unknown Brand"
        
        # Extract mission and vision from text
        mission = website_description[:300] if website_description else ""
        if not mission and website_text:
            # Try to find mission-like content (first paragraph or sentences with keywords)
            sentences = website_text.split('.')
            mission_candidates = [s.strip() for s in sentences[:3] if len(s.strip()) > 20]
            mission = '. '.join(mission_candidates[:2])[:300] if mission_candidates else ""
        
        vision = ""
        if website_text:
            # Look for vision-related keywords
            text_lower = website_text.lower()
            vision_keywords = ['vision', 'future', 'goal', 'aspire', 'believe']
            for keyword in vision_keywords:
                if keyword in text_lower:
                    # Find sentence containing keyword
                    for sentence in website_text.split('.'):
                        if keyword in sentence.lower() and len(sentence.strip()) > 30:
                            vision = sentence.strip()[:300]
                            break
                    if vision:
                        break
        
        # Extract colors
        colors = context.get('colors', [])
        color_palette = ColorPalette()
        if colors:
            if len(colors) > 0:
                color_palette.primary = ColorInfo(name=colors[0].get('name', ''), hex=colors[0].get('hex', ''))
            if len(colors) > 1:
                color_palette.secondary = ColorInfo(name=colors[1].get('name', ''), hex=colors[1].get('hex', ''))
            if len(colors) > 2:
                color_palette.support_1 = ColorInfo(name=colors[2].get('name', ''), hex=colors[2].get('hex', ''))
            if len(colors) > 3:
                color_palette.support_2 = ColorInfo(name=colors[3].get('name', ''), hex=colors[3].get('hex', ''))
            if len(colors) > 4:
                color_palette.support_3 = ColorInfo(name=colors[4].get('name', ''), hex=colors[4].get('hex', ''))
            if len(colors) > 5:
                color_palette.positive = ColorInfo(name=colors[5].get('name', ''), hex=colors[5].get('hex', ''))
            if len(colors) > 6:
                color_palette.background = ColorInfo(name=colors[6].get('name', ''), hex=colors[6].get('hex', ''))
        
        # Extract personality traits from text
        personality = []
        if website_text:
            text_lower = website_text.lower()
            trait_keywords = {
                'innovative': ['innovative', 'innovation', 'creative', 'cutting-edge'],
                'professional': ['professional', 'expert', 'expertise', 'quality'],
                'modern': ['modern', 'contemporary', 'current', 'today'],
                'trustworthy': ['trust', 'reliable', 'dependable', 'secure'],
                'friendly': ['friendly', 'welcoming', 'approachable', 'accessible'],
                'ambitious': ['ambitious', 'bold', 'visionary', 'forward-thinking']
            }
            for trait, keywords in trait_keywords.items():
                if any(kw in text_lower for kw in keywords):
                    personality.append(trait)
        
        if not personality:
            personality = ["professional", "modern", "innovative"]
        
        # Create brand identity
        brand_identity = BrandIdentity(
            brand_details=BrandDetails(
                brand_name=brand_name,
                brand_mission=mission or "Mission statement not found",
                brand_vision=vision or "Vision statement not found",
                brand_personality=personality[:5]  # Limit to 5 traits
            ),
            image_style=ImageStyle(
                style=context.get('style_analysis', {}).get('style', 'modern'),
                keywords=["brand", "professional", "modern"],
                temperature="warm",
                color_palette=color_palette
            )
        )
        
        return brand_identity

