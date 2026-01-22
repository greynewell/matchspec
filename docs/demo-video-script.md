# mcpbr Claude Code Plugin Demo Video Script

**Target Duration:** 3 minutes (195 seconds)
**Target Audience:** MCP server developers, AI engineers, open-source contributors
**Primary Goal:** Showcase how the Claude Code plugin makes benchmarking MCP servers effortless
**Secondary Goal:** Drive GitHub stars and plugin adoption

---

## Video Overview

This demo video showcases the mcpbr Claude Code plugin, demonstrating how Claude becomes an expert at running benchmarks with zero configuration mistakes. The video uses a before/after structure to highlight the plugin's value.

**Key Message:** "Claude Code + mcpbr plugin = No silly mistakes, perfect benchmarks every time."

---

## Shot-by-Shot Breakdown

### INTRO (0:00 - 0:15) - 15 seconds

**Visual:**
- Open on terminal with clean prompt in dark theme
- Top corner shows: "mcpbr + Claude Code Plugin Demo"
- Fade in mcpbr logo briefly (2s)

**Voiceover:**
> "Building an MCP server? You need to prove it actually works. But running benchmarks correctly is surprisingly easy to mess up."

**Terminal Commands:** *(None - just intro screen)*

---

### PROBLEM DEMONSTRATION (0:15 - 0:45) - 30 seconds

**Visual:**
- Split screen or quick cuts showing common mistakes
- Terminal showing error messages in red
- Frustrated developer vibes (optional: emoji reactions in terminal)

**Voiceover:**
> "Without the Claude Code plugin, even Claude makes rookie mistakes. Forgetting to check Docker. Missing the critical workdir placeholder. Using the wrong command flags. These errors waste time and break your flow."

**Terminal Commands:**

```bash
# Scene 1: Docker not running (3s)
$ mcpbr run -c config.yaml
Error: Docker daemon is not running. Please start Docker and try again.

# Scene 2: Missing config file (3s)
$ mcpbr run
Error: --config is required

# Scene 3: Invalid config - missing {workdir} (4s)
$ cat config.yaml
mcp_server:
  args:
    - "@modelcontextprotocol/server-filesystem"
    - "/workspace"  # ❌ Wrong! Should be {workdir}

$ mcpbr run -c config.yaml
Error: MCP server failed to start in container...

# Scene 4: Wrong command structure (3s)
$ mcpbr run --sample 5  # Missing -c flag
Error: --config is required
```

**On-Screen Text Overlays:**
- "Mistake #1: Docker not running"
- "Mistake #2: Missing config file"
- "Mistake #3: Wrong workdir path"
- "Mistake #4: Invalid command syntax"

---

### SOLUTION DEMONSTRATION (0:45 - 2:15) - 90 seconds

**Visual:**
- Clean terminal session in mcpbr repository
- Show `.claude-plugin/` directory briefly
- Natural conversational flow with Claude Code
- Green checkmarks appear as validations pass

**Voiceover:**
> "Now watch what happens with the Claude Code plugin. When you clone mcpbr, Claude automatically becomes an expert. It knows to check Docker first, generate valid configs with the workdir placeholder, and use the right command flags every single time."

#### Part 1: Natural conversation (0:45 - 1:05) - 20 seconds

**Terminal Commands:**

```bash
# Show we're in the mcpbr repo
$ pwd
/Users/dev/mcpbr

# Show the plugin is detected
$ ls -la .claude-plugin/
total 8
drwxr-xr-x  3 dev  staff   96 Jan 22 10:00 .
drwxr-xr-x 25 dev  staff  800 Jan 22 10:00 ..
-rw-r--r--  1 dev  staff  423 Jan 22 10:00 plugin.json

# User asks Claude in natural language
$ claude "Run the SWE-bench benchmark with 5 tasks"
```

**Voiceover:**
> "Just ask Claude in plain English. The plugin handles the rest."

#### Part 2: Pre-flight validation (1:05 - 1:25) - 20 seconds

**Terminal Output:**

```
Claude: I'll help you run a SWE-bench evaluation with 5 tasks. Let me first
verify the prerequisites.

Checking Docker status...
$ docker ps
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
✓ Docker is running

Verifying API key...
$ echo $ANTHROPIC_API_KEY | cut -c1-10
sk-ant-api
✓ ANTHROPIC_API_KEY is set

Checking for config file...
$ ls mcpbr.yaml
ls: mcpbr.yaml: No such file or directory

I'll generate a config file for you first.
```

**Voiceover:**
> "Claude automatically validates prerequisites. Docker running? Check. API key set? Check. Config file missing? No problem."

