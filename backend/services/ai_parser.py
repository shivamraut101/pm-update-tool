"""Smart AI parser with full organizational knowledge.

This module builds a rich context of the entire organization — team members,
their project assignments, recent work history, and open items — so the AI
never has to guess. It KNOWS who works where and what they were doing.
"""

import json
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher

import google.generativeai as genai

from backend.config import settings
from backend.database import get_db
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)

MODELS = [
    "gemini-2.5-flash",          # Best flash: fast + high quality
    "gemini-2.5-pro",            # Best pro: highest quality fallback
    "gemini-2.0-flash",          # Older stable fallback
]

SYSTEM_INSTRUCTION = """You are an expert project management update parser for PrimeX, an Indian software company.

CRITICAL RULES — follow these EXACTLY:
1. You are given COMPLETE knowledge of the organization: every team member, every project, who is assigned where, and what each person was working on recently.
2. You MUST use EXACT names from the KNOWN TEAM MEMBERS and KNOWN PROJECTS lists. Never invent, abbreviate, or paraphrase names.
3. When a person is mentioned, ALWAYS check their ASSIGNED PROJECTS to determine which project the update is about. If the person only works on one active project context, use that project.
4. When a person is mentioned WITHOUT a project name, use their RECENT ACTIVITY to determine the most likely project. If still ambiguous, check their assigned projects.
5. You understand Indian English, informal shorthand, Hinglish, and common developer slang.
6. You infer status from context: "done"/"fixed"/"completed"/"pushed"/"merged" = completed, "working on"/"doing"/"started" = in_progress, "stuck"/"blocked"/"waiting" = blocked, "will start"/"tomorrow"/"next" = not_started
7. You extract percentages: "80% done", "almost done" = ~90%, "half done" = ~50%, "just started" = ~10%
8. You detect ALL implicit action items and blockers — even if not stated directly.
9. You NEVER guess. If you truly cannot determine something, say so in general_notes with confidence < 0.7.
10. For team_member_name and project_name, you MUST return the EXACT full name as listed in KNOWN TEAM MEMBERS / KNOWN PROJECTS.
11. If a project/client/member is mentioned that is NOT in the known lists, still include it — the system will handle auto-creation."""


# ---------------------------------------------------------------------------
# AI Entity Extraction (pre-parsing for unknown entities)
# ---------------------------------------------------------------------------

