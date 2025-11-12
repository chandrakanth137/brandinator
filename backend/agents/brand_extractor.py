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
        
        # Check if we got useful data
        if scraped_data.get('error'):
            print(f"Warning: Scraping error: {scraped_data.get('error')}")
        title = scraped_data.get('title', '').lower()
        if not title or title in ['just a moment', 'checking your browser', 'please wait']:
            print("Warning: May have hit a protection page. Consider installing Playwright browsers:")
            print("  uv run playwright install chromium")
        
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
        
        # Step 5: Use LLM to generate structured brand identity with intelligent analysis
        print("Analyzing content and generating brand identity JSON with LLM...")
        brand_identity = self._generate_brand_identity(
            scraped_data=scraped_data,
            search_results=search_results,
            colors=colors,
            style_analysis=style_analysis
        )
        
        # If LLM is not available, use enhanced fallback
        if not self.llm:
            print("LLM not available, using enhanced fallback extraction...")
        
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
        """Create prompt for brand extraction with intelligent inference."""
        return f"""You are an expert brand identity analyst. Your task is to analyze the provided website content and intelligently extract a comprehensive brand identity. You must INFER and ANALYZE brand characteristics even if they are not explicitly stated.

IMPORTANT: Use your analytical skills to infer brand values, personality, vision, and style from the overall content, tone, messaging, and visual elements. Don't just look for explicit statements - analyze what the brand communicates through its content.

Website Data:
Title: {context['website_title']}
Description: {context['website_description']}
Content Excerpt: {context['website_text']}

Additional Context:
Search Results: {json.dumps(context['search_results'], indent=2)}
Extracted Colors: {json.dumps(context['colors'], indent=2)}
Style Analysis: {json.dumps(context['style_analysis'], indent=2)}

ANALYSIS INSTRUCTIONS:

1. **Brand Name**: Extract the clean brand name (remove taglines, remove "|", "-", etc.)

2. **Brand Mission**: Analyze the content to infer the brand's mission. Look for:
   - What problem they solve
   - Who they serve
   - What value they provide
   - Their core purpose
   If not explicit, synthesize from their messaging and value propositions.

3. **Brand Vision**: Infer the brand's vision by analyzing:
   - Future aspirations mentioned
   - Long-term goals
   - What they want to achieve
   - Their ideal future state
   Synthesize from content even if not explicitly stated as "vision".

4. **Brand Personality**: Analyze the tone, language, and messaging to infer personality traits:
   - Professional, friendly, innovative, trustworthy, bold, creative, etc.
   - Extract 3-5 traits that best describe the brand's character
   - Base this on how they communicate, not just explicit mentions

5. **Image Style**: Analyze the brand's visual identity:
   - Style: modern, minimalist, bold, elegant, playful, etc.
   - Keywords: Extract relevant style keywords from content
   - Temperature: warm, cool, or neutral based on color palette and tone
   - People/Ethnicity: Infer from content if they show diverse representation
   - Occupation: What types of people/roles are featured or implied
   - Props: What objects/elements are associated with the brand
   - Environment: What settings/contexts are shown or implied

6. **Color Palette**: Use the extracted colors and assign them meaningfully:
   - Primary: Most prominent brand color
   - Secondary: Supporting brand color
   - Support colors: Additional brand colors
   - Positive: Color used for positive actions/CTAs
   - Background: Typical background color

Return a complete Brand Identity JSON:
{{
  "brand_details": {{
    "brand_name": "clean brand name only",
    "brand_mission": "inferred mission statement based on content analysis",
    "brand_vision": "inferred vision statement based on content analysis",
    "brand_personality": ["trait1", "trait2", "trait3", "trait4"]
  }},
  "image_style": {{
    "style": "inferred visual style",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "temperature": "warm|cool|neutral",
    "people_ethnicity": "diverse|specific|not specified",
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

CRITICAL: Return ONLY valid JSON. No markdown, no explanations, no additional text. Just the JSON object."""

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
        
        # Check if we hit a protection page
        protection_indicators = ['just a moment', 'checking your browser', 'please wait', 'cloudflare']
        title_lower = website_title.lower()
        is_protection_page = any(indicator in title_lower for indicator in protection_indicators)
        
        # Try to extract brand name from title
        brand_name = website_title.split('|')[0].split('-')[0].split('—')[0].strip()
        
        # If we hit a protection page, try to extract from URL or use placeholder
        if is_protection_page:
            # Try to extract domain name from context if available
            # This is a fallback - ideally Playwright should handle this
            brand_name = "Website (Protected by Cloudflare)"
            print("Note: Detected protection page. Install Playwright browsers for better results.")
        
        # If title extraction failed, try to get from first words of description or text
        elif not brand_name or brand_name.lower() in ['home', 'welcome', 'index', '']:
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
        
        # Extract mission - analyze content to infer mission
        mission = website_description[:300] if website_description else ""
        if not mission and website_text:
            # Try to find mission-like content by analyzing value propositions
            text_lower = website_text.lower()
            mission_keywords = ['mission', 'purpose', 'help', 'enable', 'empower', 'build', 'create', 'provide']
            
            # Look for sentences with mission-related keywords
            sentences = website_text.split('.')
            mission_candidates = []
            for sentence in sentences[:10]:  # Check first 10 sentences
                sentence_lower = sentence.lower()
                if any(kw in sentence_lower for kw in mission_keywords) and len(sentence.strip()) > 30:
                    mission_candidates.append(sentence.strip())
            
            if mission_candidates:
                mission = '. '.join(mission_candidates[:2])[:300]
            else:
                # Synthesize from first meaningful sentences
                meaningful = [s.strip() for s in sentences[:5] if len(s.strip()) > 40]
                if meaningful:
                    mission = '. '.join(meaningful[:2])[:300]
        
        # Extract vision - infer from future-oriented language
        vision = ""
        if website_text:
            text_lower = website_text.lower()
            vision_keywords = ['vision', 'future', 'goal', 'aspire', 'believe', 'imagine', 'envision', 'strive', 'aim']
            
            # Look for vision-related content
            sentences = website_text.split('.')
            vision_candidates = []
            for sentence in sentences:
                sentence_lower = sentence.lower()
                if any(kw in sentence_lower for kw in vision_keywords) and len(sentence.strip()) > 30:
                    vision_candidates.append(sentence.strip())
            
            if vision_candidates:
                vision = '. '.join(vision_candidates[:2])[:300]
            else:
                # Try to infer from aspirational language
                aspirational_keywords = ['better', 'best', 'leading', 'transform', 'revolutionize', 'innovate']
                for sentence in sentences[:15]:
                    sentence_lower = sentence.lower()
                    if any(kw in sentence_lower for kw in aspirational_keywords) and len(sentence.strip()) > 40:
                        vision = sentence.strip()[:300]
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
        
        # Extract personality traits by analyzing tone and content
        personality = []
        if website_text:
            text_lower = website_text.lower()
            full_text = (website_title + ' ' + website_description + ' ' + website_text).lower()
            
            # Expanded trait analysis
            trait_keywords = {
                'innovative': ['innovative', 'innovation', 'creative', 'cutting-edge', 'breakthrough', 'pioneer'],
                'professional': ['professional', 'expert', 'expertise', 'quality', 'enterprise', 'business'],
                'modern': ['modern', 'contemporary', 'current', 'today', 'next-gen', 'next generation'],
                'trustworthy': ['trust', 'reliable', 'dependable', 'secure', 'safe', 'trusted'],
                'friendly': ['friendly', 'welcoming', 'approachable', 'accessible', 'easy', 'simple'],
                'ambitious': ['ambitious', 'bold', 'visionary', 'forward-thinking', 'transform'],
                'fast': ['fast', 'speed', 'quick', 'instant', 'rapid', 'performance'],
                'collaborative': ['collaborate', 'team', 'together', 'community', 'partnership'],
                'user-focused': ['user', 'customer', 'developer', 'people-first', 'human-centered']
            }
            
            for trait, keywords in trait_keywords.items():
                if any(kw in full_text for kw in keywords):
                    personality.append(trait)
            
            # Analyze tone
            if '!' in website_text[:500] or 'amazing' in text_lower or 'awesome' in text_lower:
                if 'energetic' not in personality:
                    personality.append('energetic')
            
            if 'secure' in text_lower or 'privacy' in text_lower or 'safe' in text_lower:
                if 'trustworthy' not in personality:
                    personality.append('trustworthy')
        
        if not personality:
            personality = ["professional", "modern", "innovative"]
        else:
            # Limit to 5 most relevant traits
            personality = personality[:5]
        
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

