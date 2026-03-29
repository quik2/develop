# enhancement.py — OpenAI GPT Image 1.5 integration with scene-specific prompts.

import base64
import io
import logging
from openai import AsyncOpenAI

logger = logging.getLogger("develop.enhancement")

SCENE_PROMPTS = {
    "portrait": (
        "Enhance this portrait. Improve skin tones and lighting. "
        "Keep the person exactly the same — do not change their face, "
        "features, expression, hair, or appearance in any way."
    ),
    "food": (
        "Enhance this food photograph. Make the food look warm and "
        "appetizing. Improve color saturation naturally. Apply professional "
        "food photography lighting and white balance. Keep everything "
        "exactly as it is."
    ),
    "low_light": (
        "Enhance this low-light photograph. Brighten shadows without "
        "blowing highlights. Reduce noise while preserving detail. "
        "Improve color accuracy. Keep all subjects exactly as they are."
    ),
    "landscape": (
        "Enhance the lighting and colors in this photo. Reduce haze, "
        "make the sky and scenery more vivid. Keep any people exactly "
        "the same — do not change their face, features, or appearance."
    ),
    "indoor": (
        "Enhance this indoor photograph. Correct white balance, improve "
        "lighting evenness, reduce noise. Keep all subjects exactly as "
        "they are."
    ),
    "action": (
        "Enhance this action photograph. Improve clarity, sharpen the "
        "subject, boost colors. Keep all subjects exactly as they are."
    ),
    "default": (
        "Enhance this photograph. Improve lighting, quality, and colors. "
        "Keep everything exactly as it is."
    ),
}


async def enhance_image(
    client: AsyncOpenAI,
    image_bytes: bytes,
    scene_type: str,
    style: str = "natural",
) -> tuple[str, str]:
    """
    Send an image to GPT Image 1.5 for enhancement.

    Returns (base64_image, format) on success.
    Raises on failure.
    """
    prompt = SCENE_PROMPTS.get(scene_type, SCENE_PROMPTS["default"])

    logger.info("Enhancing image: scene=%s, size=%d bytes", scene_type, len(image_bytes))

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
