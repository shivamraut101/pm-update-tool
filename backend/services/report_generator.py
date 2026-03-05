from collections import defaultdict
from datetime import datetime, timedelta
import json
import re

import google.generativeai as genai
from jinja2 import Environment, FileSystemLoader
import markdown
import os

from backend.database import get_db
from backend.config import settings
from backend.utils.date_helpers import format_date_display, week_boundaries
from backend.utils.text_formatters import markdown_to_plain_text
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Jinja2 environment for email templates
_template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
_jinja_env = Environment(loader=FileSystemLoader(_template_dir))

# Models for daily brief AI enhancement (speed matters, runs every day)
DAILY_MODELS = [
    "gemini-2.5-flash",           # Best flash: fast + quality
    "gemini-2.0-flash",           # Stable fallback
]

# Models for weekly report synthesis (quality over speed - paid tier)
WEEKLY_SYNTHESIS_MODELS = [
    "gemini-2.5-pro",             # Best pro: highest quality for synthesis
    "gemini-2.5-flash",           # Best flash: fast quality fallback
    "gemini-2.0-flash",           # Older stable fallback
]

WEEKLY_SYSTEM_INSTRUCTION = """You are a senior project management consultant writing weekly reports for C-level management.
Your reports are concise, professional, and action-oriented. You highlight risks early, celebrate wins briefly,
and always end with clear recommendations. You write in a direct, confident style suitable for busy executives."""

DAILY_SYSTEM_INSTRUCTION = """You are a project management assistant that writes concise executive summaries.
You distill a day's worth of team updates into a 3-5 sentence overview that highlights what matters most:
key completions, active risks, and items needing attention. Be direct and concise."""


async def generate_daily_brief(date: str) -> dict | None:
    """Generate a daily brief report for the given date.

    Returns the report document or None if no updates exist.
    """
    db = get_db()
    updates = await db.updates.find({"date": date}).to_list(None)

    if not updates:
        return None

    # Aggregate by project
    project_data = defaultdict(lambda: {
        "team_updates": defaultdict(list),
        "client_updates": [],
    })
    all_action_items = []
    all_blockers = []

    for update in updates:
        parsed = update.get("parsed", {})
        for tu in parsed.get("team_updates", []):
            proj = tu.get("project_name", "Unassigned")
            member = tu.get("team_member_name", "Unknown")
            project_data[proj]["team_updates"][member].append(tu)

        for cu in parsed.get("client_updates", []):
            proj = cu.get("project_name", "Unassigned")
            project_data[proj]["client_updates"].append(cu)

        all_action_items.extend(parsed.get("action_items", []))
        all_blockers.extend(parsed.get("blockers", []))

    # Generate markdown content
    markdown = _build_daily_markdown(date, project_data, all_action_items, all_blockers)

    # Generate AI executive summary (paid tier enhancement)
    executive_summary = ""
    if settings.gemini_api_key and (project_data or all_action_items or all_blockers):
        executive_summary = await _generate_daily_executive_summary(
            markdown, date, len(updates), len(all_blockers)
        )

    # Prepend executive summary to markdown
    if executive_summary:
        full_markdown = (
            f"## Daily Brief - {format_date_display(date)}\n\n"
            f"### Executive Summary\n{executive_summary}\n\n---\n\n"
            f"{markdown}"
        )
    else:
        full_markdown = markdown

    # Generate HTML from template
    try:
        template = _jinja_env.get_template("daily_brief.html")
        html = template.render(
            date=date,
            date_display=format_date_display(date),
            executive_summary=executive_summary,
            projects=dict(project_data),
            action_items=all_action_items,
            blockers=all_blockers,
            update_count=len(updates),
        )
    except Exception:
        html = f"<pre>{full_markdown}</pre>"

    # Plain text for Telegram/plain delivery
    try:
        plain = markdown_to_plain_text(full_markdown)
    except Exception:
        plain = full_markdown

    # Store report
    report_doc = {
        "type": "daily",
        "date": date,
        "week_start": None,
        "week_end": None,
        "executive_summary": executive_summary,
        "content_markdown": full_markdown,
        "content_html": html,
        "content_plain": plain,
        "stats": {
            "update_count": len(updates),
            "project_count": len(project_data),
            "team_member_count": sum(
                len(d["team_updates"]) for d in project_data.values()
            ),
            "action_item_count": len(all_action_items),
            "blocker_count": len(all_blockers),
        },
        "delivery_status": {
            "email": {"sent": False, "sent_at": None, "error": None},
            "telegram": {"sent": False, "sent_at": None, "error": None},
        },
        "source_update_ids": [str(u["_id"]) for u in updates],
        "created_at": datetime.utcnow(),
    }

    # Upsert (replace if same date report already exists)
    result = await db.reports.find_one_and_update(
        {"type": "daily", "date": date},
        {"$set": report_doc},
        upsert=True,
        return_document=True,
    )
    if result:
        report_doc["_id"] = result["_id"]

    return report_doc