**On-Screen Text Overlays:**
- "✓ Docker validation"
- "✓ API key check"
- "→ Auto-generates config"

#### Part 3: Config generation (1:25 - 1:45) - 20 seconds

**Terminal Output:**

```
$ mcpbr init

Claude: I've generated a config file. Let me verify the workdir placeholder
is included correctly.

$ cat mcpbr.yaml
mcp_server:
  command: "npx"
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"  # ✓ Correct placeholder
  env: {}

provider: "anthropic"
agent_harness: "claude-code"
model: "sonnet"
dataset: "SWE-bench/SWE-bench_Lite"
sample_size: 5
timeout_seconds: 300

✓ Config validation passed
```

**Voiceover:**
> "The plugin ensures critical details are correct, like the workdir placeholder that mcpbr needs to inject the repository path at runtime."

**On-Screen Text Overlays:**
- "✓ Valid config generated"
- "✓ {workdir} placeholder included"

#### Part 4: Running the benchmark (1:45 - 2:15) - 30 seconds

**Terminal Output:**

```
Claude: Now I'll run the evaluation with the correct flags.

$ mcpbr run -c mcpbr.yaml -n 5 -v -o results.json -r report.md

mcpbr Evaluation
  Config: mcpbr.yaml
  Provider: anthropic
  Model: sonnet
  Agent Harness: claude-code
  Dataset: SWE-bench/SWE-bench_Lite
  Sample size: 5
  Run MCP: True, Run Baseline: True

Loading dataset: SWE-bench/SWE-bench_Lite
Evaluating 5 tasks
Provider: anthropic, Harness: claude-code

14:23:15 [MCP] Starting mcp run for astropy-12907:mcp
14:23:22 astropy-12907:mcp    > TodoWrite
14:23:26 astropy-12907:mcp    > Glob
14:23:26 astropy-12907:mcp    > Grep
...
14:27:43 astropy-12907:mcp    * done turns=31 tokens=115/6,542

[Evaluation continues with progress indicators]

Evaluation Results

                 Summary
+-----------------+-----------+----------+
| Metric          | MCP Agent | Baseline |
+-----------------+-----------+----------+
| Resolved        | 4/5       | 2/5      |
| Resolution Rate | 80.0%     | 40.0%    |
+-----------------+-----------+----------+

Improvement: +100.0%

Results saved to results.json
Report saved to report.md
```

**Voiceover:**
> "Claude constructs the perfect command with verbose output, results file, and report. The benchmark runs flawlessly, comparing your MCP server against a baseline to measure real improvement."

**On-Screen Text Overlays:**
- "✓ Correct flags: -c -n -v -o -r"
- "✓ Running evaluation..."
- "✓ Results: +100% improvement"

---

### FEATURES HIGHLIGHT (2:15 - 3:00) - 45 seconds

**Visual:**
- Quick montage of terminal clips showing different capabilities
- Each feature gets 7-10 seconds of screen time

**Voiceover:**
> "The plugin includes three specialized skills that make Claude an mcpbr expert."

#### Feature 1: Multiple Benchmarks (2:15 - 2:25) - 10 seconds

**Terminal Output:**

```
$ claude "Run CyberGym benchmark at level 2"

Claude: I'll run a CyberGym evaluation at difficulty level 2.

$ mcpbr run -c config.yaml --benchmark cybergym --level 2 -n 5 -v

mcpbr Evaluation
  Benchmark: cybergym
  Level: 2
  Dataset: sunblaze-ucb/cybergym
  Sample size: 5
...
```

**Voiceover:**
> "It supports all three benchmarks: SWE-bench for bug fixes, CyberGym for security exploits, and MCPToolBench++ for tool use evaluation."

**On-Screen Text:** "✓ SWE-bench ✓ CyberGym ✓ MCPToolBench++"

#### Feature 2: Smart Troubleshooting (2:25 - 2:35) - 10 seconds

**Terminal Output:**

```
$ claude "The benchmark timed out"

Claude: Timeout issues can be fixed by increasing the timeout_seconds value
in your config. Let me update it for you.

$ cat mcpbr.yaml | grep timeout
timeout_seconds: 600  # Increased from 300

You can also use -vv for more detailed logs to diagnose where it's getting stuck.

$ mcpbr run -c mcpbr.yaml -vv --log-dir logs/
```

**Voiceover:**
> "When issues occur, Claude provides actionable troubleshooting based on deep knowledge of common problems."

**On-Screen Text:** "✓ Smart error diagnosis"

#### Feature 3: Quick Start Mode (2:35 - 2:45) - 10 seconds

**Terminal Output:**

