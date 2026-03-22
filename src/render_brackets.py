"""Render NCAA tournament bracket images using Pillow."""

import os

from PIL import Image, ImageDraw, ImageFont

# Colors
BG_COLOR = (26, 58, 42)        # #1a3a2a
ACCENT = (126, 232, 176)       # #7ee8b0
MUTED = (92, 184, 138)         # #5cb88a
LIGHT = (212, 245, 228)        # #d4f5e4
WHITE = (255, 255, 255)
ELIMINATED_COLOR = (80, 110, 95)
LINE_COLOR = (92, 184, 138, 180)

IMG_W = 1920
IMG_H = 1080


def _get_font(size, bold=False):
    """Get a font, falling back to default if needed."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _draw_team_slot(draw, x, y, w, h, name, seed, score="", is_winner=False, is_eliminated=False):
    """Draw a single team slot in the bracket."""
    # Background
    if is_winner:
        draw.rectangle([x, y, x + w, y + h], fill=(30, 80, 55), outline=ACCENT, width=2)
    elif is_eliminated:
        draw.rectangle([x, y, x + w, y + h], fill=(20, 40, 30), outline=ELIMINATED_COLOR, width=1)
    else:
        draw.rectangle([x, y, x + w, y + h], fill=(22, 50, 38), outline=MUTED, width=1)

    font = _get_font(14, bold=is_winner)
    seed_font = _get_font(11)
    score_font = _get_font(14, bold=True)

    text_color = ACCENT if is_winner else ELIMINATED_COLOR if is_eliminated else LIGHT

    # Seed number
    if seed:
        seed_text = str(seed)
        draw.text((x + 4, y + (h - 14) // 2), seed_text, fill=MUTED if not is_eliminated else ELIMINATED_COLOR, font=seed_font)

    # Team name
    name_x = x + 24
    name_text = name[:18]  # truncate long names
    draw.text((name_x, y + (h - 16) // 2), name_text, fill=text_color, font=font)

    # Strikethrough for eliminated
    if is_eliminated and name != "TBD":
        bbox = font.getbbox(name_text)
        text_w = bbox[2] - bbox[0]
        text_y = y + h // 2
        draw.line([(name_x, text_y), (name_x + text_w, text_y)], fill=ELIMINATED_COLOR, width=1)

    # Score
    if score and str(score) != "":
        draw.text((x + w - 35, y + (h - 16) // 2), str(score), fill=WHITE if is_winner else text_color, font=score_font)


def _organize_bracket_data(bracket_state):
    """Organize games into regions and rounds for rendering."""
    regions = {}
    region_names = list(bracket_state.get("regions", {}).keys())

    # If we don't have region data, organize by round
    if not region_names:
        teams = bracket_state.get("teams", [])
        # Group teams by region
        for team in teams:
            r = team.get("region", "Region")
            if r not in regions:
                regions[r] = {"teams": [], "games": []}
            regions[r]["teams"].append(team)
    else:
        for r in region_names:
            regions[r] = {
                "teams": [t for t in bracket_state.get("teams", []) if t.get("region") == r],
                "games": bracket_state["regions"][r],
            }

    return regions


def render_full_bracket(bracket_state, gender, output_path):
    """Render the full 68-team bracket as a 1920x1080 PNG.

    Layout: 2 regions on left, 2 on right, Final Four in center.
    """
    img = Image.new("RGB", (IMG_W, IMG_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Title
    title_font = _get_font(24, bold=True)
    label = "Men's" if gender == "men" else "Women's"
    title = f"NCAA {label} Tournament Bracket"
    draw.text((IMG_W // 2 - 200, 12), title, fill=ACCENT, font=title_font)

    regions = _organize_bracket_data(bracket_state)
    region_names = list(regions.keys())

    # Ensure we have 4 regions (pad if needed)
    while len(region_names) < 4:
        region_names.append(f"Region {len(region_names) + 1}")

    # Region positions: top-left, bottom-left, top-right, bottom-right
    region_positions = [
        (20, 50, IMG_W // 2 - 20, IMG_H // 2 - 10, "left"),    # top-left
        (20, IMG_H // 2 + 10, IMG_W // 2 - 20, IMG_H - 20, "left"),  # bottom-left
        (IMG_W // 2 + 20, 50, IMG_W - 20, IMG_H // 2 - 10, "right"),  # top-right
        (IMG_W // 2 + 20, IMG_H // 2 + 10, IMG_W - 20, IMG_H - 20, "right"),  # bottom-right
    ]

    all_teams = bracket_state.get("teams", [])
    team_status = {t["name"]: t for t in all_teams}

    for idx, (rx, ry, rx2, ry2, direction) in enumerate(region_positions):
        rw = rx2 - rx
        rh = ry2 - ry

        region_name = region_names[idx] if idx < len(region_names) else f"Region {idx + 1}"
        region_data = regions.get(region_name, {"teams": [], "games": []})

        # Region label
        region_font = _get_font(16, bold=True)
        draw.text((rx + 10, ry + 2), region_name.upper(), fill=ACCENT, font=region_font)

        # Get teams for this region
        region_teams = region_data.get("teams", [])
        if not region_teams:
            # Create placeholder teams
            region_teams = [{"name": f"Team {i+1}", "seed": i+1, "eliminated": False} for i in range(16)]

        # Sort by seed
        region_teams.sort(key=lambda t: int(t.get("seed", 99)) if str(t.get("seed", "99")).isdigit() else 99)

        # Draw Round of 64 matchups
        slot_w = rw // 5  # width per round column
        slot_h = 22
        matchup_order = [0, 15, 7, 8, 4, 11, 3, 12, 5, 10, 2, 13, 6, 9, 1, 14]

        start_y = ry + 22
        available_h = rh - 30
        gap = available_h / 16

        # Round of 64 (16 teams)
        r64_x = rx + 5 if direction == "left" else rx + rw - slot_w - 5
        for i, team_idx in enumerate(matchup_order):
            if team_idx < len(region_teams):
                team = region_teams[team_idx]
                name = team.get("name", "TBD")
                seed = team.get("seed", "")
                status = team_status.get(name, team)
                is_eliminated = status.get("eliminated", False)
                is_winner = not is_eliminated and name != "TBD"
                ty = start_y + i * gap
                _draw_team_slot(draw, r64_x, ty, slot_w - 5, slot_h, name, seed,
                                is_winner=is_winner and not is_eliminated,
                                is_eliminated=is_eliminated)

        # Round of 32 (8 slots)
        r32_x = rx + slot_w + 5 if direction == "left" else rx + rw - 2 * slot_w - 5
        r32_gap = gap * 2
        for i in range(8):
            ty = start_y + i * r32_gap + gap / 2
            # Determine winner from matchup
            a_idx = matchup_order[i * 2] if i * 2 < len(matchup_order) else 0
            b_idx = matchup_order[i * 2 + 1] if i * 2 + 1 < len(matchup_order) else 0
            team_a = region_teams[a_idx] if a_idx < len(region_teams) else {"name": "TBD", "seed": ""}
            team_b = region_teams[b_idx] if b_idx < len(region_teams) else {"name": "TBD", "seed": ""}

            # Higher seed advances in sample
            status_a = team_status.get(team_a["name"], team_a)
            status_b = team_status.get(team_b["name"], team_b)

            if not status_a.get("eliminated", False):
                winner = team_a
            elif not status_b.get("eliminated", False):
                winner = team_b
            else:
                winner = team_a  # both eliminated, show higher seed

            w_status = team_status.get(winner["name"], winner)
            _draw_team_slot(draw, r32_x, ty, slot_w - 5, slot_h,
                            winner["name"], winner.get("seed", ""),
                            is_winner=not w_status.get("eliminated", False),
                            is_eliminated=w_status.get("eliminated", False))

            # Connector lines
            line_color = MUTED
            if direction == "left":
                draw.line([(r64_x + slot_w - 5, start_y + i * 2 * gap + slot_h // 2),
                           (r32_x, ty + slot_h // 2)], fill=line_color, width=1)
                draw.line([(r64_x + slot_w - 5, start_y + (i * 2 + 1) * gap + slot_h // 2),
                           (r32_x, ty + slot_h // 2)], fill=line_color, width=1)
            else:
                draw.line([(r64_x, start_y + i * 2 * gap + slot_h // 2),
                           (r32_x + slot_w - 5, ty + slot_h // 2)], fill=line_color, width=1)
                draw.line([(r64_x, start_y + (i * 2 + 1) * gap + slot_h // 2),
                           (r32_x + slot_w - 5, ty + slot_h // 2)], fill=line_color, width=1)

        # Sweet 16 (4 slots)
        s16_x = rx + 2 * slot_w + 5 if direction == "left" else rx + rw - 3 * slot_w - 5
        s16_gap = gap * 4
        for i in range(4):
            ty = start_y + i * s16_gap + gap * 1.5
            draw.rectangle([s16_x, ty, s16_x + slot_w - 5, ty + slot_h],
                           fill=(22, 50, 38), outline=MUTED, width=1)
            font = _get_font(13)
            draw.text((s16_x + 6, ty + 3), "TBD", fill=MUTED, font=font)

        # Elite 8 (2 slots)
        e8_x = rx + 3 * slot_w + 5 if direction == "left" else rx + rw - 4 * slot_w - 5
        e8_gap = gap * 8
        for i in range(2):
            ty = start_y + i * e8_gap + gap * 3.5
            draw.rectangle([e8_x, ty, e8_x + slot_w - 5, ty + slot_h],
                           fill=(22, 50, 38), outline=MUTED, width=1)
            font = _get_font(13)
            draw.text((e8_x + 6, ty + 3), "TBD", fill=MUTED, font=font)

    # Final Four box in center
    ff_x = IMG_W // 2 - 100
    ff_y = IMG_H // 2 - 60
    ff_w = 200
    ff_h = 120

    draw.rectangle([ff_x - 2, ff_y - 2, ff_x + ff_w + 2, ff_y + ff_h + 2],
                   outline=ACCENT, width=2)
    draw.rectangle([ff_x, ff_y, ff_x + ff_w, ff_y + ff_h], fill=(22, 50, 38))

    ff_font = _get_font(16, bold=True)
    draw.text((ff_x + 40, ff_y + 5), "FINAL FOUR", fill=ACCENT, font=ff_font)

    slot_font = _get_font(13)
    for i in range(4):
        sy = ff_y + 28 + i * 22
        draw.rectangle([ff_x + 10, sy, ff_x + ff_w - 10, sy + 18],
                       fill=(26, 58, 42), outline=MUTED, width=1)
        draw.text((ff_x + 16, sy + 2), "TBD", fill=MUTED, font=slot_font)

    # Watermark
    wm_font = _get_font(11)
    draw.text((10, IMG_H - 20), "Annie's Madness Tracker", fill=MUTED, font=wm_font)

    img.save(output_path, "PNG")
    return output_path


def render_today_view(todays_games, bracket_state, gender, output_path):
    """Render today's matchups as a 1920x1080 PNG.

    Shows remaining teams and highlights today's games prominently.
    """
    img = Image.new("RGB", (IMG_W, IMG_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Title
    title_font = _get_font(32, bold=True)
    label = "Men's" if gender == "men" else "Women's"
    title = f"{label} Tournament - Today's Games"
    bbox = title_font.getbbox(title)
    tw = bbox[2] - bbox[0]
    draw.text(((IMG_W - tw) // 2, 30), title, fill=ACCENT, font=title_font)

    if not todays_games:
        # No games today
        no_games_font = _get_font(28)
        msg = "No games scheduled today"
        bbox = no_games_font.getbbox(msg)
        mw = bbox[2] - bbox[0]
        draw.text(((IMG_W - mw) // 2, IMG_H // 2 - 20), msg, fill=MUTED, font=no_games_font)

        sub_font = _get_font(18)
        sub_msg = "Check back tomorrow for more March Madness action!"
        bbox2 = sub_font.getbbox(sub_msg)
        sw = bbox2[2] - bbox2[0]
        draw.text(((IMG_W - sw) // 2, IMG_H // 2 + 30), sub_msg, fill=MUTED, font=sub_font)
    else:
        # Layout today's games as large cards
        card_w = 700
        card_h = 180
        cards_per_row = 2
        start_x = (IMG_W - cards_per_row * (card_w + 40)) // 2 + 20
        start_y = 100

        for i, game in enumerate(todays_games[:6]):
            col = i % cards_per_row
            row = i // cards_per_row
            cx = start_x + col * (card_w + 40)
            cy = start_y + row * (card_h + 30)

            # Card background
            draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h],
                                   radius=10, fill=(22, 50, 38), outline=ACCENT, width=2)

            # Round & region label
            round_font = _get_font(14)
            round_text = f"{game.get('round', '')} - {game.get('region', '')}"
            draw.text((cx + 15, cy + 10), round_text, fill=MUTED, font=round_font)

            # Time & network
            time_font = _get_font(16, bold=True)
            time_text = f"{game.get('start_time', 'TBD')} on {game.get('network', 'TBD')}"
            bbox = time_font.getbbox(time_text)
            ttw = bbox[2] - bbox[0]
            draw.text((cx + card_w - ttw - 15, cy + 10), time_text, fill=ACCENT, font=time_font)

            # Team matchup
            team_font = _get_font(28, bold=True)
            seed_font = _get_font(18)

            home = game.get("home", {})
            away = game.get("away", {})

            # Home team
            home_y = cy + 50
            draw.text((cx + 15, home_y + 5), f"({home.get('seed', '?')})", fill=MUTED, font=seed_font)
            draw.text((cx + 55, home_y), home.get("name", "TBD"), fill=LIGHT, font=team_font)

            if home.get("score"):
                score_font = _get_font(28, bold=True)
                score_text = str(home["score"])
                bbox = score_font.getbbox(score_text)
                sw = bbox[2] - bbox[0]
                color = ACCENT if home.get("winner") else LIGHT
                draw.text((cx + card_w - sw - 20, home_y), score_text, fill=color, font=score_font)

            # VS
            vs_font = _get_font(16)
            draw.text((cx + 15, cy + 95), "vs", fill=MUTED, font=vs_font)

            # Away team
            away_y = cy + 115
            draw.text((cx + 15, away_y + 5), f"({away.get('seed', '?')})", fill=MUTED, font=seed_font)
            draw.text((cx + 55, away_y), away.get("name", "TBD"), fill=LIGHT, font=team_font)

            if away.get("score"):
                score_font = _get_font(28, bold=True)
                score_text = str(away["score"])
                bbox = score_font.getbbox(score_text)
                sw = bbox[2] - bbox[0]
                color = ACCENT if away.get("winner") else LIGHT
                draw.text((cx + card_w - sw - 20, away_y), score_text, fill=color, font=score_font)

    # Remaining teams summary at bottom
    active_teams = [t for t in bracket_state.get("teams", []) if not t.get("eliminated", False)]
    if active_teams:
        summary_font = _get_font(16)
        summary = f"{len(active_teams)} teams remaining in the tournament"
        bbox = summary_font.getbbox(summary)
        sw = bbox[2] - bbox[0]
        draw.text(((IMG_W - sw) // 2, IMG_H - 60), summary, fill=MUTED, font=summary_font)

    # Watermark
    wm_font = _get_font(11)
    draw.text((10, IMG_H - 20), "Annie's Madness Tracker", fill=MUTED, font=wm_font)

    img.save(output_path, "PNG")
    return output_path


def render_all_brackets(mens_data, womens_data, output_dir):
    """Render all 4 bracket images.

    Args:
        mens_data: dict from fetch_tournament_data for men
        womens_data: dict from fetch_tournament_data for women
        output_dir: directory to save images

    Returns:
        dict mapping image names to file paths
    """
    os.makedirs(output_dir, exist_ok=True)

    paths = {}

    paths["mens_full"] = render_full_bracket(
        mens_data["bracket_state"], "men",
        os.path.join(output_dir, "mens-full-bracket.png"),
    )
    paths["mens_today"] = render_today_view(
        mens_data["todays_games"], mens_data["bracket_state"], "men",
        os.path.join(output_dir, "mens-today-view.png"),
    )
    paths["womens_full"] = render_full_bracket(
        womens_data["bracket_state"], "women",
        os.path.join(output_dir, "womens-full-bracket.png"),
    )
    paths["womens_today"] = render_today_view(
        womens_data["todays_games"], womens_data["bracket_state"], "women",
        os.path.join(output_dir, "womens-today-view.png"),
    )

    return paths