async def _generate_daily_executive_summary(
    markdown: str, date: str, update_count: int, blocker_count: int
) -> str:
    """Generate a short AI executive summary for the daily brief."""
    prompt = f"""Here is today's ({date}) raw project brief with {update_count} updates and {blocker_count} blockers:

{markdown}

Write a 3-5 sentence executive summary for senior management. Include:
1. Overall team productivity assessment (how active was the team today)
2. Most significant progress or completion
3. Any risks or blockers that need attention (if any)
4. One recommendation or focus for tomorrow

Keep it under 100 words. Be direct, no fluff. Do not use markdown formatting - plain text only."""

    try:
        genai.configure(api_key=settings.gemini_api_key)
        for model_name in DAILY_MODELS:
            try:
                model = genai.GenerativeModel(
                    model_name,
                    system_instruction=DAILY_SYSTEM_INSTRUCTION,
                )
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.3,
                        max_output_tokens=300,
                    ),
                )
                logger.info(f"Daily executive summary generated with {model_name}")
                return response.text.strip()
            except Exception as e:
                logger.warning(f"Daily summary model {model_name} error: {e}")
                continue
    except Exception as e:
        logger.error(f"Daily executive summary error: {e}")
    return ""


def _build_daily_markdown(date, project_data, action_items, blockers):
    """Build the daily brief in markdown format."""
    lines = [f"## Daily Brief - {format_date_display(date)}", ""]

    for proj_name, data in project_data.items():
        lines.append(f"### {proj_name}")
        lines.append("")

        for member_name, member_updates in data["team_updates"].items():
            lines.append(f"**{member_name}**")
            for tu in member_updates:
                status_tag = tu.get("status", "").upper()
                progress = tu.get("progress_percent")
                progress_str = f" ({progress}%)" if progress is not None else ""
                lines.append(f"- {tu.get('summary', '')} [{status_tag}]{progress_str}")
                if tu.get("details"):
                    lines.append(f"  {tu['details']}")
            lines.append("")

        for cu in data["client_updates"]:
            sentiment = cu.get("sentiment", "neutral").capitalize()
            lines.append(f"**Client Update ({sentiment}):** {cu.get('summary', '')}")
            lines.append("")

        lines.append("---")
        lines.append("")

    if action_items:
        lines.append("### Action Items")
        for i, ai in enumerate(action_items, 1):
            priority = ai.get("priority", "medium").upper()
            assigned = ai.get("assigned_to", "self")
            due = ai.get("due_context", "")
            due_str = f" - Due: {due}" if due else ""
            lines.append(f"{i}. [{priority}] {ai.get('description', '')} (Assigned: {assigned}){due_str}")
        lines.append("")

    if blockers:
        lines.append("### Blockers")
        for i, b in enumerate(blockers, 1):
            severity = b.get("severity", "medium").upper()
            escalation = " NEEDS ESCALATION" if b.get("needs_escalation") else ""
            lines.append(
                f"{i}. [{severity}]{escalation} {b.get('project_name', '')}: "
                f"{b.get('description', '')} - blocking {b.get('blocking_who', 'N/A')}"
            )
        lines.append("")

    return "\n".join(lines)



# ---------------------------------------------------------------------------
# Weekly report markdown → structured data parser
# ---------------------------------------------------------------------------

