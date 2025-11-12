"""FastAPI backend application."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from backend.app.models import ExtractRequest, ExtractResponse, GenerateRequest, GenerateResponse
from backend.agents.brand_extractor import BrandExtractionAgent
from backend.app.image_generator import ImageGenerator

app = FastAPI(
    title="Brand Extraction Agent API",
    description="API for extracting brand identity and generating on-brand images",
    version="0.1.0"
)

# Enable CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agents
brand_extractor = BrandExtractionAgent()
image_generator = ImageGenerator()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Brand Extraction Agent API",
        "version": "0.1.0",
        "endpoints": ["/extract", "/generate"]
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/extract", response_model=ExtractResponse)
async def extract_brand(request: ExtractRequest):
    """Extract brand identity from a website URL."""
    try:
        print(f"Extracting brand from URL: {request.url}")
        brand_identity = brand_extractor.extract(request.url)
        
        # Collect source URLs
        source_urls = [page.url for page in brand_identity._metadata.source_pages]
        
        return ExtractResponse(
            brand_identity=brand_identity,
            source_urls=source_urls
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error extracting brand: {str(e)}"
        )


@app.post("/generate", response_model=GenerateResponse)
async def generate_image(request: GenerateRequest):
    """Generate an on-brand image based on brand identity and user prompt."""
    try:
        print(f"Generating image with prompt: {request.user_prompt}")
        image_url = image_generator.generate(
            brand_identity=request.brand_json,
            user_prompt=request.user_prompt
        )
        
        return GenerateResponse(image_url=image_url)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating image: {str(e)}"
        )


def main():
    """Main entry point for running the backend server."""
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    main()

