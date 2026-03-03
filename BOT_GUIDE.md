# PM Update Tool — Telegram Bot Guide

## Overview

The PM Update Tool bot is an AI-powered Telegram assistant that helps you track daily project updates, team activities, blockers, and action items. Send updates in natural language and the bot will parse, categorize, and store everything automatically.

**Key capabilities:**
- Understands natural language, Hinglish, and developer shorthand
- Parses team member updates, project status, blockers, and action items
- Extracts information from screenshots (chat logs, project boards, emails)
- Generates daily briefs and weekly reports with AI summaries
- Auto-creates unknown projects, team members, and clients on the fly

---

## Getting Started

1. Start the bot by sending `/start`
2. The bot will reply with your **chat ID** — share this with your admin to get authorized
3. Once authorized, simply type or paste your daily updates

---

## Sending Updates

### Text Updates

Just send your update naturally. The bot understands many formats:

```
Yash fixed the login bug on B2B Portal. Shobhit pushed API docs PR.
```

```
Rahul is 80% done with the payment gateway on EcomApp.
Blocked on API keys from the client.
```

```
Had a call with ABC Corp — they want the dashboard redesign by Friday.
Priya started the new onboarding flow, will finish tomorrow.
```

### What the Bot Understands

| Input | How the Bot Interprets It |
|-------|---------------------------|
| "done", "fixed", "completed", "pushed", "merged" | Status: **Completed** |
| "working on", "doing", "started" | Status: **In Progress** |
| "stuck", "blocked", "waiting" | Status: **Blocked** |
| "will start", "tomorrow", "next" | Status: **Not Started** |
| "80% done" | Progress: **80%** |
| "almost done" | Progress: **~90%** |
| "half done" | Progress: **~50%** |
| "just started" | Progress: **~10%** |

### Screenshots

Send a screenshot (photo) with or without a caption. The bot uses AI vision to extract:
- People mentioned
- Projects and tasks
- Action items and blockers
- Key data points

Works with screenshots of: chat conversations, project boards (Jira, Trello), emails, spreadsheets, and more.

### Hinglish & Shorthand

The bot understands Indian English and common developer slang:
- "Yash ne login fix kar diya" → Yash completed login fix
- "PR merge ho gaya" → PR completed/merged
- "Client se call hua, urgent changes chahiye" → Client update with urgent sentiment

---

## Commands Reference

### Input Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message, setup info, and your chat ID |
| `/help` | Show all available commands |
| `/undo` | Delete the last submitted update for today |

### Review Commands

| Command | Description |
|---------|-------------|
| `/status` | Quick counts — total updates, team activities, action items, blockers for today |
| `/today` | Detailed view of all parsed updates grouped by project |
| `/pending` | Show which team members have updates today and who is missing |
| `/projects` | List all active projects with health status indicators |
| `/team` | List all active team members with roles and project counts |
| `/reminders` | Show active reminders (sync needed, unresolved items, etc.) |

### Action Commands

| Command | Description |
|---------|-------------|
| `/report` | Generate and send the daily brief to management (email + Telegram) |
| `/week` | Generate and send the weekly report to management (uses Pro AI for high-quality synthesis) |
| `/sync` | Re-sync projects and team members from the reference database |

---

## How AI Parsing Works

When you send an update, the bot:

1. **Builds context** — Fetches all active projects, team members, their assignments, and recent activity from the database
2. **Sends to Gemini AI** — The full context + your message is sent to Google Gemini for parsing
3. **Extracts structured data:**
   - **Team updates** — Who did what, on which project, with status and progress
   - **Client updates** — Client interactions with sentiment (positive/negative/urgent)
   - **Action items** — Tasks to be done, assigned to whom, priority level
   - **Blockers** — What's blocked, severity, whether it needs escalation
4. **Resolves entities** — Matches names to known team members and projects using:
   - Exact name matching
   - Nickname and alias matching
   - Project code matching
   - Fuzzy matching (handles typos)
   - Abbreviation matching
5. **Validates** — Checks if team members are actually assigned to the mentioned projects

### AI Models Used

| Priority | Model | Use Case |
|----------|-------|----------|
| 1st | `gemini-2.5-flash` | Fast + high quality (primary) |
| 2nd | `gemini-2.5-pro` | Highest quality (fallback) |
| 3rd | `gemini-2.0-flash` | Stable older model (last resort) |

If the primary model hits rate limits or is unavailable, the bot automatically tries the next model.

---

## Auto-Entity Creation

If you mention a project, team member, or client that doesn't exist in the database, the bot will **automatically create it** and notify you:

```
Got it! Parsed: NewPerson on NewProject.

⚠️ Auto-created:
- Project: NewProject
- Team Member: NewPerson

💡 Add these to your reference database and run /sync for full features.
```

Auto-created entities are marked with `auto_created: true` and `needs_reference_sync: true` so you can review them later.

---

## Reports

### Daily Brief (`/report`)

Generates a daily summary including:
- Per-project team updates
- Client interactions with sentiment
- Action items ranked by priority
- Blockers ranked by severity
- AI-generated executive summary (3-5 sentences)

**Delivered via:** Email to management + Telegram message

### Weekly Report (`/week`)

Synthesizes all daily reports for the week into a high-level summary:
- Key highlights (3-5 bullets)
- Project-wise progress with status
- Blockers and risks
- Action items carried forward
- Team productivity overview
- Management attention items
- Recommendations for next week

**Uses Gemini Pro** for higher quality synthesis.

**Delivered via:** Email to management + Telegram message

### Automated Scheduling

Reports can also be generated automatically:
- **Daily brief**: Configurable time (default: 18:00 IST)
- **Weekly report**: Configurable day and time (default: Friday 18:00 IST)
- **No-update reminder**: Sends alert if no updates by configured time (default: 17:00 IST)

---

## Tips for Best Results

1. **Use full names** — "Yash Sharma" works better than "YS" (though the bot handles nicknames after `/sync`)
2. **Mention the project** — "Yash fixed login on B2B Portal" gives better results than just "Yash fixed login"
3. **Be specific about status** — "completed", "in progress", "blocked" are clearer than vague descriptions
4. **Include percentages** — "80% done" gives the bot concrete progress data
5. **Flag blockers explicitly** — "Blocked on API keys" ensures blockers are tracked
6. **Send updates throughout the day** — The bot deduplicates, so multiple updates are fine
7. **Use /today to review** — Check what the bot parsed before generating the daily report
8. **Run /sync after adding people** — Keep the reference database in sync for best matching
9. **Send screenshots** — Chat logs, board screenshots, and emails are all understood
10. **Use /undo if needed** — Made a mistake? Delete the last update and resend
