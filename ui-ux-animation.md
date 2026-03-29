# Develop — UI/UX & Animation Design Research

> Deep research report for "Develop," an iOS camera app where photos save instantly and AI-enhanced versions replace them 15-20 seconds later — like a Polaroid developing.

---

**TABLE OF CONTENTS**
1. The Developing Animation — Technical Implementation
2. Best iOS Camera App UI Patterns
3. The Camera Roll / Gallery Experience
4. Haptics, Sound, and Micro-interactions
5. Onboarding UX
6. The Full UX Flow — Every Screen

---

## Section 1: The Developing Animation — Technical Implementation

### Framework Selection: SwiftUI vs Core Animation vs Lottie

**Recommended approach: Layered architecture using SwiftUI for orchestration + Core Image/Metal for the actual image effect.**

| Framework | Best For | Limitations |
|-----------|----------|-------------|
| **SwiftUI Animations** | Orchestrating state transitions (opacity, scale, blur radius changes), UI chrome animations, thumbnail transitions | Not ideal for pixel-level image manipulation; `.blur()` modifier is view-level, not image-level |
| **Core Animation (CALayer)** | Complex, multi-property keyframe animations; precise timing control; GPU-accelerated layer compositing | Requires `UIViewRepresentable` bridge in SwiftUI; more boilerplate |
| **Core Image (CIFilter)** | Real-time image processing — gaussian blur, saturation, color adjustments, dissolves | Perfect for the actual "developing" effect on the photo itself |
| **Metal / MPS** | Maximum GPU performance for real-time filter chains; `MPSImageGaussianBlur` for hardware-accelerated blur | Overkill for simple transitions; right choice if chaining multiple filters |
| **Lottie** | Pre-designed overlay animations (shimmer effects, progress indicators, decorative elements) | Wrong tool for the core image reveal — Lottie animates vector art, not raster image transformations |

**Verdict:** Use **Core Image (`CIFilter`) driven by SwiftUI state** for the photo-level developing effect. Use **SwiftUI's native animation system** for all UI transitions. Reserve **Lottie** only for decorative overlay animations (e.g., a subtle shimmer or sparkle effect on the developing indicator).

### The "Developing" Effect — Technical Implementation

The developing effect should feel like a Polaroid coming to life. Here's the recommended multi-layer approach:

**Phase 1: Capture → Instant Save (0-1s)**
- Photo saves immediately as the "undeveloped" version
- Thumbnail appears in the corner with a warm, slightly desaturated treatment
- A subtle amber glow or pulse indicates "developing"