```
$ claude "Quick demo of mcpbr"

Claude: I'll run a fast SWE-bench Lite evaluation with 3 tasks for demonstration.

$ mcpbr run -c examples/quick-start/getting-started.yaml -n 3 -v

Expected runtime: 5-10 minutes
Estimated cost: $1-2

[Evaluation starts...]
```

**Voiceover:**
> "Need a quick demo? Claude knows the fastest way to validate your setup without reading documentation."

**On-Screen Text:** "✓ Quick start templates"

#### Feature 4: No Documentation Required (2:45 - 3:00) - 15 seconds

**Visual:**
- Side-by-side comparison:
  - LEFT: Someone scrolling through long documentation
  - RIGHT: Simple Claude conversation getting work done

**Terminal Output:**

```
$ claude "Run regression detection against my baseline results"

Claude: I'll compare your current run against the baseline and alert you
if the regression rate exceeds 10%.

$ mcpbr run -c config.yaml \
    --baseline-results baseline.json \
    --regression-threshold 0.1 \
    --slack-webhook $SLACK_WEBHOOK \
    -v

[Regression detection running...]

Regression rate: 4.2% (within acceptable threshold)
✓ No alert sent
```

**Voiceover:**
> "From regression detection to custom prompts, Claude knows every feature without you needing to remember flags or read docs."

**On-Screen Text:** "Natural language → Perfect commands"

---

### CALL TO ACTION (3:00 - 3:15) - 15 seconds

**Visual:**
- Terminal clears
- Large, clean display of key information
- Optional: QR code or short URL

**On-Screen Display:**

