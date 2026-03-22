"""Team logo downloading and name-to-slug mapping for NCAA teams."""

import os
import time

import requests

# Map display names to ncaa-api slugs for teams that don't follow the default pattern
SLUG_OVERRIDES = {
    # Abbreviations / short names
    "Michigan St": "michigan-st",
    "Michigan State": "michigan-st",
    "Mississippi St": "mississippi-st",
    "Mississippi State": "mississippi-st",
    "Iowa St": "iowa-st",
    "Iowa State": "iowa-st",
    "Colorado St": "colorado-st",
    "Colorado State": "colorado-st",
    "San Diego St": "san-diego-st",
    "San Diego State": "san-diego-st",
    "Norfolk St": "norfolk-st",
    "Norfolk State": "norfolk-st",
    "S Dakota St": "south-dakota-st",
    "South Dakota St": "south-dakota-st",
    "St. Mary's": "st-marys-ca",
    "Saint Mary's": "st-marys-ca",
    "St. John's": "st-johns-ny",
    "Saint John's": "st-johns-ny",
    "Texas A&M": "texas-am",
    "Ole Miss": "ole-miss",
    "SIU Edwardsville": "siu-edwardsville",
    "SIUE": "siu-edwardsville",
    "UC San Diego": "uc-san-diego",
    "UC Irvine": "uc-irvine",
    "VCU": "vcu",
    "BYU": "byu",
    "UCLA": "ucla",
    "UConn": "uconn",
    "UNLV": "unlv",
    "LSU": "lsu",
    "USC": "usc",
    "TCU": "tcu",
    "FGCU": "florida-gulf-coast",
    "IUPUI": "iupui",
    "SF Austin": "stephen-f-austin",
    "Middle Tenn": "middle-tennessee",
    "SE Louisiana": "southeastern-louisiana",
    "E Washington": "eastern-washington",
    "UT Martin": "ut-martin",
    "North Carolina": "north-carolina",
    "Georgia Tech": "georgia-tech",
    "NC State": "nc-state",
    "Virginia Tech": "virginia-tech",
    "Michigan St": "michigan-st",
    "Florida St": "florida-st",
    "Florida State": "florida-st",
    "Grand Canyon": "grand-canyon",
    "Robert Morris": "robert-morris",
    "Green Bay": "green-bay",
    "High Point": "high-point",
    "Sacred Heart": "sacred-heart",
    "Illinois St": "illinois-st",
    "Illinois State": "illinois-st",
    "Texas Tech": "texas-tech",
    "New Mexico": "new-mexico",
    "Wake Forest": "wake-forest",
    "Boston College": "boston-college",
    "Ohio St": "ohio-st",
    "Ohio State": "ohio-st",
    "Penn St": "penn-st",
    "Penn State": "penn-st",
}


def team_name_to_slug(name):
    """Convert a team display name to an ncaa-api slug.

    Examples:
        "Houston" -> "houston"
        "Michigan St" -> "michigan-st"
        "St. John's" -> "st-johns-ny"
        "Texas A&M" -> "texas-am"
    """
    if name in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[name]

    # Default conversion: lowercase, replace spaces with hyphens, strip punctuation
    slug = name.lower()
    slug = slug.replace("&", "")
    slug = slug.replace("'", "")
    slug = slug.replace(".", "")
    slug = slug.replace("  ", " ")
    slug = slug.strip().replace(" ", "-")
    return slug


def download_team_logo(slug, cache_dir, size=24):
    """Download an SVG logo and convert to PNG.

    Args:
        slug: ncaa-api team slug
        cache_dir: directory to cache converted PNGs
        size: output PNG size in pixels

    Returns:
        path to PNG file, or None if download/conversion failed
    """
    os.makedirs(cache_dir, exist_ok=True)
    png_path = os.path.join(cache_dir, f"{slug}_{size}.png")

    # Use cache if available
    if os.path.exists(png_path) and os.path.getsize(png_path) > 0:
        return png_path

    url = f"https://ncaa-api.henrygd.me/logo/{slug}.svg"
    try:
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Annie-Madness-Tracker/1.0"
        })
        if resp.status_code != 200:
            return None

        svg_bytes = resp.content
        if not svg_bytes or len(svg_bytes) < 50:
            return None

        # Convert SVG to PNG using cairosvg
        import cairosvg
        cairosvg.svg2png(
            bytestring=svg_bytes,
            write_to=png_path,
            output_width=size,
            output_height=size,
        )
        return png_path

    except Exception:
        return None


def download_all_logos(team_names, cache_dir, size=24):
    """Download logos for all teams.

    Args:
        team_names: list of team display names
        cache_dir: directory to cache logos
        size: output PNG size in pixels

    Returns:
        dict mapping team name -> PIL Image or None
    """
    from PIL import Image

    logos = {}
    seen_slugs = set()

    for name in team_names:
        if not name or name == "TBD":
            continue
        slug = team_name_to_slug(name)
        if slug in seen_slugs:
            # Already downloaded for a different name variant
            for prev_name, prev_img in logos.items():
                if team_name_to_slug(prev_name) == slug:
                    logos[name] = prev_img
                    break
            continue

        seen_slugs.add(slug)
        path = download_team_logo(slug, cache_dir, size)
        if path:
            try:
                img = Image.open(path).convert("RGBA")
                logos[name] = img
            except Exception:
                logos[name] = None
        else:
            logos[name] = None

        time.sleep(0.1)  # respect rate limits

    return logos
