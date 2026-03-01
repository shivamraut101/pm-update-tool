import google.generativeai as genai
from PIL import Image
from backend.config import settings

if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)

EXTRACTION_PROMPT = """Analyze this screenshot and extract all project management relevant information.
This could be:
- A chat screenshot: Extract who said what, any tasks mentioned, any deadlines
- A dashboard/board: Extract task names, statuses, assignees, progress
- An email screenshot: Extract sender, subject, key points, action items
- A spreadsheet: Extract relevant data points, numbers, status updates
- Any other image: Describe what you see that is relevant to project tracking

Return a structured text summary of everything relevant.
Include specific names, dates, numbers, and statuses you can see.
Be factual and concise."""


async def process_screenshots(image_paths: list) -> str:
    """Process multiple screenshots and return combined extracted text."""
    if not settings.gemini_api_key:
        return "[Screenshot processing unavailable - no Gemini API key configured]"

    extracted_parts = []
    for path in image_paths:
        text = await _process_single_screenshot(path)
        if text:
            extracted_parts.append(text)

    return "\n\n".join(extracted_parts)


async def _process_single_screenshot(image_path: str) -> str:
    """Process a single screenshot with Gemini vision."""
    try:
        img = Image.open(image_path)

        # Resize if too large (Gemini handles up to ~4MB inline)
        max_dim = 2048
        if img.size[0] > max_dim or img.size[1] > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            [EXTRACTION_PROMPT, img],
            generation_config=genai.GenerationConfig(
                temperature=0.1,
            ),
        )
        return response.text
    except Exception as e:
        print(f"Screenshot processing error for {image_path}: {e}")
        return f"[Could not process screenshot: {str(e)}]"
