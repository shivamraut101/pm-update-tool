import json
import google.generativeai as genai
from backend.config import settings

# Configure Gemini
if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)


async def parse_update(
    combined_text: str,
    projects: list,
    team_members: list,
) -> tuple:
    """Parse a natural language update using Gemini AI.

    Returns (parsed_dict, confidence_score).
    """
    if not settings.gemini_api_key:
        return _fallback_parse(combined_text), 0.0

    # Build context about known projects and team members
    project_context = "\n".join(
        f"- {p['name']} (code: {p.get('code', '')}, client: {p.get('client_name', '')})"
        for p in projects
    ) or "No projects registered yet."

    team_context = "\n".join(
        f"- {t['name']} (aliases: {', '.join(t.get('aliases', []))}, "
        f"role: {t.get('role', '')}, nickname: {t.get('nickname', '')})"
        for t in team_members
    ) or "No team members registered yet."

    prompt = f"""You are an AI assistant that parses project management updates from a project manager.

KNOWN PROJECTS:
{project_context}

KNOWN TEAM MEMBERS:
{team_context}

USER'S UPDATE:
\"\"\"{combined_text}\"\"\"

Parse this update and return a JSON object with this EXACT structure:
{{
  "team_updates": [
    {{
      "team_member_name": "exact name from known list or new name if not found",
      "project_name": "exact project name from known list or new name if not found",
      "summary": "one-line summary of what they did",
      "status": "completed|in_progress|blocked|not_started",
      "details": "any additional details"
    }}
  ],
  "client_updates": [
    {{
      "project_name": "project name",
      "client_name": "client name",
      "summary": "what the client said or did",
      "sentiment": "positive|neutral|negative|urgent"
    }}
  ],
  "action_items": [
    {{
      "description": "what needs to be done",
      "assigned_to": "self or team member name",
      "due_context": "any mentioned deadline or timeframe",
      "priority": "high|medium|low"
    }}
  ],
  "blockers": [
    {{
      "description": "what is blocked",
      "project_name": "which project",
      "blocking_who": "who is blocked",
      "severity": "high|medium|low"
    }}
  ],
  "general_notes": "anything that doesn't fit above categories"
}}

RULES:
1. Match team member names to the KNOWN list using closest match. Consider nicknames and aliases.
2. Match project names to the KNOWN list. If ambiguous, use context clues.
3. If a name is new and not in any known list, still include it with the name as-is.
4. Extract ALL action items, even implicit ones (e.g., "I need to tell the client" = action item for self).
5. If no items exist for a category, return an empty array [].
6. Return ONLY valid JSON. No markdown, no code fences, no explanation.
"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        parsed = json.loads(response.text)
        # Resolve entity IDs
        parsed = _resolve_entities(parsed, projects, team_members)
        return parsed, 0.9
    except Exception as e:
        print(f"AI parsing error: {e}")
        return _fallback_parse(combined_text), 0.0


def _resolve_entities(parsed: dict, projects: list, team_members: list) -> dict:
    """Match parsed names to database IDs using fuzzy matching."""
    # Build lookup maps
    project_map = {}
    for p in projects:
        pid = str(p["_id"])
        project_map[p["name"].lower()] = pid
        if p.get("code"):
            project_map[p["code"].lower()] = pid

    team_map = {}
    for t in team_members:
        tid = str(t["_id"])
        team_map[t["name"].lower()] = tid
        if t.get("nickname"):
            team_map[t["nickname"].lower()] = tid
        for alias in t.get("aliases", []):
            team_map[alias.lower()] = tid

    # Resolve team_updates
    for update in parsed.get("team_updates", []):
        name = update.get("team_member_name", "").lower()
        update["team_member_id"] = team_map.get(name)
        proj = update.get("project_name", "").lower()
        update["project_id"] = project_map.get(proj)

    # Resolve client_updates
    for cu in parsed.get("client_updates", []):
        proj = cu.get("project_name", "").lower()
        cu["project_id"] = project_map.get(proj)

    # Resolve blockers
    for b in parsed.get("blockers", []):
        proj = b.get("project_name", "").lower()
        b["project_id"] = project_map.get(proj)

    return parsed


def _fallback_parse(text: str) -> dict:
    """Return a basic parsed structure when AI is unavailable."""
    return {
        "team_updates": [],
        "client_updates": [],
        "action_items": [],
        "blockers": [],
        "general_notes": text,
    }
