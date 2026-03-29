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

PHOTOGRAPHER_PROMPT = """You're editing this photo in post-production. The photo was already taken — you can't add new lights or change anything physical. You're working with the existing light in the scene.

Your tools: color grading, exposure curves, selective color adjustments, depth-of-field effects, atmosphere and haze, shadow/highlight recovery. Think of what a great colorist does to a movie — they don't add lights, they shape what's already there into something beautiful.

What color grade and mood would you give this specific photo? How would you shape the existing light to make it feel more intentional and professional? Be creative but realistic — the result should look like a real photograph, not CGI."""


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

Turn this into a short image editing prompt (2-4 sentences). Focus on the color grading and mood — how the existing light should be shaped. Skip anything that sounds like adding new light sources or physical changes. The result should look like a real photograph, not CGI or a render.

End with: "Keep everything in the scene as it is. The result should look like a real, natural photograph."

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
    "Give this photo a professional color grade that fits the mood of the scene. "
    "Shape the existing light to feel more intentional — recover shadows, control "
    "highlights, add depth. Keep everything in the scene as it is. The result "
    "should look like a real, natural photograph."
)


async def enhance_image(
    client: AsyncOpenAI,
    image_bytes: bytes,
    scene_type: str,
    style: str = "natural",
) -> tuple[str, str, str, str]:
    """
    Three-step enhancement:
    1. Photographer looks at the photo (~$0.0003)
    2. Crafter writes a clean prompt (~$0.0001)
    3. Editor enhances the image (~$0.05-0.10)

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

    return image_b64, "png", notes, prompt
