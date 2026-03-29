# Develop
*The camera app that develops every photo.*

---

## The Concept

Develop is a camera app that makes every photo you take look like a photographer took it. You shoot. It develops. That's all you do.

You open Develop instead of the native camera. You shoot exactly like normal. 15-20 seconds later, a better version of every photo appears in your camera roll. The original is gone. Only the developed version exists.

---

## Identity

**Name:** Develop

**Tagline:** *Every photo, developed.*

**Visual identity:**
- Near-black background
- Single warm amber accent — the color of a darkroom safelight
- Clean sans-serif typography (Inter or custom grotesque)
- No gradients, no chrome, no camera iconography
- App icon: a simple circle — aperture of a lens, or a developing photo
- Minimal to the point of feeling intentional

---

## How It Works

### What the user does
Open the app. Tap the shutter. That's it.

### What happens invisibly

**At capture:**
1. Silent 15-frame HEIC burst in 500ms — user taps once
2. Each frame scored for sharpness, blur, motion, and (for portraits) eye open/closed state
3. Best frame selected — blink detection silently retriggers if needed
4. One ProRAW captured of the winning moment
5. HEIC preview saves to camera roll immediately — user sees their photo instantly
6. Developing animation begins on the thumbnail

**In the background (agentic pipeline):**
1. **Analyze** — lightweight vision model reads the scene in <1 second: night shot, distant subject, portrait, indoor, landscape, action
2. **Route** — based on scene type, selects the right enhancement path:
   - Low light → aggressive denoising first, then enhance
   - Zoom / distant subject → super-resolution pass
   - Portrait → face-aware enhancement + skin detail
   - Bright / static → color grading, sharpness, detail
3. **Enhance** — Topaz Labs API runs enhancement with scene-calibrated parameters. Style preference baked in at this stage (not applied after).
4. **Quality check** — MUSIQ quality scoring model grades the output. If below threshold, retries with alternate model path. If fails twice, falls back to non-generative enhancement (denoising, sharpening, color correction). Something always saves.
5. **Deliver** — enhanced version replaces preview in camera roll. Thumbnail pulses. Developed.

**Everything gets enhanced, always.** The routing logic doesn't skip — it calibrates. Bright daylight gets color grading and sharpness. Low light gets the full aggressive pipeline. Every photo develops into the best version of itself.

### Tech stack
- **Capture:** Native Swift, AVFoundation, PhotoKit
- **Multi-frame:** AVCaptureBracketedStillImageSettings + Laplacian variance scoring
- **RAW:** ProRAW via AVCapturePhotoOutput
- **Background upload:** URLSessionConfiguration.background (survives phone lock)
- **On-device preview:** Real-ESRGAN via Core ML (instant lower-quality preview while cloud processes)
- **AI enhancement:** Topaz Labs API (primary) — auto-parameter detection, RAW-optimized, no hallucination
- **Quality check:** MUSIQ on-device scoring
- **Agentic routing:** Lightweight on-device scene classifier + cloud routing logic
- **Style:** Baked into Topaz enhancement pass as prompt parameters — not post-processing filters

---

## Capture Quality — On Par With the Best Third-Party Cameras

Develop's capture pipeline is built to match Halide and !Camera — the highest-quality third-party camera apps. The AI enhancement is only as good as what it starts with.

### The Core Principle: Capture Clean, Enhance With Our Pipeline

Apple's native camera aggressively pre-processes every photo before you ever see it — Deep Fusion stacks 9 frames, Photonic Engine applies semantic rendering, noise reduction blurs detail, sharpening introduces halos. This is baked in before AVFoundation hands the image to any third-party app.

Develop bypasses as much of this as AVFoundation allows and sends **clean sensor data** to the AI. The AI does the enhancement — not Apple's ISP.

This is the same philosophy as Halide's Process Zero: "skip almost all of those steps... take one photo, collect the raw sensor data." The difference is Develop then runs that clean RAW through a world-class AI pipeline rather than leaving it to the user to edit.

### The Capture Pipeline (invisible to the user)

**Step 1 — Silent 15-frame HEIC burst (500ms)**
- Captures 15 frames at full speed
- Scores each frame: Laplacian variance (sharpness) + face confidence + motion blur estimate
- Selects the optimal frame — eliminating camera shake, subject motion, and blink
- This is what Apple does with Deep Fusion; Develop does it explicitly to feed better input to AI

**Step 2 — ProRAW capture of the winning moment**
- Single ProRAW frame at full resolution (up to 48MP on iPhone 15 Pro+)
- Linear light, no gamma curve, no pre-sharpening, no Apple noise reduction baked in
- 12-bit depth vs 8-bit HEIC — maximum tonal range for AI to work with
- This is the image sent to the enhancement pipeline

**Step 3 — Instant HEIC preview**
- Standard HEIC saves to camera roll immediately — user sees their photo within milliseconds
- The developing animation begins

**Step 4 — AI enhancement on ProRAW**
- The clean ProRAW goes to the agentic pipeline
- AI works from the best possible input: full resolution, linear light, natural sensor noise, no compression artifacts
- 15-20 seconds later, the enhanced version replaces the preview

### What This Matches (and Why It Matters)

