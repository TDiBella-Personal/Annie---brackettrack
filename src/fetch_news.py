"""Fetch tournament news stories using Anthropic API with web_search tool."""

import json
import os
from datetime import datetime


def fetch_news(gender, api_key=None):
    """Fetch 5 human interest stories for the given tournament.

    Args:
        gender: 'men' or 'women'
        api_key: Anthropic API key (falls back to env var)

    Returns:
        list of dicts with title, summary, source_url, source_name
    """
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return _sample_news(gender)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        tournament = f"Men's" if gender == "men" else "Women's"

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            tools=[{"type": "web_search_20250305"}],
            messages=[
                {
                    "role": "user",
                    "content": f"""You are a sports news curator for a teacher's daily March Madness briefing.

Search for today's NCAA {tournament} tournament news stories focused on human interest angles about players. Look for: emotional backstories, family stories, underdog narratives, records broken, milestone moments, players overcoming adversity, heartwarming sportsmanship, and surprise performances.

Target sources: ESPN, CBS Sports, The Athletic, Yahoo Sports, NBC Sports, NCAA.com

Return ONLY a JSON array of exactly 5 objects. No other text.
Each object has:
- "title": short headline (10 words max)
- "summary": the story in 50 words or fewer
- "source_url": direct link to the article
- "source_name": publication name

Focus on stories from the last 24 hours. Prioritize stories a teacher could use as conversation starters with high school or college students.""",
                }
            ],
        )

        # Extract text from response
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text
                break

        if text:
            # Try to parse JSON from the response
            text = text.strip()
            # Handle markdown code blocks
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                if text.startswith("json"):
                    text = text[4:].strip()

            stories = json.loads(text)
            if isinstance(stories, list) and len(stories) > 0:
                # Validate and clean
                cleaned = []
                for s in stories[:5]:
                    cleaned.append({
                        "title": str(s.get("title", "Tournament Update"))[:80],
                        "summary": str(s.get("summary", ""))[:300],
                        "source_url": str(s.get("source_url", "#")),
                        "source_name": str(s.get("source_name", "ESPN")),
                    })
                return cleaned

    except Exception as e:
        print(f"Warning: Failed to fetch news via Anthropic API: {e}")

    return _sample_news(gender)


def _sample_news(gender):
    """Return sample news stories when API is unavailable."""
    if gender == "men":
        return [
            {
                "title": "Cinderella Run Captures Nation's Heart",
                "summary": "A mid-major program makes its deepest tournament run ever, led by a senior guard who walked on as a freshman and earned a scholarship through sheer determination.",
                "source_url": "#",
                "source_name": "ESPN",
            },
            {
                "title": "Coach Returns to Alma Mater for Sweet 16",
                "summary": "A first-year head coach leads his alma mater back to the Sweet 16 for the first time in 20 years, fulfilling a promise he made as a player.",
                "source_url": "#",
                "source_name": "CBS Sports",
            },
            {
                "title": "Father and Son Share March Madness Moment",
                "summary": "A freshman forward hits the game-winning shot while his father, a former player at the same school, watches from the stands in tears.",
                "source_url": "#",
                "source_name": "The Athletic",
            },
            {
                "title": "Player Overcomes Injury for Tournament Return",
                "summary": "After missing most of the season with a torn ACL, a junior center returns to the court just in time for March, providing a crucial spark off the bench.",
                "source_url": "#",
                "source_name": "Yahoo Sports",
            },
            {
                "title": "Small Town Rallies Behind Local Hero",
                "summary": "A tiny college town of 3,000 people sees its main street painted in school colors as their team advances past the first weekend for the first time ever.",
                "source_url": "#",
                "source_name": "NBC Sports",
            },
        ]
    else:
        return [
            {
                "title": "Record-Breaking Point Guard Makes History",
                "summary": "A junior point guard breaks the all-time tournament assist record while leading her team to the Elite Eight, crediting her grandmother who taught her to play.",
                "source_url": "#",
                "source_name": "ESPN",
            },
            {
                "title": "Twin Sisters Face Off in Sweet 16",
                "summary": "For the first time in tournament history, twin sisters compete against each other, with both earning starting roles at different Power 5 programs.",
                "source_url": "#",
                "source_name": "CBS Sports",
            },
            {
                "title": "Walk-On Becomes Tournament Star Overnight",
                "summary": "A former walk-on who almost quit basketball scores 28 points in an upset win, becoming the feel-good story of the tournament.",
                "source_url": "#",
                "source_name": "The Athletic",
            },
            {
                "title": "Coach Dedicates Win to Late Mentor",
                "summary": "An emotional post-game interview goes viral as a coach dedicates her team's victory to her former coach who passed away earlier this season.",
                "source_url": "#",
                "source_name": "Yahoo Sports",
            },
            {
                "title": "International Player Inspires Young Fans",
                "summary": "A center from a small European country becomes a fan favorite, with children from her hometown watching games at 3 AM to cheer her on.",
                "source_url": "#",
                "source_name": "NBC Sports",
            },
        ]