def _parse_weekly_sections(md_text: str) -> dict:
    """Parse AI-generated weekly markdown into structured template data.

    Returns a dict with keys: executive_summary, highlights, projects,
    blockers, action_items, team_productivity, attention_items, recommendations.
    Falls back to ai_content_html when structured parsing isn't possible.
    """
    result = {
        "executive_summary": "",
        "highlights": [],
        "projects": [],
        "blockers": [],
        "action_items": [],
        "team_productivity": {"active": [], "missing": [], "notes": []},
        "attention_items": [],
        "recommendations": [],
        "ai_content_html": None,
    }

    if not md_text or not md_text.strip():
        return result

    # Split into sections by ## or ### headers
    # Pattern: captures heading level, title, and body
    sections = re.split(r'^(#{2,3})\s+(.+)$', md_text, flags=re.MULTILINE)

    # sections[0] = text before first heading
    # then groups of 3: [level, title, body]
    parsed_sections = {}
    i = 1
    while i < len(sections) - 2:
        level = sections[i]
        title = sections[i + 1].strip()
        body = sections[i + 2].strip()
        parsed_sections[title.lower()] = {"level": level, "title": title, "body": body}
        i += 3

    if not parsed_sections:
        # No sections found — use fallback HTML rendering
        try:
            result["ai_content_html"] = markdown.markdown(
                md_text, extensions=["tables", "fenced_code"]
            )
        except Exception:
            result["ai_content_html"] = f"<pre>{md_text}</pre>"
        return result

    # --- Key Highlights ---
    highlights_body = _find_section(parsed_sections, ["key highlights", "highlights"])
    if highlights_body:
        result["highlights"] = _extract_bullets(highlights_body)

    # --- Executive Summary (preamble text, or body of the top-level ## heading) ---
    preamble = sections[0].strip() if sections[0].strip() else ""
    preamble_lines = [l for l in preamble.split("\n") if not l.strip().startswith("#")]
    preamble_clean = "\n".join(preamble_lines).strip()
    if preamble_clean:
        result["executive_summary"] = _clean_text(preamble_clean)
    else:
        # Check if the first ## heading has introductory body text
        for sec_key, sec_data in parsed_sections.items():
            if sec_data["level"] == "##" and sec_data["body"]:
                # Use the first paragraph of the ## section body as summary
                first_para = sec_data["body"].split("\n\n")[0].strip()
                if first_para and not first_para.startswith("-") and not first_para.startswith("*"):
                    result["executive_summary"] = _clean_text(first_para)
                break

    # --- Project-wise Progress ---
    proj_body = _find_section(parsed_sections, [
        "project-wise progress", "project progress", "projects",
        "project wise progress", "project updates",
    ])
    if proj_body:
        result["projects"] = _parse_projects(proj_body)

    # --- Blockers & Risks ---
    blocker_body = _find_section(parsed_sections, [
        "blockers & risks", "blockers and risks", "blockers",
        "risks", "blockers & risk",
    ])
    if blocker_body:
        result["blockers"] = _parse_blockers(blocker_body)

    # --- Action Items ---
    action_body = _find_section(parsed_sections, [
        "action items carried forward", "action items", "pending action items",
    ])
    if action_body:
        result["action_items"] = _parse_action_items(action_body)

    # --- Team Productivity ---
    team_body = _find_section(parsed_sections, [
        "team productivity", "team performance", "team activity",
    ])
    if team_body:
        result["team_productivity"] = _parse_team_productivity(team_body)

    # --- Management Attention ---
    attn_body = _find_section(parsed_sections, [
        "management attention required", "management attention",
        "needs attention", "escalations",
    ])
    if attn_body:
        result["attention_items"] = _extract_bullets(attn_body)

    # --- Recommendations ---
    rec_body = _find_section(parsed_sections, [
        "recommendations for next week", "recommendations",
        "next week recommendations", "suggestions",
    ])
    if rec_body:
        result["recommendations"] = _extract_bullets(rec_body)

    return result


def _find_section(sections: dict, keys: list[str]) -> str | None:
    """Find a section body by trying multiple key variations."""
    for key in keys:
        for sec_key, sec_data in sections.items():
            if key in sec_key:
                return sec_data["body"]
    return None


def _extract_bullets(text: str) -> list[str]:
    """Extract bullet points from markdown text."""
    bullets = []
    for line in text.split("\n"):
        line = line.strip()
        # Match lines starting with -, *, or numbered (1., 2., etc.)
        m = re.match(r'^[-*]\s+(.+)$', line) or re.match(r'^\d+[.)]\s+(.+)$', line)
        if m:
            bullets.append(_clean_text(m.group(1)))
    # If no bullets found but there's content, split by newlines
    if not bullets and text.strip():
        for line in text.strip().split("\n"):
            cleaned = _clean_text(line.strip())
            if cleaned and not cleaned.startswith("#"):
                bullets.append(cleaned)
    return bullets


