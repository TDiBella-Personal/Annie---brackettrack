"""Generate the static HTML site from tournament data."""

import os
import shutil
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from src.team_logos import team_name_to_slug


def generate_site(mens_data, womens_data, mens_news, womens_news, output_dir, highlight_photos=None):
    """Generate the complete static site.

    Args:
        mens_data: dict from fetch_tournament_data for men
        womens_data: dict from fetch_tournament_data for women
        mens_news: list of news story dicts for men's tournament
        womens_news: list of news story dicts for women's tournament
        output_dir: directory to write output files
        highlight_photos: list of highlight photo dicts (optional)
    """
    os.makedirs(output_dir, exist_ok=True)

    # Set up Jinja2
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    env.filters["team_slug"] = team_name_to_slug
    template = env.get_template("index.html.j2")

    # Determine if data is stale
    stale = mens_data.get("stale", False) or womens_data.get("stale", False)
    data_source = mens_data.get("source", "unknown")

    # Format update time
    now = datetime.now()
    updated_time = now.strftime("%B %d, %Y at %I:%M %p EST")

    # Render
    html = template.render(
        updated_time=updated_time,
        stale=stale,
        data_source=data_source,
        mens_todays_games=mens_data.get("todays_games", []),
        mens_last_results=mens_data.get("last_results", []),
        mens_news=mens_news,
        womens_todays_games=womens_data.get("todays_games", []),
        womens_last_results=womens_data.get("last_results", []),
        womens_news=womens_news,
        highlight_photos=highlight_photos or [],
    )

    # Write index.html
    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, "w") as f:
        f.write(html)

    # Copy Grogu icon to output
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
    icon_src = os.path.join(assets_dir, "grogu-icon.svg")
    if os.path.exists(icon_src):
        shutil.copy2(icon_src, os.path.join(output_dir, "grogu-icon.svg"))

    return index_path
