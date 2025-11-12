# Brand Extraction Agent + On-Brand Image Generation

A full-stack Python application that extracts brand identity from websites and generates on-brand images using AI.

## Features

- **Brand Extraction**: Automatically extracts brand identity (mission, vision, personality, color palette, style) from any website
- **On-Brand Image Generation**: Generates images that match the extracted brand style
- **LangChain Agent**: Uses LangChain for intelligent brand extraction orchestration
- **Modern UI**: Clean Streamlit frontend with intuitive interface

## Tech Stack

- **Backend**: FastAPI
- **Frontend**: Streamlit
- **Agent Framework**: LangChain
- **Web Scraping**: Playwright (with BeautifulSoup fallback)
- **Search**: Playwright-based Google Search (no API key needed)
- **Image Processing**: Pillow, ColorThief
- **Package Manager**: uv

## Project Structure

```
brandinator/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI application
│   │   ├── models.py        # Pydantic models
│   │   └── image_generator.py
│   └── agents/
│       ├── __init__.py
│       ├── brand_extractor.py  # LangChain agent
│       └── tools.py            # Extraction tools
├── frontend/
│   └── app.py              # Streamlit frontend
├── pyproject.toml
├── .env.example
└── README.md
```

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. **Clone the repository** (if applicable):

   ```bash
   git clone <repository-url>
   cd brandinator
   ```

2. **Install dependencies with uv**:

   ```bash
   uv sync
   ```

3. **Install Playwright browsers** (required for web scraping and Google search):

   ```bash
   uv run playwright install chromium
   ```

4. **Set up environment variables**:

   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

   Required API keys (optional for basic functionality):

   - `OPENAI_API_KEY`: For LangChain agent (optional, has fallback)
   - `GEMINI_ANALYSIS_API_KEY`: For brand analysis using Google Gemini (optional, has fallback)
   - `GEMINI_API_KEY`: Fallback if specific keys not set (optional)
   - `GOOGLE_PROJECT_ID`: Your Google Cloud Project ID (required for image generation)
   - `GOOGLE_LOCATION`: Vertex AI region (default: `us-central1`, optional)

   **For Image Generation (Vertex AI Imagen)**:

   You need to:

   1. Create a Google Cloud Project
   2. Enable the Vertex AI API in your project
   3. Set up authentication:
      ```bash
      # Install gcloud CLI: https://cloud.google.com/sdk/docs/install
      gcloud auth application-default login
      ```
   4. Set `GOOGLE_PROJECT_ID` in your `.env` file

   **Install Playwright browsers** (required for web scraping and Google search):

   ```bash
   uv run playwright install chromium
   ```

## Running Locally

### Start the Backend

In one terminal, you can use any of these methods:

**Option 1: Using the run script**

```bash
./run_backend.sh
```

**Option 2: Using uv run**

```bash
uv run backend/app/main.py
```

**Option 3: Using uvicorn directly**

```bash
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Start the Frontend

In another terminal:

**Option 1: Using the run script**

```bash
./run_frontend.sh
```

**Option 2: Using streamlit directly**

```bash
streamlit run frontend/app.py
```

The UI will be available at `http://localhost:8501`

## API Endpoints

### POST /extract

Extract brand identity from a website URL.

**Request:**

```json
{
  "url": "https://example.com"
}
```

**Response:**

```json
{
  "brand_identity": {
    "brand_details": {
      "brand_name": "...",
      "brand_mission": "...",
      "brand_vision": "...",
      "brand_personality": [...]
    },
    "image_style": {
      "style": "...",
      "keywords": [...],
      "color_palette": {...}
    },
    "_metadata": {
      "source_pages": [...]
    }
  },
  "source_urls": [...]
}
```

### POST /generate

Generate an on-brand image.

**Request:**

```json
{
  "brand_json": {...},
  "user_prompt": "A professional team working together"
}
```

**Response:**

```json
{
  "image_url": "https://..."
}
```

## Usage

1. **Extract Brand Identity**:

   - Enter a website URL in the frontend
   - Click "Extract Brand"
   - View the extracted brand identity JSON

2. **Generate Image**:
   - After extracting a brand, enter an image prompt
   - Click "Generate Image"
   - View the generated on-brand image

## Development

### Adding New Tools

Add new extraction tools in `backend/agents/tools.py` and integrate them into the brand extractor.

### Extending the Agent

Modify `backend/agents/brand_extractor.py` to add new reasoning steps or integrate additional LLM capabilities.

## License

MIT
