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


class WebScraper:
    """Web scraper using BeautifulSoup."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, url: str) -> Dict[str, Any]:
        """Scrape a website and extract text content, images, and metadata."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract text content
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Extract title
            title = soup.find('title')
            title_text = title.get_text().strip() if title else ""
            
            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else ""
            
            # Extract images
            images = []
            for img in soup.find_all('img', src=True):
                img_url = img['src']
                # Convert relative URLs to absolute
                if not img_url.startswith('http'):
                    img_url = urljoin(url, img_url)
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
                # Only include links from same domain
                if urlparse(href).netloc == urlparse(url).netloc:
                    links.append(href)
            
            return {
                'url': url,
                'title': title_text,
                'description': description,
                'text': text[:5000],  # Limit text length
                'images': images[:20],  # Limit number of images
                'links': list(set(links))[:10]  # Limit and deduplicate links
            }
        except Exception as e:
            return {
                'url': url,
                'error': str(e),
                'text': '',
                'images': [],
                'links': []
            }


class GoogleSearchTool:
    """Google Search tool for supplementing brand info."""
    
    def __init__(self, api_key: Optional[str] = None, search_engine_id: Optional[str] = None):
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY', '')
        self.search_engine_id = search_engine_id or os.getenv('GOOGLE_SEARCH_ENGINE_ID', '')
    
    def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """Search Google and return results."""
        if not self.api_key or not self.search_engine_id:
            # Return mock results if API keys not configured
            return [
                {
                    'title': f'Mock result for: {query}',
                    'snippet': f'This is a mock search result for the query: {query}',
                    'link': 'https://example.com'
                }
            ]
        
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': self.api_key,
                'cx': self.search_engine_id,
                'q': query,
                'num': num_results
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get('items', [])[:num_results]:
                results.append({
                    'title': item.get('title', ''),
                    'snippet': item.get('snippet', ''),
                    'link': item.get('link', '')
                })
            return results
        except Exception as e:
            # Fallback to mock results on error
            return [
                {
                    'title': f'Search result for: {query}',
                    'snippet': f'Error occurred: {str(e)}',
                    'link': 'https://example.com'
                }
            ]


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