async def extract_entities_with_ai(text: str) -> dict:
    """Use Gemini to extract ALL mentioned entities with confidence scores.

    This runs BEFORE main parsing to identify potential unknowns.
    """
    if not settings.gemini_api_key:
        return {"projects": [], "team_members": [], "clients": []}

    prompt = f"""Extract ALL entity mentions from this project update text.

TEXT: {text}

Return JSON with all projects, team members, and clients mentioned:
{{
  "projects": [
    {{
      "mentioned_name": "exact text from update (e.g., 'NewClient Mobile')",
      "normalized_name": "normalized name (e.g., 'NewClient Mobile')",
      "confidence": 0.95
    }}
  ],
  "team_members": [
    {{
      "mentioned_name": "exact text",
      "normalized_name": "Proper Name Case",
      "confidence": 0.90
    }}
  ],
  "clients": [
    {{
      "mentioned_name": "exact text",
      "normalized_name": "Client Name",
      "confidence": 0.85
    }}
  ]
}}

Confidence scoring:
- 0.95+: Explicitly named (e.g., "working on Project X")
- 0.8-0.95: Strongly inferred from context
- 0.7-0.8: Weak inference
- <0.7: Ambiguous (skip)

Rules:
1. Include EVERY entity mentioned or strongly implied
2. Normalize names to proper case
3. For abbreviated names, expand if obvious (e.g., "PX" if context suggests "Project X")
4. Extract client names from phrases like "NewClient called", "feedback from ABC Corp"
5. Return empty arrays if no entities found
"""

    try:
        for model_name in MODELS[:2]:  # Use fast models for extraction
            try:
                t_model = time.time()
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                        max_output_tokens=500,
                    ),
                )
                extracted = json.loads(response.text)
                logger.info(f"Entity extraction OK with {model_name} in {time.time() - t_model:.1f}s")
                return extracted
            except Exception as e:
                logger.warning(f"Entity extraction with {model_name} failed after {time.time() - t_model:.1f}s: {e}")
                continue
    except Exception as e:
        logger.error(f"Entity extraction error: {e}")

    return {"projects": [], "team_members": [], "clients": []}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def parse_update(
    combined_text: str,
    projects: list,
    team_members: list,
) -> tuple:
    """Parse a natural language update using Gemini AI with full context.

    Returns (parsed_dict, confidence_score).
    """
    if not settings.gemini_api_key:
        return _fallback_parse(combined_text), 0.0

    # Build rich organizational context
    t_ctx = time.time()
    context = await _build_smart_context(projects, team_members)

    prompt = _build_prompt(combined_text, context)
    logger.info(f"Context built in {time.time() - t_ctx:.1f}s (prompt ~{len(prompt)} chars)")

    try:
        last_error = None
        for model_name in MODELS:
            try:
                t_model = time.time()
                model = genai.GenerativeModel(
                    model_name,
                    system_instruction=SYSTEM_INSTRUCTION,
                )
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                parsed = json.loads(response.text)

                # Extract AI's self-assessed confidence
                ai_confidence = 0.9
                if "confidence" in parsed:
                    ai_confidence = parsed["confidence"].get("overall", 0.9)
                    reason = parsed["confidence"].get("reasoning", "")
                    if reason:
                        logger.info(f"AI confidence: {ai_confidence} — {reason}")
                    del parsed["confidence"]

                # Post-processing: resolve IDs + validate
                parsed = _resolve_entities(parsed, projects, team_members)
                parsed = _validate_assignments(parsed, projects, team_members)

                logger.info(f"Parse OK with {model_name} in {time.time() - t_model:.1f}s (confidence: {ai_confidence})")
                return parsed, ai_confidence

            except Exception as e:
                last_error = e
                err = str(e)
                if "429" in err or "quota" in err.lower():
                    logger.warning(f"{model_name} quota exceeded after {time.time() - t_model:.1f}s, trying next...")
                elif "404" in err or "not found" in err.lower():
                    logger.warning(f"{model_name} not available after {time.time() - t_model:.1f}s, trying next...")
                else:
                    logger.warning(f"{model_name} error after {time.time() - t_model:.1f}s: {e}")
                continue

        logger.error(f"All AI models failed: {last_error}")
        return _fallback_parse(combined_text), 0.0

    except Exception as e:
        logger.error(f"Parse error: {e}")
        return _fallback_parse(combined_text), 0.0


# ---------------------------------------------------------------------------
# Smart Context Builder
# ---------------------------------------------------------------------------

async def _build_smart_context(projects: list, team_members: list) -> dict:
    """Build complete organizational knowledge for the AI prompt."""
    db = get_db()

    # Build project-name lookup by ID
    proj_by_id = {str(p["_id"]): p["name"] for p in projects}

    # Build team member profiles with their assigned projects
    team_profiles = []
    for t in team_members:
        assigned_projects = []
        for pid in t.get("project_ids", []):
            pname = proj_by_id.get(pid)
            if pname:
                assigned_projects.append(pname)

        team_profiles.append({
            "name": t["name"],
            "nickname": t.get("nickname", ""),
            "aliases": t.get("aliases", []),
            "role": t.get("role", ""),
            "assigned_projects": assigned_projects,
        })

    # Build project profiles with their assigned team members
    team_by_id = {str(t["_id"]): t["name"] for t in team_members}
    project_profiles = []
    for p in projects:
        assigned_members = []
        for mid in p.get("team_member_ids", []):
            mname = team_by_id.get(mid)
            if mname:
                assigned_members.append(mname)

        project_profiles.append({
            "name": p["name"],
            "code": p.get("code", ""),
            "client_name": p.get("client_name", ""),
            "status": p.get("status", "active"),
            "team_members": assigned_members,
        })

    # Fetch last 3 days of updates for recent activity context
    three_days_ago = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
    recent_updates = await db.updates.find(
        {"date": {"$gte": three_days_ago}},
    ).sort("created_at", -1).to_list(50)

    # Build recent activity per person
    recent_activity = {}
    for upd in recent_updates:
        for tu in upd.get("parsed", {}).get("team_updates", []):
            name = tu.get("team_member_name", "")
            if name not in recent_activity:
                recent_activity[name] = []
            if len(recent_activity[name]) < 3:  # Keep last 3 items per person
                recent_activity[name].append({
                    "date": upd["date"],
                    "project": tu.get("project_name", "?"),
                    "summary": tu.get("summary", ""),
                    "status": tu.get("status", ""),
                })

    # Fetch open blockers (unresolved)
    open_blockers = []
    for upd in recent_updates:
        for b in upd.get("parsed", {}).get("blockers", []):
            open_blockers.append({
                "date": upd["date"],
                "project": b.get("project_name", "?"),
                "description": b.get("description", ""),
                "blocking": b.get("blocking_who", "?"),
            })

    # Fetch pending action items
    pending_actions = []
    for upd in recent_updates:
        for ai in upd.get("parsed", {}).get("action_items", []):
            if not ai.get("is_completed", False):
                pending_actions.append({
                    "date": upd["date"],
                    "description": ai.get("description", ""),
                    "assigned_to": ai.get("assigned_to", "self"),
                })

    return {
        "team_profiles": team_profiles,
        "project_profiles": project_profiles,
        "recent_activity": recent_activity,
        "open_blockers": open_blockers[:10],
        "pending_actions": pending_actions[:10],
    }


