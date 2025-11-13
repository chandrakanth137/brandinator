"""Tools for brand extraction agent."""
import re
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from colorthief import ColorThief
import io
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
                future = self.executor.submit(self._init_playwright)
                future.result(timeout=15)
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
        """Scrape a single page and extract text content, images, and metadata."""
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
                    # Retry with much longer wait (15 seconds initial + 20 seconds for resolution)
                    if loop and loop.is_running():
                        future = self.executor.submit(self._scrape_with_playwright, url, wait_time=15000)
                        result = future.result(timeout=120)  # 2 minute timeout
                    else:
                        result = self._scrape_with_playwright(url, wait_time=15000)
                
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
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing fragments and trailing slashes."""
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        # Remove fragment and normalize path
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip('/') or '/',
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        return normalized
    
    def _is_same_domain(self, url: str, base_domain: str) -> bool:
        """Check if URL belongs to the same domain."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base_parsed = urlparse(base_domain)
        return parsed.netloc == base_parsed.netloc or parsed.netloc == ''
    
    def _fetch_sitemap_urls(self, base_url: str) -> List[str]:
        """Try to fetch URLs from sitemap.xml files."""
        from urllib.parse import urljoin
        from bs4 import BeautifulSoup
        
        sitemap_urls = [
            urljoin(base_url, '/sitemap.xml'),
            urljoin(base_url, '/sitemap_index.xml'),
            urljoin(base_url, '/sitemap1.xml'),
        ]
        
        found_urls = []
        
        for sitemap_url in sitemap_urls:
            try:
                response = self.session.get(sitemap_url, timeout=10)
                if response.status_code == 200:
                    # Try parsing as XML
                    soup = BeautifulSoup(response.content, 'xml')
                    locs = soup.find_all('loc')
                    
                    if locs:
                        urls = [loc.text.strip() for loc in locs if loc.text]
                        found_urls.extend(urls)
                        print(f"  ✓ Found {len(urls)} URLs in {sitemap_url}")
                        break
            except Exception as e:
                continue
        
        return found_urls
    
    def _extract_links_from_html(self, html: str, current_url: str) -> Set[str]:
        """Extract all internal links from HTML."""
        from urllib.parse import urljoin, urlparse
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue
            
            # Join with current URL
            absolute_url = urljoin(current_url, href)
            normalized = self._normalize_url(absolute_url)
            
            # Only keep same-domain links
            if self._is_same_domain(normalized, current_url):
                links.add(normalized)
        
        return links
    
    def _classify_page_type(self, url: str, title: str = '', text: str = '') -> str:
        """Classify page type based on URL and content."""
        url_lower = url.lower()
        title_lower = title.lower()
        text_lower = text.lower()[:500]  # Check first 500 chars
        
        # Check URL patterns first
        if any(x in url_lower for x in ['/about', '/about-us', '/aboutus', '/company']):
            return 'about'
        elif any(x in url_lower for x in ['/contact', '/contact-us']):
            return 'other'
        elif any(x in url_lower for x in ['/blog', '/blogs', '/news', '/articles', '/posts', '/post']):
            return 'blog'
        elif any(x in url_lower for x in ['/product', '/products', '/shop', '/store', '/service', '/services']):
            return 'products'
        elif url.rstrip('/') == url.rstrip('/').split('?')[0] and not url_lower.endswith(('.html', '.php', '.aspx')):
            # Likely homepage if it's just the base domain
            return 'homepage'
        else:
            return 'other'
    
    def crawl_website(self, base_url: str, max_pages: int = 5, use_sitemap: bool = True) -> List[Dict[str, Any]]:
        """
        Crawl multiple pages from a website using BFS with sitemap support.
        
        Strategy:
        1. Try to fetch sitemap.xml for comprehensive URL list
        2. Scrape homepage to extract links
        3. Use BFS to crawl important pages (about, products, blog)
        4. Prioritize pages by type and content quality
        
        Args:
            base_url: Base website URL
            max_pages: Maximum number of pages to crawl (default: 5)
            use_sitemap: Whether to try using sitemap.xml (default: True)
            
        Returns:
            List of scraped page data, each with 'url' and page content
        """
        from collections import deque
        from urllib.parse import urlparse
        
        print(f"\n{'='*60}")
        print(f"🌐 CRAWLING WEBSITE: {base_url}")
        print(f"{'='*60}")
        
        parsed_base = urlparse(base_url)
        base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
        base_url_normalized = self._normalize_url(base_url)
        
        pages_to_scrape = []
        visited_urls = set()
        to_visit = deque()
        
        # Step 1: Try to fetch sitemap.xml
        sitemap_urls = []
        if use_sitemap:
            print(f"\n📋 Step 1: Checking for sitemap.xml...")
            sitemap_urls = self._fetch_sitemap_urls(base_url)
            if sitemap_urls:
                print(f"  ✓ Found {len(sitemap_urls)} URLs from sitemap")
                # Add sitemap URLs to queue (prioritize important pages)
                for url in sitemap_urls[:max_pages * 2]:  # Get more than needed for filtering
                    normalized = self._normalize_url(url)
                    if self._is_same_domain(normalized, base_url):
                        to_visit.append(normalized)
            else:
                print(f"  ✗ No sitemap found, using link discovery")
        
        # Step 2: Always start with homepage
        if base_url_normalized not in visited_urls:
            to_visit.appendleft(base_url_normalized)  # Prioritize homepage
        
        # Step 3: Add common important pages if not in sitemap
        if not sitemap_urls:
            from urllib.parse import urljoin
            common_paths = [
                '/about', '/about-us', '/aboutus',
                '/products', '/product', '/services', '/service',
                '/blog', '/blogs', '/news', '/articles'
            ]
            for path in common_paths:
                test_url = self._normalize_url(urljoin(base_url, path))
                if test_url not in visited_urls:
                    to_visit.append(test_url)
        
        # Step 4: BFS crawl with smart parallelization
        print(f"\n📄 Step 2: Crawling pages (BFS with smart scraping)...")
        page_type_priority = {'homepage': 0, 'about': 1, 'products': 2, 'blog': 3, 'other': 4}
        pages_by_type = {ptype: [] for ptype in page_type_priority.keys()}
        
        # Strategy: Try parallel BeautifulSoup first (fast), but if we get 403s,
        # fall back to sequential Playwright (slower but bypasses protection)
        use_parallel = True
        max_workers = min(5, max_pages)  # Don't use more threads than pages needed
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def scrape_single_page(url_to_scrape: str) -> tuple:
            """Scrape a single page and return (url, page_data, error).
            
            Creates a separate browser instance per thread since Playwright
            cannot be shared across threads.
            """
            try:
                # For parallel scraping, we need to use BeautifulSoup or create
                # a separate browser instance. Since Playwright doesn't work across
                # threads, we'll use BeautifulSoup for parallel requests.
                # This is faster for static content but won't handle JS-heavy sites.
                from urllib.parse import urlparse
                from bs4 import BeautifulSoup
                
                # Use requests session for parallel scraping
                session = requests.Session()
                session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
                
                response = session.get(url_to_scrape, timeout=15, allow_redirects=True)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract title
                title = soup.find('title')
                title_text = title.get_text().strip() if title else ''
                
                # Extract meta description
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if not meta_desc:
                    meta_desc = soup.find('meta', attrs={'property': 'og:description'})
                description = meta_desc.get('content', '').strip() if meta_desc else ''
                
                # Extract text content
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                
                # Extract images
                images = []
                for img in soup.find_all('img', src=True)[:20]:
                    src = img.get('src') or img.get('data-src')
                    if src:
                        if not src.startswith('http'):
                            src = urljoin(url_to_scrape, src)
                        images.append({'url': src, 'alt': img.get('alt', '')})
                
                # Extract links
                links = []
                for link in soup.find_all('a', href=True)[:50]:
                    href = link.get('href')
                    if href:
                        if not href.startswith('http'):
                            href = urljoin(url_to_scrape, href)
                        parsed = urlparse(href)
                        base_parsed = urlparse(url_to_scrape)
                        if parsed.netloc == base_parsed.netloc or not parsed.netloc:
                            links.append(href)
                
                page_data = {
                    'url': url_to_scrape,
                    'title': title_text,
                    'description': description,
                    'text': text[:5000],
                    'images': images[:20],
                    'links': list(set(links))[:10],
                    'html': str(soup)  # Include HTML for CSS color extraction
                }
                
                return (url_to_scrape, page_data, None)
            except Exception as e:
                return (url_to_scrape, None, str(e))
        
        # Collect URLs to scrape in batches
        urls_to_scrape = []
        while to_visit and len(urls_to_scrape) < max_pages:
            url = to_visit.popleft()
            if url not in visited_urls:
                visited_urls.add(url)
                urls_to_scrape.append(url)
        
        # Scrape pages - try parallel first, fall back to sequential if needed
        if urls_to_scrape:
            if use_parallel:
                print(f"  Scraping {len(urls_to_scrape)} pages with {max_workers} workers (parallel)...")
                failed_count = 0
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all scraping tasks
                    future_to_url = {
                        executor.submit(scrape_single_page, url): url 
                        for url in urls_to_scrape
                    }
                    
                    # Process completed tasks as they finish
                    completed = 0
                    for future in as_completed(future_to_url):
                        url = future_to_url[future]
                        completed += 1
                        
                        try:
                            url_scraped, page_data, error = future.result()
                            
                            if error:
                                if '403' in error or 'Forbidden' in error:
                                    failed_count += 1
                                print(f"  [{completed}/{len(urls_to_scrape)}] ✗ {url_scraped}: {error}")
                                continue
                            
                            if not page_data or not page_data.get('title'):
                                print(f"  [{completed}/{len(urls_to_scrape)}] ✗ {url_scraped}: No data")
                                failed_count += 1
                                continue
                            
                            # Skip protection pages
                            if self._is_protection_page(page_data.get('title', ''), page_data.get('text', '')):
                                print(f"  [{completed}/{len(urls_to_scrape)}] ✗ {url_scraped}: Protection page")
                                failed_count += 1
                                continue
                            
                            # Check content quality
                            text_length = len(page_data.get('text', ''))
                            if text_length < 100:
                                print(f"  [{completed}/{len(urls_to_scrape)}] ✗ {url_scraped}: Too short ({text_length} chars)")
                                failed_count += 1
                                continue
                            
                            # Classify page type
                            page_type = self._classify_page_type(
                                url_scraped,
                                page_data.get('title', ''),
                                page_data.get('text', '')
                            )
                            page_data['page_type'] = page_type
                            
                            print(f"  [{completed}/{len(urls_to_scrape)}] ✓ [{page_type}] {url_scraped} ({text_length} chars)")
                            
                            # Store by type for prioritization
                            pages_by_type[page_type].append(page_data)
                            
                            # Extract links for further crawling (if we need more pages)
                            total_pages = sum(len(pages) for pages in pages_by_type.values())
                            if total_pages < max_pages - 1:
                                html = page_data.get('html', '')
                                if html:
                                    new_links = self._extract_links_from_html(html, url_scraped)
                                    for link in new_links:
                                        if link not in visited_urls and link not in to_visit:
                                            # Prioritize important page types
                                            link_type = self._classify_page_type(link)
                                            if link_type in ['homepage', 'about', 'products', 'blog']:
                                                to_visit.appendleft(link)  # Add to front
                                            else:
                                                to_visit.append(link)  # Add to back
                            
                        except Exception as e:
                            print(f"  [{completed}/{len(urls_to_scrape)}] ✗ {url}: {e}")
                            failed_count += 1
                            continue
                
                # If all parallel requests failed (likely 403s), fall back to sequential Playwright
                total_pages_scraped = sum(len(pages) for pages in pages_by_type.values())
                if total_pages_scraped == 0 and failed_count > 0 and self.use_playwright:
                    print(f"\n  ⚠ All parallel requests failed (likely bot protection).")
                    print(f"  ↳ Falling back to sequential Playwright scraping...")
                    use_parallel = False
                    # Clear visited URLs to retry with Playwright
                    for url in urls_to_scrape:
                        visited_urls.discard(url)
                    urls_to_scrape = urls_to_scrape[:max_pages]  # Reset list
            
            # Sequential Playwright scraping (for sites with bot protection)
            if not use_parallel or sum(len(pages) for pages in pages_by_type.values()) < max_pages:
                print(f"  Scraping {len(urls_to_scrape)} pages sequentially (Playwright)...")
                for idx, url in enumerate(urls_to_scrape, 1):
                    if sum(len(pages) for pages in pages_by_type.values()) >= max_pages:
                        break
                    
                    try:
                        print(f"  [{idx}/{len(urls_to_scrape)}] Scraping: {url}")
                        page_data = self.scrape(url)  # Uses Playwright if available
                        
                        if not page_data or not page_data.get('title'):
                            print(f"    ✗ No data")
                            continue
                        
                        # Skip protection pages
                        if self._is_protection_page(page_data.get('title', ''), page_data.get('text', '')):
                            print(f"    ✗ Protection page")
                            continue
                        
                        # Check content quality
                        text_length = len(page_data.get('text', ''))
                        if text_length < 100:
                            print(f"    ✗ Too short ({text_length} chars)")
                            continue
                        
                        # Classify page type
                        page_type = self._classify_page_type(
                            url,
                            page_data.get('title', ''),
                            page_data.get('text', '')
                        )
                        page_data['page_type'] = page_type
                        
                        print(f"    ✓ [{page_type}] ({text_length} chars)")
                        
                        # Store by type for prioritization
                        pages_by_type[page_type].append(page_data)
                        
                        # Extract links for further crawling
                        total_pages = sum(len(pages) for pages in pages_by_type.values())
                        if total_pages < max_pages - 1:
                            html = page_data.get('html', '')
                            if html:
                                new_links = self._extract_links_from_html(html, url)
                                for link in new_links:
                                    if link not in visited_urls and link not in to_visit:
                                        link_type = self._classify_page_type(link)
                                        if link_type in ['homepage', 'about', 'products', 'blog']:
                                            to_visit.appendleft(link)
                                        else:
                                            to_visit.append(link)
                        
                    except Exception as e:
                        print(f"    ✗ Error: {e}")
                        continue
        
        # Step 5: Prioritize pages by type (homepage > about > products > blog > other)
        for ptype in ['homepage', 'about', 'products', 'blog', 'other']:
            pages_to_scrape.extend(pages_by_type[ptype][:max_pages])
            if len(pages_to_scrape) >= max_pages:
                break
        
        pages_to_scrape = pages_to_scrape[:max_pages]  # Limit to max_pages
        
        print(f"\n{'='*60}")
        print(f"✓ Crawled {len(pages_to_scrape)} pages:")
        for i, page in enumerate(pages_to_scrape, 1):
            print(f"  {i}. [{page.get('page_type', 'unknown')}] {page.get('url', 'unknown')}")
        print(f"{'='*60}\n")
        
        return pages_to_scrape
    
    def _scrape_with_playwright(self, url: str, wait_time: int = 3000) -> Dict[str, Any]:
        """Scrape using Playwright (handles JavaScript-rendered content)."""
        page = self.browser.new_page()
        try:
            # Set realistic viewport and user agent to appear more human-like
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.set_extra_http_headers({
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })
            
            # Navigate to the page - use 'networkidle' for JS-heavy sites
            # This waits for network connections to be idle (no requests for 500ms)
            try:
                page.goto(url, wait_until='networkidle', timeout=60000)
            except Exception as e:
                # Fallback to 'load' if networkidle times out
                print(f"  Networkidle timeout, trying 'load' strategy: {e}")
                try:
                    page.goto(url, wait_until='load', timeout=60000)
                except:
                    # Last resort: domcontentloaded
                    page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for dynamic content and potential protection pages
            page.wait_for_timeout(wait_time)
            
            # For JS-heavy sites: Scroll to trigger lazy-loaded content
            try:
                # Scroll down slowly to trigger any lazy-loaded content
                page.evaluate("""
                    async () => {
                        const scrollHeight = document.documentElement.scrollHeight;
                        const viewportHeight = window.innerHeight;
                        const scrollStep = viewportHeight * 0.8;
                        let currentPosition = 0;
                        
                        while (currentPosition < scrollHeight) {
                            window.scrollTo(0, currentPosition);
                            await new Promise(resolve => setTimeout(resolve, 300));
                            currentPosition += scrollStep;
                        }
                        // Scroll back to top
                        window.scrollTo(0, 0);
                        await new Promise(resolve => setTimeout(resolve, 500));
                    }
                """)
            except Exception as e:
                print(f"  Scroll failed (non-critical): {e}")
            
            # Wait for content to actually appear (not just DOM ready)
            try:
                page.wait_for_function(
                    """
                    () => {
                        const body = document.body;
                        if (!body) return false;
                        const text = body.innerText || body.textContent || '';
                        // Wait for substantial content (at least 100 chars)
                        return text.length > 100;
                    }
                    """,
                    timeout=10000
                )
            except Exception as e:
                print(f"  Content wait timeout (non-critical): {e}")
            
            # Additional wait for any remaining JS to execute
            page.wait_for_timeout(2000)
            
            # Check if we're on a protection page and wait for it to resolve
            page_title = page.title()
            page_content = page.content()
            
            # More comprehensive protection page detection
            is_protection = (
                'just a moment' in page_title.lower() or 
                'checking' in page_title.lower() or
                'cloudflare' in page_content.lower()[:1000] or
                'cf-browser-verification' in page_content.lower()
            )
            
            if is_protection:
                print("Waiting for protection page to resolve (this may take 10-20 seconds)...")
                # Try multiple strategies to wait for protection to resolve
                max_wait = 20000  # 20 seconds
                start_time = page.evaluate("Date.now()")
                
                try:
                    # Strategy 1: Wait for title to change
                    page.wait_for_function(
                        """
                        () => {
                            const title = document.title.toLowerCase();
                            return title.indexOf('just a moment') === -1 && 
                                   title.indexOf('checking') === -1 &&
                                   title.length > 5;
                        }
                        """,
                        timeout=max_wait
                    )
                    
                    # Strategy 2: Wait for body content to appear (not just Cloudflare)
                    page.wait_for_function(
                        """
                        () => {
                            const body = document.body.innerText.toLowerCase();
                            return body.length > 100 && 
                                   body.indexOf('just a moment') === -1 &&
                                   body.indexOf('checking your browser') === -1;
                        }
                        """,
                        timeout=5000
                    )
                    
                    # Additional wait after resolution
                    page.wait_for_timeout(3000)
                    print("Protection page resolved!")
                except Exception as e:
                    print(f"Protection page wait timeout: {e}")
                    # Try one more time with a simple wait
                    page.wait_for_timeout(5000)
                    # Check again
                    final_title = page.title()
                    if 'just a moment' in final_title.lower() or 'checking' in final_title.lower():
                        print("Warning: Protection page may not have fully resolved")
            
            # Get page content
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract computed styles for background, text colors, and fonts
            try:
                body_element = page.query_selector('body') or page.query_selector('main')
                if body_element:
                    # Extract colors
                    bg_color = page.evaluate("""
                        (element) => {
                            const style = window.getComputedStyle(element);
                            return style.backgroundColor || style.background || '';
                        }
                    """, body_element)
                    text_color = page.evaluate("""
                        (element) => {
                            const style = window.getComputedStyle(element);
                            return style.color || '';
                        }
                    """, body_element)
                    
                    # Extract fonts from body and headings
                    fonts_data = page.evaluate("""
                        () => {
                            const body = document.body;
                            const h1 = document.querySelector('h1');
                            const h2 = document.querySelector('h2');
                            const bodyStyle = window.getComputedStyle(body);
                            const h1Style = h1 ? window.getComputedStyle(h1) : null;
                            const h2Style = h2 ? window.getComputedStyle(h2) : null;
                            
                            return {
                                body_font: bodyStyle.fontFamily || '',
                                h1_font: h1Style ? h1Style.fontFamily : '',
                                h2_font: h2Style ? h2Style.fontFamily : '',
                                body_font_size: bodyStyle.fontSize || '',
                                h1_font_size: h1Style ? h1Style.fontSize : '',
                            };
                        }
                    """)
                    
                    # Extract colors from key elements (buttons, links, headers)
                    key_colors = page.evaluate("""
                        () => {
                            const button = document.querySelector('button, a[class*="btn"], [class*="button"]');
                            const link = document.querySelector('a:not([class*="btn"])');
                            const header = document.querySelector('header, nav');
                            
                            const colors = {};
                            if (button) {
                                const style = window.getComputedStyle(button);
                                colors.button_bg = style.backgroundColor || '';
                                colors.button_color = style.color || '';
                            }
                            if (link) {
                                const style = window.getComputedStyle(link);
                                colors.link_color = style.color || '';
                            }
                            if (header) {
                                const style = window.getComputedStyle(header);
                                colors.header_bg = style.backgroundColor || '';
                            }
                            return colors;
                        }
                    """)
            except:
                bg_color = None
                text_color = None
                fonts_data = None
                key_colors = None
            
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
            
            result = {
                'url': url,
                'title': title_text,
                'description': description,
                'text': text[:5000],
                'images': images[:20],
                'links': list(set(links))[:10],
                'html': html  # Include HTML for CSS color extraction
            }
            
            # Add computed colors if available
            if 'bg_color' in locals() and bg_color:
                result['background_color'] = bg_color
            if 'text_color' in locals() and text_color:
                result['text_color'] = text_color
            
            # Add computed fonts if available
            if 'fonts_data' in locals() and fonts_data:
                result['fonts'] = fonts_data
            
            # Add key element colors if available
            if 'key_colors' in locals() and key_colors:
                result['key_colors'] = key_colors
            
            return result
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
            
            result = {
                'url': url,
                'title': title_text,
                'description': description,
                'text': text[:5000],
                'images': images[:20],
                'links': list(set(links))[:10],
                'html': str(soup)  # Include HTML for CSS color extraction
            }
            
            # Try to extract background color from body element
            try:
                body = soup.find('body') or soup.find('main')
                if body and body.get('style'):
                    bg_match = re.search(r'background[^:]*:\s*([^;]+)', body.get('style', ''))
                    if bg_match:
                        result['background_color'] = bg_match.group(1).strip()
            except:
                pass
            
            return result
        except Exception as e:
            print(f"BeautifulSoup scraping error: {e}")
            return {
                'url': url,
                'error': str(e),
                'text': '',
                'images': [],
                'links': [],
                'html': ''
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


class TypographyExtractor:
    """Extract typography information from websites."""
    
    def extract_fonts(self, html_content: str, computed_fonts: Dict = None, soup: BeautifulSoup = None) -> Dict[str, str]:
        """Extract font families from CSS and computed styles."""
        fonts = {
            'primary_font': '',
            'secondary_font': '',
            'font_families': []
        }
        
        if soup is None:
            soup = BeautifulSoup(html_content, 'html.parser')
        
        # Font family regex pattern
        font_pattern = re.compile(r'font-family\s*:\s*([^;]+)', re.IGNORECASE)
        font_families = set()
        
        # Extract from style tags
        for style_tag in soup.find_all('style'):
            style_content = style_tag.string or ''
            for match in font_pattern.finditer(style_content):
                font_list = match.group(1).strip()
                # Parse font stack (e.g., "Arial, sans-serif" -> "Arial")
                fonts_in_stack = [f.strip().strip('"\'') for f in font_list.split(',')]
                for font in fonts_in_stack[:2]:  # Take first 2 fonts from stack
                    if font and font.lower() not in ['sans-serif', 'serif', 'monospace', 'cursive', 'fantasy']:
                        font_families.add(font)
        
        # Extract from inline styles
        for element in soup.find_all(style=True):
            style = element.get('style', '')
            for match in font_pattern.finditer(style):
                font_list = match.group(1).strip()
                fonts_in_stack = [f.strip().strip('"\'') for f in font_list.split(',')]
                for font in fonts_in_stack[:2]:
                    if font and font.lower() not in ['sans-serif', 'serif', 'monospace', 'cursive', 'fantasy']:
                        font_families.add(font)
        
        # Use computed fonts from Playwright if available (more accurate)
        if computed_fonts:
            if computed_fonts.get('body_font'):
                body_font = computed_fonts['body_font'].split(',')[0].strip().strip('"\'')
                if body_font and body_font.lower() not in ['sans-serif', 'serif', 'monospace']:
                    font_families.add(body_font)
                    fonts['primary_font'] = body_font
            
            if computed_fonts.get('h1_font'):
                h1_font = computed_fonts['h1_font'].split(',')[0].strip().strip('"\'')
                if h1_font and h1_font.lower() not in ['sans-serif', 'serif', 'monospace']:
                    font_families.add(h1_font)
                    if not fonts['primary_font']:
                        fonts['primary_font'] = h1_font
                    elif h1_font != fonts['primary_font']:
                        fonts['secondary_font'] = h1_font
        
        # Convert set to list and assign
        font_list = list(font_families)
        if font_list:
            fonts['primary_font'] = fonts['primary_font'] or font_list[0]
            if len(font_list) > 1:
                fonts['secondary_font'] = font_list[1]
            fonts['font_families'] = font_list[:5]  # Keep top 5
        
        return fonts


class ColorPaletteExtractor:
    """Extract color palette from images and website CSS."""
    
    def extract_from_css(self, html_content: str, computed_colors: Dict = None, soup: BeautifulSoup = None) -> List[Dict[str, str]]:
        """Extract colors from CSS styles in the HTML with focus on BRAND colors."""
        colors = []
        # Improved regex patterns for color extraction
        hex_pattern = re.compile(r'#([0-9a-fA-F]{3,6})\b')
        rgb_pattern = re.compile(r'rgba?\((\d+),\s*(\d+),\s*(\d+)')
        
        if soup is None:
            soup = BeautifulSoup(html_content, 'html.parser')
        
        print("  🎨 Color extraction starting...")
        
        # PRIORITY 1: Extract from BRAND-IDENTIFYING ELEMENTS (buttons, CTAs, headers, logos)
        # These are most likely to contain primary brand colors
        brand_elements = soup.select('button, a[class*="btn"], [class*="button"], [class*="cta"], nav, header, [class*="logo"], h1, h2, [class*="primary"], [class*="brand"]')
        print(f"  Found {len(brand_elements)} brand-identifying elements")
        
        for element in brand_elements[:50]:  # Check first 50 brand elements
            # Inline styles
            if element.get('style'):
                style = element.get('style', '')
                
                # Extract hex colors
                for match in hex_pattern.finditer(style):
                    hex_val = match.group(1)
                    hex_color = f"#{hex_val}"
                    if len(hex_val) == 3:
                        hex_color = f"#{hex_val[0]}{hex_val[0]}{hex_val[1]}{hex_val[1]}{hex_val[2]}{hex_val[2]}"
                    colors.append({
                        'name': self._hex_to_name(hex_color),
                        'hex': hex_color.upper(),
                        'source': 'brand_element',
                        'priority': 1  # High priority
                    })
                
                # Extract RGB colors
                for match in rgb_pattern.finditer(style):
                    r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    hex_color = f"#{r:02x}{g:02x}{b:02x}".upper()
                    colors.append({
                        'name': self._hex_to_name(hex_color),
                        'hex': hex_color,
                        'source': 'brand_element',
                        'priority': 1
                    })
        
        # PRIORITY 2: Extract from ALL style attributes (inline styles)
        for element in soup.find_all(style=True):
            style = element.get('style', '')
            
            # Extract hex colors
            for match in hex_pattern.finditer(style):
                hex_val = match.group(1)
                hex_color = f"#{hex_val}"
                if len(hex_val) == 3:
                    hex_color = f"#{hex_val[0]}{hex_val[0]}{hex_val[1]}{hex_val[1]}{hex_val[2]}{hex_val[2]}"
                colors.append({
                    'name': self._hex_to_name(hex_color),
                    'hex': hex_color.upper(),
                    'source': 'css_inline',
                    'priority': 2
                })
            
            # Extract RGB colors
            for match in rgb_pattern.finditer(style):
                r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
                hex_color = f"#{r:02x}{g:02x}{b:02x}".upper()
                colors.append({
                    'name': self._hex_to_name(hex_color),
                    'hex': hex_color,
                    'source': 'css_inline',
                    'priority': 2
                })
        
        # PRIORITY 3: Extract from style tags (CSS rules)
        for style_tag in soup.find_all('style'):
            style_content = style_tag.string or ''
            
            # Look for important CSS selectors that indicate brand colors
            brand_css_patterns = [
                r':root\s*{([^}]+)}',  # CSS variables
                r'\.primary[^{]*{([^}]+)}',
                r'\.brand[^{]*{([^}]+)}',
                r'\.btn[^{]*{([^}]+)}',
                r'button[^{]*{([^}]+)}',
            ]
            
            for pattern in brand_css_patterns:
                matches = re.finditer(pattern, style_content, re.IGNORECASE)
                for match in matches:
                    css_block = match.group(1) if match.lastindex >= 1 else match.group(0)
                    
                    # Extract hex colors from this CSS block
                    for hex_match in hex_pattern.finditer(css_block):
                        hex_val = hex_match.group(1)
                        hex_color = f"#{hex_val}"
                        if len(hex_val) == 3:
                            hex_color = f"#{hex_val[0]}{hex_val[0]}{hex_val[1]}{hex_val[1]}{hex_val[2]}{hex_val[2]}"
                        colors.append({
                            'name': self._hex_to_name(hex_color),
                            'hex': hex_color.upper(),
                            'source': 'brand_css',
                            'priority': 1
                        })
                    
                    # Extract RGB colors
                    for rgb_match in rgb_pattern.finditer(css_block):
                        r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
                        hex_color = f"#{r:02x}{g:02x}{b:02x}".upper()
                        colors.append({
                            'name': self._hex_to_name(hex_color),
                            'hex': hex_color,
                            'source': 'brand_css',
                            'priority': 1
                        })
            
            # Extract ALL colors from style tags
            for match in hex_pattern.finditer(style_content):
                hex_val = match.group(1)
                hex_color = f"#{hex_val}"
                if len(hex_val) == 3:
                    hex_color = f"#{hex_val[0]}{hex_val[0]}{hex_val[1]}{hex_val[1]}{hex_val[2]}{hex_val[2]}"
                colors.append({
                    'name': self._hex_to_name(hex_color),
                    'hex': hex_color.upper(),
                    'source': 'css_style_tag',
                    'priority': 3
                })
            
            # Extract RGB colors
            for match in rgb_pattern.finditer(style_content):
                r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
                hex_color = f"#{r:02x}{g:02x}{b:02x}".upper()
                colors.append({
                    'name': self._hex_to_name(hex_color),
                    'hex': hex_color,
                    'source': 'css_style_tag',
                    'priority': 3
                })
        
        # Extract background and text colors from body/main elements
        try:
            body = soup.find('body') or soup.find('main') or soup.find('html')
            if body:
                # Check inline styles
                if body.get('style'):
                    bg_match = re.search(r'background[^:]*:\s*([^;]+)', body.get('style', ''))
                    if bg_match:
                        color_val = bg_match.group(1).strip()
                        hex_color = self._parse_color_value(color_val)
                        if hex_color:
                            colors.append({
                                'name': 'background',
                                'hex': hex_color.upper(),
                                'source': 'body_background',
                                'priority': 2
                            })
        except:
            pass
        
        # Add computed colors from Playwright (most accurate)
        if computed_colors:
            # Background color
            if computed_colors.get('background_color'):
                bg_hex = self._parse_color_value(computed_colors['background_color'])
                if bg_hex:
                    colors.append({
                        'name': 'background',
                        'hex': bg_hex.upper(),
                        'source': 'computed_background',
                        'priority': 1  # High priority - actual computed value
                    })
            
            # Button colors (primary brand color)
            if computed_colors.get('key_colors'):
                kc = computed_colors['key_colors']
                if kc.get('button_bg'):
                    btn_hex = self._parse_color_value(kc['button_bg'])
                    if btn_hex and btn_hex.upper() not in ['#FFFFFF', '#000000']:  # Skip pure white/black
                        colors.append({
                            'name': 'primary',
                            'hex': btn_hex.upper(),
                            'source': 'computed_button',
                            'priority': 1  # Very high priority - button color is usually primary
                        })
                
                if kc.get('link_color'):
                    link_hex = self._parse_color_value(kc['link_color'])
                    if link_hex and link_hex.upper() not in ['#000000', '#FFFFFF']:
                        colors.append({
                            'name': 'accent',
                            'hex': link_hex.upper(),
                            'source': 'computed_link',
                            'priority': 1
                        })
        
        # Deduplicate by hex and sort by priority
        seen = set()
        unique_colors = []
        
        # Filter out common non-brand colors (pure white, pure black, very light grays)
        def is_likely_brand_color(hex_color, color_obj):
            hex_clean = hex_color.lstrip('#').upper()
            # Normalize 3-digit hex to 6-digit
            if len(hex_clean) == 3:
                hex_clean = ''.join([c*2 for c in hex_clean])
            
            # Always keep colors from computed styles (Playwright) - these are accurate
            if color_obj.get('source') in ['computed_button', 'computed_link', 'computed_background']:
                return True
            
            # Keep black/white if they're from brand elements (buttons, CTAs, etc.)
            if hex_clean in ['FFFFFF', '000000']:
                # Keep if from brand elements or computed styles
                priority = color_obj.get('priority', 999)
                return priority <= 2  # Brand elements or computed styles
            
            # Skip very light grays (F8F8F8, F9F9F9, etc.) unless from brand elements
            if hex_clean.startswith('F') and len(set(hex_clean)) <= 2:
                # Only keep if it's from a brand element (priority 1) or computed
                priority = color_obj.get('priority', 999)
                return priority == 1  # Only high-priority brand colors
            
            # Keep all other colors (medium grays, colored colors, etc.)
            return True
        
        # Sort by priority (lower = more important)
        colors_sorted = sorted(colors, key=lambda x: x.get('priority', 999))
        
        for color in colors_sorted:
            hex_upper = color['hex'].upper()
            if hex_upper not in seen and is_likely_brand_color(color['hex'], color):
                seen.add(hex_upper)
                unique_colors.append(color)
        
        print(f"  ✓ Extracted {len(unique_colors)} unique colors:")
        for i, c in enumerate(unique_colors[:15]):
            print(f"    {i+1}. {c['hex']} ({c['name']}) from {c['source']}")
        
        return unique_colors[:15]  # Return top 15 unique colors
    
    def _parse_color_value(self, color_val: str) -> Optional[str]:
        """Parse various color formats to hex."""
        color_val = color_val.strip().lower()
        
        # Hex color
        if color_val.startswith('#'):
            if len(color_val) == 4:
                return f"#{color_val[1]}{color_val[1]}{color_val[2]}{color_val[2]}{color_val[3]}{color_val[3]}"
            return color_val[:7]
        
        # RGB/RGBA
        rgb_match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', color_val)
        if rgb_match:
            r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
            return f"#{r:02x}{g:02x}{b:02x}"
        
        # Named colors (basic)
        named_colors = {
            'white': '#ffffff', 'black': '#000000', 'red': '#ff0000',
            'green': '#00ff00', 'blue': '#0000ff', 'gray': '#808080',
            'grey': '#808080'
        }
        if color_val in named_colors:
            return named_colors[color_val]
        
        return None
    
    def _hex_to_name(self, hex_color: str) -> str:
        """Convert hex color to approximate name."""
        if not hex_color or not hex_color.startswith('#'):
            return 'unknown'
        
        try:
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 3:
                hex_color = ''.join([c*2 for c in hex_color])
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return self._rgb_to_name((r, g, b))
        except:
            return 'unknown'
    
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
        
        return style_analysis

