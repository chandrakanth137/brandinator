"""Brand Extraction Agent using LangChain."""
import json
import os
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from backend.agents.tools import (
    WebScraper,
    GoogleSearchTool,
    ColorPaletteExtractor,
    TypographyExtractor,
    VisionStyleAnalyzer
)
from backend.app.models import (
    BrandIdentity, BrandPersonality, VisualIdentity, DesignStyle, 
    ColorPalette, ColorInfo, ImageGenerationGuidelines, TechnicalSpecs, SourcePage
)


class BrandExtractionAgent:
    """LangChain-based agent for extracting brand identity from websites."""
    
    def __init__(self):
        self.web_scraper = WebScraper()
        self.search_tool = GoogleSearchTool()
        self.color_extractor = ColorPaletteExtractor()
        self.typography_extractor = TypographyExtractor()
        self.vision_analyzer = VisionStyleAnalyzer()
        
        self.llm = self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize LLM with Google Gemini."""
        if GOOGLE_AVAILABLE:
            api_key = os.getenv('GEMINI_ANALYSIS_API_KEY', '') or os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_API_KEY', '')
            if api_key:
                try:
                    llm = ChatGoogleGenerativeAI(
                        model="gemini-2.5-flash",
                        temperature=0.7,
                        google_api_key=api_key
                    )
                    print("✓ Google Gemini LLM (gemini-2.5-flash) initialized successfully")
                    return llm
                except Exception as e:
                    print(f"⚠ Google Gemini LLM failed: {e}")
        
        print("⚠ No LLM available - using enhanced rule-based extraction")
        print("  Set GEMINI_ANALYSIS_API_KEY for Google Gemini")
        return None
    
    def _initialize_llm_with_skip(self, skip_llm=None):
        """Initialize LLM skipping the one that failed."""
        if GOOGLE_AVAILABLE:
            api_key = os.getenv('GEMINI_ANALYSIS_API_KEY', '') or os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_API_KEY', '')
            if api_key:
                try:
                    llm = ChatGoogleGenerativeAI(
                        model="gemini-2.5-flash",
                        temperature=0.7,
                        google_api_key=api_key
                    )
                    print("✓ Switched to Google Gemini LLM (gemini-2.5-flash)")
                    return llm
                except Exception as e:
                    print(f"⚠ Google Gemini LLM fallback failed: {e}")
        return None
    
    def extract(self, url: str) -> BrandIdentity:
        """Extract brand identity from a website URL by crawling multiple pages."""
        
        # Step 1: Crawl multiple pages from the website
        print(f"\n{'='*60}")
        print(f"🌐 STARTING BRAND EXTRACTION")
        print(f"{'='*60}")
        all_pages = self.web_scraper.crawl_website(url, max_pages=5)
        
        if not all_pages:
            print("⚠ No pages could be scraped. Using fallback extraction.")
            return self._fallback_extraction({})
        
        # Aggregate data from all pages
        aggregated_data = {
            'pages': all_pages,
            'combined_text': '',
            'combined_titles': [],
            'combined_descriptions': [],
            'all_images': [],
            'all_html': ''
        }
        
        for page in all_pages:
            aggregated_data['combined_text'] += '\n\n' + page.get('text', '')
            aggregated_data['combined_titles'].append(page.get('title', ''))
            aggregated_data['combined_descriptions'].append(page.get('description', ''))
            aggregated_data['all_images'].extend(page.get('images', []))
            aggregated_data['all_html'] += '\n' + page.get('html', '')
        
        # Use homepage as primary data source
        homepage = all_pages[0] if all_pages else {}
        
        # Step 2: Extract color palette and typography from all pages
        print("\n" + "="*60)
        print("🎨 EXTRACTING COLOR PALETTE & TYPOGRAPHY")
        print("="*60)
        colors = []
        fonts_info = {}
        
        # Extract colors and fonts from all pages' HTML
        for page in all_pages:
            html_content = page.get('html', '')
            if html_content:
                try:
                    # Extract colors with computed colors from Playwright
                    computed_colors = {
                        'background_color': page.get('background_color'),
                        'text_color': page.get('text_color'),
                        'key_colors': page.get('key_colors')
                    }
                    css_colors = self.color_extractor.extract_from_css(
                        html_content, 
                        computed_colors=computed_colors if any(computed_colors.values()) else None
                    )
                    if css_colors:
                        colors.extend(css_colors)
                    
                    # Extract fonts
                    computed_fonts = page.get('fonts')
                    page_fonts = self.typography_extractor.extract_fonts(
                        html_content,
                        computed_fonts=computed_fonts
                    )
                    if page_fonts.get('primary_font'):
                        if 'primary_font' not in fonts_info or not fonts_info['primary_font']:
                            fonts_info['primary_font'] = page_fonts['primary_font']
                        if page_fonts.get('secondary_font') and 'secondary_font' not in fonts_info:
                            fonts_info['secondary_font'] = page_fonts['secondary_font']
                        if 'font_families' not in fonts_info:
                            fonts_info['font_families'] = []
                        fonts_info['font_families'].extend(page_fonts.get('font_families', []))
                except Exception as e:
                    print(f"  Error extracting from {page.get('url', 'unknown')}: {e}")
        
        # Deduplicate colors
        seen_hex = set()
        unique_colors = []
        for color in colors:
            hex_upper = color.get('hex', '').upper()
            if hex_upper and hex_upper not in seen_hex:
                seen_hex.add(hex_upper)
                unique_colors.append(color)
        colors = unique_colors[:20]  # Keep top 20 unique colors
        
        # Deduplicate fonts
        if 'font_families' in fonts_info:
            fonts_info['font_families'] = list(dict.fromkeys(fonts_info['font_families']))[:5]
        
        print(f"✓ Extracted {len(colors)} unique colors across all pages")
        if fonts_info.get('primary_font'):
            print(f"✓ Extracted fonts: Primary={fonts_info.get('primary_font')}, Secondary={fonts_info.get('secondary_font', 'N/A')}")
        
        # Step 3: Analyze visual style from images
        print("\n📸 Analyzing visual style from images...")
        all_image_urls = [img['url'] for page in all_pages for img in page.get('images', [])[:3]]
        style_analysis = self.vision_analyzer.analyze(all_image_urls[:10])
        
        # Step 4: Search for additional brand information
        print("\n🔍 Searching for additional brand info...")
        brand_name = homepage.get('title', '').split('|')[0].split('-')[0].strip()
        if brand_name:
            search_results = self.search_tool.search(f"{brand_name} brand mission vision values")
        else:
            search_results = []
        
        # Step 5: Use LLM to generate comprehensive brand identity
        print("\n" + "="*60)
        print("🤖 ANALYZING WITH LLM")
        print("="*60)
        brand_identity = self._generate_brand_identity(
            all_pages=all_pages,
            aggregated_data=aggregated_data,
            search_results=search_results,
            colors=colors,
            fonts_info=fonts_info,
            style_analysis=style_analysis
        )
        
        # Add source pages metadata
        source_pages = [
            SourcePage(url=page.get('url', ''), page_type=page.get('page_type', 'other'))
            for page in all_pages
        ]
        brand_identity.source_pages = source_pages
        
        # Log final extracted brand identity
        print("\n" + "="*60)
        print("📊 FINAL BRAND IDENTITY EXTRACTED")
        print("="*60)
        print(f"Brand Name: {brand_identity.brand_core.brand_name}")
        print(f"Industry: {brand_identity.brand_core.industry}")
        print(f"Personality Traits: {', '.join(brand_identity.brand_core.brand_personality.traits)}")
        print(f"\nColor Palette:")
        cp = brand_identity.visual_identity.color_palette
        if cp.primary:
            print(f"  Primary: {cp.primary.hex} ({cp.primary.name})")
        if cp.secondary:
            print(f"  Secondary: {cp.secondary.hex} ({cp.secondary.name})")
        if cp.accent:
            print(f"  Accent: {cp.accent.hex} ({cp.accent.name})")
        print(f"\nSource Pages: {len(brand_identity.source_pages)} pages crawled")
        print("="*60 + "\n")
        
        return brand_identity
    
    def _generate_brand_identity(
        self,
        all_pages: List[Dict[str, Any]],
        aggregated_data: Dict[str, Any],
        search_results: List[Dict[str, str]],
        colors: List[Dict[str, str]],
        fonts_info: Dict[str, Any],
        style_analysis: Dict[str, Any]
    ) -> BrandIdentity:
        """Generate comprehensive Brand Identity JSON using LLM reasoning from multiple pages."""
        
        # Prepare context for LLM from all pages
        homepage = all_pages[0] if all_pages else {}
        
        # Combine text from all pages (limit to 5000 chars for LLM)
        combined_text = aggregated_data.get('combined_text', '')[:5000]
        
        # Create page summaries
        page_summaries = []
        for page in all_pages:
            page_summaries.append({
                'url': page.get('url', ''),
                'type': page.get('page_type', 'other'),
                'title': page.get('title', ''),
                'text_preview': page.get('text', '')[:300]
            })
        
        context = {
            'homepage_title': homepage.get('title', ''),
            'homepage_description': homepage.get('description', ''),
            'combined_text': combined_text,
            'page_summaries': page_summaries,
            'search_results': search_results[:3],
            'colors': colors[:15],
            'fonts': fonts_info if fonts_info else {},
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
        """Create comprehensive prompt for brand extraction matching new schema."""
        from backend.agents.prompt_template import COMPREHENSIVE_EXTRACTION_PROMPT
        
        # Format page summaries
        page_summaries_str = "\n".join([
            f"  - {p['type']}: {p['url']} - {p['title'][:50]}"
            for p in context.get('page_summaries', [])
        ])
        
        return COMPREHENSIVE_EXTRACTION_PROMPT.format(
            homepage_title=context.get('homepage_title', ''),
            homepage_description=context.get('homepage_description', ''),
            combined_text=context.get('combined_text', '')[:3000],  # Limit for LLM
            page_summaries=page_summaries_str,
            search_results=json.dumps(context.get('search_results', []), indent=2),
            colors=json.dumps(context.get('colors', []), indent=2),
            fonts=json.dumps(context.get('fonts', {}), indent=2),
            style_analysis=json.dumps(context.get('style_analysis', {}), indent=2)
        )

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
            
            # Fix None values and invalid types in the response
            # Fix typography fields
            if 'visual_identity' in data and 'typography' in data['visual_identity']:
                typo = data['visual_identity']['typography']
                if typo.get('primary_font') is None:
                    typo['primary_font'] = ""
                if typo.get('secondary_font') is None:
                    typo['secondary_font'] = ""
                if typo.get('font_personality') is None:
                    typo['font_personality'] = []
                if typo.get('hierarchy_style') is None:
                    typo['hierarchy_style'] = ""
            
            # Normalize string fields (convert None to empty string, keep any string value)
            # This allows the LLM to provide descriptive values beyond strict literals
            if 'visual_identity' in data and 'imagery_style' in data['visual_identity']:
                istyle = data['visual_identity']['imagery_style']
                for field in ['primary_type', 'photo_style', 'lighting', 'composition', 'color_treatment']:
                    if field in istyle and istyle[field] is None:
                        istyle[field] = ""
            
            if 'image_generation_guidelines' in data:
                ig = data['image_generation_guidelines']
                
                # Normalize people_representation fields
                if 'people_representation' in ig:
                    pr = ig['people_representation']
                    for field in ['diversity_level', 'authenticity_level']:
                        if field in pr and pr[field] is None:
                            pr[field] = ""
                
                # Normalize other fields
                if 'props_and_objects' in ig and 'technology_presence' in ig['props_and_objects']:
                    if ig['props_and_objects']['technology_presence'] is None:
                        ig['props_and_objects']['technology_presence'] = ""
                
                if 'mood_and_emotion' in ig and 'energy_level' in ig['mood_and_emotion']:
                    if ig['mood_and_emotion']['energy_level'] is None:
                        ig['mood_and_emotion']['energy_level'] = ""
                
                if 'technical_specs' in ig and 'color_temperature' in ig['technical_specs']:
                    if ig['technical_specs']['color_temperature'] is None:
                        ig['technical_specs']['color_temperature'] = ""
            
            # Normalize brand_voice formality_level
            if 'brand_voice' in data and 'formality_level' in data['brand_voice']:
                if data['brand_voice']['formality_level'] is None:
                    data['brand_voice']['formality_level'] = ""
            
            # Ensure color palette fields are properly formatted (handle None values)
            if 'visual_identity' in data and 'color_palette' in data['visual_identity']:
                color_palette = data['visual_identity']['color_palette']
                # Convert None/invalid values - keep them as None (optional fields)
                for key in ['primary', 'secondary', 'accent']:
                    if key in color_palette:
                        if color_palette[key] is None:
                            continue
                        elif not isinstance(color_palette[key], dict):
                            color_palette[key] = None
                        elif not color_palette[key].get('hex'):
                            color_palette[key] = None
            
            return BrandIdentity(**data)
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            # Try to fix common issues and retry
            try:
                # If it's a validation error, try to fix the data structure
                if 'color_palette' in str(e) and 'data' in locals():
                    # Ensure all color fields exist
                    if 'image_style' in data and 'color_palette' in data['image_style']:
                        cp = data['image_style']['color_palette']
                        for key in ['primary', 'secondary', 'support_1', 'support_2', 'support_3', 'positive', 'background']:
                            if key not in cp or cp[key] is None:
                                cp[key] = {"name": "", "hex": ""}
                    return BrandIdentity(**data)
            except:
                pass
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
        
        # Create brand identity with new schema
        brand_identity = BrandIdentity(
            brand_core=BrandCore(
                brand_name=brand_name,
                brand_mission=mission or "Mission statement not found",
                brand_vision=vision or "Vision statement not found",
                brand_personality=BrandPersonality(
                    traits=personality[:5]  # Limit to 5 traits
                )
            ),
            visual_identity=VisualIdentity(
                design_style=DesignStyle(
                    overall_aesthetic=context.get('style_analysis', {}).get('style', 'modern'),
                    keywords=["brand", "professional", "modern"]
                ),
                color_palette=color_palette
            ),
            image_generation_guidelines=ImageGenerationGuidelines(
                technical_specs=TechnicalSpecs(
                    color_temperature="warm"
                )
            )
        )
        
        return brand_identity

