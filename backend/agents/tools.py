"""Tools for brand extraction agent."""
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from PIL import Image
from colorthief import ColorThief
import io
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import Playwright (both sync and async)
try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not available, falling back to BeautifulSoup only")


class WebScraper:
    """Web scraper using Playwright with BeautifulSoup fallback."""
    
    def __init__(self):
        self.use_playwright = PLAYWRIGHT_AVAILABLE
        self.playwright = None
        self.browser = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        if self.use_playwright:
            try:
                # Initialize Playwright in a thread to avoid asyncio conflicts
                print("Initializing Playwright...")
                future = self.executor.submit(self._init_playwright)
                future.result(timeout=15)
                print("✓ Playwright initialized successfully")
            except Exception as e:
                error_msg = str(e)
                print(f"✗ Failed to initialize Playwright: {error_msg}")
                if "Executable doesn't exist" in error_msg or "browser" in error_msg.lower():
                    print("  → Install Playwright browsers with: uv run playwright install chromium")
                print("  → Falling back to BeautifulSoup (may not work with JS-heavy sites)")
                self.use_playwright = False
    
    def _init_playwright(self):
        """Initialize Playwright (called in thread pool)."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
    
    def __del__(self):
        """Cleanup Playwright resources."""
        if self.browser:
            try:
                self.browser.close()
            except:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except:
                pass
    
    def _is_protection_page(self, title: str, text: str) -> bool:
        """Detect if we hit a protection/anti-bot page."""
        protection_indicators = [
            'just a moment',
            'checking your browser',
            'please wait',
            'cloudflare',
            'ddos protection',
            'access denied',
            'challenge',
            'security check'
        ]
        title_lower = title.lower()
        text_lower = text.lower()[:500]  # Check first 500 chars
        
        for indicator in protection_indicators:
            if indicator in title_lower or indicator in text_lower:
                return True
        return False
    
    def scrape(self, url: str) -> Dict[str, Any]:
        """Scrape a website and extract text content, images, and metadata."""
        # Always try Playwright first if available (handles JS and protection pages)
        if self.use_playwright:
            try:
                print(f"Attempting to scrape with Playwright: {url}")
                # Run Playwright in thread pool to avoid asyncio conflicts
                loop = None
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    pass
                
                if loop and loop.is_running():
                    # We're in an async context, use thread pool
                    future = self.executor.submit(self._scrape_with_playwright, url)
                    result = future.result(timeout=60)
                else:
                    # Not in async context, run directly
                    result = self._scrape_with_playwright(url)
                
                # Check if we got a protection page
                if self._is_protection_page(result.get('title', ''), result.get('text', '')):
                    print("Detected protection page, waiting longer and retrying with Playwright...")
                    # Retry with longer wait
                    if loop and loop.is_running():
                        future = self.executor.submit(self._scrape_with_playwright, url, wait_time=10000)
                        result = future.result(timeout=90)
                    else:
                        result = self._scrape_with_playwright(url, wait_time=10000)
                
                return result
            except Exception as e:
                print(f"Playwright scraping failed: {e}, falling back to BeautifulSoup")
                # Try BeautifulSoup as fallback
                result = self._scrape_with_bs4(url)
                # If we detect protection page, warn user
                if self._is_protection_page(result.get('title', ''), result.get('text', '')):
                    print("WARNING: Detected protection page. Playwright is needed to bypass it.")
                    print("Please ensure Playwright browsers are installed: uv run playwright install chromium")
                return result
        else:
            # No Playwright available, use BeautifulSoup
            print(f"Playwright not available, using BeautifulSoup: {url}")
            result = self._scrape_with_bs4(url)
            # Check for protection page
            if self._is_protection_page(result.get('title', ''), result.get('text', '')):
                print("WARNING: Detected protection page (e.g., Cloudflare).")
                print("Install Playwright to bypass: uv run playwright install chromium")
            return result
    
    def _scrape_with_playwright(self, url: str, wait_time: int = 3000) -> Dict[str, Any]:
        """Scrape using Playwright (handles JavaScript-rendered content)."""
        page = self.browser.new_page()
        try:
            # Set realistic viewport and user agent
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.set_extra_http_headers({
                'Accept-Language': 'en-US,en;q=0.9',
            })
            
            # Navigate to the page
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for dynamic content and potential protection pages
            page.wait_for_timeout(wait_time)
            
            # Check if we're on a protection page and wait for it to resolve
            page_title = page.title()
            if 'just a moment' in page_title.lower() or 'checking' in page_title.lower():
                print("Waiting for protection page to resolve...")
                # Wait up to 15 seconds for protection page to resolve
                try:
                    page.wait_for_function(
                        "document.title.toLowerCase().indexOf('just a moment') === -1 && document.title.toLowerCase().indexOf('checking') === -1",
                        timeout=15000
                    )
                    page.wait_for_timeout(2000)  # Additional wait after resolution
                except:
                    print("Protection page may not have resolved, continuing anyway...")
            
            # Get page content
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            title = page.title()
            title_text = title.strip() if title else ""
            
            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if not meta_desc:
                meta_desc = soup.find('meta', attrs={'property': 'og:description'})
            description = meta_desc.get('content', '') if meta_desc else ""
            
            # Extract text content
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Extract images
            images = []
            img_elements = page.query_selector_all('img')
            for img in img_elements[:20]:
                try:
                    src = img.get_attribute('src') or img.get_attribute('data-src')
                    alt = img.get_attribute('alt') or ''
                    if src:
                        if not src.startswith('http'):
                            src = urljoin(url, src)
                        images.append({'url': src, 'alt': alt})
                except:
                    continue
            
            # Extract links
            links = []
            link_elements = page.query_selector_all('a[href]')
            for link in link_elements[:50]:
                try:
                    href = link.get_attribute('href')
                    if href:
                        if not href.startswith('http'):
                            href = urljoin(url, href)
                        if urlparse(href).netloc == urlparse(url).netloc:
                            links.append(href)
                except:
                    continue
            
            return {
                'url': url,
                'title': title_text,
                'description': description,
                'text': text[:5000],
                'images': images[:20],
                'links': list(set(links))[:10]
            }
        finally:
            page.close()
    
    def _scrape_with_bs4(self, url: str) -> Dict[str, Any]:
        """Scrape using BeautifulSoup (fallback for static content)."""
        try:
            # Increase timeout and add better headers
            response = self.session.get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title - try multiple methods
            title_text = ""
            title = soup.find('title')
            if title:
                title_text = title.get_text().strip()
            else:
                # Try og:title or other meta tags
                og_title = soup.find('meta', attrs={'property': 'og:title'})
                if og_title:
                    title_text = og_title.get('content', '').strip()
                else:
                    # Try h1 as fallback
                    h1 = soup.find('h1')
                    if h1:
                        title_text = h1.get_text().strip()
            
            # Extract meta description - try multiple methods
            description = ""
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                description = meta_desc.get('content', '').strip()
            else:
                meta_desc = soup.find('meta', attrs={'property': 'og:description'})
                if meta_desc:
                    description = meta_desc.get('content', '').strip()
            
            # Extract text content - prioritize main content areas
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Try to find main content area
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile('content|main|body', re.I))
            if main_content:
                text = main_content.get_text()
            else:
                text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk and len(chunk) > 1)
            
            # Extract images - try multiple attributes
            images = []
            for img in soup.find_all('img'):
                img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-original')
                if img_url:
                    # Skip data URIs and very small images
                    if img_url.startswith('data:'):
                        continue
                    if not img_url.startswith('http'):
                        img_url = urljoin(url, img_url)
                    # Filter out tracking pixels and icons
                    if any(skip in img_url.lower() for skip in ['pixel', 'tracking', 'icon', 'logo']):
                        continue
                    images.append({
                        'url': img_url,
                        'alt': img.get('alt', '')
                    })
            
            # Extract links
            links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if not href.startswith('http'):
                    href = urljoin(url, href)
                if urlparse(href).netloc == urlparse(url).netloc:
                    links.append(href)
            
            return {
                'url': url,
                'title': title_text,
                'description': description,
                'text': text[:5000],
                'images': images[:20],
                'links': list(set(links))[:10]
            }
        except Exception as e:
            print(f"BeautifulSoup scraping error: {e}")
            return {
                'url': url,
                'error': str(e),
                'text': '',
                'images': [],
                'links': []
            }


class GoogleSearchTool:
    """Google Search tool using Playwright (no API key needed)."""
    
    def __init__(self):
        self.use_playwright = PLAYWRIGHT_AVAILABLE
        self.playwright = None
        self.browser = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        
        if self.use_playwright:
            try:
                # Initialize Playwright in a thread to avoid asyncio conflicts
                future = self.executor.submit(self._init_playwright)
                future.result(timeout=10)
                print("GoogleSearchTool: Playwright initialized")
            except Exception as e:
                print(f"GoogleSearchTool: Failed to initialize Playwright: {e}")
                self.use_playwright = False
    
    def _init_playwright(self):
        """Initialize Playwright (called in thread pool)."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
    
    def __del__(self):
        """Cleanup Playwright resources."""
        if self.browser:
            try:
                self.browser.close()
            except:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except:
                pass
    
    def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """Search Google using Playwright and return results."""
        if not self.use_playwright:
            # Fallback to mock results if Playwright not available
            return [
                {
                    'title': f'Search result for: {query}',
                    'snippet': f'Playwright not available. Install with: playwright install chromium',
                    'link': 'https://example.com'
                }
            ]
        
        try:
            # Run Playwright in thread pool to avoid asyncio conflicts
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                pass
            
            if loop and loop.is_running():
                # We're in an async context, use thread pool
                future = self.executor.submit(self._search_with_playwright, query, num_results)
                return future.result(timeout=60)
            else:
                # Not in async context, run directly
                return self._search_with_playwright(query, num_results)
        except Exception as e:
            print(f"Google search failed: {e}")
            # Return mock results on error
            return [
                {
                    'title': f'Search result for: {query}',
                    'snippet': f'Search failed: {str(e)}',
                    'link': 'https://example.com'
                }
            ]
    
    def _search_with_playwright(self, query: str, num_results: int) -> List[Dict[str, str]]:
        """Perform Google search using Playwright."""
        page = self.browser.new_page()
        results = []
        
        try:
            # Navigate to Google Search
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            page.goto(search_url, wait_until='networkidle', timeout=30000)
            
            # Wait for search results to load
            page.wait_for_timeout(2000)
            
            # Try to handle cookie consent if present
            try:
                accept_button = page.query_selector('button:has-text("Accept"), button:has-text("I agree"), #L2AGLb')
                if accept_button:
                    accept_button.click()
                    page.wait_for_timeout(1000)
            except:
                pass
            
            # Extract search results
            # Google search results are in divs with class 'g' or 'tF2Cxc'
            result_selectors = [
                'div.g',
                'div.tF2Cxc',
                'div[data-ved]'
            ]
            
            result_elements = []
            for selector in result_selectors:
                elements = page.query_selector_all(selector)
                if elements:
                    result_elements = elements[:num_results]
                    break
            
            for element in result_elements:
                try:
                    # Extract title (usually in h3)
                    title_elem = element.query_selector('h3')
                    title = title_elem.inner_text() if title_elem else ""
                    
                    # Extract link (usually in a tag)
                    link_elem = element.query_selector('a[href]')
                    link = link_elem.get_attribute('href') if link_elem else ""
                    
                    # Extract snippet (usually in span with class 'aCOpRe' or similar)
                    snippet_elem = element.query_selector('span.aCOpRe, span.VwiC3b, div.VwiC3b')
                    snippet = snippet_elem.inner_text() if snippet_elem else ""
                    
                    if title and link:
                        # Clean up Google redirect URLs
                        if link.startswith('/url?q='):
                            from urllib.parse import parse_qs, urlparse
                            parsed = urlparse(link)
                            link = parse_qs(parsed.query).get('q', [link])[0]
                        
                        results.append({
                            'title': title,
                            'snippet': snippet,
                            'link': link
                        })
                        
                        if len(results) >= num_results:
                            break
                except Exception as e:
                    continue
            
            # If we didn't get enough results, try alternative selectors
            if len(results) < num_results:
                # Try getting all links from the page
                all_links = page.query_selector_all('a[href]')
                for link_elem in all_links:
                    if len(results) >= num_results:
                        break
                    try:
                        href = link_elem.get_attribute('href')
                        if href and ('http' in href) and ('google.com' not in href):
                            title = link_elem.inner_text().strip()
                            if title and title not in [r['title'] for r in results]:
                                results.append({
                                    'title': title,
                                    'snippet': '',
                                    'link': href
                                })
                    except:
                        continue
            
            return results[:num_results]
            
        finally:
            page.close()


