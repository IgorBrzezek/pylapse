# Timelapse Creator

Professional-grade Python script for creating high-quality timelapse videos from JPG image sequences using FFmpeg.

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
- `argparse`, `os`, `re`, `shutil`, `signal`, `subprocess`, `sys`, `time`
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
Timelapse Creator v0.0.1 - Igor Brzezek
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

## Options Reference

### Required Arguments
| Option | Description |
|--------|-------------|
| `-d`, `--dir DIR` | Directory containing JPG files |
| `-outfile`, `--output FILE` | Output video file (MP4) |

### Video Settings
| Option | Default | Description |
|--------|---------|-------------|
| `-fr`, `-framerate N` | 30 | Frames per second |
| `-res`, `-resolution WxH` | Auto | Target resolution (e.g., 1920x1080) |
| `-c`, `-codec CODEC` | libx264 | Video codec |
| `-crf N` | 18 | Constant Rate Factor (0-51, lower=better) |
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
| `-rotate H\|V\|HV` | Flip: Horizontal, Vertical, or Both (180°) |
| `-resize VAL` | Resize: `50%` (percentage), `1920` (width), `1080Y` (height) |
| `-frames VAL` | Frame selection: `N` (first N), `N-M` (range), `-X` (last X) |
| `-sort NAME\|DATE` | Sort by filename (default) or modification date |

### Effects
| Option | Description |
|--------|-------------|
| `--fadein N` | Fade in duration in seconds |
| `--fadeout N` | Fade out duration in seconds |
| `--text 'TEXT,START,END[,SCALE]'` | Text overlay (repeatable) |

### Text Overlay Format
```
--text "Your text,start_sec,end_sec[,scale_percent]"
```
- `TEXT` - Text to display (use `\n` for new lines)
- `START` - Start time in seconds
- `END` - End time in seconds
- `SCALE` - Font size percentage (1-1000, default: 100)

**Multiple overlays:** Repeat `--text` option

### Output Control
| Option | Description |
|--------|-------------|
| `--overwrite` | Overwrite existing output file |
| `--dry-run` | Show FFmpeg command without executing |
| `-v`, `--verbose` | Verbose output |
| `-h` | Show short help |
| `--help` | Show full help with examples |
| `--testlib` | Check system dependencies |

## Examples

### Basic Timelapse
```bash
# 30 fps, auto resolution (max 1920x1080)
python pylapse -d ./photos -outfile timelapse.mp4

# 24 fps cinematic
python pylapse -d ./photos -outfile timelapse.mp4 -framerate 24
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

### Development & Testing
```bash
# Check dependencies
python pylapse --testlib

# Preview FFmpeg command (dry run)
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

### Auto Resolution Scaling
Without `-resolution`, images are scaled to fit within 1920x1080 preserving aspect ratio:
- Landscape: width ≤ 1920
- Portrait: height ≤ 1080

### Frame Selection
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

### Graceful Interruption
- `Ctrl+C` (SIGINT) stops encoding cleanly
- Temporary text files cleaned up automatically
- Returns exit code 130

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
2. **Resize input** with `-resize 50%` for faster encoding
3. **Limit frames** with `-frames` for testing
4. **Use `-preset fast`** for quick previews
5. **Dry run first** with `--dry-run` to verify command

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
**Version:** 0.0.1 (2026-08-28)

Script uses standard library only. FFmpeg licensed under LGPL/GPL.