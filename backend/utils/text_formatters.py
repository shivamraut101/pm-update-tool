import re


def markdown_to_plain_text(text: str) -> str:
    """Convert markdown formatting to simplified plain text for Telegram/messaging."""
    # Convert ## headers to *BOLD CAPS*
    text = re.sub(
        r"^##\s+(.+)$",
        lambda m: f"*{m.group(1).upper()}*",
        text,
        flags=re.MULTILINE,
    )
    # Convert ### headers to *bold*
    text = re.sub(
        r"^###\s+(.+)$",
        lambda m: f"*{m.group(1)}*",
        text,
        flags=re.MULTILINE,
    )
    # Convert **bold** to *bold* (single asterisk for messaging apps)
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Convert `code` to ```code```
    text = re.sub(r"`([^`]+)`", r"```\1```", text)
    # Convert --- to a line separator
    text = re.sub(r"^---+$", "─" * 30, text, flags=re.MULTILINE)
    return text


def truncate_text(text: str, max_length: int = 1500) -> list:
    """Split text into chunks suitable for messaging (1600 char limit)."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = ""
    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 > max_length:
            if current:
                chunks.append(current.strip())
            current = paragraph
        else:
            if current:
                current += "\n\n" + paragraph
            else:
                current = paragraph
    if current:
        chunks.append(current.strip())

    return chunks
