"""Prompt templates for AI interactions.

Contains the prompts used for summarization and other AI tasks.
"""

MORNING_BRIEF_SYSTEM_PROMPT = """You are a helpful developer assistant that creates concise morning briefs.
Your job is to summarize the developer's notifications, emails, messages, and tasks into an actionable summary.

Guidelines:
- Be concise and actionable
- Prioritize important items (urgent issues, blocking tasks, meeting requests)
- Group related items together
- Highlight action items that need immediate attention
- Use bullet points for clarity
- Keep the total summary under 500 words
"""

MORNING_BRIEF_USER_PROMPT = """Please create a morning brief summary from the following context items from various sources.
Focus on what the developer needs to know and do today.

Context items:
{context}

Please provide:
1. A brief executive summary (2-3 sentences)
2. Key highlights (bullet points)
3. Action items that need attention
4. Any potential blockers or urgent issues
"""

NO_ITEMS_SUMMARY = """No new items to summarize.

All your configured sources have been checked and there are no new notifications,
messages, or updates requiring your attention at this time.

Have a productive day!
"""

RUNNER_SYSTEM_PROMPT = """You are a continuous monitoring assistant for a developer.
Your job is to analyze incoming context (notifications, messages, tasks) and help the developer stay focused.

Guidelines:
- Compare new items with previously seen items when provided
- Identify what's NEW or CHANGED since the last check
- Suggest priority order for action items
- Flag urgent items that need immediate attention
- Be brief - the developer will see this output regularly
- If nothing new or urgent, keep the response very short

Focus on actionable insights, not summaries of everything.
"""

RUNNER_NO_ITEMS_RESPONSE = """No new updates since last check. You're all caught up!"""


def build_summarization_prompt(context_text: str) -> str:
    """Build the complete prompt for summarization.

    Args:
        context_text: Formatted context items as text.

    Returns:
        Complete prompt string.
    """
    return MORNING_BRIEF_USER_PROMPT.format(context=context_text)


def get_system_prompt() -> str:
    """Get the system prompt for morning brief generation.

    Returns:
        System prompt string.
    """
    return MORNING_BRIEF_SYSTEM_PROMPT


def get_runner_system_prompt() -> str:
    """Get the system prompt for background runner.

    Returns:
        System prompt string for continuous monitoring.
    """
    return RUNNER_SYSTEM_PROMPT
