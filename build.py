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
from src.render_brackets import render_all_brackets
from src.generate_site import generate_site

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")

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
    print("\n[1/4] Fetching tournament data...")
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

    # Step 2: Render bracket images
    print("\n[2/4] Rendering bracket images...")
    try:
        image_paths = render_all_brackets(mens_data, womens_data, IMAGES_DIR)
        for name, path in image_paths.items():
            print(f"  {name}: {os.path.basename(path)}")
    except Exception as e:
        print(f"  Error rendering brackets: {e}")
        raise

    # Step 3: Fetch news stories
    print("\n[3/4] Fetching tournament stories...")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    mens_news = fetch_news("men", api_key)
    womens_news = fetch_news("women", api_key)
    print(f"  Men's stories: {len(mens_news)}")
    print(f"  Women's stories: {len(womens_news)}")

    # Step 4: Generate static site
    print("\n[4/4] Generating static site...")
    index_path = generate_site(mens_data, womens_data, mens_news, womens_news, OUTPUT_DIR)
    print(f"  Output: {index_path}")

    print("\n" + "=" * 60)
    print("Build complete!")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
