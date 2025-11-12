"""Brand Extraction Agent using LangChain."""
import json
import os
from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import various LLM providers
try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try:
    from langchain_ollama import ChatOllama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

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
        
        # Initialize LLM with multiple provider support and fallbacks
        self.llm = self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize LLM with fallback to multiple providers."""
        # Try OpenAI first
        if OPENAI_AVAILABLE:
            api_key = os.getenv('OPENAI_API_KEY', '')
            if api_key:
                try:
                    llm = ChatOpenAI(
                        model="gpt-4o-mini",  # Use cheaper model, fallback to gpt-4o if needed
                        temperature=0.7,
                        api_key=api_key
                    )
                    print("✓ OpenAI LLM (gpt-4o-mini) initialized successfully")
                    return llm
                except Exception as e:
                    error_msg = str(e)
                    if "quota" in error_msg.lower() or "429" in error_msg:
                        print("⚠ OpenAI quota exceeded, trying alternative providers...")
                    else:
                        print(f"⚠ OpenAI LLM failed: {e}, trying alternatives...")
        
        # Try Google Gemini (free tier available)
        if GOOGLE_AVAILABLE:
            api_key = os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_API_KEY', '')
            if api_key:
                try:
                    llm = ChatGoogleGenerativeAI(
                        model="gemini-1.5-flash",
                        temperature=0.7,
                        google_api_key=api_key
                    )
                    print("✓ Google Gemini LLM initialized successfully")
                    return llm
                except Exception as e:
                    print(f"⚠ Google Gemini LLM failed: {e}")
        
        # Try Ollama (local, free, no API key needed)
        if OLLAMA_AVAILABLE:
            try:
                llm = ChatOllama(
                    model="llama3.2",  # or "mistral", "llama2", etc.
                    temperature=0.7
                )
                print("✓ Ollama LLM (local) initialized successfully")
                return llm
            except Exception as e:
                print(f"⚠ Ollama LLM not available: {e}")
                print("  Install Ollama: https://ollama.ai/")
        
        # No LLM available
        print("⚠ No LLM available - using enhanced rule-based extraction")
        print("  Options:")
        print("    - Set OPENAI_API_KEY for OpenAI")
        print("    - Set GEMINI_API_KEY for Google Gemini (free tier)")
        print("    - Install Ollama for local LLM: https://ollama.ai/")
        return None
    
    def _initialize_llm_with_skip(self, skip_llm=None):
        """Initialize LLM skipping the one that failed."""
        # Try Google Gemini if OpenAI failed
        if skip_llm and OPENAI_AVAILABLE and isinstance(skip_llm, ChatOpenAI):
            if GOOGLE_AVAILABLE:
                api_key = os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_API_KEY', '')
                if api_key:
                    try:
                        llm = ChatGoogleGenerativeAI(
                            model="gemini-1.5-flash",
                            temperature=0.7,
                            google_api_key=api_key
                        )
                        print("✓ Switched to Google Gemini LLM")
                        return llm
                    except:
                        pass
        
        # Try Ollama as last resort
        if OLLAMA_AVAILABLE:
            try:
                llm = ChatOllama(model="llama3.2", temperature=0.7)
                print("✓ Switched to Ollama LLM (local)")
                return llm
            except:
                pass
        
        return None
    
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
        
        # Step 2: Extract color palette from website CSS and images
        print("Extracting color palette from website...")
        colors = []
        
        # First, extract colors from CSS/styles (background, text, brand colors)
        html_content = scraped_data.get('html', '')
        if html_content:
            try:
                # Extract from CSS
                css_colors = self.color_extractor.extract_from_css(html_content)
                if css_colors:
                    colors.extend(css_colors)
                    print(f"  Found {len(css_colors)} colors from CSS")
            except Exception as e:
                print(f"Error extracting colors from CSS: {e}")
        
        # Add computed colors from Playwright if available
        if scraped_data.get('background_color'):
            bg_hex = self.color_extractor._parse_color_value(scraped_data['background_color'])
            if bg_hex:
                colors.append({
                    'name': 'background',
                    'hex': bg_hex,
                    'source': 'computed_background'
                })
        if scraped_data.get('text_color'):
            text_hex = self.color_extractor._parse_color_value(scraped_data['text_color'])
            if text_hex:
                colors.append({
                    'name': 'text',
                    'hex': text_hex,
                    'source': 'computed_text'
                })
        
        # Also extract colors from images (for additional brand colors)
        if scraped_data.get('images') and len(colors) < 5:  # Only if we don't have enough colors
            try:
                # Try to extract colors from first few images
                for img in scraped_data.get('images', [])[:2]:
                    try:
                        img_colors = self.color_extractor.extract_from_url(img['url'])
                        colors.extend(img_colors)
                    except Exception as e:
                        print(f"Error extracting colors from {img['url']}: {e}")
            except Exception as e:
                print(f"Error extracting colors from images: {e}")
        
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
            # Use real LLM for intelligent analysis
            try:
                print("Using LLM to analyze and infer brand identity...")
                response = self.llm.invoke([HumanMessage(content=prompt)])
                # Handle different response formats
                if hasattr(response, 'content'):
                    content = response.content
                elif hasattr(response, 'text'):
                    content = response.text
                else:
                    content = str(response)
                
                brand_json = self._parse_llm_response(content)
                print("✓ Brand identity extracted successfully with LLM")
            except Exception as e:
                error_msg = str(e)
                if "quota" in error_msg.lower() or "429" in error_msg or "insufficient_quota" in error_msg:
                    print(f"LLM quota exceeded: {e}")
                    print("  Trying to reinitialize with alternative provider...")
                    # Try to reinitialize with alternative (skip the one that failed)
                    original_llm = self.llm
                    self.llm = self._initialize_llm_with_skip(original_llm)
                    if self.llm and self.llm != original_llm:
                        try:
                            response = self.llm.invoke([HumanMessage(content=prompt)])
                            content = response.content if hasattr(response, 'content') else str(response)
                            brand_json = self._parse_llm_response(content)
                            print("✓ Brand identity extracted with alternative LLM")
                        except Exception as e2:
                            print(f"Alternative LLM also failed: {e2}")
                            brand_json = self._fallback_extraction(context)
                    else:
                        brand_json = self._fallback_extraction(context)
                else:
                    print(f"LLM error: {e}, using enhanced fallback")
                    brand_json = self._fallback_extraction(context)
        else:
            # Use enhanced fallback extraction
            print("LLM not available, using rule-based extraction...")
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
   - Background: The actual website background color (usually white, black, or a brand color)
   - Primary: Most prominent brand/accent color (often used in logos, CTAs, headers)
   - Secondary: Supporting brand color (complementary to primary)
   - Support colors: Additional brand colors found in the design
   - Positive: Color used for positive actions/CTAs (often green, blue, or accent color)
   - Text: The main text color (usually black or dark gray on light backgrounds, white on dark)
   
   IMPORTANT: Only fill colors that are actually found. If a color isn't present, leave it empty.
   Focus on extracting the actual background, text, and 1-3 main brand colors from the website.

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
        
        # Extract colors and assign them meaningfully
        colors = context.get('colors', [])
        color_palette = ColorPalette()
        
        if colors:
            # Separate colors by source/type
            background_colors = [c for c in colors if 'background' in c.get('name', '').lower() or c.get('source') == 'body_background']
            text_colors = [c for c in colors if 'text' in c.get('name', '').lower() or c.get('source') == 'text']
            brand_colors = [c for c in colors if c.get('source') != 'body_background' and 'background' not in c.get('name', '').lower()]
            
            # Assign background color (most important)
            if background_colors:
                bg = background_colors[0]
                color_palette.background = ColorInfo(name=bg.get('name', 'background'), hex=bg.get('hex', ''))
            elif len(colors) > 0:
                # Use first color as background if no explicit background found
                color_palette.background = ColorInfo(name=colors[0].get('name', 'background'), hex=colors[0].get('hex', ''))
            
            # Assign primary brand color (usually the most prominent non-background color)
            if brand_colors:
                color_palette.primary = ColorInfo(name=brand_colors[0].get('name', 'primary'), hex=brand_colors[0].get('hex', ''))
                if len(brand_colors) > 1:
                    color_palette.secondary = ColorInfo(name=brand_colors[1].get('name', 'secondary'), hex=brand_colors[1].get('hex', ''))
            elif len(colors) > 1:
                color_palette.primary = ColorInfo(name=colors[1].get('name', 'primary'), hex=colors[1].get('hex', ''))
            
            # Assign remaining colors
            remaining = [c for c in colors if c not in background_colors[:1] and c not in brand_colors[:2]]
            if len(remaining) > 0:
                color_palette.secondary = ColorInfo(name=remaining[0].get('name', 'secondary'), hex=remaining[0].get('hex', ''))
            if len(remaining) > 1:
                color_palette.support_1 = ColorInfo(name=remaining[1].get('name', 'support'), hex=remaining[1].get('hex', ''))
            if len(remaining) > 2:
                color_palette.support_2 = ColorInfo(name=remaining[2].get('name', 'support'), hex=remaining[2].get('hex', ''))
            if len(remaining) > 3:
                color_palette.support_3 = ColorInfo(name=remaining[3].get('name', 'support'), hex=remaining[3].get('hex', ''))
            
            # Positive color (usually a bright/CTA color, often green or blue)
            positive_candidates = [c for c in colors if any(word in c.get('name', '').lower() for word in ['green', 'blue', 'positive', 'cta', 'accent'])]
            if positive_candidates:
                color_palette.positive = ColorInfo(name=positive_candidates[0].get('name', 'positive'), hex=positive_candidates[0].get('hex', ''))
            elif len(colors) > 2:
                color_palette.positive = ColorInfo(name=colors[2].get('name', 'positive'), hex=colors[2].get('hex', ''))
        
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