# ---------------------------------------------------------------------------
# Prompt Builder
# ---------------------------------------------------------------------------

def _build_prompt(text: str, ctx: dict) -> str:
    """Build the full prompt with all organizational context."""

    # --- Team Members with their projects ---
    team_lines = []
    for t in ctx["team_profiles"]:
        projs = ", ".join(t["assigned_projects"]) if t["assigned_projects"] else "no active projects"
        aliases = ", ".join(set(t["aliases"])) if t["aliases"] else "none"
        team_lines.append(
            f"- {t['name']} (nickname: {t['nickname']}, aliases: {aliases}, role: {t['role']})\n"
            f"  ASSIGNED PROJECTS: {projs}"
        )
    team_section = "\n".join(team_lines) or "No team members."

    # --- Projects with their team ---
    proj_lines = []
    for p in ctx["project_profiles"]:
        if p["status"] != "active":
            continue
        members = ", ".join(p["team_members"]) if p["team_members"] else "no one assigned"
        client = f", client: {p['client_name']}" if p["client_name"] else ""
        proj_lines.append(
            f"- {p['name']} (code: {p['code']}{client})\n"
            f"  TEAM: {members}"
        )
    proj_section = "\n".join(proj_lines) or "No projects."

    # --- Recent Activity (what people were doing recently) ---
    activity_lines = []
    for person, items in ctx["recent_activity"].items():
        entries = "; ".join(
            f"{a['date']}: {a['summary']} on {a['project']} [{a['status']}]"
            for a in items
        )
        activity_lines.append(f"- {person}: {entries}")
    activity_section = "\n".join(activity_lines) if activity_lines else "No recent activity."

    # --- Open Blockers ---
    blocker_lines = []
    for b in ctx["open_blockers"]:
        blocker_lines.append(
            f"- [{b['date']}] {b['project']}: {b['description']} (blocking {b['blocking']})"
        )
    blocker_section = "\n".join(blocker_lines) if blocker_lines else "None."

    # --- Pending Actions ---
    action_lines = []
    for a in ctx["pending_actions"]:
        action_lines.append(
            f"- [{a['date']}] {a['description']} (assigned: {a['assigned_to']})"
        )
    action_section = "\n".join(action_lines) if action_lines else "None."

    return f"""=== ORGANIZATION KNOWLEDGE BASE ===

KNOWN TEAM MEMBERS (with their project assignments):
{team_section}

KNOWN PROJECTS (with their team members):
{proj_section}

RECENT ACTIVITY (last 3 days — use this to determine context when project is not mentioned):
{activity_section}

OPEN BLOCKERS (still unresolved):
{blocker_section}

PENDING ACTION ITEMS (not yet completed):
{action_section}

=== END KNOWLEDGE BASE ===

USER'S UPDATE MESSAGE:
\"\"\"{text}\"\"\"

Parse this update into structured JSON. Use the knowledge base above to accurately match every person and project. Do NOT guess — use the assignment data and recent activity.

Return this EXACT JSON structure:
{{
  "team_updates": [
    {{
      "team_member_name": "EXACT full name from KNOWN TEAM MEMBERS list",
      "project_name": "EXACT project name from KNOWN PROJECTS list",
      "summary": "concise one-line summary of what they did/are doing",
      "status": "completed|in_progress|blocked|not_started",
      "progress_percent": null or 0-100 if mentioned or inferable,
      "details": "additional context, specifics, or technical details"
    }}
  ],
  "client_updates": [
    {{
      "project_name": "EXACT project name",
      "client_name": "client name",
      "summary": "what the client said, requested, or feedback given",
      "sentiment": "positive|neutral|negative|urgent"
    }}
  ],
  "action_items": [
    {{
      "description": "what needs to be done",
      "assigned_to": "self or EXACT team member name",
      "due_context": "any mentioned deadline or timeframe",
      "priority": "high|medium|low",
      "is_completed": false
    }}
  ],
  "blockers": [
    {{
      "description": "what is blocked and why",
      "project_name": "EXACT project name",
      "blocking_who": "EXACT team member name or 'team'",
      "severity": "high|medium|low",
      "needs_escalation": true or false
    }}
  ],
  "general_notes": "anything that does not fit above categories, or ambiguity notes",
  "confidence": {{
    "overall": 0.0 to 1.0,
    "reasoning": "explain what was clear vs what required inference"
  }}
}}

MATCHING RULES:
1. Person mentioned → check KNOWN TEAM MEMBERS → use their EXACT full name.
2. Project not mentioned but person is mentioned → check that person's ASSIGNED PROJECTS. If they have only 1 active project, use that. If multiple, check RECENT ACTIVITY to pick the most likely one.
3. If a person mentions something that matches an OPEN BLOCKER or PENDING ACTION, link it.
4. If an existing blocker seems resolved by this update, note it in general_notes.
5. Empty arrays [] for categories with no items. Never omit a category.
6. Confidence 0.95+ = all names and projects matched exactly. 0.8-0.95 = inferred project from context. <0.8 = some guessing involved."""


