# Timelapse Creator

Professional-grade Python script for creating high-quality timelapse videos from JPG image sequences using FFmpeg.

**Version:** 0.0.6 (2026-08-31)

## Table of Contents
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Options Reference](#options-reference)
- [Examples](#examples)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)

## Requirements

### System Dependencies
| Tool | Purpose | Minimum Version |
|------|---------|-----------------|
| **FFmpeg** | Video encoding | 4.0+ |
| **FFprobe** | Media analysis (bundled with FFmpeg) | 4.0+ |

### Python Dependencies
All required Python modules are part of the **standard library** (Python 3.7+):
- `argparse`, `os`, `re`, `shutil`, `signal`, `subprocess`, `sys`, `threading`, `time`
- `pathlib`, `typing`, `json`, `tempfile`

### Supported Platforms
- Windows 10/11
- macOS 10.14+
- Linux (any modern distribution)

## Installation

### 1. Install FFmpeg

**Windows:**
```powershell
# Using winget (recommended)
winget install Gyan.FFmpeg

# Using Chocolatey
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

**macOS:**
```bash
# Using Homebrew
brew install ffmpeg

# Using MacPorts
sudo port install ffmpeg
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg

# openSUSE
sudo zypper install ffmpeg
```

### 2. Verify Installation
```bash
python pylapse --testlib
```
Expected output:
```
Timelapse Creator v0.0.6 - Igor Brzezek
GitHub: https://github.com/IgorBrzezek

Checking dependencies...
  ffmpeg: OK (/usr/bin/ffmpeg)
    Version: ffmpeg version 6.0 ...
  ffprobe: OK (/usr/bin/ffprobe)
  Python: OK (3.11.4)

All dependencies satisfied.
```

### 3. Get the Script
```bash
# Clone or download pylapse
git clone https://github.com/IgorBrzezek/pylapse.git
cd pylapse
```

## Quick Start

```bash
# Basic usage
python pylapse -d ./photos -outfile timelapse.mp4

# With custom framerate
python pylapse -d ./photos -outfile timelapse.mp4 -framerate 24
```

## Revert (Extract Frames from Video)

Turn a video (MP4) back into a series of JPG stills. Works the other way from the main
timelapse builder. Two selection modes:

- **`-revert FR`** - read every **FR-th** frame of the movie (single FFmpeg pass)
- **`--timecode TIMES`** - grab a frame at each explicit timestamp (accurate seeking)

```bash
# Extract every 10th frame as JPGs
python pylapse -d ./frames --infile sunset_final.mp4 -revert 10

# Every 10th frame, heavier JPEG compression (default quality 10)
python pylapse -d ./frames --infile sunset_final.mp4 -revert 10 --compress 40

# Frames at specific timestamps (S, M:S, or H:M:S; decimals allowed)
python pylapse -d ./frames --infile sunset_final.mp4 --timecode 0:05,0:10,0:20

# Half-size, rotated 90 degrees
python pylapse -d ./frames --infile sunset_final.mp4 -revert 10 --scale 50 --rotate 90
```

### Revert Options
| Option | Default | Description |
|--------|---------|-------------|
| `-d`, `--dir DIR` | — | **Output** directory where the JPG images are saved (created if missing) |
| `--infile MOVIE` | — | Input video file (MP4) to extract frames from (required in revert mode) |
| `-revert FR` | — | Extract every FR-th frame: `1` = every frame, `2` = every 2nd, `10` = every 10th. Mutually exclusive with `--timecode` |
| `--timecode TIMES` | — | Comma-separated timestamps to grab a frame at each, e.g., `0:05,0:10,0:20` (`S`, `M:S`, `H:M:S`, decimals OK). Sorted, no duplicates. Mutually exclusive with `-revert` |
| `--compress %` | 10 | JPEG compression degree `0-100`: `0` = best quality / least compression, `100` = maximum compression. Internal quality maps to FFmpeg `q:v` (1-31) |
| `--scale N` | (none) | Scale JPGs to `N%` of the original size (e.g., `50` = 50%) |
| `--width N` | (none) | Exact output width for JPGs (height auto, keeps aspect ratio) |
| `--height N` | (none) | Exact output height for JPGs (width auto, keeps aspect ratio) |
| `-resize VAL` | (none) | Alternate resize: `50%`, `1920`, or `1080Y` (same resize engine as timelapse) |
| `--rotate N.M` | (none) | Rotate each JPG by N.M degrees (negative = left/counter-clockwise) |
| `--rotate-cut` | off | Crop rotated JPG to remove black corners (largest inscribed rectangle) |
| `-flip H\|V\|HV` | (none) | Flip each JPG: Horizontal, Vertical, or Both (180°) |
| `--fast-scale` | off | Faster scaling (`bilinear`) instead of high quality (`lanczos`) |

**Resize precedence when several are given:** `--scale` > `--width`/`--height` > `-resize`.

**Output naming:** `<video_stem>_NNNN.jpg` (e.g., from `sunset_final.mp4` you get
`sunset_final_0001.jpg`, `sunset_final_0002.jpg`, ...). `--timecode` names frames in
timestamp order (`_0001` = earliest). Files inherit the video's resolution unless a
resize option is given. If a timestamp falls past the end of the video, a warning is
printed and that frame is skipped.

**Note:** `--compress` is the inverse of radius/quality - lower value = larger, sharper
files; higher value = smaller files with more compression artifacts.

## Options Reference

### Required / Mode Arguments
| Option | Description |
|--------|-------------|
| `-d`, `--dir DIR` | Directory: input JPGs for **timelapse** mode, output JPGs for **revert** mode |
| `-outfile`, `--output FILE` | Output video file (MP4) — timelapse mode |
| `--infile MOVIE` | Input video file (MP4) to extract frames from — revert mode |
| `-revert FR` | Extract every FR-th frame from the video — revert mode |
| `--timecode TIMES` | Grab a frame at each comma-separated timestamp — revert mode |
| `--compress %` | JPEG compression 0-100 for revert (0=best, default 10) |
| `--scale / --width / --height` | Output size of extracted JPGs — revert mode |

### Video Settings
| Option | Default | Description |
|--------|---------|-------------|
| `-fr`, `-framerate N` | 30 | Frames per second |
| `-res`, `-resolution WxH` | Original size | Target resolution (e.g., 1920x1080; omit to keep original image size) |
| `-c`, `-codec CODEC` | libx264 | Video codec |
| `-crf N` | 18 | Constant Rate Factor (0-51, lower=better) |
| `-rc`, `--rate-control` | constqp | NVENC rate control mode (constqp, vbr, cbr, vbr_minqp, ll_2pass_quality, ll_2pass_size, ll_2pass_bitrate) |
| `-cq`, `--const-qp` | 18 | Constant QP for NVENC constqp mode (0-51, lower=better) |
| `-preset PRESET` | slow | Encoding preset |
| `-pix-fmt FMT` | yuv420p | Pixel format |

### Supported Codecs

**CPU (Software):**
- `libx264` - H.264/AVC (default)
- `libx265` - HEVC/H.265
- `libsvtav1` - AV1

**NVIDIA GPU (NVENC):**
- `h264_nvenc`, `hevc_nvenc`, `av1_nvenc` (RTX 40+)

**AMD GPU (AMF):**
- `h264_amf`, `hevc_amf`

**Intel GPU (QSV):**
- `h264_qsv`, `hevc_qsv`, `av1_qsv`

**Apple VideoToolbox:**
- `h264_videotoolbox`, `hevc_videotoolbox`

### Presets by Codec

**libx264/libx265:** `ultrafast`, `superfast`, `veryfast`, `faster`, `fast`, `medium`, `slow`, `slower`, `veryslow`

**NVENC:** `p1`–`p7` (p7=slowest/best), `hq`, `bd`, `ll`, `llhq`, `llhp`

**QSV:** `veryfast`, `faster`, `fast`, `medium`, `slow`, `slower`, `veryslow`

**AMF:** `quality`, `balanced`, `speed`

### Color & HDR
| Option | Description |
|--------|-------------|
| `-colorspace CS` | Colorspace (bt709, bt2020nc, etc.) |
| `-color-primaries CP` | Color primaries (bt709, bt2020, etc.) |
| `-color-transfer CT` | Transfer function (bt709, smpte2084/PQ, arib-std-b67/HLG) |
| `-tune TUNE` | Content tuning (film, animation, grain, stillimage, etc.) |
| `-profile PROFILE` | Codec profile |
| `-level LEVEL` | Codec level (4.0, 4.1, 4.2, 5.0, 5.1, 5.2, 6.0, etc.) |

### Image Processing
| Option | Description |
|--------|-------------|
| `-flip H\|V\|HV` | Flip: Horizontal, Vertical, or Both (180°) |
| `--rotate N.M` | Rotate each image by N.M degrees (negative = left/counter-clockwise) |
| `--rotate-cut` | Crop rotated image to remove black corners (largest inscribed rectangle) |
| `-resize VAL` | Resize: `50%` (percentage), `1920` (width), `1080Y` (height). **Omit to keep the original image size (no scaling is applied)** |
| `--fast-scale` | Use faster scaling filter (`bilinear`) instead of high quality (`lanczos`) |
| `-frames VAL` | Frame selection: `N` (first N), `N-M` (range), `-X` (last X). **Omit to use ALL JPG files in the directory** |
| `-sort NAME\|DATE` | Sort by filename (default) or modification date |

### Effects
| Option | Description |
|--------|-------------|
| `--fadein N` | Fade in duration in seconds |
| `--fadeout N` | Fade out duration in seconds (should be less than video duration for visible end fade) |
| `--text 'TEXT,START,END[,SCALE]'` | Text overlay (repeatable) |
| `--addsound FILE[,BITRATE]` | Add audio from WAV/MP3 file; optional bitrate in kbps (e.g., `audio.wav,128`) |

### Audio Options
| Option | Description |
|--------|-------------|
| `--addsound FILE` | Add audio from WAV/MP3 file |
| `--addsound FILE,BITRATE` | Add audio with specific bitrate (kbps); WAV default: 128kbps, MP3: auto |
| `--loopsound` | Loop audio if shorter than video duration (repeat audio to match video duration) |
| Audio fade | If `--fadein`/`--fadeout` used, audio fades in/out synchronously with video |

### Text Overlay Format
```
--text "Your text,start_sec,end_sec[,scale_percent][,R,G,B]"
```
- `TEXT` - Text to display (use `\n` for new lines)
- `START` - Start time in seconds
- `END` - End time in seconds
- `SCALE` - Font size percentage (1-1000, default: 100)
- `R,G,B` - RGB color values (0-255 each), e.g., `255,0,0` for red

**Multiple overlays:** Repeat `--text` option

**Color examples:**
```
# Red text at 150% size
--text "Hello,5,10,150,255,0,0"

# Blue text with default size
--text "Hello,5,10,,0,0,255"

# Green text with default size (no scale)
--text "Hello,5,10,100,0,255,0"
```

### Output Control
| Option | Description |
|--------|-------------|
| `--overwrite` | Overwrite existing output file |
| `--dry-run` | Show FFmpeg command, estimated duration (HH:MM:SS.mmm), and estimated file size without executing |
| `-v`, `--verbose` | Verbose output |
| `-h` | Show short help |
| `--help` | Show full help with examples |
| `--testlib` | Check system dependencies |

## Examples

### Basic Timelapse
```bash
# 30 fps, original image size (no scaling)
python pylapse -d ./photos -outfile timelapse.mp4

# 24 fps cinematic
python pylapse -d ./photos -outfile timelapse.mp4 -framerate 24
```

### Revert (Extract Frames from Video)
```bash
# Extract every 10th frame to ./frames as JPGs (default quality 10)
python pylapse -d ./frames --infile sunset_final.mp4 -revert 10

# Every 5th frame, lighter JPEG compression (0 = best quality)
python pylapse -d ./frames --infile sunset_final.mp4 -revert 5 --compress 5

# Every 2nd frame, heavy compression (saves small files, previews)
python pylapse -d ./frames --infile sunset_final.mp4 -revert 2 --compress 70

# Specific frames by timestamp, resized to 1920px wide
python pylapse -d ./frames --infile sunset_final.mp4 --timecode 0:05,0:10,0:20 --width 1920

# Half-size thumbnails rotated 90 degrees
python pylapse -d ./frames --infile sunset_final.mp4 -revert 10 --scale 50 --rotate 90
```

### Fast Encoding (pre-scaled photos)
```bash
# Fastest NVENC path: p1 preset + fast scale, no resize (photos already scaled)
python pylapse -d ./photos -outfile timelapse.mp4 \
  -codec h264_nvenc -preset p1 -rc constqp -cq 18 --fast-scale \
  --addsound music.mp3 --loopsound --overwrite
```

### High Quality Production
```bash
# 4K H.265, high quality
python pylapse -d ./photos -outfile timelapse.mp4 \
  -framerate 30 -resolution 3840x2160 -codec libx265 -crf 20 -preset veryslow

# GPU accelerated (NVIDIA)
python pylapse -d ./photos -outfile timelapse.mp4 \
  -framerate 30 -codec h264_nvenc -preset p7 -crf 22
```

### Image Processing
```bash
# Resize to 50%, first 100 frames, sorted by date
python pylapse -d ./photos -outfile timelapse.mp4 \
  -resize 50% -frames 100 -sort DATE

# Resize width to 1920px, frames 10-50
python pylapse -d ./photos -outfile timelapse.mp4 \
  -resize 1920 -frames 10-50

# Resize height to 1080px, last 30 frames
python pylapse -d ./photos -outfile timelapse.mp4 \
  -resize 1080Y -frames -30
```

### Effects & Text
```bash
# Fade in/out
python pylapse -d ./photos -outfile timelapse.mp4 \
  --fadein 2 --fadeout 3

# Text overlays (each line centered)
python pylapse -d ./photos -outfile timelapse.mp4 \
  --text "Chorwacja 2026\nPowrót,3,6,200" \
  --text "Filmed by Igor,60,65,100"

# Combined effects
python pylapse -d ./photos -outfile timelapse.mp4 \
  --fadein 2 --fadeout 2 \
  --text "Start,0,5,200" \
  --text "Middle\nSection,30,40,150" \
  --text "End,55,60,100" \
-resize 50% -frames 100-200 -sort DATE
```

### Rotation & Audio Examples
```bash
# Rotation
python pylapse -d ./photos -outfile timelapse.mp4 \
  --rotate 90

python pylapse -d ./photos -outfile timelapse.mp4 \
  --rotate -45.5

python pylapse -d ./photos -outfile timelapse.mp4 \
  -flip H --rotate 45

# Rotation with crop (remove black corners)
python pylapse -d ./photos -outfile timelapse.mp4 \
  --rotate 30 --rotate-cut

python pylapse -d ./photos -outfile timelapse.mp4 \
  --rotate -45 --rotate-cut

# Audio
python pylapse -d ./photos -outfile timelapse.mp4 \
  --addsound music.mp3

python pylapse -d ./photos -outfile timelapse.mp4 \
  --addsound narration.wav,128

python pylapse -d ./photos -outfile timelapse.mp4 \
  --addsound music.mp3 --fadein 3 --fadeout 3

python pylapse -d ./photos -outfile timelapse.mp4 \
  --addsound short_jingle.wav --loopsound

python pylapse -d ./photos -outfile timelapse.mp4 \
  --addsound music.mp3 --fadein 3 --fadeout 3 --loopsound
```

### Development & Testing
```bash
# Check dependencies
python pylapse --testlib

# Preview FFmpeg command (dry run) - shows estimated duration and file size
python pylapse -d ./photos -outfile test.mp4 --dry-run

# Verbose output
python pylapse -d ./photos -outfile timelapse.mp4 -v
```

## Advanced Features

### Automatic Sequence Detection
The script automatically detects numbered sequences:
- `IMG_001.jpg`, `IMG_002.jpg` → `IMG_%03d.jpg`
- `photo-1.jpg`, `photo-2.jpg` → `photo-%d.jpg`
- `001.jpg`, `002.jpg` → `%03d.jpg`

On Windows, uses concat demuxer for better compatibility.

### Original Image Size by Default
If neither `-resolution` nor `-resize` is given, images are **not scaled** - the video keeps the original
image size (useful when photos are already pre-scaled). The `scale` filter is only added when a resize
option is explicitly requested.

### Encoder Size Limit Warning
The script estimates the final frame size (taking `-resize`, `--rotate` and `--rotate-cut` into account)
and checks it against the encoder's maximum supported resolution:

| Codec family | Maximum frame |
|--------------|---------------|
| `h264_*` (nvenc/amf/qsv/videotoolbox, libx264) | 4096x4096 |
| `hevc_*`, `av1_*` (nvenc/amf/qsv/videotoolbox, libx265, libsvtav1) | 8192x8192 |

When `-level` is set for H.264, the level's frame-size budget (macroblocks) is also verified.
If the frame would be too large, a clear warning is printed before encoding, with a suggestion to use
`-resize`, lower `-level`, or switch codec (e.g., `hevc_nvenc`).

**Note:** H.264 NVENC on a 4096x4096 limit means large originals (e.g., 5184x3888) rotated and cropped
may exceed the limit - either `-resize` them or use `hevc_nvenc` (8192x8192).

### Fast Scaling
`--fast-scale` switches the resize filter from `lanczos` (best quality, slowest) to `bilinear` (slightly
lower quality, noticeably faster). Combined with `-preset p1` it gives the fastest encode throughput.

### Scaled-Before-Rotated Filter Chain
`scale` runs **before** `rotate`, so rotation is applied to far fewer pixels. With `--rotate-cut` the crop
is recomputed proportionally to the post-resize dimensions, keeping the largest-inscribed-rectangle
behavior correct at any target size.

### Frame Selection
If `-frames` is omitted, **all** JPG files in the input directory are used (one video frame per photo).

| Format | Example | Description |
|--------|---------|-------------|
| `N` | `100` | First 100 frames |
| `N-M` | `50-200` | Frames 50 to 200 (inclusive) |
| `-X` | `-50` | Last 50 frames |

### Sorting
- `NAME` (default): Alphabetical by filename
- `DATE`: By file modification time (oldest first)

### Hardware Acceleration
Use GPU codecs directly via `-codec`:
```bash
# NVIDIA
-codec h264_nvenc -preset p7

# AMD
-codec hevc_amf -preset quality

# Intel
-codec h264_qsv -preset medium

# Apple Silicon
-codec h264_videotoolbox
```
No separate `-hwaccel` needed for JPEG input.

### Progress Display
Real-time encoding progress with:
- Current frame / total
- Percentage complete
- Current FPS
- Encoding speed multiplier
- ETA

**Revert (video -> JPG)** shows a similar real-time status line while extracting:
- `[N/M images]` - JPG files saved so far / expected total
- Percentage complete (of the JPGs to produce)
- Elapsed time (`Elapsed:`)
- Output rate (`imgs/s`)
- ETA to finish

### Graceful Interruption & Reliability
- `Ctrl+C` (SIGINT) stops encoding cleanly and removes the incomplete output file
- **Stall detection:** if FFmpeg reports no progress for 60s a warning is shown; after 180s the process is
  killed automatically and the broken output is removed
- **Partial-file cleanup:** any interrupted/failed encoding deletes the unusable (no `moov` atom) output
- **Output verification:** after encoding, the file is checked with `ffprobe` (video stream, plus audio
  when `--addsound` was used) before reporting success
- Temporary text files cleaned up automatically
- Returns exit code 130 on interruption

## Troubleshooting

### "ffmpeg not found in PATH"
```bash
# Verify installation
ffmpeg -version

# Add to PATH or use full path
# Windows: C:\ffmpeg\bin\ffmpeg.exe
```

### "Output file already exists"
```bash
# Use overwrite flag
python pylapse -d ./photos -outfile out.mp4 --overwrite
```

### "No JPG files found"
- Check directory path: `-d /path/to/photos`
- Supported extensions: `.jpg`, `.jpeg`, `.JPG`, `.JPEG`
- Files must be directly in the directory (not recursive)

### "Resolution must be in format WxH"
```bash
# Correct format
-res 1920x1080
-resolution 3840x2160
```

### Text Overlay Issues
- Use `\n` for line breaks: `--text "Line1\nLine2,1,2"`
- Escape special chars: `'` and `:` are auto-escaped
- Scale range: 1-1000 (percentage of base 48pt font)

### Performance Tips
1. **Use GPU codec** for 10-50x speedup
2. **Use `-preset p1`** (fastest NVENC) for quick encodes
3. **Add `--fast-scale`** to speed up any resizing (bilinear instead of lanczos)
4. **Skip resize for pre-scaled photos** - the script keeps the original size by default
5. **Resize input** with `-resize 50%` for faster encoding of large originals
6. **Limit frames** with `-frames` for testing
7. **Dry run first** with `--dry-run` to verify command

### Common Error Codes
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error / missing dependencies |
| 130 | Interrupted (Ctrl+C) |
| FFmpeg codes | See FFmpeg documentation |

## License & Author

**Author:** Igor Brzezek  
**GitHub:** https://github.com/IgorBrzezek  
**Version:** 0.0.6 (2026-08-31)

Script uses standard library only. FFmpeg licensed under LGPL/GPL.