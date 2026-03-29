# enhancement.py — Two-step AI enhancement: analyze with GPT-4o mini, enhance with GPT Image 1.5.

import base64
import io
import logging
from openai import AsyncOpenAI

logger = logging.getLogger("develop.enhancement")

# Scene-specific analysis guidance for the vision model
SCENE_GUIDANCE = {
    "portrait": "This is a portrait. Focus on: lighting direction, skin tones, background separation, catchlights, hair detail, and mood. Suggest professional portrait photography techniques.",
    "food": "This is a food photo. Focus on: color temperature, texture detail, plating composition, background blur, and appetizing qualities. Suggest professional food photography techniques.",
    "low_light": "This is a low-light scene. Focus on: shadow detail recovery, noise characteristics, mood preservation, light sources, and atmosphere. Suggest techniques to make it look intentionally moody and cinematic rather than just brightened.",
    "landscape": "This is a landscape. Focus on: sky drama, depth layers, color gradients, foreground interest, and atmospheric quality. Suggest techniques from landscape masters like Peter Lik or Marc Adamus.",
    "indoor": "This is an indoor scene. Focus on: white balance, ambient vs artificial light mix, spatial depth, and architectural lines. Suggest interior photography techniques.",
    "action": "This is an action/movement shot. Focus on: subject sharpness, motion energy, dynamic range, and decisive moment. Suggest sports/action photography techniques.",
    "default": "Analyze this photo's subject, composition, and lighting. Suggest the most impactful professional photography techniques to transform it.",
}

ANALYSIS_SYSTEM_PROMPT = """You are a professional photo retoucher writing enhancement instructions for a photo editing app.

Your job: describe specific photography-grade lighting, color grading, and detail improvements for this photo. You are writing instructions for an image editing AI — like Lightroom adjustments but described in words.

Focus on:
- Lighting adjustments: direction, warmth, contrast ratios
- Color grading: tonal palette, complementary colors, mood
- Depth and focus: background softness, atmospheric perspective
- Detail: texture clarity, micro-contrast, sharpness
- Mood: overall atmosphere and emotional tone

Be SPECIFIC with your adjustments. Instead of "improve lighting" say "warm the highlights to golden tones, add subtle cool fill in the shadows, increase rim light separation."

Rules:
- All people, faces, and subjects must remain unchanged — only adjust lighting and color ON them.
- The composition and framing stay the same.
- You are writing photo editing instructions, nothing else."""

ANALYSIS_USER_PROMPT = """Write photo editing instructions (3-5 sentences) to make this photo look like it was taken by a professional photographer. Describe the specific lighting, color, and detail adjustments.

Context: {guidance}

Write ONLY the editing instructions — no explanation, no preamble. Be specific and cinematic."""


async def analyze_photo(client: AsyncOpenAI, image_bytes: bytes, scene_type: str) -> str:
    """Use GPT-4o mini vision to analyze the photo and generate a custom enhancement prompt."""
    guidance = SCENE_GUIDANCE.get(scene_type, SCENE_GUIDANCE["default"])

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=300,
        messages=[
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": ANALYSIS_USER_PROMPT.format(guidance=guidance),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}",
                            "detail": "low",
                        },
                    },
                ],
            },
        ],
    )

    prompt = response.choices[0].message.content.strip()

    # Detect refusals
    refusal_signals = ["i can't", "i'm sorry", "i cannot", "i'm unable", "not able to"]
    if any(s in prompt.lower() for s in refusal_signals):
        logger.warning("Analysis refused, will use fallback")
        return None

    logger.info("Analysis generated prompt: %s", prompt[:120])
    return prompt


# Fallback prompts if analysis fails — these are still much better than before
FALLBACK_PROMPTS = {
    "portrait": (
        "Transform this into a professional studio-quality portrait. Add soft, "
        "directional golden-hour lighting from the upper left with gentle rim light "
        "separating the subject from the background. Apply cinematic color grading — "
        "warm highlights, cool shadows. Enhance skin texture naturally with soft "
        "micro-contrast. Create creamy background bokeh. Reduce any glare or "
        "reflections on glasses. Keep the person's face, identity, and expression "
        "exactly the same."
    ),
    "food": (
        "Transform this into an award-winning food photograph. Apply warm, dramatic "
        "side lighting that highlights texture and creates appetizing shadows. Boost "
        "color vibrancy — make reds richer, greens fresher, warm tones more inviting. "
        "Add a subtle depth-of-field effect with creamy bokeh on the background. "
        "Enhance surface textures — every grain, drip, and garnish should pop. "
        "Keep the food and plating exactly as they are."
    ),
    "low_light": (
        "Transform this into a cinematic night photograph. Recover shadow detail while "
        "preserving the moody atmosphere — don't over-brighten. Add rich, filmic color "
        "grading: warm tungsten highlights against cool blue shadows. Enhance light "
        "sources with subtle bloom. Reduce noise while keeping grain texture for a "
        "film-like quality. Deepen blacks for contrast. Keep all subjects exactly the same."
    ),
    "landscape": (
        "Transform this into an epic landscape photograph worthy of a gallery wall. "
        "Enhance the sky with dramatic cloud detail and rich color gradients. Add depth "
        "through atmospheric perspective — foreground warm and sharp, background cool and "
        "slightly hazy. Boost color saturation naturally with a golden-hour palette. "
        "Enhance textures in foliage, water, and terrain. Create a sense of grandeur. "
        "Keep any people exactly the same."
    ),
    "indoor": (
        "Transform this into a professional architectural/interior photograph. Balance "
        "all light sources for clean white balance. Add depth through subtle light "
        "gradients — brighter foreground fading to slightly warmer background. Enhance "
        "textures on surfaces and materials. Straighten any converging verticals. Apply "
        "a clean, editorial color palette. Keep all subjects exactly the same."
    ),
    "action": (
        "Transform this into a dynamic professional sports/action photograph. Enhance "
        "the subject with razor sharpness and pop them from the background with dramatic "
        "contrast. Apply bold, punchy color grading. Add a subtle motion energy to the "
        "background. Boost mid-tone contrast for a powerful, editorial look. Keep all "
        "subjects exactly the same."
    ),
    "default": (
        "Transform this into a stunning professional photograph. Apply cinematic lighting "
        "with warm highlights and cool shadows. Enhance depth through selective focus and "
        "atmospheric perspective. Boost color with a rich, film-inspired palette. Enhance "
        "textures and micro-contrast for a high-end editorial look. Keep all subjects "
        "exactly the same."
    ),
}


async def enhance_image(
    client: AsyncOpenAI,
    image_bytes: bytes,
    scene_type: str,
    style: str = "natural",
) -> tuple[str, str]:
    """
    Two-step enhancement:
    1. Analyze photo with GPT-4o mini to generate a custom prompt
    2. Enhance with GPT Image 1.5 using that prompt

    Returns (base64_image, format) on success.
    Raises on failure.
    """
    # Step 1: Analyze the photo and generate a custom prompt
    prompt = None
    try:
        prompt = await analyze_photo(client, image_bytes, scene_type)
    except Exception as e:
        logger.warning("Photo analysis failed, using fallback prompt: %s", e)

    if not prompt:
        prompt = FALLBACK_PROMPTS.get(scene_type, FALLBACK_PROMPTS["default"])

    logger.info("Enhancing image: scene=%s, size=%d bytes", scene_type, len(image_bytes))

    # Step 2: Enhance with GPT Image 1.5
    image_file = io.BytesIO(image_bytes)
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
