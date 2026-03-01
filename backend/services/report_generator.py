from collections import defaultdict
from datetime import datetime, timedelta
import json

import google.generativeai as genai
from jinja2 import Environment, FileSystemLoader
import os

from backend.database import get_db
from backend.config import settings
from backend.utils.date_helpers import format_date_display, week_boundaries
from backend.utils.text_formatters import markdown_to_whatsapp

# Jinja2 environment for email templates
_template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
_jinja_env = Environment(loader=FileSystemLoader(_template_dir))


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

    # Generate HTML from template
    try:
        template = _jinja_env.get_template("daily_brief.html")
        html = template.render(
            date=date,
            date_display=format_date_display(date),
            projects=dict(project_data),
            action_items=all_action_items,
            blockers=all_blockers,
            update_count=len(updates),
        )
    except Exception:
        html = f"<pre>{markdown}</pre>"

    # Plain text for WhatsApp
    plain = markdown_to_whatsapp(markdown)

    # Store report
    report_doc = {
        "type": "daily",
        "date": date,
        "week_start": None,
        "week_end": None,
        "content_markdown": markdown,
        "content_html": html,
        "content_plain": plain,
        "delivery_status": {
            "email": {"sent": False, "sent_at": None, "error": None},
            "whatsapp": {"sent": False, "sent_at": None, "error": None},
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
                lines.append(f"- {tu.get('summary', '')} [{status_tag}]")
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
            lines.append(f"{i}. [{priority}] {ai.get('description', '')} (Assigned: {assigned})")
        lines.append("")

    if blockers:
        lines.append("### Blockers")
        for i, b in enumerate(blockers, 1):
            severity = b.get("severity", "medium").upper()
            lines.append(
                f"{i}. [{severity}] {b.get('project_name', '')}: "
                f"{b.get('description', '')} - blocking {b.get('blocking_who', 'N/A')}"
            )
        lines.append("")

    return "\n".join(lines)


async def generate_weekly_report(week_end_date: str) -> dict | None:
    """Generate a synthesized weekly report.

    Uses Gemini to create a high-level summary from daily reports.
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

    # Use Gemini to synthesize a weekly summary
    if settings.gemini_api_key:
        weekly_markdown = await _synthesize_weekly_with_ai(all_daily_content, week_start, week_end)
    else:
        weekly_markdown = f"## Weekly Summary - {week_start} to {week_end}\n\n{all_daily_content}"

    # Generate HTML
    try:
        template = _jinja_env.get_template("weekly_report.html")
        html = template.render(
            week_start=week_start,
            week_end=week_end,
            content=weekly_markdown,
        )
    except Exception:
        html = f"<pre>{weekly_markdown}</pre>"

    plain = markdown_to_whatsapp(weekly_markdown)

    report_doc = {
        "type": "weekly",
        "date": week_end,
        "week_start": week_start,
        "week_end": week_end,
        "content_markdown": weekly_markdown,
        "content_html": html,
        "content_plain": plain,
        "delivery_status": {
            "email": {"sent": False, "sent_at": None, "error": None},
            "whatsapp": {"sent": False, "sent_at": None, "error": None},
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


async def _synthesize_weekly_with_ai(daily_content: str, week_start: str, week_end: str) -> str:
    """Use Gemini to create a synthesized weekly summary."""
    prompt = f"""Given the following daily project management briefs from the week of {week_start} to {week_end},
create a concise WEEKLY SUMMARY. Organize by project. For each project include:
- Overall progress this week (1-2 sentences)
- Key accomplishments (bullet points)
- Outstanding blockers
- Upcoming priorities (inferred)

Also include sections for:
- Cross-project action items still pending
- Client relationship status per project
- Items needing management attention

Daily briefs:
{daily_content}

Return the summary as clean markdown."""

    try:
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(temperature=0.3),
        )
        return response.text
    except Exception as e:
        print(f"Weekly synthesis error: {e}")
        return f"## Weekly Summary - {week_start} to {week_end}\n\n[AI synthesis unavailable]\n\n{daily_content}"
