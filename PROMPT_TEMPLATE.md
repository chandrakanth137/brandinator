# Image Generation Prompt Template

This document explains how the Brand Extraction Agent generates AI image prompts that blend user input with extracted brand style.

## How It Works

### Input

1. **User Prompt**: What the user wants to see (e.g., "nurse teaching IV setup")
2. **Brand JSON**: Extracted brand identity including:
   - Colors (hex codes)
   - Visual style (modern, minimalist, etc.)
   - Personality traits (professional, friendly, etc.)
   - Environment preferences

### Output

A comprehensive AI image generation prompt that creates images matching the user's content in the brand's visual style.

## Prompt Structure

The prompt is built in 7 sections:

### 1. Core Content (User's Request)

```
"Create a high-quality image: [USER_PROMPT]"
```

Example: `"Create a high-quality image: nurse teaching IV setup"`

### 2. Visual Personality

Converts brand personality traits to visual descriptors:

- `"professional"` → `"clean, polished, and well-organized aesthetic"`
- `"innovative"` → `"cutting-edge, creative, and forward-thinking aesthetic"`
- `"friendly"` → `"warm, approachable, and inviting aesthetic"`

### 3. Artistic Style

```
"Art direction: [STYLE] style"
"Visual theme: [KEYWORDS]"
```

Example: `"Art direction: modern style. Visual theme: technology, healthcare, education"`

### 4. Color Palette (MOST IMPORTANT)

```
"Color palette: use [PRIMARY_HEX] as the dominant primary color,
[SECONDARY_HEX] as the secondary color, [ACCENT_COLORS] as accent colors
on a [BACKGROUND_HEX] background"

"Color mood: [warm/cool/neutral] tones"
```

Example:

```
"Color palette: use #0070F3 as the dominant primary color, #000000 as the
secondary color, #FFFFFF, #F5F5F5 as accent colors on a #FAFAFA background.
Color mood: cool, professional tones"
```

### 5. Composition & Environment

```
"Environment: [ENVIRONMENT_LIST]"
"Include elements: [PROPS_LIST]"
```

Example: `"Environment: modern hospital, training room. Include elements: medical equipment, IV bags, training materials"`

### 6. People Representation

```
"Featuring: [OCCUPATIONS]"
"People: [ETHNICITY/DIVERSITY]"
```

Example: `"Featuring: healthcare professionals, medical educators. People: diverse, professional"`

### 7. Quality & Consistency

```
"High quality, professional composition. Ensure all elements use the
specified color palette consistently. Maintain visual harmony and
cohesive aesthetic throughout."
```

## Full Example

### Input:

**User Prompt**: `"team working together in office"`

**Brand JSON**:

```json
{
  "brand_details": {
    "brand_personality": ["professional", "innovative", "collaborative"]
  },
  "image_style": {
    "style": "modern",
    "keywords": ["technology", "workspace"],
    "temperature": "cool",
    "environment": ["office", "workspace"],
    "props": ["laptops", "whiteboards"],
    "color_palette": {
      "primary": { "hex": "#0070F3" },
      "secondary": { "hex": "#000000" },
      "support_1": { "hex": "#FFFFFF" },
      "background": { "hex": "#F5F5F5" }
    }
  }
}
```

### Generated Prompt:

```
Create a high-quality image: team working together in office.

Visual style: clean, polished, and well-organized, cutting-edge, creative,
and forward-thinking, collaborative and team-focused aesthetic.

Art direction: modern style.

Visual theme: technology, workspace.

Color palette: use #0070F3 as the dominant primary color, #000000 as the
secondary color, #FFFFFF as accent colors on a #F5F5F5 background.

Color mood: cool, professional tones.

Environment: office, workspace.

Include elements: laptops, whiteboards.

High quality, professional composition. Ensure all elements use the
specified color palette consistently. Maintain visual harmony and
cohesive aesthetic throughout.
```

## Key Features

### 1. Style Transfer Without Brand Text

- ❌ Does NOT include: brand names, mission statements, slogans
- ✅ DOES include: colors, visual style, aesthetic personality

### 2. Smart Personality Mapping

Maps 30+ brand personality types to visual descriptors:

- Professional → Clean & polished
- Modern → Contemporary & sleek
- Luxurious → Elegant & premium
- Playful → Vibrant & energetic
- And many more...

### 3. Natural Color Instructions

Instead of: `"primary: #0070F3, secondary: #000000"`  
Uses: `"use #0070F3 as the dominant primary color, #000000 as the secondary color"`

This natural language helps AI models better understand color application.

### 4. Hierarchical Color Application

1. **Primary** - Main/dominant color
2. **Secondary** - Supporting color
3. **Accent** (support_1, support_2, support_3) - Highlights
4. **Positive** - Special highlights/CTAs
5. **Background** - Base/backdrop

## Customization

To modify the prompt template, edit `backend/app/image_generator.py`:

1. **Add personality mappings**: Update `_personality_to_visual()` method
2. **Change color instructions**: Modify `_build_color_instruction()` method
3. **Adjust prompt structure**: Edit `_build_style_prompt()` method

## Testing Tips

1. **Test with different brand personalities**:
   - Try "professional" vs "playful" → Should produce different aesthetics
2. **Test color application**:
   - Use contrasting palettes → Images should clearly reflect the colors
3. **Test with vague vs specific user prompts**:
   - Vague: "team meeting" → Brand style should fill in the gaps
   - Specific: "5 people in blue shirts around a table" → Brand style should complement

## API Usage

```python
# In your application
from backend.app.image_generator import ImageGenerator
from backend.app.models import BrandIdentity

generator = ImageGenerator()

# Your extracted brand
brand_identity = BrandIdentity(...)

# User's image request
user_prompt = "nurse teaching IV setup"

# Generate image with brand style applied
image_url = generator.generate(brand_identity, user_prompt)
```

The image generation will automatically blend the user's content with the brand's visual style!