def _clean_text(text: str) -> str:
    """Remove markdown bold/italic markers from text."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    return text.strip()


def _parse_projects(body: str) -> list[dict]:
    """Parse the project-wise progress section into structured project data."""
    projects = []

    # Split by bold project names: **Project Name** or #### Project Name
    # Also handles - **Project Name** at top level
    chunks = re.split(r'^(?:[-*]\s+)?\*\*([^*]+)\*\*|^####?\s+(.+)', body, flags=re.MULTILINE)

    i = 1
    while i < len(chunks):
        # Pick whichever group matched
        name = (chunks[i] or chunks[i + 1] or "").strip() if i + 1 < len(chunks) else (chunks[i] or "").strip()
        content = chunks[i + 2].strip() if i + 2 < len(chunks) else ""
        i += 3

        if not name:
            continue

        proj = {"name": name, "summary": "", "status": "", "status_class": "default",
                "accomplishments": [], "next_steps": ""}

        lines = content.split("\n")
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Check for Status line
            status_match = re.search(r'(?:status|overall)[:\s]*\*{0,2}(on track|at risk|blocked|completed|in progress)\*{0,2}', line_stripped, re.IGNORECASE)
            if status_match:
                status_raw = status_match.group(1).strip()
                proj["status"] = status_raw.title()
                proj["status_class"] = status_raw.lower().replace(" ", "-")
                continue

            # Check for Next steps line
            next_match = re.match(r'^[-*]?\s*(?:next\s*steps?|upcoming)[:\s]*(.+)', line_stripped, re.IGNORECASE)
            if next_match:
                proj["next_steps"] = _clean_text(next_match.group(1))
                continue

            # Check for progress summary (first non-bullet line)
            bullet_match = re.match(r'^[-*]\s+(.+)$', line_stripped) or re.match(r'^\d+[.)]\s+(.+)$', line_stripped)
            if bullet_match:
                proj["accomplishments"].append(_clean_text(bullet_match.group(1)))
            elif not proj["summary"] and not line_stripped.startswith("#"):
                proj["summary"] = _clean_text(line_stripped)

        projects.append(proj)

    return projects


def _parse_blockers(body: str) -> list[dict]:
    """Parse blockers section into structured data."""
    blockers = []
    for line in body.split("\n"):
        line = line.strip()
        bullet_match = re.match(r'^[-*]\s+(.+)$', line) or re.match(r'^\d+[.)]\s+(.+)$', line)
        if not bullet_match:
            continue
        text = bullet_match.group(1)

        severity = "medium"
        sev_match = re.search(r'\b(critical|high|medium|low)\b', text, re.IGNORECASE)
        if sev_match:
            severity = sev_match.group(1).lower()

        project = ""
        proj_match = re.match(r'\*\*([^*]+)\*\*[:\s-]*(.+)', text)
        if proj_match:
            project = proj_match.group(1).strip()
            text = proj_match.group(2).strip()

        blockers.append({
            "severity": severity,
            "project": project,
            "description": _clean_text(text),
        })

    return blockers


def _parse_action_items(body: str) -> list[dict]:
    """Parse action items into structured data."""
    items = []
    for line in body.split("\n"):
        line = line.strip()
        bullet_match = re.match(r'^[-*]\s+(.+)$', line) or re.match(r'^\d+[.)]\s+(.+)$', line)
        if not bullet_match:
            continue
        text = bullet_match.group(1)

        priority = "medium"
        prio_match = re.search(r'\b(high|medium|low)\b', text, re.IGNORECASE)
        if prio_match:
            priority = prio_match.group(1).lower()

        items.append({
            "priority": priority,
            "description": _clean_text(text),
        })

    return items


def _parse_team_productivity(body: str) -> dict:
    """Parse team productivity section."""
    result = {"active": [], "missing": [], "notes": []}

    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Check for "no updates from" pattern
        missing_match = re.search(r'no\s+updates?\s+from[:\s]*(.+)', line, re.IGNORECASE)
        if missing_match:
            names = re.split(r'[,;]', missing_match.group(1))
            result["missing"].extend([_clean_text(n) for n in names if n.strip()])
            continue

        # Check for member with count: "Name (X updates)"
        member_match = re.search(r'\*{0,2}([^*:(]+?)\*{0,2}\s*[:(]\s*(\d+)\s*(?:updates?|submissions?)', line, re.IGNORECASE)
        if member_match:
            result["active"].append({
                "name": member_match.group(1).strip(),
                "updates": member_match.group(2),
            })
            continue

        # General bullet point
        bullet_match = re.match(r'^[-*]\s+(.+)$', line) or re.match(r'^\d+[.)]\s+(.+)$', line)
        if bullet_match:
            result["notes"].append(_clean_text(bullet_match.group(1)))

    return result


def _format_week_display(date_str: str) -> str:
    """Format a date string (YYYY-MM-DD) into a nice display format."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%B %d, %Y")
    except Exception:
        return date_str


