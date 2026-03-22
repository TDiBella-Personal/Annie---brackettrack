"""Render NCAA tournament bracket images using Pillow."""

import os

from PIL import Image, ImageDraw, ImageFont

# Colors - black theme
BG_COLOR = (0, 0, 0)           # #000000
ACCENT = (79, 200, 130)        # #4fc882
MUTED = (42, 122, 74)          # #2a7a4a
LIGHT = (224, 224, 224)        # #e0e0e0
WHITE = (255, 255, 255)
ELIMINATED_COLOR = (80, 80, 80)
LINE_COLOR = (42, 122, 74, 180)
SURFACE = (17, 17, 17)         # #111111
SLOT_BG = (20, 20, 20)
SLOT_WIN_BG = (15, 50, 30)
SLOT_ELIM_BG = (10, 10, 10)

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
        draw.rectangle([x, y, x + w, y + h], fill=SLOT_WIN_BG, outline=ACCENT, width=2)
    elif is_eliminated:
        draw.rectangle([x, y, x + w, y + h], fill=SLOT_ELIM_BG, outline=ELIMINATED_COLOR, width=1)
    else:
        draw.rectangle([x, y, x + w, y + h], fill=SLOT_BG, outline=MUTED, width=1)

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
                           fill=SLOT_BG, outline=MUTED, width=1)
            font = _get_font(13)
            draw.text((s16_x + 6, ty + 3), "TBD", fill=MUTED, font=font)

        # Elite 8 (2 slots)
        e8_x = rx + 3 * slot_w + 5 if direction == "left" else rx + rw - 4 * slot_w - 5
        e8_gap = gap * 8
        for i in range(2):
            ty = start_y + i * e8_gap + gap * 3.5
            draw.rectangle([e8_x, ty, e8_x + slot_w - 5, ty + slot_h],
                           fill=SLOT_BG, outline=MUTED, width=1)
            font = _get_font(13)
            draw.text((e8_x + 6, ty + 3), "TBD", fill=MUTED, font=font)

    # Final Four box in center
    ff_x = IMG_W // 2 - 100
    ff_y = IMG_H // 2 - 60
    ff_w = 200
    ff_h = 120

    draw.rectangle([ff_x - 2, ff_y - 2, ff_x + ff_w + 2, ff_y + ff_h + 2],
                   outline=ACCENT, width=2)
    draw.rectangle([ff_x, ff_y, ff_x + ff_w, ff_y + ff_h], fill=SLOT_BG)

    ff_font = _get_font(16, bold=True)
    draw.text((ff_x + 40, ff_y + 5), "FINAL FOUR", fill=ACCENT, font=ff_font)

    slot_font = _get_font(13)
    for i in range(4):
        sy = ff_y + 28 + i * 22
        draw.rectangle([ff_x + 10, sy, ff_x + ff_w - 10, sy + 18],
                       fill=BG_COLOR, outline=MUTED, width=1)
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
                                   radius=10, fill=SLOT_BG, outline=ACCENT, width=2)

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


def _determine_active_round(bracket_state):
    """Determine the furthest completed round and return which rounds to show in zoom.

    Returns a label for the zoom bracket and the round names to include.
    Once all teams in a round are known, the zoom shows that round forward.
    """
    teams = bracket_state.get("teams", [])
    total = len(teams)
    active = [t for t in teams if not t.get("eliminated", False)]
    active_count = len(active)

    # Determine the current round based on how many teams remain
    if active_count <= 2:
        return "Championship", ["Championship"]
    elif active_count <= 4:
        return "Final Four", ["Final Four", "Championship"]
    elif active_count <= 8:
        return "Elite Eight", ["Elite Eight", "Final Four", "Championship"]
    elif active_count <= 16:
        return "Sweet Sixteen", ["Sweet 16", "Elite Eight", "Final Four", "Championship"]
    elif active_count <= 32:
        return "Round of 32", ["Round of 32", "Sweet 16", "Elite Eight", "Final Four", "Championship"]
    else:
        return "Full Bracket", []  # No zoom needed, still in round of 64


