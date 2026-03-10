I want to automate some of my facebook marketing operations automated agentic AI way. 

Use python, env and uv as package manager

I want to use Playwright
+ playwright-stealth
+ residential proxies
+ real browser profiles

1st, please implement to go to this page, scroll and Add friend, it should be 20 friend request everyday with 5 second apart. Could you try until it works? 

https://www.facebook.com/groups/LegalWindowMGL/members/contributors

Add friend button looks like this:
<span class="...">Add friend</span>

- I will use my macbook from residential proxies. 

Basically My AI marketing agent will auto control facebook. 

**• Ghost-Cursor: This is essential. It generates realistic, curved mouse movements between elements. Instead of teleporting the mouse to a button, it "glides" there like a real person**

**• Playwright-Extra: This is the wrapper that allows you to use the stealth plugin you mentioned. It also supports other plugins like recaptcha solving**

**• Confuser: A utility to add "noise" to your interactions—randomizing typing speeds and adding small delays between keystrokes**

# **2. Profile & Session Management**

# Since you want to use "Real Browser Profiles," you need a way to save and inject cookies and local storage so you don't have to log in every time (which triggers security checkpoints).

# **Playwright Persistent Context:** Use the built-in launchPersistentContext. This points Playwright to a specific folder on your MacBook where all Chrome profile data (cookies, history, cache) is saved

Always use headed browser

**Fingerprint-Generator: Use this to generate a header/fingerprint that matches a MacBook Pro specifically, so your browser headers don't look like a generic Linux server.**




- I will do lightweight marketing such as posting, scroll like and comment things, send friend request etc. around 20 actions per hour etc.

2nd: please 
https://www.facebook.com/groups/518398729138196


## Advanced filters

Self-Healing Automation: Instead of your script crashing and ending the session, the AI acts as a "on-call engineer" that wakes up only when an error occurs. It analyzes the failure, generates a fix, and continues the execution in the same window**

**Healwright:** A specialized library for Playwright that intercepts "Element not found" errors. It automatically sends a minimized version of your HTML (to save tokens) to an LLM, gets a new selector, and retries the click.


# I will do AI reel generator soon

Building an affordable AI reel generator in 2026 is much easier than it was a few years ago, thanks to the explosion of open-source models and "API-first" creative tools. You don't need a massive server farm; you just need a smart "orchestration" layer.
Here is the breakdown of how to build one without breaking the bank.

1. The Core Components (The Architecture)
To keep it affordable, you should use a modular pipeline. Instead of one giant AI doing everything, you use specialized "micro-services" for each step.
| Component | Purpose | Affordable/Open Source Choice |
|---|---|---|
| The Brain | Scriptwriting & Image Prompting | Llama 3 (via Groq for speed) or GPT-4o mini. |
| The Visuals | Generating the video clips | Wan 2.2 (Open Source) or Kling AI API (High quality/Low cost). |
| The Voice | Text-to-Speech (TTS) | Edge TTS (Free) or ElevenLabs (Top tier). |
| The Glue | Joining clips, music, and subtitles | FFmpeg (Command line) or MoviePy (Python). |
| The Polish | Dynamic subtitles | Whisper (Open Source) for timestamping. |
2. Step-by-Step Build Guide
Phase 1: Scripting
Don't just ask for a "script." Ask the LLM to output a JSON object. This makes it easy for your code to read.
- Example Output: {"scene1": "Close up of coffee", "audio1": "Start your morning right...", "duration": 3}
Phase 2: Visual Generation
- Budget Route: Use Wan 2.2 or Stable Video Diffusion (SVD). You can run these on a rented GPU (like Lambda Labs or RunPod) for about $0.40/hour.
- Quality Route: Use Google Veo 3 or Luma Dream Machine APIs. These are "pay-as-you-go," so you only pay for what you generate.
Phase 3: Assembly (The "Headless" Editor)
You don't need a GUI. Use Python to automate the edit:
- Overlay the audio on the video clips.
- Use Whisper to generate a .srt file.
- Use FFmpeg to burn those subtitles onto the video with "karaoke-style" highlighting (very popular for engagement).
1. How to Make it "Engaging" (The Secret Sauce)
An AI reel that looks like a slideshow will fail. To go viral, you need to bake these into your code:
- The 3-Second Hook: Program your script generator to always start with a "pattern interrupt"—a bold statement or a high-motion visual in the first 3 seconds.
- Dynamic Captions: Don't use static text. Use Python to make words pop up one by one. Studies show this increases "watch time" by up to 40%.
- The "J-Cut" and "L-Cut": In your assembly code, have the audio from the next scene start a split-second before the visual changes. This makes the video feel professional and "snappy."
- Trending Audio Integration: Use an API to fetch top-performing background tracks from TikTok/Instagram and mix them at 10% volume under your AI voiceover.
1. Cost Estimation (Per Reel)
If you build this yourself using the "Affordable" stack:
- LLM Script: ~$0.01
- AI Video (5 clips): ~$0.20 (using open-source models on rented GPUs)
- Voiceover: Free (Edge TTS) or ~$0.05 (ElevenLabs)
- Total: ~$0.26 per high-quality Reel.
Compare that to a $20/month subscription that limits you to 10 videos—you're saving a fortune!

> Pro Tip: If you're using Python, look into the Manim library. It was built for math animations (like 3Blue1Brown), but it’s incredible for creating sleek, high-engagement motion graphics for AI reels.
> 

Would you like me to write a basic Python script structure to help you get started with the assembly phase?

# Generative Engine Optimization (GEO) is **the next evolution of SEO designed to make content visible in AI-powered search results**

**Key Aspects of GEO (Generative Engine Optimization):**

- **Goal:** To become a trusted source or citation for LLMs (Large Language Models), rather than just ranking on a search results page.
- **Core Tactics:** Focus on clear, concise, and structured content (FAQ formats, lists, tables) that answers specific, often complex, user queries.
- **Content Strategy:** Create content that is independently understandable and highly authoritative, which AI systems can confidently summarize.
- **Metrics of Success:** Measured by brand mentions, citation frequency, and inclusion in AI-generated summaries, rather than traditional search traffic.
- **Difference from SEO:** While SEO targets specific keywords and pages, GEO targets "knowledge units" and "entities" (people, places, concepts) to train AI models on your expertise

**How to Implement GEO:**

- **Prioritize Information-Seeking Queries:** Focus on questions that AI is likely to answer directly.
- **Structure for AI:** Use clear HTML structures, question-and-answer formats, and data tables to make content easy for LLMs to interpret.
- **Establish Brand Authority:** Build a strong, consistent online presence to be recognized as an expert source.
- **Ensure Accuracy:** Maintain up-to-date, accurate information, as AI tends to penalize or avoid using unreliable sources.
- **Focus on Q&A:** Explicitly answer user questions early in the content to increase the likelihood of being cited.