| Feature | Apple Native Camera | Halide (Process Zero) | !Camera (SuperRAW) | Develop |
|---------|--------------------|-----------------------|-------------------|---------|
| Frame capture | 9-frame Deep Fusion stack | Single frame, minimal processing | Multi-frame underexposed stack | 15-frame burst → 1 ProRAW |
| Pre-processing | Aggressive (AI stacking, semantic rendering) | Minimal (single raw frame) | Embraces natural grain | Minimal (clean ProRAW) |
| Output format | HEIC (processed) | RAW DNG + Process Zero JPG | Proprietary processed JPEG | ProRAW → enhanced JPEG |
| AI enhancement | Apple's (locked, conservative) | None (user edits manually) | None (color grading only) | Topaz + agentic pipeline |
| Night performance | Best (Night mode fusion) | Weaker (single frame) | Weaker | Strong (AI denoising on clean RAW) |
| Mass consumer UX | ✅ | ❌ (manual controls required) | Partial | ✅ |

### Portrait-Specific: Blink Detection

For any shot containing a face, Develop analyzes the 15-frame burst for eye state using the Vision framework (`VNDetectFaceLandmarksRequest`). If every frame has closed eyes, the app silently retriggers the burst — the user never takes a bad portrait without knowing why.

Apple filed the patent for this. Nobody has shipped it to users. Develop does.

### Pro Mode (v1.1, not launch)

A long-press on the viewfinder or a toggle in Settings reveals manual controls for users who want them: ISO, shutter speed, white balance. These are hidden by default — Develop is not a manual camera. But they're accessible for the user who wants them. Same pattern as Halide's "Quick Bar" controls.

---

## Style Presets

User picks their default in Settings. Every photo develops in that style automatically.

| Style | Description |
|-------|-------------|
| **Natural** | Default. Objectively better — sharper, better lit, more detail. Nothing stylized. |
| **Film** | Grain, warm tones, Kodak Portra 400 feel. Looks shot on film. |
| **Polaroid** | Soft vignette, faded whites, slightly square crop. Reinforces the developing metaphor. |
| **Noir** | Black and white, high contrast, cinematic. |

Styles are baked into the AI enhancement pass — not LUTs applied after. The result looks integrated, not filtered.

---

## Key UX Decisions

**The original is deleted.** After the enhanced version saves, the original is gone. The user never sees a choice. They took a photo. It developed. That's the photo. A hidden local cache holds the original for 24 hours as a silent safety net — never surfaced in the UI.

**Bad enhancements cannot happen.** The quality check + retry loop is non-negotiable. The app always delivers at least a technically improved version. The user never gets something worse than what they shot.

**Requires internet to take photos.** This is a feature, not a limitation. Develop requires a connection to develop your photos. Matches the metaphor. Matches the product.

**No video.** Photos only. Doing one thing exceptionally well.

**iOS only at launch.** Premium audience, higher LTV, simpler build.

**The developing animation** is the product's emotional core. Subtle indicator on the thumbnail while processing. When it's ready, the thumbnail pulses. The photo is developed. This is also the app's native TikTok content format — "watch this photo develop."

---

## The Differentiators

**1. Capture-time enhancement — nobody does this.**
Every competitor (Remini, Lensa, Google Pixel AI, Apple Intelligence, Facetune) requires manual effort after the photo is taken. Develop is automatic and invisible. Different product category.

**2. Agentic routing pipeline — nobody has shipped this.**
AgenticIR (ICLR 2025) and 4KAgent (NeurIPS 2025) proved academically that analyze → route → enhance → quality check → retry dramatically outperforms single-model calls. Develop is the first consumer product to ship this architecture.

**3. ProRAW + silent burst — better input than Apple.**
Apple captures 9-15 frames internally but runs conservative signal processing. Develop captures smarter, sends ProRAW to AI, and runs generative enhancement Apple won't do.

**4. Blink detection.**
Apple filed the patent. Nobody shipped it. Develop silently detects closed eyes in portrait bursts and retriggers. Users never take a bad portrait again without knowing why.

**5. Patience mode.**
Camera silently waits for the optimal moment — face in frame, eyes open, camera stable, minimal motion. Pro cameras work this way. No consumer app has built it.

**6. Style is part of enhancement, not applied after.**
Film and Polaroid aesthetics baked into the AI pass produce results that look shot on film — not filtered to look that way.

---

## What It's Not

- Not a photo editor — you never edit anything
- Not a filter app — styles are subtle and tasteful, not Instagram effects
- Not a manual camera — no controls unless you want them
- Not Remini — Remini processes photos you already took, manually, one at a time

---

## The 2-Year Window

iPhone 18 (fall 2027) will likely add native AI enhancement. The window is roughly 2 years. That's enough time to build a user base large enough to survive — the same way VSCO survived Instagram's filters and Halide survived Apple's camera improvements. Differentiated product + loyal users = survivable. The window is real. Ship in 2026.

---

## Research on File

All supporting research in `/workspace/research/camera-app/`:

| File | Contents |
|------|----------|
| `design-marketing.md` | Visual identity, UX direction, target persona, TikTok marketing playbook |
| `technical.md` | iOS architecture, API integration, background uploads, build timeline |
| `business.md` | Unit economics, competitive landscape, risks, B2B angle |
| `cutting-edge-tech.md` | State-of-art models, agentic pipeline research, on-device AI, prompt engineering |
| `competitive-deep-dive.md` | Deep teardown of every competitor, capture-time gap analysis, distribution playbook |
| `capture-pipeline.md` | ProRAW vs HEIC, multi-frame capture, blink detection, patience mode, pre-processing |

---

*Developed: 2026-03-28*