# ---------------------------------------------------------------------------
# Entity Resolution (post-AI, maps names -> DB IDs)
# ---------------------------------------------------------------------------

def _fuzzy_match(name: str, lookup: dict, threshold: float = 0.75) -> str | None:
    """Find the best fuzzy match for a name in a lookup dictionary."""
    name_lower = name.lower().strip()

    # Exact match first
    if name_lower in lookup:
        return lookup[name_lower]

    # Fuzzy match
    best_id = None
    best_score = 0.0
    for key, val in lookup.items():
        score = SequenceMatcher(None, name_lower, key).ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_id = val

    return best_id


# ---------------------------------------------------------------------------
# Multi-Strategy Matching (enhanced entity resolution)
# ---------------------------------------------------------------------------

def _exact_match(mentioned: str, entities: list, lookup_field: str = "name") -> dict | None:
    """Case-insensitive exact match."""
    mentioned_lower = mentioned.lower().strip()
    for entity in entities:
        if entity.get(lookup_field, "").lower() == mentioned_lower:
            return {"id": str(entity["_id"]), "confidence": 1.0, "matched_name": entity[lookup_field]}
    return None


def _alias_match(mentioned: str, entities: list) -> dict | None:
    """Match against aliases, nicknames, or codes."""
    mentioned_lower = mentioned.lower().strip()
    for entity in entities:
        # Check aliases (team members)
        if "aliases" in entity:
            for alias in entity.get("aliases", []):
                if alias.lower() == mentioned_lower:
                    return {"id": str(entity["_id"]), "confidence": 0.95, "matched_name": entity["name"]}
        # Check nickname (team members)
        if "nickname" in entity and entity.get("nickname", "").lower() == mentioned_lower:
            return {"id": str(entity["_id"]), "confidence": 0.95, "matched_name": entity["name"]}
        # Check code (projects)
        if "code" in entity and entity.get("code", "").lower() == mentioned_lower:
            return {"id": str(entity["_id"]), "confidence": 0.95, "matched_name": entity["name"]}
    return None


def _abbreviation_match(mentioned: str, entities: list, lookup_field: str = "name") -> dict | None:
    """Match partial/abbreviated names (e.g., 'NewCl' → 'NewClient')."""
    mentioned_lower = mentioned.lower().strip()
    if len(mentioned_lower) < 3:
        return None  # Too short to be meaningful

    for entity in entities:
        entity_name = entity.get(lookup_field, "").lower()
        # Check if mentioned is a prefix of entity name
        if entity_name.startswith(mentioned_lower):
            return {"id": str(entity["_id"]), "confidence": 0.85, "matched_name": entity[lookup_field]}
    return None