async def generate_weekly_report(week_end_date: str) -> dict | None:
    """Generate a synthesized weekly report.

    Uses Gemini Pro to create a high-level summary from daily reports.
    """
    db = get_db()
    week_start, week_end = week_boundaries(
        datetime.strptime(week_end_date, "%Y-%m-%d").date()
    )

    # Fetch all daily reports for the week
    daily_reports = await db.reports.find({
        "type": "daily",
        "date": {"$gte": week_start, "$lte": week_end},
    }).to_list(None)

    if not daily_reports:
        return None

    all_daily_content = "\n\n---\n\n".join(
        r.get("content_markdown", "") for r in daily_reports
    )

    # Collect weekly stats
    weekly_stats = {
        "days_with_reports": len(daily_reports),
        "total_updates": sum(r.get("stats", {}).get("update_count", 0) for r in daily_reports),
        "total_blockers": sum(r.get("stats", {}).get("blocker_count", 0) for r in daily_reports),
        "total_action_items": sum(r.get("stats", {}).get("action_item_count", 0) for r in daily_reports),
        "total_projects": 0,
        "total_team_active": 0,
    }

    # Count unique projects and team members across the week
    all_projects = set()
    all_team_members = set()
    for r in daily_reports:
        for proj_name in r.get("project_data", {}).keys():
            all_projects.add(proj_name)
        for proj_name, proj_data in r.get("project_data", {}).items():
            for member_name in proj_data.get("team_updates", {}).keys():
                all_team_members.add(member_name)
    weekly_stats["total_projects"] = len(all_projects)
    weekly_stats["total_team_active"] = len(all_team_members)

    # Collect daily executive summaries for trend input
    daily_summaries = []
    for r in daily_reports:
        es = r.get("executive_summary", "")
        if es:
            daily_summaries.append(f"**{r['date']}:** {es}")

    # Use Gemini to synthesize a weekly summary
    if settings.gemini_api_key:
        weekly_markdown = await _synthesize_weekly_with_ai(
            all_daily_content, week_start, week_end,
            weekly_stats, daily_summaries,
        )
    else:
        weekly_markdown = f"## Weekly Summary - {week_start} to {week_end}\n\n{all_daily_content}"

    # Parse AI markdown into structured sections for rich template rendering
    parsed = _parse_weekly_sections(weekly_markdown)
    logger.info(
        f"Weekly report parsed: {len(parsed['highlights'])} highlights, "
        f"{len(parsed['projects'])} projects, {len(parsed['blockers'])} blockers, "
        f"{len(parsed['action_items'])} action items, "
        f"fallback={'yes' if parsed['ai_content_html'] else 'no'}"
    )

    # If parser extracted projects/team from AI, update stats if needed
    if parsed["projects"] and weekly_stats["total_projects"] == 0:
        weekly_stats["total_projects"] = len(parsed["projects"])
    if parsed["team_productivity"]["active"] and weekly_stats["total_team_active"] == 0:
        weekly_stats["total_team_active"] = len(parsed["team_productivity"]["active"])

    # Generate HTML using the rich template
    try:
        template = _jinja_env.get_template("weekly_report.html")
        html = template.render(
            week_start=week_start,
            week_end=week_end,
            week_start_display=_format_week_display(week_start),
            week_end_display=_format_week_display(week_end),
            stats=weekly_stats,
            executive_summary=parsed["executive_summary"],
            highlights=parsed["highlights"],
            projects=parsed["projects"],
            blockers=parsed["blockers"],
            action_items=parsed["action_items"],
            team_productivity=parsed["team_productivity"],
            attention_items=parsed["attention_items"],
            recommendations=parsed["recommendations"],
            ai_content_html=parsed["ai_content_html"],
        )
    except Exception as e:
        logger.error(f"Weekly template render failed, using fallback: {e}")
        try:
            html = markdown.markdown(weekly_markdown, extensions=["tables", "fenced_code"])
        except Exception:
            html = f"<pre>{weekly_markdown}</pre>"

    try:
        plain = markdown_to_plain_text(weekly_markdown)
    except Exception:
        plain = weekly_markdown

    report_doc = {
        "type": "weekly",
        "date": week_end,
        "week_start": week_start,
        "week_end": week_end,
        "content_markdown": weekly_markdown,
        "content_html": html,
        "content_plain": plain,
        "stats": weekly_stats,
        "delivery_status": {
            "email": {"sent": False, "sent_at": None, "error": None},
            "telegram": {"sent": False, "sent_at": None, "error": None},
        },
        "source_update_ids": [],
        "created_at": datetime.utcnow(),
    }

    result = await db.reports.find_one_and_update(
        {"type": "weekly", "date": week_end},
        {"$set": report_doc},
        upsert=True,
        return_document=True,
    )
    if result:
        report_doc["_id"] = result["_id"]

    return report_doc


