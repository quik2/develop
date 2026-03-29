# enhancement.py — Three-step AI enhancement pipeline.
#
# The goal: close the gap between "what my phone captured" and "what a skilled
# photographer would have produced from the same moment." The result should look
# like the photo was taken by someone who knows what they're doing — not like
# it was run through a filter, not like CGI, not like a render. Just a better
# version of the same real photo.

import base64
import io
import logging

from PIL import Image
from openai import AsyncOpenAI

logger = logging.getLogger("develop.enhancement")

# --- Input preprocessing ---

MAX_INPUT_SIDE = 1536
JPEG_QUALITY = 82


def resize_for_api(image_bytes: bytes) -> bytes:
    """Resize to max 1536px on longest side, compress to JPEG 82."""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size

    if max(w, h) <= MAX_INPUT_SIDE:
        buf = io.BytesIO()
        img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        return buf.getvalue()

    scale = MAX_INPUT_SIDE / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    result = buf.getvalue()
    logger.info("Resized %dx%d → %dx%d (%d bytes → %d bytes)",
                w, h, new_w, new_h, len(image_bytes), len(result))
    return result


# --- Step 1: Photographer (looks at the photo, thinks about what it should look like) ---

PHOTOGRAPHER_PROMPT = """Someone who doesn't know anything about photography just took this photo on their phone. It captures a real moment they care about.

If a skilled photographer had been standing in the exact same spot at the exact same time, what would their version of this photo look like? Same scene, same moment, same people — but taken by someone who understands light, color, and composition.

Describe how the skilled photographer's version would differ. Think about what the camera SHOULD have captured — the way the light actually looked to the human eye, the colors as they actually felt, the depth and atmosphere that were actually there but the phone camera missed."""


# --- Step 2: Prompt Crafter ---

CRAFTER_PROMPT = """A photographer described how a phone photo could look if a skilled photographer had taken it instead. Here's what they said:

---
{photographer_notes}
---

Turn this into a short image editing prompt (2-4 sentences). The edit should make the photo look like a skilled photographer took it — natural, real, and beautiful. Not filtered, not CGI, not overly dramatic. Just what the photo should have looked like.

Never suggest cropping, reframing, or changing the composition. The framing stays exactly as it is.

End with: "The result should look like a real photograph. Keep the same scene, objects, people, and framing exactly as they are." """


# --- Fallback ---

FALLBACK_PROMPT = (
    "Make this photo look like a skilled photographer took it instead of a phone. "
    "The light, colors, and depth should look natural and intentional — like what "
    "the human eye actually saw, but the phone camera couldn't capture. "
    "The result should look like a real photograph. Keep the same scene, objects, "
    "and people exactly as they are."
)


# --- Pipeline functions ---

async def step1_photographer(client: AsyncOpenAI, image_b64: str) -> str:
    """Photographer looks at the photo and describes what a better version looks like."""
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PHOTOGRAPHER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}",
                            "detail": "low",
                        },
                    },
                ],
            },
        ],
    )

    result = response.choices[0].message.content.strip()
    logger.info("Photographer: %s", result[:150])
    return result


async def step2_crafter(client: AsyncOpenAI, photographer_notes: str) -> str:
    """Turn the photographer's notes into a clean editing prompt."""
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": CRAFTER_PROMPT.format(photographer_notes=photographer_notes),
            },
        ],
    )

    result = response.choices[0].message.content.strip()
    logger.info("Crafter: %s", result[:150])
    return result


# --- Main enhancement function ---

async def enhance_image(
    client: AsyncOpenAI,
    image_bytes: bytes,
    scene_type: str,
    style: str = "natural",
) -> tuple[str, str, str, str]:
    """
    Three-step enhancement:
    1. Photographer describes what a skilled version would look like (~$0.0003)
    2. Crafter writes a clean editing prompt (~$0.0001)
    3. GPT Image 1.5 applies the edit (~$0.05-0.10)

    Returns (base64_image, format, photographer_notes, final_prompt).
    """
    # Resize input
    resized = resize_for_api(image_bytes)
    image_b64 = base64.b64encode(resized).decode("utf-8")
    logger.info("Enhancing: scene=%s, original=%d bytes, resized=%d bytes",
                scene_type, len(image_bytes), len(resized))

    # Step 1 + 2: Photographer → Crafter
    notes = None
    prompt = None
    try:
        notes = await step1_photographer(client, image_b64)
        prompt = await step2_crafter(client, notes)
    except Exception as e:
        logger.warning("Pipeline failed, using fallback: %s", e)

    # Detect refusals
    if prompt:
        refusal_signals = ["i can't", "i'm sorry", "i cannot", "i'm unable"]
        if any(s in prompt.lower() for s in refusal_signals):
            logger.warning("Got refusal, using fallback")
            prompt = None

    if not prompt:
        prompt = FALLBACK_PROMPT

    # Determine output size matching input aspect ratio
    img = Image.open(io.BytesIO(resized))
    w, h = img.size
    if h > w:
        size = "1024x1536"   # portrait
    elif w > h:
        size = "1536x1024"   # landscape
    else:
        size = "1024x1024"   # square

    # Step 3: Edit with GPT Image 1.5
    image_file = io.BytesIO(resized)
    image_file.name = "photo.jpg"

    result = await client.images.edit(
        model="gpt-image-1.5",
        image=image_file,
        prompt=prompt,
        input_fidelity="high",
        quality="medium",
        size=size,
    )

    image_b64 = result.data[0].b64_json
    logger.info("Enhancement complete: result size=%d chars", len(image_b64))

    return image_b64, "png", notes, prompt
