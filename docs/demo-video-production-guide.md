# Demo Video Production Guide

This guide provides a step-by-step checklist for producing the mcpbr Claude Code plugin demo video.

---

## Pre-Production Checklist

### Environment Setup

- [ ] **Clean macOS/Linux environment**
  - [ ] Remove personal files/folders from desktop
  - [ ] Close unnecessary applications
  - [ ] Disable notifications (Do Not Disturb mode)
  - [ ] Hide menu bar items (optional, macOS: `Bartender` app)
  - [ ] Clear terminal history: `history -c`

- [ ] **Terminal configuration**
  - [ ] Install professional font: JetBrains Mono, Fira Code, or SF Mono
  - [ ] Configure dark theme: Dracula, Nord, or Tokyo Night
  - [ ] Set font size: 16-20pt for readability
  - [ ] Window size: 120 columns × 30 rows
  - [ ] Enable cursor highlighting/visibility
  - [ ] Configure prompt: Keep it simple, e.g., `$ ` or `user@host:~$`

- [ ] **Install required software**
  - [ ] Docker Desktop (ensure it's running)
  - [ ] Python 3.11+
  - [ ] mcpbr: `pip install mcpbr`
  - [ ] Claude Code CLI: `claude` command available
  - [ ] Node.js (for npx commands)
  - [ ] Screen recording software (OBS Studio, ScreenFlow, QuickTime)

- [ ] **Set environment variables**
  - [ ] `export ANTHROPIC_API_KEY="sk-ant-..."`
  - [ ] Test key: `claude --version`
  - [ ] Optional: Create `.env` file for easy sourcing

- [ ] **Prepare demo repository**
  - [ ] Clone mcpbr: `git clone https://github.com/greynewell/mcpbr.git`
  - [ ] Navigate to directory: `cd mcpbr`
  - [ ] Verify plugin exists: `ls -la .claude-plugin/`
  - [ ] Remove any existing configs: `rm -f mcpbr.yaml`
  - [ ] Clear any old results: `rm -f results.json report.md`

### Equipment & Software

- [ ] **Microphone**
  - [ ] Test microphone levels (aim for -12dB to -6dB average)
  - [ ] Use pop filter to reduce plosives
  - [ ] Position mic 6-8 inches from mouth
  - [ ] Test recording: speak a few lines and listen back
  - [ ] Use headphones to monitor audio while recording

- [ ] **Recording software setup**
  - [ ] Configure resolution: 1920×1080 minimum
  - [ ] Set frame rate: 30fps or 60fps
  - [ ] Choose codec: H.264 for compatibility
  - [ ] Test recording: 30-second test clip
  - [ ] Verify audio is captured cleanly
  - [ ] Set up keyboard shortcuts for start/stop

- [ ] **Lighting (if showing yourself)**
  - [ ] Face a window or use key light
  - [ ] Avoid harsh shadows
  - [ ] Test camera positioning and framing

### Script Preparation

- [ ] **Print or display script**
  - [ ] Have script visible on second monitor (if available)
  - [ ] Use teleprompter app (optional): PromptSmart, Teleprompter Premium
  - [ ] Highlight key phrases and timing cues
  - [ ] Mark pauses and inflection points

- [ ] **Practice voiceover**
  - [ ] Read through script 5+ times
  - [ ] Record practice takes and listen critically
  - [ ] Time yourself (target: ~3 minutes)
  - [ ] Identify difficult phrases and practice them
  - [ ] Warm up voice: hum, do vocal exercises

- [ ] **Prepare terminal commands**
  - [ ] Create shell script with all commands (for copy-paste)
  - [ ] Test each command sequence independently
  - [ ] Verify all commands produce expected output
  - [ ] Time each section to ensure pacing matches voiceover

---

## Production Day Checklist

### Morning Of

- [ ] **Get well-rested** (avoid recording when tired)
- [ ] **Hydrate** (keep water nearby, avoid milk/coffee before recording)
- [ ] **Warm up voice** (5-10 minutes of vocal exercises)
- [ ] **Test all equipment** (mic, recording software, terminal)
- [ ] **Close all other applications**
- [ ] **Turn off phone** or put in airplane mode
- [ ] **Inform housemates/colleagues** (avoid interruptions)

### Recording Session Setup (30-45 minutes)

#### Part 1: Record Terminal Footage (20-30 min)

This is separate from voiceover to allow for timing adjustments.

- [ ] **Start screen recording**
- [ ] **Record intro sequence** (0:00-0:15)
  - [ ] Clear terminal
  - [ ] Show clean prompt
  - [ ] Brief logo flash (if using)
  - [ ] Stop recording

- [ ] **Record problem demonstrations** (0:15-0:45)
  - [ ] Scene 1: Docker not running error
    - [ ] Stop Docker: `docker stop $(docker ps -aq)` or quit Docker Desktop
    - [ ] Run: `mcpbr run -c config.yaml`
    - [ ] Capture error message
    - [ ] Restart Docker
  - [ ] Scene 2: Missing config file error
    - [ ] Ensure no `mcpbr.yaml` exists
    - [ ] Run: `mcpbr run`
    - [ ] Capture error
  - [ ] Scene 3: Invalid config (missing {workdir})
    - [ ] Create bad config (see script)
    - [ ] Show config: `cat config.yaml`
    - [ ] Run: `mcpbr run -c config.yaml`
    - [ ] Capture error
  - [ ] Scene 4: Wrong command syntax
    - [ ] Run: `mcpbr run --sample 5`
    - [ ] Capture error
  - [ ] Clean up: `rm config.yaml`

- [ ] **Record solution demonstration** (0:45-2:15)
  - [ ] Part 1: Show plugin detection (0:45-1:05)
    - [ ] `pwd` (show we're in mcpbr repo)
    - [ ] `ls -la .claude-plugin/`
    - [ ] Show directory structure
    - [ ] Type: `claude "Run the SWE-bench benchmark with 5 tasks"`
    - [ ] **Note:** This is a simulation. In reality, you'll type this and manually create the response. Consider using a script or editing in post.
  - [ ] Part 2: Pre-flight validation (1:05-1:25)
    - [ ] Simulate Claude checking Docker: `docker ps`
    - [ ] Simulate Claude checking API key: `echo $ANTHROPIC_API_KEY | cut -c1-10`
    - [ ] Simulate Claude checking config: `ls mcpbr.yaml` (should fail)
  - [ ] Part 3: Config generation (1:25-1:45)
    - [ ] Run: `mcpbr init`
    - [ ] Show config: `cat mcpbr.yaml`
    - [ ] Highlight the `{workdir}` placeholder (use cursor or text overlay in post)
  - [ ] Part 4: Running benchmark (1:45-2:15)
    - [ ] Run: `mcpbr run -c mcpbr.yaml -n 5 -v -o results.json -r report.md`
    - [ ] **Important:** This will take 15-30 minutes in reality
    - [ ] Record the start (first 10-15 seconds)
    - [ ] Record middle progress (a few task updates)
    - [ ] Record the end (results summary)
    - [ ] Edit together in post-production with speed-up effects

- [ ] **Record feature highlights** (2:15-3:00)
  - [ ] Feature 1: Multiple benchmarks (2:15-2:25)
    - [ ] Simulate: `claude "Run CyberGym benchmark at level 2"`
    - [ ] Run: `mcpbr run -c config.yaml --benchmark cybergym --level 2 -n 5 -v`
    - [ ] Record output (first few seconds)
  - [ ] Feature 2: Smart troubleshooting (2:25-2:35)
    - [ ] Simulate conversation about timeout
    - [ ] Show: `cat mcpbr.yaml | grep timeout`
    - [ ] Show updated value
    - [ ] Run: `mcpbr run -c mcpbr.yaml -vv --log-dir logs/`
  - [ ] Feature 3: Quick start (2:35-2:45)
    - [ ] Simulate: `claude "Quick demo of mcpbr"`
    - [ ] Run: `mcpbr run -c examples/quick-start/getting-started.yaml -n 3 -v`
    - [ ] Show expected runtime/cost message
  - [ ] Feature 4: Advanced features (2:45-3:00)
    - [ ] Simulate regression detection conversation
    - [ ] Show: `mcpbr run -c config.yaml --baseline-results baseline.json --regression-threshold 0.1 --slack-webhook $SLACK_WEBHOOK -v`
    - [ ] Note: You may need to create a mock `baseline.json` file

- [ ] **Record call-to-action** (3:00-3:15)
  - [ ] Clear terminal
  - [ ] Display ASCII art or text:
    ```
    ┌────────────────────────────────────────────────────┐
    │   mcpbr + Claude Code Plugin                       │
    │   🔗 github.com/greynewell/mcpbr                   │
    │   ⭐ Star the repo                                 │
    │   📦 pip install mcpbr                             │
    │   🚀 git clone && start benchmarking               │
    └────────────────────────────────────────────────────┘
    ```
  - [ ] Hold for 5 seconds

#### Part 2: Record Voiceover (15-20 min)

- [ ] **Set up recording environment**
  - [ ] Close door, minimize background noise
  - [ ] Position microphone correctly
  - [ ] Open script on second monitor or teleprompter
  - [ ] Have water nearby
  - [ ] Do final voice warm-up

- [ ] **Record in sections** (easier to fix mistakes)
  - [ ] Intro (0:00-0:15)
    - [ ] Record 3 takes
    - [ ] Choose best take
  - [ ] Problem (0:15-0:45)
    - [ ] Record 3 takes
    - [ ] Adjust tone: frustrated but understanding
  - [ ] Solution (0:45-2:15)
    - [ ] Break into 4 parts (Part 1-4 from script)
    - [ ] Record each part 2-3 times
    - [ ] Use consistent energy level
  - [ ] Features (2:15-3:00)
    - [ ] Record as one take or break into 4 features
    - [ ] Keep energy high and enthusiastic
  - [ ] CTA (3:00-3:15)
    - [ ] Record 3 takes
    - [ ] Tone: confident and inviting

- [ ] **Record room tone** (30 seconds of silence)
  - [ ] Used for noise reduction in post

#### Part 3: B-Roll & Supplementary Footage (Optional, 10-15 min)

- [ ] **GitHub repository views**
  - [ ] Navigate to github.com/greynewell/mcpbr
  - [ ] Show README
  - [ ] Show plugin directory in web UI
  - [ ] Show stars count
  - [ ] Show recent commits/activity

- [ ] **Documentation pages**
  - [ ] Show installation guide
  - [ ] Show skills documentation
  - [ ] Show configuration examples

- [ ] **Results visualization**
  - [ ] Open generated `report.md` in a viewer
  - [ ] Show `results.json` in a JSON formatter
  - [ ] Display evaluation graphs (if available)

---

## Post-Production Checklist

### Video Editing (2-4 hours)

Use video editing software: DaVinci Resolve (free), Final Cut Pro, Adobe Premiere, or iMovie.

- [ ] **Import all footage**
  - [ ] Terminal recordings (multiple clips)
  - [ ] Voiceover recordings
  - [ ] B-roll (if recorded)
  - [ ] Logo/branding assets

- [ ] **Organize timeline**
  - [ ] Create sequence: 1920×1080, 30fps
  - [ ] Arrange terminal clips in order per script
  - [ ] Trim unnecessary pauses and dead air
  - [ ] Speed up long-running processes (2x or 4x)

- [ ] **Sync voiceover to video**
  - [ ] Align voiceover with terminal actions
  - [ ] Adjust video speed to match narration
  - [ ] Add pauses where viewer needs time to read terminal output
  - [ ] Ensure smooth transitions between sections

- [ ] **Add text overlays**
  - [ ] Section headers (e.g., "PROBLEM DEMONSTRATION")
  - [ ] On-screen annotations (e.g., "✓ Docker validation")
  - [ ] Error highlights (e.g., "Mistake #1: Docker not running")
  - [ ] Call-to-action text
  - [ ] Use consistent font, size, and positioning
  - [ ] Add subtle animations (fade in/out)

- [ ] **Add visual effects**
  - [ ] Highlight important terminal lines (boxes, arrows, circles)
  - [ ] Add checkmarks (✓) for successful validations
  - [ ] Add error indicators (✗) for problems
  - [ ] Zoom in on critical text (e.g., {workdir} placeholder)
  - [ ] Blur or obscure sensitive info (API keys, etc.)

- [ ] **Color correction**
  - [ ] Ensure consistent terminal colors across clips
  - [ ] Adjust brightness/contrast if needed
  - [ ] Match color tone across all footage

- [ ] **Audio editing**
  - [ ] Remove background noise (use noise reduction filter)
  - [ ] Normalize audio levels (-3dB to -1dB peak)
  - [ ] Apply compression for consistent volume
  - [ ] Add subtle EQ to improve voice clarity
  - [ ] Remove mouth clicks, lip smacks, awkward pauses
  - [ ] Add fade in/out to voiceover clips

- [ ] **Background music** (optional)
  - [ ] Add subtle tech/ambient music track
  - [ ] Volume: -20dB to -25dB (much quieter than voice)
  - [ ] Fade in at intro, fade out at outro
  - [ ] Duck music under voiceover (sidechaining)
  - [ ] Ensure music is royalty-free or properly licensed

- [ ] **Transitions**
  - [ ] Keep transitions simple (clean cuts preferred)
  - [ ] Optional: 0.5s crossfade between major sections
  - [ ] Avoid flashy transitions (professional tone)

- [ ] **Pacing review**
  - [ ] Watch full video 2-3 times
  - [ ] Check that pacing feels natural (not too rushed or slow)
  - [ ] Ensure viewer has time to read terminal output
  - [ ] Verify total duration is close to 3 minutes

### Quality Control (30-60 minutes)

- [ ] **Technical review**
  - [ ] Audio: No clipping, pops, or distortion
  - [ ] Video: No pixelation, stuttering, or artifacts
  - [ ] Text: All overlays readable and properly timed
  - [ ] Timing: Voiceover synced to actions
  - [ ] Continuity: No jarring jumps or mismatched scenes

- [ ] **Content review**
  - [ ] All commands shown are correct
  - [ ] No sensitive information visible (API keys, tokens)
  - [ ] All URLs are correct
  - [ ] Script matches voiceover
  - [ ] Key messages are clear

- [ ] **Accessibility**
  - [ ] Add captions/subtitles (auto-generate, then manually correct)
  - [ ] Ensure text overlays are high contrast
  - [ ] Verify video works with sound off (text overlays guide viewer)

- [ ] **Peer review**
  - [ ] Share with 2-3 colleagues for feedback
  - [ ] Ask specific questions:
    - [ ] Is the pacing too fast or too slow?
    - [ ] Are the key points clear?
    - [ ] Is the CTA compelling?
    - [ ] Would you star the repo after watching?
  - [ ] Incorporate feedback into final edit

### Export & Optimization (15-30 minutes)

- [ ] **Primary export (YouTube/website)**
  - [ ] Format: MP4 (H.264)
  - [ ] Resolution: 1920×1080 (1080p)
  - [ ] Frame rate: 30fps or 60fps
  - [ ] Bitrate: 8-12 Mbps (variable bitrate)
  - [ ] Audio: AAC, 192kbps, 48kHz
  - [ ] Verify file size is reasonable (<500MB)

- [ ] **Alternative exports**
  - [ ] 4K version (3840×2160) for future-proofing
  - [ ] Vertical version (1080×1920) for Instagram/TikTok
  - [ ] Square version (1080×1080) for social feeds
  - [ ] Short 60s version for Twitter/LinkedIn
  - [ ] GIF/WebM version for README (silent, autoplay)

- [ ] **Thumbnail creation**
  - [ ] Design eye-catching thumbnail in Photoshop/Figma/Canva
  - [ ] Include text: "Claude Code + mcpbr"
  - [ ] Use contrasting colors
  - [ ] Test thumbnail at small sizes
  - [ ] Export as 1280×720 JPEG
  - [ ] Keep file size under 2MB

---

## Distribution Checklist

### Pre-Launch (Day Before)

- [ ] **Finalize all assets**
  - [ ] Main video file (MP4)
  - [ ] Thumbnail image
  - [ ] Video description text
  - [ ] Social media posts (draft)
  - [ ] Blog post (draft)

- [ ] **YouTube optimization**
  - [ ] Title: "mcpbr + Claude Code: Zero-Mistake MCP Benchmarking"
  - [ ] Description:
    ```
    Learn how the mcpbr Claude Code plugin makes benchmarking MCP servers effortless. No configuration mistakes, no wasted time - just perfect benchmarks every time.

    🔗 GitHub: https://github.com/greynewell/mcpbr
    📦 Install: pip install mcpbr
    📚 Docs: https://greynewell.github.io/mcpbr/

    Timestamps:
    0:00 - Intro
    0:15 - Common Mistakes
    0:45 - Plugin in Action
    2:15 - Feature Highlights
    3:00 - Get Started

    The Claude Code plugin includes specialized skills that make Claude an expert at:
    ✓ Validating prerequisites (Docker, API keys, configs)
    ✓ Generating valid configurations with {workdir} placeholders
    ✓ Running evaluations with correct CLI flags
    ✓ Troubleshooting common issues
    ✓ Supporting all benchmarks (SWE-bench, CyberGym, MCPToolBench++)

    Star the repo ⭐ https://github.com/greynewell/mcpbr
    ```
  - [ ] Tags: MCP, Model Context Protocol, Claude Code, Anthropic, benchmarking, SWE-bench, CyberGym, MCPToolBench, AI agents, LLM tools, developer tools, testing, evaluation
  - [ ] Category: Science & Technology
  - [ ] Thumbnail uploaded
  - [ ] Video set to unlisted (launch publicly when ready)
  - [ ] Add to "mcpbr Tutorials" playlist
  - [ ] Enable comments
  - [ ] Add end screen (subscribe button, related videos)
  - [ ] Add cards at key moments

- [ ] **Prepare social media posts**

  **Twitter/X Thread:**
  ```
  🚀 New video: How the mcpbr Claude Code plugin eliminates benchmarking mistakes

  Watch Claude automatically:
  ✓ Validate Docker & API keys
  ✓ Generate perfect configs
  ✓ Run flawless evaluations

  Zero mistakes. Every time.

  🎥 [video link]
  ⭐ github.com/greynewell/mcpbr

  [1/5]

  ---

  Before the plugin, even Claude makes mistakes:
  ❌ Forgets to check Docker
  ❌ Misses {workdir} placeholder
  ❌ Uses wrong command flags

  Result: Wasted time, broken evaluations

  [2/5]

  ---

  With the plugin, Claude becomes an mcpbr expert:
  ✅ Pre-flight validation
  ✅ Smart config generation
  ✅ Perfect command construction

  Just ask in plain English. Claude handles the rest.

  [3/5]

  ---

  The plugin includes 3 specialized skills:
  1️⃣ run-benchmark: Expert evaluation runner
  2️⃣ generate-config: Valid config generator
  3️⃣ swe-bench-lite: Quick-start command

  Support for SWE-bench, CyberGym, MCPToolBench++

  [4/5]

  ---

  Ready to benchmark your MCP server the right way?

  ⭐ Star: github.com/greynewell/mcpbr
  📦 Install: pip install mcpbr
  🎥 Watch: [video link]

  Zero mistakes. Perfect benchmarks. Every time.

  [5/5]
  ```

  **LinkedIn Post:**
  ```
  🎯 New Resource: mcpbr Claude Code Plugin Demo

  If you're building MCP servers, you need to validate they actually improve agent performance. But running benchmarks correctly is easy to mess up.

  Our new video shows how the Claude Code plugin eliminates common mistakes:

  ✅ Automatic Docker & API key validation
  ✅ Generates valid configs with proper {workdir} placeholders
  ✅ Constructs perfect CLI commands every time
  ✅ Supports SWE-bench, CyberGym, and MCPToolBench++

  Just ask Claude in plain English - the plugin handles technical details.

  Watch the 3-minute demo: [video link]
  GitHub: github.com/greynewell/mcpbr

  #MCP #AIEngineering #DeveloperTools #Anthropic #ClaudeCode
  ```

  **Reddit r/MachineLearning:**
  ```
  Title: [P] mcpbr Claude Code Plugin: Zero-Mistake MCP Benchmarking

  Body:
  We've released a Claude Code plugin that makes benchmarking MCP servers effortless.

  **What it does:**
  - Validates prerequisites (Docker, API keys) before running
  - Generates valid configs with correct placeholders
  - Constructs proper CLI commands automatically
  - Provides troubleshooting for common issues

  **Benchmarks supported:**
  - SWE-bench (bug fixing)
  - CyberGym (security exploits)
  - MCPToolBench++ (tool use evaluation)

  **Demo video:** [video link]
  **GitHub:** github.com/greynewell/mcpbr
  **Install:** `pip install mcpbr`

  The plugin is bundled with the repo - just clone and Claude gains domain expertise. Open source (MIT license), contributions welcome!
  ```

### Launch Day

- [ ] **Publish video**
  - [ ] Set YouTube video to public
  - [ ] Verify thumbnail displays correctly
  - [ ] Check description links work

- [ ] **Update repository**
  - [ ] Add video to README hero section
  - [ ] Embed video in docs landing page
  - [ ] Update CHANGELOG with video link
  - [ ] Create GitHub release announcement (optional)

- [ ] **Social media blitz**
  - [ ] Post Twitter thread
  - [ ] Share on LinkedIn
  - [ ] Post on Reddit (r/MachineLearning, r/LocalLLaMA, r/ClaudeAI)
  - [ ] Share in relevant Discord servers
  - [ ] Post in Slack communities
  - [ ] Submit to Hacker News Show HN (timing: weekday morning US time)

- [ ] **Email newsletter** (if you have one)
  - [ ] Send to subscribers
  - [ ] Include video embed or thumbnail link
  - [ ] Brief summary + CTA to star repo

- [ ] **Engage with comments**
  - [ ] Respond to YouTube comments within first hour
  - [ ] Reply to social media mentions
  - [ ] Answer questions on Reddit/HN

### Week 1 Follow-Up

- [ ] **Monitor metrics**
  - [ ] YouTube views, watch time, engagement
  - [ ] GitHub stars increase
  - [ ] PyPI download spike
  - [ ] Social media impressions/clicks

- [ ] **Community engagement**
  - [ ] Continue responding to comments
  - [ ] Thank sharers and retweeters
  - [ ] Address any technical questions

- [ ] **Iterate if needed**
  - [ ] If feedback suggests improvements, note for v2
  - [ ] Create FAQ doc if common questions arise
  - [ ] Update README based on viewer confusion

---

## Troubleshooting Common Issues

### Technical Problems

**Issue: Terminal output is hard to read**
- Solution: Increase font size, use high-contrast theme, export at higher resolution

**Issue: Screen recording is laggy**
- Solution: Lower resolution during recording, close background apps, increase recording bitrate

**Issue: Voiceover has background noise**
- Solution: Re-record in quieter environment, use noise reduction plugin, use better microphone

**Issue: Video file size is too large**
- Solution: Reduce bitrate slightly, compress with HandBrake, use variable bitrate encoding

**Issue: Claude CLI interactions are hard to simulate**
- Solution: Use text overlays to simulate responses, or record actual interactions (slower but more authentic)

### Content Problems

**Issue: Pacing feels rushed**
- Solution: Add pauses after commands, slow down voiceover, extend viewing time for terminal output

**Issue: Video is too long**
- Solution: Cut less critical features, speed up terminal output more, tighten voiceover script

**Issue: Key points aren't clear**
- Solution: Add more text overlays, emphasize in voiceover, zoom in on important details

**Issue: Call-to-action isn't compelling**
- Solution: Strengthen CTA copy, show more impressive results, emphasize pain points more

### Process Problems

**Issue: Voiceover doesn't match terminal timing**
- Solution: Adjust video speed, re-record voiceover sections, add B-roll to fill gaps

**Issue: Multiple takes have different audio quality**
- Solution: Normalize all clips, apply consistent EQ/compression, re-record if necessary

**Issue: Text overlays are hard to read**
- Solution: Increase font size, add background box or drop shadow, use higher contrast colors

---

## Post-Launch Analysis

### Week 1 Review

- [ ] Compile metrics:
  - [ ] Total views
  - [ ] Average view duration
  - [ ] Click-through rate to GitHub
  - [ ] GitHub stars increase
  - [ ] PyPI downloads

- [ ] Analyze feedback:
  - [ ] Read all comments
  - [ ] Identify common questions
  - [ ] Note feature requests
  - [ ] Gauge sentiment (positive/negative/neutral)

- [ ] Document learnings:
  - [ ] What worked well?
  - [ ] What would you change?
  - [ ] Ideas for future videos?

### Month 1 Review

- [ ] Long-term metrics:
  - [ ] Sustained view growth or plateau?
  - [ ] Continued GitHub activity increase?
  - [ ] Any influencer/thought leader mentions?

- [ ] Create supplementary content:
  - [ ] FAQ video addressing common questions
  - [ ] Deep-dive tutorial on specific features
  - [ ] Case study of successful MCP server evaluation

---

## Tips for Success

### Recording Tips

1. **Practice makes perfect:** Run through the entire script 5+ times before recording
2. **Smile while speaking:** It improves vocal tone even if you're not on camera
3. **Hydrate:** Keep water nearby, sip between takes
4. **Take breaks:** Record in 15-20 minute sessions to maintain energy
5. **Embrace mistakes:** Don't restart - just pause and redo the sentence

### Editing Tips

1. **Less is more:** Tight editing keeps viewers engaged
2. **Silence is golden:** Don't fear short pauses - they give breathing room
3. **Consistency matters:** Match audio levels, color grades, and pacing throughout
4. **Test on mobile:** Ensure text is readable on small screens
5. **Get fresh eyes:** Have someone unfamiliar with mcpbr watch and give feedback

### Distribution Tips

1. **Timing matters:** Launch on weekday morning US time for maximum reach
2. **Engage immediately:** Respond to first comments within minutes
3. **Cross-promote:** Share across all relevant platforms simultaneously
4. **Leverage hashtags:** Use platform-appropriate tags (Twitter/LinkedIn/Instagram)
5. **Pin it:** Pin announcement tweet, make it first item in README

### General Wisdom

- **Perfect is the enemy of done:** Ship a good video now rather than a perfect video never
- **Iterate:** Version 1 teaches you how to make version 2
- **Listen to feedback:** Viewers will tell you what they want to see next
- **Measure impact:** Track metrics to understand what resonates
- **Have fun:** Your enthusiasm will show in the final product

---

## Next Steps After Launch

1. **Create follow-up content:**
   - Tutorial series on specific benchmarks
   - Configuration deep-dive
   - Advanced features walkthrough
   - Community showcase (users sharing their results)

2. **Improve documentation:**
   - Add "Video Tutorials" section to docs
   - Create video playlist on YouTube
   - Embed videos in relevant doc pages

3. **Engage community:**
   - Host live Q&A session
   - Create Discord/Slack for mcpbr users
   - Feature community contributions

4. **Plan next video:**
   - Apply learnings from this production
   - Choose topic based on community feedback
   - Maintain consistent release schedule

---

**Remember:** This video is a marketing tool to drive adoption. Every decision (pacing, tone, visuals) should serve the goal of getting viewers to star the repo and try mcpbr.

Good luck with your production! 🎬