class ColorPaletteExtractor:
    """Extract color palette from images."""
    
    def extract_from_url(self, image_url: str, num_colors: int = 7) -> List[Dict[str, str]]:
        """Extract color palette from an image URL."""
        try:
            response = requests.get(image_url, timeout=10, stream=True)
            response.raise_for_status()
            
            # Download image to memory
            image_data = io.BytesIO(response.content)
            color_thief = ColorThief(image_data)
            
            # Get dominant color palette
            palette = color_thief.get_palette(color_count=num_colors, quality=1)
            
            colors = []
            for rgb in palette:
                hex_color = '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])
                # Simple color name mapping (can be enhanced)
                color_name = self._rgb_to_name(rgb)
                colors.append({
                    'name': color_name,
                    'hex': hex_color,
                    'rgb': rgb
                })
            
            return colors
        except Exception as e:
            # Return default colors on error
            return [
                {'name': 'default', 'hex': '#000000', 'rgb': (0, 0, 0)}
            ]
    
    def _rgb_to_name(self, rgb: tuple) -> str:
        """Convert RGB to approximate color name."""
        r, g, b = rgb
        
        # Simple color classification
        if r > 200 and g > 200 and b > 200:
            return 'white'
        elif r < 50 and g < 50 and b < 50:
            return 'black'
        elif r > g and r > b:
            if r > 200:
                return 'red'
            else:
                return 'dark red'
        elif g > r and g > b:
            if g > 200:
                return 'green'
            else:
                return 'dark green'
        elif b > r and b > g:
            if b > 200:
                return 'blue'
            else:
                return 'dark blue'
        elif r > 150 and g > 150:
            return 'yellow'
        elif r > 150 and b > 150:
            return 'magenta'
        elif g > 150 and b > 150:
            return 'cyan'
        else:
            return 'gray'


class VisionStyleAnalyzer:
    """Analyze visual style from images (placeholder implementation)."""
    
    def analyze(self, image_urls: List[str]) -> Dict[str, Any]:
        """Analyze visual style from a list of images."""
        # Placeholder implementation
        # In production, this would use a vision model (e.g., GPT-4 Vision, Claude Vision)
        
        style_analysis = {
            'style': 'modern',
            'mood': 'professional',
            'composition': 'balanced',
            'lighting': 'natural',
            'color_scheme': 'vibrant'
        }
        
        # Could integrate with OpenAI Vision API or similar here
        # For now, return placeholder analysis
        
        return style_analysis

