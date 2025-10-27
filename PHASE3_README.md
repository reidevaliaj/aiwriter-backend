# Phase 3: AI Pipeline Implementation

## Overview

Phase 3 replaces the mock article generation with real OpenAI integration using GPT-5 for text generation and GPT-Image-1 for image generation.

## What's New

### 1. OpenAI Configuration
- Added OpenAI settings to `config.py`
- Configurable models, tokens, temperature, and timeout
- Environment variable support

### 2. OpenAI Client
- Singleton client with proper error handling
- Text generation with `run_text()`
- Image generation with `gen_image()`
- JSON validation and retry logic

### 3. Database Schema Updates
- New `articles` table with full article data
- Updated `jobs` table with `requested_images` and `language` fields
- Alembic migration: `003_phase3_article_fields.py`

### 4. Real Article Generator
- Complete OpenAI-powered article generation pipeline
- German SEO system prompt
- Structured generation process:
  1. Create outline
  2. Write sections
  3. Write intro/conclusion
  4. Generate FAQ
  5. Generate meta data
  6. Generate schema.org markup
  7. Assemble final HTML
  8. Generate images (if requested)

## Setup Instructions

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Set Environment Variables
Create a `.env` file with:
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_TEXT_MODEL=gpt-5
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_MAX_TOKENS_TEXT=2200
OPENAI_TEMPERATURE=0.4
OPENAI_TIMEOUT_S=60
```

### 3. Run Database Migration
```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Apply migration
alembic upgrade head
```

### 4. Test the Implementation
```bash
python test_phase3.py
```

## Key Features

### German SEO System Prompt
The system uses a specialized German SEO prompt that ensures:
- Fact-based, clear articles in professional tone
- H2/H3 headings structure
- Short paragraphs (max 120 words)
- Lists when appropriate
- No repetitions or exaggerated language
- Pure HTML output (no Markdown)

### Article Generation Pipeline

1. **Outline Creation**: Generates structured outline with H2/H3 hierarchy
2. **Section Writing**: Creates content for each section based on outline
3. **Intro/Conclusion**: Writes engaging introduction and summary
4. **FAQ Generation**: Creates 3-5 relevant questions and answers
5. **Meta Data**: Generates SEO-optimized title and description
6. **Schema Markup**: Creates structured data for search engines
7. **HTML Assembly**: Combines all parts into final article
8. **Image Generation**: Creates images if requested (up to plan limit)

### Error Handling
- Comprehensive error handling at each step
- JSON validation with retry logic
- Graceful fallbacks for image generation
- Detailed logging for debugging

### Database Integration
- Full article persistence in `articles` table
- Token usage tracking
- Image cost calculation
- Status tracking (draft/ready/failed)

## Testing

The `test_phase3.py` script tests:
- OpenAI client connectivity
- Text generation
- Image generation
- Complete article generation pipeline
- Database integration

## Deployment

### VPS Deployment
1. Set environment variables on VPS
2. Run database migration: `alembic upgrade head`
3. Restart the service: `sudo systemctl restart aiwriter`

### Environment Variables for VPS
```bash
export OPENAI_API_KEY="your_key_here"
export OPENAI_TEXT_MODEL="gpt-5"
export OPENAI_IMAGE_MODEL="gpt-image-1"
```

## Next Steps

Phase 3 is now complete! The system can:
- ✅ Generate real articles using OpenAI
- ✅ Create images with DALL-E
- ✅ Store complete article data
- ✅ Send articles to WordPress
- ✅ Track usage and costs

Ready for Phase 4: Enhanced licensing and quota management!