async def _synthesize_weekly_with_ai(
    daily_content: str,
    week_start: str,
    week_end: str,
    stats: dict = None,
    daily_summaries: list = None,
) -> str:
    """Use Gemini Pro to create a management-grade weekly summary."""

    stats_context = ""
    if stats:
        stats_context = f"""
WEEK STATISTICS:
- Reports generated: {stats.get('days_with_reports', 0)} out of 5 working days
- Total updates submitted: {stats.get('total_updates', 0)}
- Total blockers raised: {stats.get('total_blockers', 0)}
- Total action items: {stats.get('total_action_items', 0)}
"""

    summaries_context = ""
    if daily_summaries:
        summaries_context = f"""
DAILY EXECUTIVE SUMMARIES (for trend analysis):
{chr(10).join(daily_summaries)}
"""

    prompt = f"""Generate a professional WEEKLY PROJECT SUMMARY for senior management.

Period: {week_start} to {week_end}
{stats_context}
{summaries_context}

DAILY BRIEFS (raw data):
{daily_content}

REQUIRED SECTIONS (use markdown formatting):

## Weekly Project Summary - {week_start} to {week_end}

### Key Highlights
- 3-5 bullet points of the most important things that happened this week

### Project-wise Progress
For each active project:
- **Project Name**
  - Progress summary (1-2 sentences)
  - Key accomplishments (bullet points)
  - Status: On Track / At Risk / Blocked
  - Next steps

### Blockers & Risks
- List all unresolved blockers with severity
- Flag anything that needs management intervention

### Action Items Carried Forward
- Pending action items that need follow-up next week

### Team Productivity
- Which team members were most active
- Any team members with no updates (potential concern)

### Management Attention Required
- Items that explicitly need a decision or escalation from management
- Client situations that need awareness

### Recommendations for Next Week
- 2-3 specific recommendations based on this week's patterns

Keep the tone professional and concise. This goes directly to senior management."""

    try:
        genai.configure(api_key=settings.gemini_api_key)

        last_error = None
        for model_name in WEEKLY_SYNTHESIS_MODELS:
            try:
                model = genai.GenerativeModel(
                    model_name,
                    system_instruction=WEEKLY_SYSTEM_INSTRUCTION,
                )
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.3,
                        max_output_tokens=4096,
                    ),
                )
                logger.info(f"Weekly synthesis success with {model_name}")
                return response.text
            except Exception as e:
                last_error = e
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower():
                    logger.warning(f"Model {model_name} quota exceeded, trying next...")
                elif "404" in error_str or "not found" in error_str.lower():
                    logger.warning(f"Model {model_name} not available, trying next...")
                else:
                    logger.warning(f"Model {model_name} error: {e}, trying next...")
                continue

        # All models failed
        logger.error(f"All weekly synthesis models failed: {last_error}")
        return f"## Weekly Summary - {week_start} to {week_end}\n\n[AI synthesis unavailable]\n\n{daily_content}"
    except Exception as e:
        logger.error(f"Weekly synthesis error: {e}")
        return f"## Weekly Summary - {week_start} to {week_end}\n\n[AI synthesis unavailable]\n\n{daily_content}"
