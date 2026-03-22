#!/usr/bin/env python3
"""Annie's Madness Tracker - Build Script

Orchestrates fetching tournament data, generating bracket images,
fetching news stories, and building the static site.
"""

import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.fetch_scores import fetch_tournament_data, generate_sample_data
from src.fetch_news import fetch_news
from src.fetch_photos import fetch_highlight_photos
from src.render_brackets import render_all_brackets
from src.generate_site import generate_site
from src.team_logos import download_all_logos

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
LOGOS_CACHE = os.path.join(os.path.dirname(__file__), "cache", "logos")

# Tournament active window (adjust yearly)
TOURNAMENT_START = datetime(2026, 3, 15)  # Selection Sunday
TOURNAMENT_END = datetime(2026, 4, 7)     # Day after Championship


def is_tournament_active():
    """Check if we're within the tournament window."""
    now = datetime.now()
    # Allow a buffer of 2 days before and after
    return (TOURNAMENT_START.replace(day=TOURNAMENT_START.day - 2) <= now
            <= TOURNAMENT_END.replace(day=TOURNAMENT_END.day + 2))


def main():
    print("=" * 60)
    print("Annie's Madness Tracker - Building site")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    use_sample = os.environ.get("USE_SAMPLE_DATA", "").lower() in ("1", "true", "yes")

    # Step 1: Fetch tournament data
    print("\n[1/5] Fetching tournament data...")
    if use_sample:
        print("  Using sample data (USE_SAMPLE_DATA=true)")
        mens_data = generate_sample_data("men")
        womens_data = generate_sample_data("women")
    else:
        try:
            mens_data = fetch_tournament_data("men")
            print(f"  Men's data source: {mens_data['source']}")
        except Exception as e:
            print(f"  Warning: Failed to fetch men's data: {e}")
            print("  Falling back to sample data")
            mens_data = generate_sample_data("men")

        try:
            womens_data = fetch_tournament_data("women")
            print(f"  Women's data source: {womens_data['source']}")
        except Exception as e:
            print(f"  Warning: Failed to fetch women's data: {e}")
            print("  Falling back to sample data")
            womens_data = generate_sample_data("women")

    # Step 2: Download team logos
    print("\n[2/5] Downloading team logos...")
    mens_teams = [t["name"] for t in mens_data.get("bracket_state", {}).get("teams", [])]
    womens_teams = [t["name"] for t in womens_data.get("bracket_state", {}).get("teams", [])]
    # Also include teams from today's games
    for game in mens_data.get("todays_games", []) + mens_data.get("last_results", []):
        for side in ("home", "away"):
            name = game.get(side, {}).get("name", "")
            if name and name not in mens_teams:
                mens_teams.append(name)
    for game in womens_data.get("todays_games", []) + womens_data.get("last_results", []):
        for side in ("home", "away"):
            name = game.get(side, {}).get("name", "")
            if name and name not in womens_teams:
                womens_teams.append(name)

    try:
        mens_logos = download_all_logos(mens_teams, LOGOS_CACHE, size=24)
        womens_logos = download_all_logos(womens_teams, LOGOS_CACHE, size=24)
        mens_found = sum(1 for v in mens_logos.values() if v is not None)
        womens_found = sum(1 for v in womens_logos.values() if v is not None)
        print(f"  Men's logos: {mens_found}/{len(mens_teams)}")
        print(f"  Women's logos: {womens_found}/{len(womens_teams)}")
    except Exception as e:
        print(f"  Warning: Failed to download logos: {e}")
        mens_logos = {}
        womens_logos = {}

    # Step 3: Render bracket images
    print("\n[3/5] Rendering bracket images...")
    try:
        image_paths = render_all_brackets(
            mens_data, womens_data, IMAGES_DIR,
            mens_logos=mens_logos, womens_logos=womens_logos,
        )
        for name, path in image_paths.items():
            print(f"  {name}: {os.path.basename(path)}")
    except Exception as e:
        print(f"  Error rendering brackets: {e}")
        raise

    # Step 4: Fetch news stories and highlight photos
    print("\n[4/5] Fetching tournament stories...")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    mens_news = fetch_news("men", api_key)
    womens_news = fetch_news("women", api_key)
    print(f"  Men's stories: {len(mens_news)}")
    print(f"  Women's stories: {len(womens_news)}")

    print("\n  Fetching highlight photos...")
    highlight_photos = fetch_highlight_photos(api_key, IMAGES_DIR)
    print(f"  Photos found: {len(highlight_photos)}")

    # Step 5: Generate static site
    print("\n[5/5] Generating static site...")
    index_path = generate_site(
        mens_data, womens_data, mens_news, womens_news, OUTPUT_DIR,
        highlight_photos=highlight_photos,
    )
    print(f"  Output: {index_path}")

    print("\n" + "=" * 60)
    print("Build complete!")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
