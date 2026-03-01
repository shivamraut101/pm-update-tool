import google.generativeai as genai
from PIL import Image
from backend.config import settings
from backend.database import get_db

if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)

SYSTEM_INSTRUCTION = """You are a vision-based project management data extractor.
You analyze screenshots sent by a project manager and extract all actionable information.
You know the company's team members and projects, so you match names/projects to the known list.
Be precise with names, dates, percentages, and statuses. Do not fabricate information not visible in the image."""

MODELS = [
    "gemini-2.5-flash",           # Best flash: fast + high quality vision
    "gemini-2.5-pro",             # Best pro: highest quality fallback
    "gemini-2.0-flash",           # Older stable fallback
]


async def process_screenshots(image_paths: list) -> str:
    """Process multiple screenshots and return combined extracted text."""
    if not settings.gemini_api_key:
        return "[Screenshot processing unavailable - no Gemini API key configured]"

    # Fetch project/team context for smarter extraction
    context = await _build_context()

    extracted_parts = []
    for path in image_paths:
        text = await _process_single_screenshot(path, context)
        if text:
            extracted_parts.append(text)

    return "\n\n".join(extracted_parts)


async def _build_context() -> str:
    """Build project/team context for smarter screenshot extraction."""
    try:
        db = get_db()
        projects = await db.projects.find({"status": "active"}).to_list(None)
        team_members = await db.team_members.find({"is_active": True}).to_list(None)

        project_names = [p["name"] for p in projects]
        team_names = [t["name"] for t in team_members]

        return (
            f"Known projects: {', '.join(project_names)}\n"
            f"Known team members: {', '.join(team_names)}"
        )
    except Exception:
        return ""


async def _process_single_screenshot(image_path: str, context: str = "") -> str:
    """Process a single screenshot with Gemini vision."""
    try:
        img = Image.open(image_path)

        # Resize if too large (Gemini handles up to ~4MB inline)
        max_dim = 2048
        if img.size[0] > max_dim or img.size[1] > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        prompt = f"""Analyze this screenshot and extract all project management relevant information.

{f"CONTEXT - " + context if context else ""}

This could be:
- A chat screenshot (WhatsApp, Slack, Teams): Extract who said what, tasks mentioned, deadlines, decisions made
- A project board (Jira, Trello, Asana): Extract task names, statuses, assignees, sprint progress, story points
- An email screenshot: Extract sender, subject, key points, action items, deadlines
- A spreadsheet/report: Extract data points, numbers, status updates, percentages
- A deployment/CI screen: Extract build status, version numbers, environments, errors
- Any other image: Extract anything relevant to project tracking

OUTPUT FORMAT - Structure your response clearly:

**People Mentioned:** List each person and what they did/said (use names from known list when matching)
**Projects Referenced:** Which projects are involved
**Tasks/Updates:** Specific task statuses, completions, changes
**Action Items:** Any follow-ups or pending items visible
**Blockers/Issues:** Any problems, errors, or blockers visible
**Key Data:** Dates, percentages, numbers, deadlines mentioned

Be factual and precise. Only report what you can actually see in the image."""

        for model_name in MODELS:
            try:
                model = genai.GenerativeModel(
                    model_name,
                    system_instruction=SYSTEM_INSTRUCTION,
                )
                response = model.generate_content(
                    [prompt, img],
                    generation_config=genai.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=2048,
                    ),
                )
                print(f"Screenshot extraction success with {model_name}")
                return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower():
                    print(f"Screenshot model {model_name} quota exceeded, trying next...")
                elif "404" in error_str or "not found" in error_str.lower():
                    print(f"Screenshot model {model_name} not available, trying next...")
                else:
                    print(f"Screenshot model {model_name} error: {e}, trying next...")
                continue
        return "[All AI models failed for screenshot processing]"
    except Exception as e:
        print(f"Screenshot processing error for {image_path}: {e}")
        return f"[Could not process screenshot: {str(e)}]"
