# Brand Extraction Agent + On-Brand Image Generation

A full-stack Python application that extracts brand identity from websites and generates on-brand images using AI.

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager (will be installed automatically if missing)

### Installation

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd brandinator
   ```

2. **Run the installation script**:

   ```bash
   ./install.sh
   ```

   This will:

   - Check Python version
   - Install uv if not present
   - Install all project dependencies
   - Install Playwright browsers
   - Create .env file from .env.example (if it exists)
   - Make run scripts executable

3. **Set up environment variables**:

   Edit the `.env` file and add your API key:

   ```bash
   GEMINI_API_KEY=your_key_here
   ```

   Get your API key from: https://aistudio.google.com/app/apikey

## How to Run

### Start the Backend

```bash
./run_backend.sh
```

The API will be available at `http://localhost:8000`

**Alternative method**:

```bash
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### Start the Frontend

In a separate terminal:

```bash
./run_frontend.sh
```

The UI will be available at `http://localhost:8501`

**Alternative method**:

```bash
uv run streamlit run frontend/app.py
```

## Design Choices

### Architecture

- **FastAPI Backend**: RESTful API with async support, providing `/extract` and `/generate` endpoints
- **Streamlit Frontend**: Single-page application for user interaction
- **LangChain Agents**: Orchestrates brand extraction workflow with tool usage
- **Modular Design**: Separation of concerns with dedicated modules for scraping, extraction, and image generation

### Brand Extraction

- **Multi-Page Crawling**: Uses BFS algorithm to crawl multiple pages (homepage, about, products, blog) for comprehensive brand understanding
- **Sitemap Support**: Automatically detects and uses sitemap.xml when available for efficient URL discovery
- **Hybrid Scraping Strategy**:
  - Parallel BeautifulSoup scraping for speed (static content)
  - Sequential Playwright scraping as fallback (JavaScript-heavy sites)
  - Smart detection of bot protection and automatic fallback
- **Computed Style Extraction**: Uses Playwright's computed styles for accurate color and font extraction from rendered pages
- **LLM-Powered Analysis**: Google Gemini 2.5 Flash analyzes scraped content to infer brand identity, personality, and visual style

### Image Generation

- **Prompt Crafting Agent**: Dedicated LLM agent that intelligently combines user prompts with brand identity, selecting only relevant brand elements
- **Style Transfer**: Generates images that match brand colors, aesthetic, and mood without including brand names or logos
- **Gemini 2.5 Flash**: Uses Google's Gemini 2.5 Flash for image generation (Nano Banana)
- **Data URL Response**: Images are returned as base64 data URLs for immediate display, with download button in UI