**Phase 2: Developing State (1-18s)**
- The thumbnail shows a **gentle animated shimmer** — a warm amber gradient that sweeps across the image on loop
- This is NOT a blur-to-sharp transition (that would require the final image, which isn't ready yet)
- The shimmer communicates "something is happening" without promising what the result will look like
- Implementation: SwiftUI `LinearGradient` with animated offset, overlaid on the thumbnail at ~20% opacity

**Phase 3: The Reveal (18-20s)**
- The AI-enhanced image arrives from the server
- **The reveal animation** (the money shot):
  1. Cross-dissolve from original to enhanced image using `CIDissolveTransition` (Core Image) — 1.5-2s duration
  2. Simultaneously animate: slight desaturation → full color, subtle blur (radius 3→0) → sharp
  3. A barely-perceptible scale pulse (1.0 → 1.02 → 1.0) draws the eye
  4. The shimmer overlay fades out as the dissolve begins

**Core Image Filter Chain for the Reveal:**
```
CIGaussianBlur (inputRadius: 3 → 0, animated over 1.5s)
CIColorControls (inputSaturation: 0.7 → 1.0, animated over 1.5s)
CIExposureAdjust (inputEV: -0.1 → 0, subtle brightness lift)
```
Drive the filter parameters from a SwiftUI `@State` property animated with `.easeOut(duration: 1.5)`.

### How Spectre Camera Handles Processing State

Spectre (by the Halide team / Lux Optics) processes long exposures using ML and Metal. During capture:
- The viewfinder shows a **live preview of the exposure building** — frames accumulate in real-time
- The processing state uses Metal graphics acceleration to blend frames
- After capture, the result saves as a Live Photo, letting you replay the exposure process
- Key insight: **Spectre makes the wait part of the experience** — you watch the image form. Develop should adopt this philosophy: the developing animation IS the feature, not a loading spinner.

### BeReal's Async Reveal Mechanic

BeReal's architecture is simpler than Develop's but relevant:
- Photos upload to cloud storage (Firebase/GCS) immediately after capture
- The "reveal" is social, not computational — you can't see others' photos until you post yours
- Technically: two images (front + back camera) upload as separate requests, then a finalization API call links them
- The reveal uses a simple **fade-in transition** when unlocking friends' photos
- Key takeaway: BeReal proves that **delayed gratification works** as a UX mechanic — users find the anticipation engaging, not frustrating

### Animation Timing That Feels Premium

Based on research into SwiftUI animation curves and Apple's HIG:

| Animation | Duration | Curve | Why |
|-----------|----------|-------|-----|
| Shimmer loop (developing state) | 2.0s per cycle | `.linear` | Continuous, hypnotic, non-distracting |
| Image reveal cross-dissolve | 1.5s | `.easeOut` | Fast start catches attention, gentle finish feels natural |
| Blur dissolve (3→0 radius) | 1.5s | `.easeOut` | Matches the cross-dissolve timing |
| Saturation fade-in | 1.5s | `.easeInOut` | Color should bloom gradually, not snap |
| Scale pulse on completion | 0.4s | `.spring(response: 0.32, dampingFraction: 0.72)` | Lively, noticeable, Apple Music-quality feel |
| Thumbnail slide-in after capture | 0.3s | `.snappy(duration: 0.25)` | Fast, modern iOS feel |

**Frame rate:** All animations should target 60fps minimum. Core Image filter animations can use `CADisplayLink` to ensure frame-perfect timing. On ProMotion devices (120Hz), the shimmer and reveal will feel especially smooth.

**What feels cheap vs premium:**
- ❌ Cheap: Linear opacity fade, abrupt property changes, bouncy springs on photos, skeleton loading screens
- ✅ Premium: Layered property animations (blur + saturation + scale simultaneously), easeOut curves, spring animations with high damping (0.72-0.85), subtle scale changes (< 5%)

### Lottie's Role

Lottie is **not the right tool for the core developing effect** — that requires real-time image manipulation. However, Lottie is excellent for:
- **The developing indicator badge** — a small animated icon (e.g., an hourglass, a chemical flask, or an abstract amber swirl) that overlays the thumbnail during processing
- **Onboarding animations** — explaining the developing concept with polished vector animations
- **Empty states** — animated illustrations when the gallery is empty
- **Celebration moments** — a subtle particle effect when the first photo develops

Use Airbnb's `lottie-ios` with the dotLottie player for optimal performance. Keep Lottie animations under 10s and avoid complex expressions that cause frame drops.

---


## Section 2: Best iOS Camera App UI Patterns

### Halide's Design Philosophy — The Gold Standard

Halide (by Lux Optics) is the most relevant reference for Develop's UI direction. Key principles from their design:

**"We didn't say we made an app — we say we made a camera."** This philosophy underpins everything. The interface disappears in service of the image. Key takeaways:

- **Gesture-modeled-after-dials:** Swiping up/down for exposure, left/right for focus — mimics physical camera manipulation. Creates muscle memory.
- **Single highlight color (yellow):** Only one accent color to indicate active state. For Develop, this maps perfectly to warm amber.
- **Excitement without intimidation:** Complexity exists but never overwhelms. Pro tools are there but don't clutter the default view.
- **Edge gestures for mode switching** (Mark II): Swipe from edges to change modes, keeping the viewfinder unobstructed.
- **Custom typefaces:** Three custom typefaces based on etched type from camera bodies/lenses. Typography as identity.
- **One-hand design:** "Designed to be used with one hand on all phones without compromising on power."
- **Privacy by design:** No tracking, no data collection. A trust signal that resonates with the target audience.

**Halide III (2025):** Planned complete UI redesign + one-tap color grading (most requested feature). Apple reportedly tried to acquire Lux Optics — validating the design approach.

### What Makes a Viewfinder Feel Premium

Based on analysis of Halide, Obscura, and Apple's native Camera:

| Element | Premium Feel | Cheap Feel |
|---------|-------------|------------|
| **Background** | True black (#000000) — OLED pixels off | Dark gray, gradients, patterns |
| **Controls** | Minimal, context-aware, appear when needed | Always visible, cluttered |
| **Typography** | Custom or carefully chosen monospace/sans-serif, consistent | System default, inconsistent sizing |
| **Spacing** | Generous padding, breathing room | Cramped, elements touching |
| **Transitions** | Smooth spring animations between states | Instant snaps or linear fades |
| **Information** | Show only what matters NOW | Show everything simultaneously |
| **Touch targets** | 44pt minimum, generous hit areas | Tiny buttons requiring precision |

**For Develop specifically:** The viewfinder should be almost entirely image. A dark status bar area at top (time, battery — standard iOS). Controls at bottom in the thumb zone. The only persistent elements: shutter button, gallery thumbnail, and a subtle mode indicator. Everything else hidden or gestural.

### Control Placement — The Anatomy of a Camera App

**Bottom Bar (Primary Zone — Thumb Reach):**
- Center: **Shutter button** — large (70-80pt), prominent, the dominant element
- Left of shutter: **Gallery thumbnail** — last photo taken, rounded rectangle, ~44pt
- Right of shutter: **Flash/mode toggle** — secondary action

**Viewfinder Overlays (Minimal):**
- Top-left: Back/close (if navigated from gallery)
- Top-right: Settings gear or filter indicator (only when relevant)
- No persistent overlays on the viewfinder image itself

**Hidden/Gestural Controls:**
- Swipe up from bottom bar: Reveal style selector (Natural/Film/Polaroid/Noir)
- Pinch: Zoom (matched to native Camera expectation)
- Tap viewfinder: Focus point (with animated ring)
- Long-press shutter: Burst mode (optional, future feature)

### How The Best Apps Handle the Shutter Button

**Halide:** Textured, tactile shutter button with haptic feedback. Distinctive design — not a plain circle. Position: center-bottom, large.

**Obscura:** "Controls can be reached with one thumb, and gestures and haptics combine to create a tactile experience." Entirely gesture-based control with haptic feedback. The control wheel was replaced by gestures in v3, improving single-thumb control.

**Apple Camera (iOS 18+):** Physical Camera Control button on iPhone 16. Light press for adjustments, full press for shutter. Haptic feedback simulates mechanical feel.

**For Develop:**
- **Size:** 72pt diameter — larger than most apps. This is a one-button camera; the shutter should dominate.
- **Design:** Warm amber ring with a dark center. Subtle inner glow. Not a flat circle — slight depth/shadow.
- **Animation on tap:** Scale down to 0.92 → spring back to 1.0 (0.15s, spring damping 0.6). Amber ring pulses once.
- **Haptic:** `UIImpactFeedbackGenerator(.medium)` on tap. Satisfying but not jarring.

### Information Density — What's Visible vs Hidden

**Develop is NOT a pro camera app.** It's the anti-Halide in terms of information density. The target user doesn't want ISO readouts or histograms. They want to point, shoot, and get a great photo.

**Always visible (3 elements max):**
1. Shutter button
2. Last photo thumbnail (with developing indicator if processing)
3. Ambient mode hint (e.g., tiny "Film" label if non-default style selected)

**Visible on interaction:**
- Focus ring (on tap)
- Zoom indicator (on pinch)
- Flash state (on toggle)

**Hidden in settings/sheets:**
- Style selection (Natural/Film/Polaroid/Noir)
- Resolution preferences
- AI processing toggle
- Account/subscription

### One-Handed Use & Thumb Zones

Based on 2026 phone sizes (6.1"-6.9" screens), the reachable thumb zone for right-handed use covers roughly the bottom-right 40% of the screen. For left-handed, bottom-left 40%.

**Develop's approach:**
- All interactive elements live in the **bottom 25%** of the screen
- The viewfinder fills the remaining 75% — pure image
- No controls in the top half that require frequent access
- Swipe gestures work from any screen position (no need to reach specific buttons)
- Support both portrait and landscape, but optimize for **portrait one-handed shooting** (how most people actually use their phones)

### Natural Gestures for a Camera App

| Gesture | Action | Precedent |
|---------|--------|-----------|
| **Tap viewfinder** | Set focus point | Universal (Apple Camera, Halide, all) |
| **Pinch** | Zoom in/out | Universal |
| **Swipe left on viewfinder** | Open gallery | Apple Camera pattern |
| **Swipe up on bottom bar** | Reveal style selector | Instagram-inspired |
| **Double-tap viewfinder** | Reset focus to auto | Halide pattern |
| **Swipe down** | Dismiss overlays/sheets | iOS standard |
| **Long press shutter** | Future: burst or video | Apple Camera pattern |

---

## Section 3: The Camera Roll / Gallery Experience

### Gallery Architecture: In-App vs Native Photos

**Recommendation: Dual approach — in-app gallery as primary, with automatic save to Photos library.**

| Approach | Pros | Cons |
|----------|------|------|
| **In-app gallery only** | Full control over developing UX, before/after, states | Users can't find photos in their normal workflow |
| **Native Photos only** | Zero friction, familiar | Can't show developing state, can't do before/after, loses the magic |
| **Hybrid (recommended)** | Best of both worlds | Slightly more complexity |

**How the hybrid works:**
1. Photos always save to the native Photos library via `PHPhotoLibrary` (using "Add Only" permission — no need to read the full library)
2. The in-app gallery is the premium experience — shows developing states, before/after, style info
3. When AI-enhanced version arrives, the app updates the photo in the Photos library using `PHAssetChangeRequest`
4. The in-app gallery uses a local database (SwiftData or Core Data) to track metadata: original photo reference, AI version, processing status, style applied, timestamps

**Privacy advantage:** Using "Add Only" permission (introduced iOS 14) means the app never needs to read the user's photo library. This is a trust signal and simplifies the permission flow.

### Gallery Grid Design

**Layout:** 3-column uniform grid with 2pt spacing between cells. Rounded corners (8pt radius) on each thumbnail. Dark background (#000000).

**Why 3 columns:** Matches Apple Photos and Instagram — users expect this layout. 4 columns makes thumbnails too small to see developing states. 2 columns wastes space and feels like a feed, not a gallery.

**Thumbnail sizing:** Square crops, aspect-fill. Each thumbnail is roughly (screen width - 8pt spacing) / 3 = ~127pt on iPhone 16 Pro.

**Scroll behavior:** Standard `LazyVGrid` with smooth scrolling. No pagination — infinite scroll within the app's photo collection.

### Showing "Developing" State on Thumbnails

This is the signature UX moment in the gallery. When a photo is still developing, the thumbnail must communicate this clearly but elegantly.

**Recommended approach — The Amber Pulse:**

1. **Thumbnail shows the original (undeveloped) photo** — slightly desaturated overlay (opacity 0.15 black)
2. **Warm amber border** — 2pt border in the accent color, with a subtle pulsing glow animation
3. **Small amber dot indicator** — bottom-right corner, 8pt diameter, gentle pulse animation (scale 0.8→1.2, repeating)
4. **No text label** — the visual language should be self-explanatory after onboarding explains it once

**When developing completes:**
- The amber border and dot fade out (0.3s)
- The thumbnail briefly flashes with a subtle brightness increase (like a camera flash in miniature)
- The desaturation overlay lifts, revealing the full-color enhanced image
- A tiny checkmark or sparkle replaces the dot momentarily (0.5s), then fades

**What NOT to do:**
- ❌ Skeleton/shimmer placeholder — this isn't loading content, the original photo IS there
- ❌ Progress bar — the wait time is short and variable; a progress bar creates anxiety
- ❌ Blur overlay — makes the gallery look broken
- ❌ "Processing..." text — clutters the grid, doesn't scale

### Before/After Comparison — UI Pattern

**Primary interaction: Tap-and-hold to toggle.**

After evaluating sliders, split screens, and tap toggles:

| Pattern | Pros | Cons | Best For |
|---------|------|------|----------|
| **Draggable slider** | Precise comparison, dramatic | Complex gesture, blocks part of image | Dedicated comparison apps, editing tools |
| **Split screen** | See both simultaneously | Each image is half-size, awkward with portraits | Side-by-side technical comparison |
| **Tap to toggle** | Simple, full-size view of each | Can't see both at once, easy to miss differences | Quick casual comparison |
| **Hold to see original** ✅ | Instant, intuitive, full-size, one-gesture | Requires hold instruction | Develop's use case |

**Recommended: "Hold to see original"**

- Default view: The developed (AI-enhanced) photo at full resolution
- **Press and hold anywhere on the image:** Cross-dissolve (0.2s, easeOut) to the original version. A subtle "Original" label fades in at top
- **Release:** Cross-dissolve back to the enhanced version. Label fades out
- This is the exact pattern used by the native iOS Camera for Live Photos (hold to play) — users already understand it
- A small "Hold for original" hint text appears on first use, then disappears after 3 uses

**Secondary option: Swipe horizontally** between original and enhanced as two "pages" in the detail view. This gives users a second way to compare without discovering the hold gesture.

### The Moment the Enhanced Version Arrives

When the user is looking at the gallery and a photo finishes developing:

**If the photo is visible on screen:**
1. The amber pulse stops
2. A brief, warm flash effect on the thumbnail (amber → white → clear, 0.4s)
3. The thumbnail smoothly transitions from original to enhanced
4. Haptic: `UIImpactFeedbackGenerator(.light)` — a gentle tap to draw attention

**If the photo is NOT visible on screen (scrolled away):**
- No intrusive notification
- When the user scrolls back, the photo simply shows as developed (no amber border)
- The gallery header could show a subtle count: "3 photos developed" that auto-dismisses

**If the user is in the camera view (not the gallery):**
- The gallery thumbnail in the bottom-left corner updates silently
- The developing indicator on the thumbnail stops
- No banner, no sound, no interruption — the camera experience is sacred

**If the app is backgrounded:**
- Optional: A silent notification that updates the app badge
- NEVER a push notification for individual photos — that's spam
- The notification value is in the aggregate: "5 photos developed while you were away" (shown passively when reopening the app)

---


## Section 4: Haptics, Sound, and Micro-interactions

### The Haptic Language of Develop

Haptics are not decorative — they're communication. Every haptic should mean something specific and feel distinct. The Develop haptic vocabulary:

| Moment | Haptic | Why |
|--------|--------|-----|
| Shutter tap | `UIImpactFeedbackGenerator(.medium)` | Satisfying, mechanical feel — mirrors a physical shutter |
| Photo saved to camera roll | `UIImpactFeedbackGenerator(.light)` | Lighter than shutter — "captured, now processing" |
| Development complete | `UINotificationFeedbackGenerator(.success)` | The payoff moment — distinctly different from capture |
| Focus lock | `UIImpactFeedbackGenerator(.rigid)` | Sharp, precise — confirms locked state |
| Style change | `UISelectionFeedbackGenerator()` | Subtle click per option — picker behavior |
| Paywall hit | none | Avoid negative haptic associations |

**What NOT to do:**
- No haptic on the shimmer animation — that would be constant and maddening
- No haptic on zoom — the native Camera doesn't, and users would find it bizarre
- No custom `CHHapticEngine` patterns at launch — they're complex, can feel gimmicky, and the standard generators cover all use cases here

### Sound Design

The temptation is to add a developing sound — a darkroom chemical sizzle, a Polaroid whirring. Don't.

**Shutter sound only.** The native iOS shutter sound (or a custom, premium variant) on capture. That's it.

Reasons:
1. Users shoot in silent environments — meetings, concerts, intimate moments. Sounds other than the shutter are intrusive.
2. iOS enforces the shutter sound in some regions (Japan, South Korea) by law. Any additional sounds compound this problem.
3. The developing mechanic is a visual and haptic experience, not an audio one. Adding sound makes it feel like a notification, not a photo developing.

**Optional:** An extremely subtle "reveal" sound when development completes — something like a quiet, high-end film camera advance sound (< 0.5s, very low volume). This respects the user's audio context but rewards those paying attention. Make it opt-in in settings.

**Implementation:** `AVAudioPlayer` with a pre-loaded audio buffer. Keep the file under 100KB. Use `AVAudioSession.Category.ambient` so it mixes with music.

### Micro-interactions

**Focus tap indicator:**
- Animated ring appears at tap location — expands from center (0.5x → 1.0x scale, 0.2s easeOut), then pulses once before settling
- Amber color (matches accent)
- Auto-dismisses after 3 seconds if no further interaction
- A tiny "AF" or lock icon appears inside the ring when focus locks

**Zoom state:**
- No UI element by default — just the pinch gesture working
- When actively zooming: a minimal zoom level indicator fades in at top-center ("2.0x"), fades out 1 second after pinch ends
- No zoom track/slider — that's pro territory and adds visual noise

**Shutter button press animation:**
- Tap: scale to 0.92 instantly, spring back to 1.0 (0.15s, spring damping 0.6, response 0.3)
- The amber ring briefly pulses outward (scale 1.0 → 1.08 → 1.0, 0.3s)
- Simultaneously: viewfinder flashes white very briefly (opacity 0.15, 0.1s) — mimics a camera flash

**Style selector:**
- Swipe up reveals a bottom sheet with 4 options: Natural, Film, Polaroid, Noir
- Active style shows amber underline
- Switching styles: `UISelectionFeedbackGenerator` click + tiny animation showing the new style name
- The viewfinder live-previews the style toning (a subtle filter applied to the live viewfinder — not the captured image, just the preview)

**Gallery transitions:**
- Tap photo thumbnail → expand to full screen: zoom-from-thumbnail transition (matched geometry animation in SwiftUI) — same transition Apple Photos uses
- Swipe down to dismiss: drag-to-dismiss with velocity-responsive spring return
- All transitions 60fps minimum, 120fps on ProMotion devices

---

## Section 5: Onboarding UX

### The Principle: First Great Photo as Fast as Possible

Every screen before the first enhanced photo is a cost. The goal is to get the user to their first "wow" moment — seeing their first developed photo — in under 2 minutes from first launch. Every unnecessary screen before that moment reduces the probability they stay.

**Optimal onboarding length: 3 screens + 2 permission dialogs.**

### Screen 1: The Promise (10 seconds to read)

Full-screen, dark background. A before/after pair of a compelling real photo — not a stock image, an actual compelling shot. A zoo animal or night scene works perfectly for this.

Text:
- Large: **"Take a photo."**
- Small pause in the design
- Large: **"Watch it develop."**
- Below: "Develop uses AI to make every photo you take look professionally shot. No editing. No effort."
- CTA button: "Get Started" (amber, full-width)

No feature lists. No bullet points. Just the promise, proven by the before/after photo behind it.

### Screen 2: Camera Permission (the most important screen)

**Context before the system dialog.** Apple requires the system dialog — but you control what the user reads right before it appears.

Design: Centered card, dark background, simple camera icon in amber.

Text:
- **"Develop needs your camera"** (headline)
- "To take photos and develop them automatically, Develop needs access to your camera." (subhead)
- Small: "Your photos are processed to enhance quality and are never stored or shared."
- CTA: "Allow Camera Access" (amber button)

On button tap: present the system `AVCaptureDevice` permission dialog.

**If denied:** Show a recovery screen explaining how to enable in Settings, with a direct deep link via `UIApplication.openSettingsURLString`.

**Research-backed:** Camera permission grant rates are highest when the context screen:
1. Explains the specific benefit ("to develop your photos")
2. Includes a privacy statement before the ask
3. Uses first-person app name ("Develop needs") rather than passive ("Camera access is required")

### Screen 3: AI Disclosure (legally required, Apple Guideline 5.1.2i)

Must be clear and affirmative — user must actively consent.

Design: Same card style. Small AI/processor icon.

Text:
- **"Your photos are enhanced by AI"** (headline)
- "When you take a photo, Develop sends it to Topaz Labs' AI servers for enhancement. The process takes 10-30 seconds. Your original photo is saved immediately and the enhanced version replaces it."
- "Enhanced photos may differ from the original. You can always see the original by holding the photo."
- Toggle: "I understand my photos will be processed by AI" (must be ON to continue)
- CTA: "Start Shooting" (amber, full-width) — disabled until toggle is on

**Note:** This is not a legal wall. It's a feature explanation that happens to also satisfy the legal requirement. Frame it as "here's how the magic works," not "here's a disclaimer."

### Photos Library Permission

**Don't ask for it upfront.** Ask for "Add Only" permission the first time a developed photo is ready to save — at the moment of maximum motivation (the user just saw their first enhanced photo and wants it in their camera roll). This dramatically increases grant rates vs. asking cold on launch.

### What Apple Onboarding Research Shows

- **Permission grant rates increase 30-40%** when context screens precede system dialogs
- **Users spend 8-12 seconds on onboarding screens** — copy must be scannable
- **The "try before you buy" effect:** If users can take at least one photo before seeing a paywall, conversion rates are 2-3x higher than paywalling on first launch
- **Progress indicators** ("2 of 3") increase completion rates vs. no indicator
- **Single-task screens** (one thing per screen) outperform multi-item screens

### What Halide and !Camera Do

**Halide:** Minimal onboarding. The app's design philosophy is communicated through the interface itself — you understand what it is by using it. Permission asks are contextual, not upfront.

**!Camera:** Even more minimal. Opens directly to the camera. Permission dialog appears when you first try to shoot. No marketing onboarding screens at all. This works because the brand is already known to their enthusiast audience. For Develop targeting mass consumers, slightly more explanation is warranted.

**The balance:** Develop should be closer to !Camera (minimal) than Remini (lengthy). 3 screens is the ceiling.

---

## Section 6: The Full UX Flow — Every Screen

### Screen 1: Launch / Splash
- Black screen, amber Develop circle logo (the aperture mark)
- Logo fades in (0.3s), holds 0.3s, app transitions to camera or onboarding
- No loading spinner — if the app needs network connectivity, check silently in background
- Duration: < 0.8s total

### Screen 2-4: Onboarding (first launch only)
- Screen 2: The Promise (before/after photo + "Take a photo. Watch it develop.")
- Screen 3: Camera permission context + system dialog
- Screen 4: AI disclosure + consent toggle
- Progress: Three amber dots at bottom, current one filled
- Skip: None — all three screens are necessary (2 are legally/technically required)

### Screen 5: Main Camera Viewfinder (primary screen)
**Layout:**
- Full-screen viewfinder (edge to edge, even under status bar)
- Status bar: transparent, white text (time, battery, signal)
- Bottom bar (safe area inset): black, ~100pt tall
  - Left: Gallery thumbnail (44x44pt, rounded rectangle, 8pt radius) — shows most recent photo with amber pulse if developing
  - Center: Shutter button (72pt diameter, amber ring, dark fill)
  - Right: Flash toggle (34pt icon, amber when on) or camera flip (if front-facing mode added later)
- Viewfinder overlays appear only on interaction (focus ring, zoom indicator)
- No mode switchers, no format selectors, no timer

**Interactions:**
- Tap viewfinder: focus point (amber ring animation)
- Pinch: zoom (zoom indicator fades in)
- Swipe up from bottom bar: style selector sheet
- Tap gallery thumbnail: navigate to gallery
- Long-press gallery thumbnail: quick peek at last photo (spring sheet preview)

### Screen 6: Style Selector (sheet, not full screen)
**Layout:**
- Bottom sheet, ~180pt tall, dark background, rounded corners (12pt)
- Four options in a horizontal row: Natural · Film · Polaroid · Noir
- Active option: amber underline, slightly larger text
- Each option: small icon above text (circle for Natural, grain texture for Film, etc.)
- Dismiss: tap anywhere outside, swipe down, or tap the current camera

**Behavior:**
- Changing style: selection haptic + live viewfinder previews the style toning
- Style persists across sessions (saved to UserDefaults)
- Label on viewfinder when non-default style active: tiny amber pill "Film" in top-right corner

### Screen 7: Photo Captured (brief transition state)
- Shutter animation: white flash overlay (opacity 0.15, 0.1s) + scale pulse on button
- Save haptic (.light) immediately after shutter haptic
- Gallery thumbnail updates to show new photo with amber developing border
- No modal, no confirmation — return immediately to viewfinder
- Duration: < 0.3s before fully back to shooting

### Screen 8: Gallery View
**Layout:**
- Navigation bar: dark, "Develop" title (or just the circle logo), Settings gear (right)
- 3-column grid, 2pt gaps, no section headers
- Most recent photo first (top-left)
- Developing photos: amber pulse border, subtle desaturation
- Developed photos: full color, no border
- Bottom: tab bar or none (single-screen app — consider no tab bar)

**Entry/exit:**
- Enter from camera: slide up from bottom (cards-style) or cross-fade
- Exit to camera: swipe down or tap a "Camera" button

**Empty state:**
- First launch before any photos: "Take your first photo." with arrow pointing back
- Lottie animation: subtle ambient animation of a Polaroid developing

### Screen 9: Photo Detail View
**Layout:**
- Full-screen photo (enhanced version by default), edge to edge
- Top: transparent overlay with back chevron (left) and share button (right)
- Bottom: "Hold to see original" hint on first view (fades after 3 uses)
- If still developing: amber shimmer overlays the photo, "Developing..." text at bottom center

**Interactions:**
- Hold: cross-dissolve to original (0.2s), "Original" label fades in
- Release: cross-dissolve back to enhanced
- Swipe left/right: navigate to adjacent photos
- Swipe down: dismiss back to gallery (drag-to-dismiss)
- Tap share: iOS share sheet with enhanced photo
- Long press: context menu (Share, Copy, "View Original", Delete)

**Developing state in detail view:**
- If user taps a thumbnail that's still developing, they see the original photo with the amber shimmer overlay
- Bottom text: "Developing... ~10 seconds"
- When it completes: amber flash, cross-dissolve to enhanced version, success haptic

### Screen 10: Settings
**Layout:**
- Standard iOS settings-style grouped table
- Header: Develop logo + version

**Sections:**
1. **Style** — current style with right detail, taps into style selector
2. **Account** — subscription status, manage subscription (opens App Store)
3. **Privacy** — "How AI processing works" (explains the pipeline, addresses concerns), "Delete my data"
4. **About** — Credits, privacy policy, terms, version

**No toggle to disable AI processing** — that defeats the entire product. If users don't want AI enhancement, they shouldn't be using Develop.

### Screen 11: Paywall
**When it appears:** When user takes their 11th photo in a day (exceeds free tier of 10/day).

**Layout:**
- Minimal, dark, no aggressive tactics
- Large text: "You've developed 10 photos today."
- Subhead: "Upgrade to develop unlimited photos."
- The comparison:
  - Free: 10 photos/day
  - Pro ($4.99/month): Unlimited photos, all styles, priority processing
- Single CTA: "Start Pro — $4.99/month" (amber, full-width)
- Below: "Restore Purchase" (text link) + "Not now" (smaller text)
- No countdown timers, no artificial scarcity, no guilt language

**After paywall hit:**
- The photo they just took still saves normally
- It just won't be enhanced (shows as "Development paused" in developing state)
- When they upgrade, queue drains and all paused photos develop

**What to avoid:**
- No "LIMITED TIME OFFER" banners — these signal desperation
- No blocking the entire app — always let them take photos and save originals
- No dark patterns — Remini's playbook is the cautionary tale

---

## Summary: The UX Principles Behind Every Decision

1. **Get out of the way.** The photo is the product. The app is the frame. Every pixel of UI that isn't the viewfinder or the photo is overhead.

2. **The developing mechanic is the product's soul.** Design every interaction to respect and celebrate it. The shimmer is not a loading state — it's anticipation. The reveal is not a transition — it's the moment the app earns its keep.

3. **One task, one screen.** The viewfinder shoots. The gallery shows photos. Settings configure. No screen does two things.

4. **Haptics speak when visuals can't.** The user might be looking at the subject through the viewfinder, not the screen. The haptic sequence (shutter → save → develop complete) tells the story without requiring attention.

5. **Premium means invisible craft.** The spring curves, the amber glow, the matched geometry transitions — users won't notice them. But they'll feel the difference between this and a cheap app without being able to say why.

6. **Never interrupt a shooter.** Notifications, banners, alerts during camera use break the experience irreparably. All async events (development complete, paywall triggers, errors) are handled silently and reviewed on the user's schedule.

---
*UI/UX research compiled 2026-03-28*