def _intelligent_match(mentioned: str, entities: list, entity_type: str = "project") -> dict | None:
    """Multi-strategy matching orchestrator.

    Tries strategies in order until a match is found.
    Returns: {"id": str, "confidence": float, "matched_name": str, "strategy": str} or None
    """
    lookup_field = "name"

    # Strategy 1: Exact match
    result = _exact_match(mentioned, entities, lookup_field)
    if result:
        return {**result, "strategy": "exact"}

    # Strategy 2: Alias/nickname/code match
    result = _alias_match(mentioned, entities)
    if result:
        return {**result, "strategy": "alias"}

    # Strategy 3: Fuzzy match (typo tolerance)
    # Build simple lookup map for fuzzy matching
    lookup_map = {e.get(lookup_field, "").lower(): str(e["_id"]) for e in entities if e.get(lookup_field)}
    fuzzy_id = _fuzzy_match(mentioned, lookup_map, threshold=0.75)
    if fuzzy_id:
        # Find matched entity name
        for e in entities:
            if str(e["_id"]) == fuzzy_id:
                return {"id": fuzzy_id, "confidence": 0.80, "matched_name": e[lookup_field], "strategy": "fuzzy"}

    # Strategy 4: Abbreviation match
    result = _abbreviation_match(mentioned, entities, lookup_field)
    if result:
        return {**result, "strategy": "abbreviation"}

    # No match found
    return None


def _resolve_entities(parsed: dict, projects: list, team_members: list) -> dict:
    """Map parsed names to database IDs using exact + fuzzy matching."""
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
        name = update.get("team_member_name", "")
        update["team_member_id"] = _fuzzy_match(name, team_map)
        proj = update.get("project_name", "")
        update["project_id"] = _fuzzy_match(proj, project_map)

    # Resolve client_updates
    for cu in parsed.get("client_updates", []):
        proj = cu.get("project_name", "")
        cu["project_id"] = _fuzzy_match(proj, project_map)

    # Resolve blockers
    for b in parsed.get("blockers", []):
        proj = b.get("project_name", "")
        b["project_id"] = _fuzzy_match(proj, project_map)

    # Resolve action items
    for ai_item in parsed.get("action_items", []):
        assigned = ai_item.get("assigned_to", "")
        if assigned and assigned.lower() != "self":
            ai_item["assigned_to_id"] = _fuzzy_match(assigned, team_map)

    return parsed


# ---------------------------------------------------------------------------
# Post-Parse Validation
# ---------------------------------------------------------------------------

def _validate_assignments(parsed: dict, projects: list, team_members: list) -> dict:
    """Validate and flag mismatches between parsed data and known assignments."""
    # Build quick lookup: team_member_id -> set of project_ids they're assigned to
    member_projects = {}
    for t in team_members:
        tid = str(t["_id"])
        member_projects[tid] = set(t.get("project_ids", []))

    # Build project name lookup
    proj_name_by_id = {str(p["_id"]): p["name"] for p in projects}

    warnings = []
    for tu in parsed.get("team_updates", []):
        mid = tu.get("team_member_id")
        pid = tu.get("project_id")
        if mid and pid:
            assigned_pids = member_projects.get(mid, set())
            if pid not in assigned_pids:
                pname = tu.get("project_name", "?")
                mname = tu.get("team_member_name", "?")
                warnings.append(
                    f"{mname} is not assigned to {pname} — verify this update"
                )
                tu["_warning"] = f"Not assigned to {pname}"

    if warnings:
        existing_notes = parsed.get("general_notes", "") or ""
        parsed["general_notes"] = (
            existing_notes + "\n\nASSIGNMENT WARNINGS:\n" + "\n".join(f"- {w}" for w in warnings)
        ).strip()
        logger.warning(f"Validation warnings: {warnings}")

    return parsed


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def _fallback_parse(text: str) -> dict:
    """Return a basic parsed structure when AI is unavailable."""
    return {
        "team_updates": [],
        "client_updates": [],
        "action_items": [],
        "blockers": [],
        "general_notes": text,
    }
