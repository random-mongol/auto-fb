Automatically produce short, engaging **informational legal Reels** (Instagram / TikTok / YouTube Shorts) with minimal manual work.

- Each step must generate artifact and should be resumable from the step

Pipeline:
**Topic → Script → Voice → Visuals → Edit → Publish**

---

# 1. Content Pipeline Architecture

```
Legal Topic Source
      ↓
Script Generation (LLM)
      ↓
Hook Optimization
      ↓
Voiceover Generation
      ↓
Visual / B-roll Generation
      ↓
Video Assembly
      ↓
Auto Subtitles
      ↓
Auto Posting
```

---

# 2. Step-by-Step Implementation

## Step 1 — Auto-Generate Topics

1. Get topic:
Fetches articles from `https://huuli.tech/sitemap.xml` like auto facebook poster
 - Filters out already generated reels using DB table.
 - Select one, go into URL and fetch text


## Step 2 — Generate the Script

Ideal reel structure:

```
0–2 sec   Hook
2–10 sec  Problem
10–20 sec Explanation
20–30 sec Takeaway
```

Example script:

```
Hook:
Did you know police usually cannot search your phone without a warrant?

Body:
Your phone contains private digital information.
Courts treat it differently than physical objects.

Rule:
Police normally need a warrant before searching your phone.

Exception:
Unless you consent or there is an emergency.

Takeaway:
Never unlock your phone unless you clearly understand your rights.
```

LLM prompt:

```
Write a 30-second legal educational reel script.

Rules:
- very simple language
- strong hook
- one legal insight
- maximum 80 words
```

---

## Step 3 — AI Voiceover

Tools:

| Tool       | Quality     | Notes          |
| ---------- | ----------- | -------------- |
| ElevenLabs | excellent   | most realistic |

Automation example:

```
script.txt
→ ElevenLabs API (Get word timestamps)
```

---

## Step 4 — Generate Visuals

Generate backgrounds programmatically.

Examples:

animated gradients

particle effects

slow motion patterns

blurred motion loops
---

# 5. Video Assembly

Libraries:

### Python

```
moviepy
ffmpeg
opencv
```

Example flow:

```
voice.mp3
+ background clips
+ subtitles
+ logo
→ reel.mp4
```

Structure:

```
0–3s   Hook text
3–25s  Visual explanation
25–30s Call to action
```

---

# 6. Auto Subtitles (VERY IMPORTANT)

Most reels are watched **without sound**.


Get word timestamps from elevenlabs -> Then ( script → caption groups → timestamps

Design principles:

Rule	Explanation
1–5 words per caption	faster comprehension
Highlight keywords	increases retention
Big center text	optimized for phone viewing
Rapid changes	increases engagement

Style:

```
BIG BOLD captions
dynamic highlight words
```

Example:

```
YOU CANNOT
be arrested
just for refusing
to answer police questions.
```

---

Bad:

-----
If
police
ask
you
to
unlock
your
phone
-----

Good:
-----
IF POLICE ASK
TO UNLOCK YOUR PHONE
-----

# 7. Auto Posting (coming soon)

Post to Meta 

---

# 9. Optimal Reel Structure

```
0–2 sec
Pattern interrupt hook

3–10 sec
Curiosity + context

10–20 sec
Explain rule

20–30 sec
Takeaway
```

Example:

```
Hook:
Most people sign contracts that are legally invalid.

Explanation:
If a contract lacks mutual consideration, courts may not enforce it.

Takeaway:
Never sign an agreement unless both sides exchange value.
```