def render_zoom_bracket(bracket_state, gender, output_path):
    """Render a zoomed bracket showing only the active/populated rounds.

    Once all Sweet 16 teams are known, shows Sweet 16 -> Championship.
    Once all Elite 8 teams are known, shows Elite 8 -> Championship. Etc.
    """
    img = Image.new("RGB", (IMG_W, IMG_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    round_label, active_rounds = _determine_active_round(bracket_state)

    # Title
    title_font = _get_font(28, bold=True)
    glabel = "Men's" if gender == "men" else "Women's"
    title = f"{glabel} Tournament - {round_label} & Beyond"
    bbox = title_font.getbbox(title)
    tw = bbox[2] - bbox[0]
    draw.text(((IMG_W - tw) // 2, 20), title, fill=ACCENT, font=title_font)

    teams = bracket_state.get("teams", [])
    active_teams = [t for t in teams if not t.get("eliminated", False)]
    active_teams.sort(key=lambda t: int(t.get("seed", 99)) if str(t.get("seed", "99")).isdigit() else 99)

    if not active_rounds:
        # Still in round of 64, just show the full bracket message
        msg_font = _get_font(22)
        msg = "Tournament is still in early rounds - use Full Bracket view"
        bbox = msg_font.getbbox(msg)
        mw = bbox[2] - bbox[0]
        draw.text(((IMG_W - mw) // 2, IMG_H // 2 - 15), msg, fill=MUTED, font=msg_font)
        img.save(output_path, "PNG")
        return output_path

    num_teams = len(active_teams)
    team_status = {t["name"]: t for t in teams}

    # Organize active teams by region
    region_teams = {}
    for t in active_teams:
        r = t.get("region", "Unknown")
        if r not in region_teams:
            region_teams[r] = []
        region_teams[r].append(t)

    regions = list(region_teams.keys())

    # Layout: show remaining teams in a clean bracket
    # Calculate number of rounds to display
    num_rounds = len(active_rounds)

    # Slot dimensions - bigger since fewer teams
    slot_w = 220
    slot_h = 36
    round_spacing = (IMG_W - 100) // max(num_rounds + 1, 2)

    start_y = 80
    available_h = IMG_H - 120

    if num_teams <= 4:
        # Final Four layout - centered
        ff_font = _get_font(20, bold=True)
        draw.text((IMG_W // 2 - 60, 70), "FINAL FOUR", fill=ACCENT, font=ff_font)

        # Semi-final matchups
        semi_y = [200, 200]
        semi_x = [IMG_W // 4 - slot_w // 2, 3 * IMG_W // 4 - slot_w // 2]

        for i, team in enumerate(active_teams[:4]):
            col = i // 2
            row = i % 2
            tx = semi_x[col]
            ty = semi_y[col] + row * (slot_h + 40)
            _draw_team_slot(draw, tx, ty, slot_w, slot_h,
                            team["name"], team.get("seed", ""),
                            is_winner=True)

        # Championship slot
        champ_x = IMG_W // 2 - slot_w // 2
        champ_y = 500
        champ_font = _get_font(18, bold=True)
        draw.text((champ_x + 20, champ_y - 25), "CHAMPIONSHIP", fill=ACCENT, font=champ_font)
        draw.rectangle([champ_x, champ_y, champ_x + slot_w, champ_y + slot_h],
                       fill=SLOT_BG, outline=ACCENT, width=2)
        tfont = _get_font(15)
        draw.text((champ_x + 10, champ_y + 8), "TBD", fill=MUTED, font=tfont)

        # Connector lines
        for col in range(2):
            mid_x = semi_x[col] + slot_w // 2
            for row in range(2):
                sy = semi_y[col] + row * (slot_h + 40) + slot_h // 2
                draw.line([(mid_x, sy), (IMG_W // 2, champ_y + slot_h // 2)],
                          fill=MUTED, width=1)

    elif num_teams <= 16:
        # Sweet 16 / Elite 8 layout by region
        # 4 regions, show remaining teams per region
        region_positions = [
            (50, start_y, "left"),
            (50, start_y + available_h // 2, "left"),
            (IMG_W - 50 - slot_w * 2, start_y, "right"),
            (IMG_W - 50 - slot_w * 2, start_y + available_h // 2, "right"),
        ]

        region_font = _get_font(16, bold=True)

        for idx, region_name in enumerate(regions[:4]):
            if idx >= len(region_positions):
                break
            rx, ry, direction = region_positions[idx]
            rteams = region_teams[region_name]

            draw.text((rx, ry), region_name.upper(), fill=ACCENT, font=region_font)

            region_h = available_h // 2 - 40
            team_gap = min(region_h // max(len(rteams), 1), slot_h + 20)

            for ti, team in enumerate(rteams):
                ty = ry + 24 + ti * team_gap
                _draw_team_slot(draw, rx, ty, slot_w, slot_h,
                                team["name"], team.get("seed", ""),
                                is_winner=True)

            # Elite 8 / Final 4 slots to the right (or left for right-side regions)
            if len(rteams) >= 2:
                e8_x = rx + slot_w + 30 if direction == "left" else rx - slot_w - 30
                e8_y = ry + 24 + (len(rteams) - 1) * team_gap // 2
                draw.rectangle([e8_x, e8_y, e8_x + slot_w, e8_y + slot_h],
                               fill=SLOT_BG, outline=MUTED, width=1)
                tfont = _get_font(14)
                draw.text((e8_x + 10, e8_y + 8), "TBD", fill=MUTED, font=tfont)

                # Lines
                for ti in range(len(rteams)):
                    sy = ry + 24 + ti * team_gap + slot_h // 2
                    if direction == "left":
                        draw.line([(rx + slot_w, sy), (e8_x, e8_y + slot_h // 2)],
                                  fill=MUTED, width=1)
                    else:
                        draw.line([(rx, sy), (e8_x + slot_w, e8_y + slot_h // 2)],
                                  fill=MUTED, width=1)

        # Final Four in center
        ff_x = IMG_W // 2 - slot_w // 2
        ff_y = IMG_H // 2 - 50
        ff_font = _get_font(16, bold=True)
        draw.rectangle([ff_x - 5, ff_y - 5, ff_x + slot_w + 5, ff_y + 110],
                       outline=ACCENT, width=2)
        draw.text((ff_x + 50, ff_y + 5), "FINAL FOUR", fill=ACCENT, font=ff_font)
        tfont = _get_font(13)
        for i in range(4):
            sy = ff_y + 28 + i * 20
            draw.rectangle([ff_x + 10, sy, ff_x + slot_w - 10, sy + 17],
                           fill=BG_COLOR, outline=MUTED, width=1)
            draw.text((ff_x + 16, sy + 1), "TBD", fill=MUTED, font=tfont)

    else:
        # Round of 32 - show teams grouped by region
        region_font = _get_font(14, bold=True)
        cols = min(len(regions), 4)
        col_w = (IMG_W - 60) // cols

        for idx, region_name in enumerate(regions[:4]):
            rx = 30 + idx * col_w
            rteams = region_teams[region_name]
            draw.text((rx, start_y), region_name.upper(), fill=ACCENT, font=region_font)

            team_gap = min((available_h - 30) // max(len(rteams), 1), slot_h + 8)
            sw = min(slot_w, col_w - 20)

            for ti, team in enumerate(rteams):
                ty = start_y + 22 + ti * team_gap
                _draw_team_slot(draw, rx, ty, sw, slot_h,
                                team["name"], team.get("seed", ""),
                                is_winner=True)

    # Summary
    summary_font = _get_font(14)
    summary = f"{num_teams} teams remaining"
    bbox = summary_font.getbbox(summary)
    sw = bbox[2] - bbox[0]
    draw.text(((IMG_W - sw) // 2, IMG_H - 50), summary, fill=MUTED, font=summary_font)

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

    paths["mens_zoom"] = render_zoom_bracket(
        mens_data["bracket_state"], "men",
        os.path.join(output_dir, "mens-zoom-bracket.png"),
    )
    paths["womens_zoom"] = render_zoom_bracket(
        womens_data["bracket_state"], "women",
        os.path.join(output_dir, "womens-zoom-bracket.png"),
    )

    return paths
