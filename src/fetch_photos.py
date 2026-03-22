"""Fetch tournament highlight photos using Anthropic API with web_search."""

import json
import os

import requests
from PIL import Image


def fetch_highlight_photos(api_key=None, output_dir="output/images"):
    """Fetch 2 recent tournament action highlight photo URLs and download them.

    Args:
        api_key: Anthropic API key
        output_dir: directory to save downloaded images

    Returns:
        list of dicts with local_path, caption, credit
    """
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return []

    os.makedirs(output_dir, exist_ok=True)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            tools=[{"type": "web_search_20250305"}],
            messages=[
                {
                    "role": "user",
                    "content": """Search for NCAA March Madness tournament action photos from the last 48 hours.

Find 2 high-quality action/highlight photos from recent tournament games. Look on ESPN, CBS Sports, NCAA.com, Getty Images, or major sports media sites.

I need DIRECT image URLs (ending in .jpg, .png, or from image CDNs like media.gettyimages.com, a.espncdn.com, etc.) that can be downloaded.

Return ONLY a JSON array of exactly 2 objects. No other text.
Each object has:
- "image_url": direct URL to the image file
- "caption": short description of the action in the photo (15 words max)
- "credit": photographer or publication credit""",
                }
            ],
        )

        # Extract text from response
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text
                break

        if not text:
            return []

        # Parse JSON
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            if text.startswith("json"):
                text = text[4:].strip()

        photos_data = json.loads(text)
        if not isinstance(photos_data, list):
            return []

        # Download each photo
        results = []
        for i, photo in enumerate(photos_data[:2]):
            url = photo.get("image_url", "")
            if not url:
                continue

            try:
                resp = requests.get(url, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                if resp.status_code != 200:
                    continue

                content_type = resp.headers.get("Content-Type", "")
                if "image" not in content_type and not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    continue

                # Save image
                ext = "jpg"
                if "png" in content_type or url.lower().endswith(".png"):
                    ext = "png"
                elif "webp" in content_type or url.lower().endswith(".webp"):
                    ext = "webp"

                local_filename = f"highlight_{i + 1}.{ext}"
                local_path = os.path.join(output_dir, local_filename)

                with open(local_path, "wb") as f:
                    f.write(resp.content)

                # Validate it's actually an image and resize
                img = Image.open(local_path)
                # Resize to consistent width while maintaining aspect ratio
                target_width = 580
                ratio = target_width / img.width
                target_height = int(img.height * ratio)
                img = img.resize((target_width, target_height), Image.LANCZOS)
                img.save(local_path)

                results.append({
                    "local_path": f"images/{local_filename}",
                    "caption": str(photo.get("caption", "Tournament action"))[:100],
                    "credit": str(photo.get("credit", ""))[:80],
                })

            except Exception:
                continue

        return results

    except Exception as e:
        print(f"  Warning: Failed to fetch highlight photos: {e}")
        return []
