# enhancement.py — Three-step AI enhancement pipeline.
#
# Step 1: Photographer — GPT-4o mini looks at the photo and says what it needs
# Step 2: Prompt Crafter — GPT-4o mini turns that into a clean editing prompt
# Step 3: Editor — GPT Image 1.5 applies it
#
# Philosophy: no rules, no constraints, no "DO NOT" lists. Let the AI think
# freely and creatively. The only fixed thing: people stay looking the same.

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


# --- Step 1: Photographer (looks at the photo, thinks freely) ---

PHOTOGRAPHER_PROMPT = """You're a professional photographer looking at this photo someone just took on their phone.

What would you do to make this photo look amazing? Think about what this specific photo needs — the lighting, the colors, the background, the composition, everything. Be specific about what you'd change and why. Some photos need a lot of work, some just need a little polish. Match your edits to what the photo is actually asking for."""


async def step1_photographer(client: AsyncOpenAI, image_b64: str) -> str:
    """Photographer looks at the photo and says what it needs."""
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


# --- Step 2: Prompt Crafter (turns the photographer's ideas into an editing prompt) ---

CRAFTER_PROMPT = """A professional photographer looked at a photo and described how they'd edit it. Here's what they said:

---
{photographer_notes}
---

Turn this into a short, natural image editing prompt (2-4 sentences). Write it like you're telling an editor what to do. Keep it creative and specific to this photo — don't be generic.

If the photographer mentioned anything about people in the photo, add one simple line at the end: "Keep any people looking exactly as they are."

Just write the prompt, nothing else."""


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


# --- Step 3: Editor (GPT Image 1.5 applies the prompt) ---

FALLBACK_PROMPT = (
    "Make this photo look like it was taken by a professional photographer. "
    "Improve the lighting, colors, and atmosphere to match what the scene naturally "
    "calls for. Clean up any distracting elements in the background. "
    "Keep any people looking exactly as they are."
)


async def enhance_image(
    client: AsyncOpenAI,
    image_bytes: bytes,
    scene_type: str,
    style: str = "natural",
) -> tuple[str, str]:
    """
    Three-step enhancement:
    1. Photographer looks at the photo (~$0.0003)
    2. Crafter writes a clean prompt (~$0.0001)
    3. Editor enhances the image (~$0.05-0.10)
    """
    # Resize input
    resized = resize_for_api(image_bytes)
    image_b64 = base64.b64encode(resized).decode("utf-8")
    logger.info("Enhancing: scene=%s, original=%d bytes, resized=%d bytes",
                scene_type, len(image_bytes), len(resized))

    # Step 1 + 2: Photographer → Crafter
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

    # Step 3: Edit with GPT Image 1.5
    image_file = io.BytesIO(resized)
    image_file.name = "photo.jpg"

    result = await client.images.edit(
        model="gpt-image-1.5",
        image=image_file,
        prompt=prompt,
        input_fidelity="high",
        quality="medium",
        size="auto",
    )

    image_b64 = result.data[0].b64_json
    logger.info("Enhancement complete: result size=%d chars", len(image_b64))

    return image_b64, "png"