```
┌────────────────────────────────────────────────────┐
│                                                    │
│   mcpbr + Claude Code Plugin                       │
│                                                    │
│   🔗 github.com/greynewell/mcpbr                   │
│                                                    │
│   ⭐ Star the repo                                 │
│   📦 pip install mcpbr                             │
│   🚀 git clone && start benchmarking               │
│                                                    │
│   Zero mistakes. Perfect benchmarks. Every time.   │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Voiceover:**
> "Ready to benchmark your MCP server the right way? Star mcpbr on GitHub, install it with pip, and let Claude Code do the heavy lifting. Zero mistakes, perfect benchmarks, every time."

**On-Screen Text:**
- "github.com/greynewell/mcpbr"
- "⭐ Star • 📦 Install • 🚀 Benchmark"

---

## Technical Production Notes

### Terminal Settings

**Color Scheme:** Use a professional dark theme (e.g., Dracula, Nord, Tokyo Night)
- Background: Dark but not pure black (#1e1e2e or similar)
- Text: High contrast white/light gray
- Success messages: Green (#a6e3a1)
- Errors: Red (#f38ba8)
- Commands: Cyan or blue (#89b4fa)
- Prompts: Yellow/orange (#f9e2af)

**Font:**
- Family: JetBrains Mono, Fira Code, or SF Mono
- Size: Large enough for 1080p/4K viewing (16-20pt)
- Enable ligatures for better code readability

**Terminal Emulator:**
- macOS: iTerm2 or Warp (supports better recording)
- Linux: Alacritty or Kitty
- Or use Asciinema for terminal recording + convert to video

**Window Size:**
- 120 columns × 30 rows minimum
- Center the terminal window for recording
- Remove distractions (disable notifications, close other apps)

### Screen Recording

**Resolution:** 1920x1080 (1080p) minimum, 4K preferred for quality
**Frame Rate:** 30 fps minimum, 60 fps preferred for smooth playback
**Format:** MP4 (H.264 codec) for broad compatibility

**Recommended Tools:**
- **macOS:** QuickTime Player (built-in), ScreenFlow (pro), or OBS Studio (free)
- **Linux:** OBS Studio, SimpleScreenRecorder, Kazam
- **Windows:** OBS Studio, Camtasia
- **Terminal-specific:** Asciinema (terminal recording) + agg (convert to GIF/video)

**Cursor Settings:**
- Enable visible cursor with highlight/ring
- Smooth cursor movement (not too fast)
- Pause 1-2 seconds after typing before pressing Enter

### Pacing & Timing

**Typing Speed:**
- Commands: Type at moderate pace (2-3 chars/second) or use "instant type" effect
- Allow 2-3 seconds for viewer to read command before executing
- Natural pauses between sections (1-2 seconds)

**Execution Timing:**
- Show realistic command output but edit for time
- Use fast-forward effect for long-running processes
- Keep each "scene" under 30 seconds to maintain engagement

**Transitions:**
- Clean cuts between scenes (no need for fancy transitions)
- Optional: 0.5s fade for major section changes
- Use subtle zoom-ins to highlight important text

### Audio Production

**Voiceover Quality:**
- Record in quiet environment (use noise gate/reduction if needed)
- Professional microphone preferred (Blue Yeti, Shure SM7B, or similar)
- Format: 48kHz, 24-bit WAV or FLAC, convert to AAC for final video
- Normalize audio levels (-3dB to -1dB max peak)

**Background Music (Optional):**
- Subtle, non-distracting tech/ambient music
- Volume: -20dB to -25dB (much quieter than voice)
- Royalty-free sources: Epidemic Sound, Artlist, YouTube Audio Library
- Fade in/out at intro/outro

**Script Recording Tips:**
- Read through script 3-5 times before recording
- Record in sections (easier to fix mistakes)
- Maintain consistent energy and tone
- Smile while speaking (improves vocal tone)
- Record multiple takes and choose best clips

### Text Overlays & Graphics

**Font for On-Screen Text:**
- Family: Inter, Roboto, or SF Pro (clean, readable)
- Size: Large enough to read on mobile (48pt+)
- Style: Bold for headings, regular for body
- Color: White with dark semi-transparent background or drop shadow

**Positioning:**
- Top 1/3 of screen for titles/headings
- Bottom 1/3 for captions/URLs
- Avoid center (terminal content area)

**Duration:**
- Show text overlays for 3-5 seconds minimum
- Sync with voiceover mentions
- Fade in/out (0.3-0.5s transitions)

**Visual Effects:**
- Checkmarks: Green ✓ for successful validations
- Error indicators: Red ✗ or warning triangle
- Arrow highlights: Draw attention to specific terminal lines
- Blur or dim background when showing overlay text

### Branding

**Logo Usage:**
- Show mcpbr logo in intro (2-3 seconds)
- Optional: Small watermark in corner throughout video
- Use official mcpbr logo from assets/ directory

**Color Palette:**
- Use mcpbr brand colors if defined
- Maintain consistency with GitHub repo theme
- Professional, technical aesthetic

**URLs & Links:**
- Display clearly at beginning and end
- Use shortened URLs if needed (bit.ly, rebrand.ly)
- Optional: QR code in corner for mobile scanning

### Post-Production Checklist

- [ ] Color correction (ensure consistent terminal colors)
- [ ] Audio leveling (normalize voice, reduce noise)
- [ ] Remove dead air/long pauses
- [ ] Add subtle transitions between sections
- [ ] Insert text overlays with proper timing
- [ ] Add background music (if using)
- [ ] Include captions/subtitles for accessibility
- [ ] Export in multiple formats (1080p, 4K, Twitter/LinkedIn optimized)
- [ ] Test playback on different devices (desktop, mobile, tablet)
- [ ] Get feedback from 2-3 people before publishing

---

## Alternative Versions

### Short Form (60 seconds) - Twitter/LinkedIn/Instagram
- Cut: Problem demonstration (reduce to 10s)
- Cut: Feature highlights (reduce to 20s)
- Focus: Quick demo of one successful benchmark run
- Format: Vertical video (1080x1920) or square (1080x1080)

### Long Form (5-7 minutes) - YouTube Deep Dive
- Add: Extended feature walkthroughs
- Add: Live coding/config editing
- Add: Detailed results analysis
- Add: Comparison with manual approach
- Include: Developer commentary/tips

### Silent Version (GIF/Webm) - README/Documentation
- Remove: Voiceover entirely
- Add: More text overlays to guide viewer
- Keep: Essential terminal commands and output
- Optimize: For autoplay without sound (social media feeds)

---

## Distribution Checklist

### Video Platforms
- [ ] Upload to YouTube (add to channel)
- [ ] Post on Twitter/X with thread
- [ ] Share on LinkedIn
- [ ] Post in relevant Discord servers
- [ ] Share in Slack communities
- [ ] Submit to Hacker News Show HN
- [ ] Post on Reddit (r/MachineLearning, r/LocalLLaMA, r/ClaudeAI)

### Embedding
- [ ] Add to README.md hero section
- [ ] Include in documentation landing page
- [ ] Link from installation guide
- [ ] Feature in blog post announcement
- [ ] Add to PyPI project description (if supported)

### Metadata & SEO
- [ ] YouTube title: "mcpbr + Claude Code: Zero-Mistake MCP Benchmarking"
- [ ] YouTube description: Include repo link, timestamps, installation instructions
- [ ] Tags: MCP, Model Context Protocol, Claude Code, Anthropic, benchmarking, SWE-bench
- [ ] Thumbnail: Eye-catching with "Claude Code + mcpbr" text
- [ ] Playlist: Create "mcpbr Tutorials" playlist

### Accompanying Content
- [ ] Write blog post announcement
- [ ] Create Twitter thread with key screenshots
- [ ] Update CHANGELOG.md with video link
- [ ] Add "Featured in" section to README
- [ ] Create GIF version for quick sharing

---

## Success Metrics

Track the following to measure video impact:

**Engagement Metrics:**
- Video views (target: 1,000+ in first week)
- Watch time percentage (target: >50% average)
- Likes/reactions
- Comments and questions
- Shares and retweets

**Conversion Metrics:**
- GitHub stars increase (track spike after release)
- pip install downloads (check PyPI stats)
- Repository clones/forks
- Issue/PR activity increase
- New contributors joining

**Distribution Metrics:**
- Social media impressions
- Click-through rate to GitHub
- Traffic sources (YouTube, Twitter, Reddit, etc.)
- Geographic distribution of viewers

**Qualitative Feedback:**
- Positive comments and testimonials
- Feature requests related to video content
- Community discussions sparked
- Influencer/thought leader mentions

---

## Maintenance & Updates

**When to Update Video:**
- Major version releases (v1.0, v2.0, etc.)
- Significant UI/UX changes to Claude Code
- New benchmark support added
- Plugin features change substantially

**Version Annotations:**
- Add YouTube cards pointing to newer version
- Update README to link to latest video
- Keep old versions in playlist for historical reference

---

## Notes for Scriptwriter/Director

1. **Keep it conversational:** The voiceover should sound natural, not like reading a manual.
2. **Show, don't tell:** Let the terminal output demonstrate capabilities rather than just describing them.
3. **Emphasize ease:** The core value prop is "no mistakes" - hammer this home.
4. **Build credibility:** Mention SWE-bench, show real metrics, demonstrate professional workflow.
5. **Create FOMO:** Viewers should feel they're missing out if they don't try this.
6. **End strong:** The CTA should feel like the natural next step, not a hard sell.

**Tone Guide:**
- **Intro:** Relatable (acknowledging the pain point)
- **Problem:** Slightly frustrated but understanding (we've all been there)
- **Solution:** Impressed and relieved (this actually works!)
- **Features:** Educational but enthusiastic (look what else it can do!)
- **CTA:** Confident and inviting (you should definitely try this)

---

## Raw Script (Voiceover Only)

**INTRO (0:00-0:15)**
> Building an MCP server? You need to prove it actually works. But running benchmarks correctly is surprisingly easy to mess up.

**PROBLEM (0:15-0:45)**
> Without the Claude Code plugin, even Claude makes rookie mistakes. Forgetting to check Docker. Missing the critical workdir placeholder. Using the wrong command flags. These errors waste time and break your flow.

**SOLUTION (0:45-2:15)**
> Now watch what happens with the Claude Code plugin. When you clone mcpbr, Claude automatically becomes an expert. It knows to check Docker first, generate valid configs with the workdir placeholder, and use the right command flags every single time.
>
> Just ask Claude in plain English. The plugin handles the rest.
>
> Claude automatically validates prerequisites. Docker running? Check. API key set? Check. Config file missing? No problem.
>
> The plugin ensures critical details are correct, like the workdir placeholder that mcpbr needs to inject the repository path at runtime.
>
> Claude constructs the perfect command with verbose output, results file, and report. The benchmark runs flawlessly, comparing your MCP server against a baseline to measure real improvement.

**FEATURES (2:15-3:00)**
> The plugin includes three specialized skills that make Claude an mcpbr expert.
>
> It supports all three benchmarks: SWE-bench for bug fixes, CyberGym for security exploits, and MCPToolBench++ for tool use evaluation.
>
> When issues occur, Claude provides actionable troubleshooting based on deep knowledge of common problems.
>
> Need a quick demo? Claude knows the fastest way to validate your setup without reading documentation.
>
> From regression detection to custom prompts, Claude knows every feature without you needing to remember flags or read docs.

**CTA (3:00-3:15)**
> Ready to benchmark your MCP server the right way? Star mcpbr on GitHub, install it with pip, and let Claude Code do the heavy lifting. Zero mistakes, perfect benchmarks, every time.

---

## Word Count & Pacing

- **Total words:** ~420 words
- **Speaking pace:** 140-150 words/minute (natural, clear pace)
- **Total duration:** ~3 minutes
- **Buffer time:** Terminal actions, pauses, and visual demonstrations

This pacing allows for:
- Natural breathing and inflection
- Time for viewers to read terminal output
- Smooth transitions between sections
- Emphasis on key points without rushing
