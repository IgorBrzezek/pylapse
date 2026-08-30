#!/usr/bin/env python3
"""
Timelapse creator from JPG sequence using FFmpeg.
Professional-grade script for creating high-quality timelapse videos.
"""

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Tuple, List


SCRIPT_VER = '0.0.5'
SCRIPT_DATE = '30.08.2026'
SCRIPT_AUTHOR = 'Igor Brzezek'
SCRIPT_GIT = 'https://github.com/IgorBrzezek'

SCRIPT_NAME = "Timelapse Creator"

STALL_WARN_SEC = 60   # no progress for this long -> warn that encode may be stuck
STALL_KILL_SEC = 180  # no progress for this long -> kill FFmpeg and remove broken output

# Maximum output frame dimensions supported by each encoder
ENCODER_MAX_DIMS = {
    "h264_nvenc": (4096, 4096),
    "hevc_nvenc": (8192, 8192),
    "av1_nvenc": (8192, 8192),
    "h264_amf": (4096, 4096),
    "hevc_amf": (8192, 8192),
    "h264_qsv": (4096, 4096),
    "hevc_qsv": (8192, 8192),
    "av1_qsv": (8192, 8192),
    "h264_videotoolbox": (4096, 4096),
    "hevc_videotoolbox": (8192, 8192),
    "libx264": (4096, 4096),
    "libx265": (8192, 8192),
    "libsvtav1": (8192, 8192),
}

# H.264 level limits: maximum frame size in macroblocks (16x16). Pixel budget = MB * 256.
H264_LEVEL_MAX_MB = {
    "3.0": 1620, "3.1": 3600, "3.2": 5120,
    "4.0": 8192, "4.1": 8192, "4.2": 8704,
    "5.0": 22080, "5.1": 36864, "5.2": 36864,
    "6.0": 139264, "6.1": 139264, "6.2": 207360,
}


def check_dependencies() -> bool:
    missing = []
    for cmd in ("ffmpeg", "ffprobe"):
        if not shutil.which(cmd):
            missing.append(cmd)

    python_modules = [
        ("argparse", "argparse"),
        ("os", "os"),
        ("re", "re"),
        ("shutil", "shutil"),
        ("signal", "signal"),
        ("subprocess", "subprocess"),
        ("sys", "sys"),
        ("time", "time"),
        ("pathlib", "pathlib"),
        ("typing", "typing"),
        ("json", "json"),
        ("tempfile", "tempfile"),
    ]
    missing_py = []
    for name, import_name in python_modules:
        try:
            __import__(import_name)
        except ImportError:
            missing_py.append(name)

    all_ok = True
    if missing:
        print(f"Error: Required command(s) not found: {', '.join(missing)}", file=sys.stderr)
        print("Install FFmpeg:", file=sys.stderr)
        print("  Windows: winget install Gyan.FFmpeg  OR  choco install ffmpeg", file=sys.stderr)
        print("  macOS:   brew install ffmpeg", file=sys.stderr)
        print("  Linux:   sudo apt install ffmpeg  (or your distro's package manager)", file=sys.stderr)
        all_ok = False

    if missing_py:
        print(f"Error: Required Python module(s) not found: {', '.join(missing_py)}", file=sys.stderr)
        print("All required modules are part of Python standard library.", file=sys.stderr)
        print("Ensure you have a complete Python installation.", file=sys.stderr)
        all_ok = False

    return all_ok


def signal_handler(signum, frame):
    print("\nInterrupted by user. Cleaning up...")
    sys.exit(130)


signal.signal(signal.SIGINT, signal_handler)
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, signal_handler)

class TimelapseBuilder:
    def __init__(self):
        self.input_dir: Optional[Path] = None
        self.output_file: Optional[Path] = None
        self.framerate: int = 30
        self.target_resolution: Optional[Tuple[int, int]] = None
        self.codec: str = "libx264"
        self.crf: int = 18
        self.preset: str = "slow"
        self.pix_fmt: str = "yuv420p"
        self.colorspace: Optional[str] = None
        self.color_primaries: Optional[str] = None
        self.color_transfer: Optional[str] = None
        self.tune: Optional[str] = None
        self.profile: Optional[str] = None
        self.level: Optional[str] = None
        self.movflags: str = "+faststart"
        self.start_number: Optional[int] = None
        self.rotate_flip: Optional[str] = None
        self.rotate_angle: Optional[float] = None
        self.rotate_cut: bool = False
        self.pattern_type: str = "glob"
        self.dry_run: bool = False
        self.verbose: bool = False
        self.resize_percent: Optional[float] = None
        self.resize_width: Optional[int] = None
        self.resize_height: Optional[int] = None
        self.frame_range: Optional[Tuple[int, int]] = None
        self.sort_by: str = "name"
        self._total_files: int = 0
        self._frame_start: int = 0
        self._frame_end: int = 0
        self.fadein: Optional[float] = None
        self.fadeout: Optional[float] = None
        self.text_overlays: List[dict] = []
        self.overwrite: bool = False
        self.addsound: Optional[str] = None
        self.addsound_bitrate: Optional[int] = None
        self.loopsound: bool = False
        self._needs_audio_loop: bool = False

    def print_short_help(self) -> None:
        print(f"{SCRIPT_NAME} v{SCRIPT_VER} - {SCRIPT_AUTHOR}")
        print(f"GitHub: {SCRIPT_GIT}")
        print()
        print("Usage: pylapse -d DIR -outfile FILE [OPTIONS]")
        print()
        print("Required:")
        print("  -d, --dir DIR         Directory containing JPG files")
        print("  -outfile, --output    Output video file (MP4)")
        print()
        print("Options:")
        print("  -fr, -framerate N     Frames per second (default: 30)")
        print("  -res, -resolution WxH Target resolution (e.g., 1920x1080)")
        print("  -c, -codec CODEC      Video codec (default: libx264)")
        print("  -crf N                Constant Rate Factor 0-51 (default: 18)")
        print("  -rc, --rate-control   Rate control mode for NVENC (constqp, vbr, cbr, etc.)")
        print("  -cq, --const-qp N     Constant QP for NVENC constqp mode (0-51)")
        print("  -preset PRESET        Encoding preset (default: slow)")
        print("  -pix-fmt FMT          Pixel format (default: yuv420p)")
        print("  -colorspace CS        Colorspace (e.g., bt709)")
        print("  -color-primaries CP   Color primaries (e.g., bt709)")
        print("  -color-transfer CT    Color transfer (e.g., bt709)")
        print("  -tune TUNE            Tune for content type (film, animation, etc.)")
        print("  -profile PROFILE      Codec profile (baseline, main, high, etc.)")
        print("  -level LEVEL          Codec level (4.0, 4.1, 4.2, 5.0, etc.)")
        print("  -start-number N       Start frame number (sequential naming)")
        print("  -pattern-type TYPE    Input pattern: glob or sequence (default: glob)")
        print("  -flip H|V|HV          Flip: horizontal, vertical, or both")
        print("  --rotate N.M          Rotate each image by N.M degrees (negative = left)")
        print("  --rotate-cut          Crop rotated image to remove black corners")
        print("  -resize VAL           Resize: 50%%, 1920, or 1080Y (omit to keep original size)")
        print("  --fast-scale          Use faster scaling (bilinear) instead of high quality (lanczos)")
        print("  -frames VAL           Frames: N, N-M, or -X (last X) (omit to use ALL JPG files)")
        print("  -sort NAME|DATE       Sort by name (default) or date")
        print("  --fadein N            Fade in duration in seconds")
        print("  --fadeout N           Fade out duration in seconds (should be less than video duration for visible end fade)")
        print("  --text 'T,S,E[,S][,R,G,B]'    Text: text, start sec, end sec, scale%, RGB 0-255 (repeatable)")
        print("  --addsound FILE       Add audio from file (WAV/MP3), optional bitrate: 'FILE,BITRATE' (e.g., 'audio.wav,128')")
        print("  --loopsound           Loop audio if shorter than video (repeat audio to match video duration)")
        print("  --overwrite           Overwrite output file if exists")
        print("  --dry-run             Show FFmpeg command, estimated duration & size")
        print("  -v, --verbose         Verbose output")
        print("  -h                    Show this short help")
        print("  --help                Show full help with examples")
        print()
        print("Safety: encoder size limits are auto-checked (warning), stalled encodings are killed after 180s,")
        print("incomplete output files are removed, and finished files are verified with ffprobe.")

    def print_full_help(self) -> None:
        self.print_short_help()
        print()
        print("Option values:")
        print("  -framerate, -fr:       integer (default: 30)")
        print("  -resolution, -res:     WxH (e.g., 1920x1080, 3840x2160, 1280x720)")
        print("  -codec, -c:            libx264 | libx265 | libsvtav1 |")
        print("                         h264_nvenc | hevc_nvenc | av1_nvenc |")
        print("                         h264_amf | hevc_amf |")
        print("                         h264_qsv | hevc_qsv | av1_qsv |")
        print("                         h264_videotoolbox | hevc_videotoolbox")
        print("  -crf:                  0-51 (default: 18, lower=better)")
        print("  -rc, --rate-control:   constqp | vbr | cbr | vbr_minqp | ll_2pass_quality | ll_2pass_size | ll_2pass_bitrate")
        print("  -cq, --const-qp:       0-51 (default: 18, lower=better) for NVENC constqp mode")
        print("  -preset:               libx264/libx265: ultrafast superfast veryfast faster fast medium slow slower veryslow")
        print("                         NVENC: p1 p2 p3 p4 p5 p6 p7 hq bd ll llhq llhp")
        print("                         QSV:   veryfast faster fast medium slow slower veryslow")
        print("                         AMF:   quality balanced speed")
        print("  -pix-fmt:              yuv420p | yuv422p | yuv444p | yuv420p10le | yuv422p10le | yuv444p10le |")
        print("                         nv12 | p010le | qsv | cuda | vaapi | videotoolbox")
        print("  -colorspace:           bt709 | bt470bg | smpte170m | smpte240m | bt2020nc | bt2020c |")
        print("                         iec61966-2-1 | iec61966-2-4 | smpte2085 | chroma-derived-nc | chroma-derived-c")
        print("  -color-primaries:      bt709 | bt470m | bt470bg | smpte170m | smpte240m | film | bt2020 |")
        print("                         smpte428 | smpte431 | smpte432 | jedec-p22")
        print("  -color-transfer:       bt709 | bt470m | bt470bg | smpte170m | smpte240m | linear | log100 |")
        print("                         log316 | iec61966-2-1 | iec61966-2-4 | bt1361e | bt2020-10 |")
        print("                         bt2020-12 | smpte2084 | smpte428 | arib-std-b67")
        print("  -tune:                 film | animation | grain | stillimage | fastdecode | zerolatency |")
        print("                         psnr | ssim")
        print("  -profile:              libx264: baseline main high high10 high422 high444")
        print("                         libx265: main main10 mainstillpicture")
        print("                         NVENC:   baseline main high high444p")
        print("  -level:                1.0 | 1.1 | 1.2 | 1.3 | 2.0 | 2.1 | 2.2 | 3.0 | 3.1 | 3.2 |")
        print("                         4.0 | 4.1 | 4.2 | 5.0 | 5.1 | 5.2 | 6.0 | 6.1 | 6.2")
        print("  -start-number:         integer")
        print("  -pattern-type:         glob | sequence")
        print("  -flip:                 H | V | HV")
        print("  --rotate:              float (degrees, e.g., 90, -45.5)")
        print("  --rotate-cut:          flag (crop rotated image to remove black corners)")
        print("  -resize:               NN% (1-100) | NNNN (width) | NNNNY (height)")
        print("                         (omit to keep original image size - no scaling is applied)")
        print("  --fast-scale:          flag (bilinear scaling, faster but slightly lower quality than lanczos)")
        print("  -frames:               N (first N) | N-M (range) | -X (last X)")
        print("                         (omit to use ALL JPG files found in the input directory)")
        print("  -sort:                 NAME | DATE")
        print("  --fadein:              float (seconds, e.g., 2)")
        print("  --fadeout:             float (seconds, e.g., 2)")
        print("  --text:                'TEXT,START,END[,SCALE][,R,G,B]' scale% (1-1000, default 100), RGB 0-255, \\n for new line")
        print("  --addsound:            'FILE[,BITRATE]' audio file (WAV/MP3), bitrate in kbps (default: 128 for WAV)")
        print("  --loopsound:           flag (loop audio if shorter than video duration)")
        print("  --overwrite:           flag (overwrite existing output file)")
        print("  --dry-run:             flag (show FFmpeg command, estimated duration & size)")
        print()
        print("Reliability:")
        print("  - Frame size is estimated (resize + rotation + crop) and checked against the encoder's")
        print("    maximum resolution; a warning is printed before encoding if the frame is too large.")
        print("  - H.264 level limits are also checked when -level is given.")
        print("  - If FFmpeg reports no progress for 60s a warning is printed; after 180s the process is")
        print("    killed and the incomplete output file is removed.")
        print("  - After encoding, the output is verified with ffprobe (video and audio streams).")
        print()
        print("Examples:")
        print("  pylapse -d ./photos -outfile timelapse.mp4 -framerate 24")
        print("  pylapse -d ./photos -outfile timelapse.mp4 -framerate 30 -resolution 1920x1080 -codec libx265 -crf 20")
        print("  pylapse -d ./photos -outfile timelapse.mp4 -framerate 60 -preset veryslow -tune film -profile high -level 4.2")
        print("  pylapse -d ./photos -outfile timelapse.mp4 -framerate 30 -codec h264_nvenc -preset p7 -crf 22")
        print("  pylapse -d ./photos -outfile timelapse.mp4 -codec h264_nvenc -preset p1 --fast-scale -cq 18  # fastest NVENC")
        print("  pylapse -d ./photos -outfile timelapse.mp4 -resize 50% -frames 10-100 -sort DATE")
        print("  pylapse -d ./photos -outfile timelapse.mp4 --addsound music.mp3 --fadein 3 --fadeout 3")
        print("  pylapse -d ./photos -outfile timelapse.mp4 --addsound jingle.wav --loopsound")

    def parse_args(self) -> None:
        import sys
        if "--testlib" in sys.argv:
            self.test_dependencies()
            sys.exit(0)
        if "-h" in sys.argv and "--help" not in sys.argv:
            self.print_short_help()
            sys.exit(0)
        if "--help" in sys.argv:
            self.print_full_help()
            sys.exit(0)

        parser = argparse.ArgumentParser(
            description="Create timelapse video from JPG sequence using FFmpeg",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            add_help=False,
        )

        parser.add_argument("-d", "--dir", required=True, help="Directory containing JPG files")
        parser.add_argument("-outfile", "--output", required=True, help="Output video file (MP4)")
        parser.add_argument("-framerate", "-fr", type=int, default=30, help="Frames per second (default: 30)")
        parser.add_argument("-resolution", "-res", help="Target resolution WxH (e.g., 1920x1080, 3840x2160)")
        parser.add_argument("-codec", "-c", default="libx264", help="Video codec (default: libx264)")
        parser.add_argument("-crf", type=int, default=18, help="Constant Rate Factor 0-51, lower=better (default: 18)")
        parser.add_argument("-rc", "--rate-control", choices=["constqp", "vbr", "cbr", "vbr_minqp", "ll_2pass_quality", "ll_2pass_size", "ll_2pass_bitrate"], help="Rate control mode for NVENC (default: constqp for NVENC)")
        parser.add_argument("-cq", "--const-qp", type=int, help="Constant QP for NVENC constqp mode (0-51, lower=better, default: 18)")
        parser.add_argument("-preset", default="slow", help="Encoding preset (default: slow)")
        parser.add_argument("-pix-fmt", default="yuv420p", help="Pixel format (default: yuv420p for compatibility)")
        parser.add_argument("-colorspace", help="Colorspace (e.g., bt709, bt2020nc)")
        parser.add_argument("-color-primaries", help="Color primaries (e.g., bt709, bt2020)")
        parser.add_argument("-color-transfer", help="Color transfer (e.g., bt709, smpte2084 for HDR)")
        parser.add_argument("-tune", help="Tune for content type (film, animation, grain, stillimage, fastdecode, zerolatency)")
        parser.add_argument("-profile", help="Codec profile (e.g., baseline, main, high, high10, high422)")
        parser.add_argument("-level", help="Codec level (e.g., 4.0, 4.1, 4.2, 5.0, 5.1, 5.2, 6.0)")
        
        parser.add_argument("-start-number", type=int, help="Start frame number (for sequential naming)")
        parser.add_argument("-pattern-type", choices=["glob", "sequence"], default="glob", help="Input pattern type (default: glob)")
        parser.add_argument("-flip", choices=["H", "V", "HV"], dest="rotate_flip", help="Flip each image: H=horizontal, V=vertical, HV=both (180°)")
        parser.add_argument("--rotate", type=float, dest="rotate_angle", help="Rotate each image by N.M degrees (negative = left, counter-clockwise)")
        parser.add_argument("--rotate-cut", action="store_true", dest="rotate_cut", help="Crop rotated image to remove black corners (largest inscribed rectangle)")
        parser.add_argument("-resize", help="Resize images: percentage (e.g., 50), width (e.g., 1920), or height (e.g., 1080Y). Omit to keep original size")
        parser.add_argument("--fast-scale", action="store_true", help="Use faster scaling filter (bilinear) instead of high quality (lanczos)")
        parser.add_argument("-frames", help="Frame selection: N (first N), N-M (range), -X (last X). Omit to use all JPG files")
        parser.add_argument("-sort", choices=["NAME", "DATE"], default="NAME", help="Sort images by name (default) or date")
        parser.add_argument("--fadein", type=float, help="Fade in duration in seconds (e.g., 2)")
        parser.add_argument("--fadeout", type=float, help="Fade out duration in seconds (e.g., 2)")
        parser.add_argument("--text", action="append", help="Text overlay: 'TEXT,START,END' (seconds). Can be used multiple times.")
        parser.add_argument("--addsound", help="Add audio from file (WAV/MP3), optional bitrate: 'FILE,BITRATE' (e.g., 'audio.wav,128')")
        parser.add_argument("--loopsound", action="store_true", help="Loop audio if shorter than video (repeat audio to match video duration)")
        parser.add_argument("--overwrite", action="store_true", help="Overwrite output file if it exists")
        parser.add_argument("--dry-run", action="store_true", help="Show FFmpeg command without executing")
        parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

        args = parser.parse_args()

        self.input_dir = Path(args.dir).resolve()
        self.output_file = Path(args.output).resolve()
        self.framerate = args.framerate
        self.codec = args.codec
        self.crf = args.crf
        self.rate_control = args.rate_control
        self.const_qp = args.const_qp
        self.preset = args.preset
        self.pix_fmt = args.pix_fmt
        self.colorspace = args.colorspace
        self.color_primaries = args.color_primaries
        self.color_transfer = args.color_transfer
        self.tune = args.tune
        self.profile = args.profile
        self.level = args.level
        
        self.start_number = args.start_number
        self.pattern_type = args.pattern_type
        self.rotate_flip = args.rotate_flip
        self.rotate_angle = args.rotate_angle
        self.rotate_cut = args.rotate_cut
        self.fast_scale = args.fast_scale
        self.dry_run = args.dry_run
        self.verbose = args.verbose
        self.sort_by = args.sort.lower()
        self.fadein = args.fadein
        self.fadeout = args.fadeout
        self.overwrite = args.overwrite
        self.loopsound = args.loopsound

        if args.addsound:
            self._parse_addsound(args.addsound)

        if args.text:
            self._parse_text_overlays(args.text)

        if args.resize:
            self._parse_resize(args.resize)
        if args.frames:
            self._parse_frames(args.frames)

        if args.resolution:
            try:
                w, h = map(int, args.resolution.lower().split("x"))
                self.target_resolution = (w, h)
            except ValueError:
                parser.error("Resolution must be in format WxH (e.g., 1920x1080)")

        if not self.input_dir.exists() or not self.input_dir.is_dir():
            parser.error(f"Input directory does not exist: {self.input_dir}")

        if self.output_file.exists() and not self.overwrite:
            parser.error(f"Output file already exists: {self.output_file}. Use --overwrite to replace it.")

        if self.output_file.suffix.lower() != ".mp4":
            print(f"Warning: Output file should have .mp4 extension", file=sys.stderr)

    def test_dependencies(self) -> None:
        print(f"{SCRIPT_NAME} v{SCRIPT_VER} - {SCRIPT_AUTHOR}")
        print(f"GitHub: {SCRIPT_GIT}")
        print()
        print("Checking dependencies...")
        
        all_ok = True
        
        # Check ffmpeg
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            print(f"  ffmpeg: OK ({ffmpeg_path})")
            try:
                result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
                version_line = result.stdout.split('\n')[0] if result.stdout else "unknown"
                print(f"    Version: {version_line}")
            except Exception:
                print(f"    Version: unable to determine")
        else:
            print(f"  ffmpeg: MISSING")
            all_ok = False
        
        # Check ffprobe
        ffprobe_path = shutil.which("ffprobe")
        if ffprobe_path:
            print(f"  ffprobe: OK ({ffprobe_path})")
        else:
            print(f"  ffprobe: MISSING")
            all_ok = False
        
        # Check Python version
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        print(f"  Python: OK ({py_version})")
        
        print()
        if all_ok:
            print("All dependencies satisfied.")
            sys.exit(0)
        else:
            print("Some dependencies are missing.")
            print("Install FFmpeg:")
            print("  Windows: winget install Gyan.FFmpeg  OR  choco install ffmpeg")
            print("  macOS:   brew install ffmpeg")
            print("  Linux:   sudo apt install ffmpeg  (or your distro's package manager)")
            sys.exit(1)

    def _parse_resize(self, value: str) -> None:
        value = value.strip()
        if value.endswith("%"):
            try:
                pct = float(value[:-1])
                if pct <= 0 or pct > 100:
                    raise ValueError
                self.resize_percent = pct / 100.0
            except ValueError:
                raise argparse.ArgumentTypeError("Percentage must be a number between 0 and 100 (e.g., 50%)")
        elif value.endswith("Y") or value.endswith("y"):
            try:
                self.resize_height = int(value[:-1])
                if self.resize_height <= 0:
                    raise ValueError
            except ValueError:
                raise argparse.ArgumentTypeError("Height must be a positive integer (e.g., 1080Y)")
        else:
            try:
                self.resize_width = int(value)
                if self.resize_width <= 0:
                    raise ValueError
            except ValueError:
                raise argparse.ArgumentTypeError("Width must be a positive integer (e.g., 1920)")

    def _parse_addsound(self, value: str) -> None:
        value = value.strip()
        parts = value.split(",", 1)
        audio_file = parts[0].strip()
        if not audio_file:
            raise argparse.ArgumentTypeError("Audio file path is required")
        
        # Check if file exists
        audio_path = Path(audio_file)
        if not audio_path.is_absolute():
            audio_path = Path.cwd() / audio_file
        
        if not audio_path.exists():
            raise argparse.ArgumentTypeError(f"Audio file not found: {audio_file}")
        
        self.addsound = str(audio_path.resolve())
        
        # Default bitrate: 128 kbps for WAV, auto for MP3
        if len(parts) > 1:
            try:
                bitrate = int(parts[1].strip())
                if bitrate <= 0:
                    raise ValueError
                self.addsound_bitrate = bitrate
            except ValueError:
                raise argparse.ArgumentTypeError("Bitrate must be a positive integer (e.g., 128)")
        else:
            # Auto-detect based on extension
            if audio_path.suffix.lower() == ".wav":
                self.addsound_bitrate = 128
            else:
                self.addsound_bitrate = None  # Let FFmpeg decide for MP3

    def _parse_frames(self, value: str) -> None:
        value = value.strip()
        if value.startswith("-"):
            try:
                count = int(value[1:])
                if count <= 0:
                    raise ValueError
                self.frame_range = (-count, -1)
            except ValueError:
                raise argparse.ArgumentTypeError("Last frames format: -X where X is positive integer")
        elif "-" in value:
            try:
                start_str, end_str = value.split("-", 1)
                start = int(start_str)
                end = int(end_str)
                if start < 1 or end < start:
                    raise ValueError
                self.frame_range = (start - 1, end - 1)
            except ValueError:
                raise argparse.ArgumentTypeError("Frame range format: N-M (e.g., 10-50)")
        else:
            try:
                count = int(value)
                if count <= 0:
                    raise ValueError
                self.frame_range = (0, count - 1)
            except ValueError:
                raise argparse.ArgumentTypeError("Frame count must be a positive integer")

    def _parse_text_overlays(self, values: List[str]) -> None:
        for v in values:
            v = v.strip()
            parts = v.split(",", 6)
            if len(parts) < 3:
                raise argparse.ArgumentTypeError("Text format: 'TEXT,START,END[,SCALE][,R,G,B]' (e.g., 'Hello,5,10,200,255,0,0')")
            text = parts[0]
            try:
                start = float(parts[1])
                end = float(parts[2])
                if start < 0 or end < 0:
                    raise ValueError
                if end <= start:
                    raise ValueError
            except ValueError:
                raise argparse.ArgumentTypeError("START and END must be positive numbers, END > START")
            scale = 100
            color = None
            # Handle different formats:
            # 3 parts: TEXT,START,END
            # 4 parts: TEXT,START,END,SCALE
            # 5 parts: TEXT,START,END,SCALE (or TEXT,START,END,0xRRGGBB)
            # 6 parts: TEXT,START,END,R,G,B (no scale, just RGB)
            # 7 parts: TEXT,START,END,SCALE,R,G,B
            if len(parts) >= 4:
                # Check if 4th part is SCALE (integer 1-1000) or R value for RGB without scale
                # If 6 parts total, it's TEXT,START,END,R,G,B (no scale)
                # If 7 parts total, it's TEXT,START,END,SCALE,R,G,B
                # If 4 or 5 parts total, it's TEXT,START,END,SCALE (or TEXT,START,END,0xRRGGBB)
                if len(parts) == 6:
                    # Format: TEXT,START,END,R,G,B (no scale)
                    try:
                        r = int(parts[3])
                        g = int(parts[4])
                        b = int(parts[5])
                        if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
                            raise ValueError
                        color = f"0x{r:02x}{g:02x}{b:02x}"
                    except ValueError:
                        raise argparse.ArgumentTypeError("RGB values must be integers 0-255 (e.g., 255,0,0)")
                elif len(parts) >= 7:
                    # Format: TEXT,START,END,SCALE,R,G,B
                    try:
                        scale = int(parts[3])
                        if scale <= 0 or scale > 1000:
                            raise ValueError
                        r = int(parts[4])
                        g = int(parts[5])
                        b = int(parts[6])
                        if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
                            raise ValueError
                        color = f"0x{r:02x}{g:02x}{b:02x}"
                    except ValueError:
                        raise argparse.ArgumentTypeError("SCALE must be 1-1000, RGB values 0-255")
                else:
                    # 4 or 5 parts: TEXT,START,END,SCALE or TEXT,START,END,0xRRGGBB
                    try:
                        scale = int(parts[3])
                        if scale <= 0 or scale > 1000:
                            raise ValueError
                    except ValueError:
                        # Maybe it's a hex color
                        color_val = parts[3].strip()
                        if color_val.startswith("0x") or color_val.startswith("#"):
                            color = color_val.replace("#", "0x")
                        else:
                            raise argparse.ArgumentTypeError("4th parameter must be SCALE (1-1000) or color (0xRRGGBB or #RRGGBB)")
            self.text_overlays.append({"text": text, "start": start, "end": end, "scale": scale, "color": color})

    def find_jpg_files(self) -> List[Path]:
        jpg_files = list(self.input_dir.glob("*.[jJ][pP][gG]"))
        jpg_files += list(self.input_dir.glob("*.[jJ][pP][eE][gG]"))
        if not jpg_files:
            jpg_files = list(self.input_dir.glob("*.JPG"))
            jpg_files += list(self.input_dir.glob("*.JPEG"))

        if self.sort_by == "date":
            jpg_files.sort(key=lambda f: f.stat().st_mtime)
        else:
            jpg_files.sort(key=lambda f: f.name.lower())

        self._total_files = len(jpg_files)

        if self.frame_range:
            start, end = self.frame_range
            if start < 0:
                start = len(jpg_files) + start
            if end < 0:
                end = len(jpg_files) + end + 1
            else:
                end = end + 1
            start = max(0, min(start, len(jpg_files)))
            end = max(start, min(end, len(jpg_files)))
            self._frame_start = start
            self._frame_end = end
            jpg_files = jpg_files[start:end]

        return jpg_files

    def detect_sequence_pattern(self, files: List[Path]) -> Tuple[str, int, bool]:
        if not files:
            return "", 1, False

        names = [f.stem for f in files]
        first = names[0]

        patterns = [
            (r"^(\D+)(\d+)$", 1),
            (r"^(.+?)[-_](\d+)$", 1),
            (r"^(\d+)$", 0),
        ]

        for pattern, prefix_group in patterns:
            match = re.match(pattern, first)
            if match:
                prefix = match.group(prefix_group) if prefix_group == 1 else ""
                nums = []
                for n in names:
                    m = re.match(pattern, n)
                    if m:
                        try:
                            nums.append(int(m.group(1 if prefix_group == 0 else 2)))
                        except (IndexError, ValueError):
                            break
                if len(nums) == len(names):
                    nums.sort()
                    if all(nums[i] == nums[0] + i for i in range(len(nums))):
                        start_num = nums[0]
                        if prefix:
                            digit_len = len(match.group(2)) if prefix_group == 1 else len(match.group(1))
                            return f"{prefix}%0{digit_len}d.jpg", start_num, True
                        return f"%0{len(str(nums[-1]))}d.jpg", start_num, True
        return "", 1, False

    def probe_first_image(self, files: List[Path]) -> Optional[dict]:
        if not files:
            return None
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=width,height,pix_fmt,color_space,color_primaries,color_transfer",
                    "-of", "json",
                    str(files[0])
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            import json
            data = json.loads(result.stdout)
            if data.get("streams"):
                return data["streams"][0]
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pass
        return None

    def _compute_scaled_dims(self, w0: int, h0: int) -> Tuple[int, int]:
        if self.resize_percent:
            return max(2, int(w0 * self.resize_percent)), max(2, int(h0 * self.resize_percent))
        elif self.resize_width:
            new_w = self.resize_width
            new_h = int(h0 * new_w / w0)
            if new_h % 2:
                new_h -= 1
            return new_w, max(2, new_h)
        elif self.resize_height:
            new_h = self.resize_height
            new_w = int(w0 * new_h / h0)
            if new_w % 2:
                new_w -= 1
            return max(2, new_w), new_h
        elif self.target_resolution:
            return self.target_resolution[0], self.target_resolution[1]
        else:
            # No resize option: keep original size
            return w0, h0

    def _compute_rotate_crop(self, W: int, H: int, radians: float) -> Tuple[int, int]:
        import math
        cos_a = math.cos(radians)
        sin_a = math.sin(radians)
        cos2a = cos_a * cos_a - sin_a * sin_a  # cos(2*radians)
        # Rotated canvas size
        rw = int(W * cos_a + H * sin_a)
        rh = int(W * sin_a + H * cos_a)
        # Handle edge case at 45 degrees where cos2a = 0
        eps = 1e-10
        if abs(cos2a) < eps:
            # At 45 degrees: inscribed rectangle is a square
            # side = min(W, H) * sqrt(2) / 2
            side = int(min(W, H) * 0.7071067811865476)
            cw = side
            ch = side
        elif cos2a > 0:
            cw = int((W * cos_a - H * sin_a) / cos2a)
            ch = int((H * cos_a - W * sin_a) / cos2a)
        else:
            # For angles > 45 degrees, swap W and H, use 90-angle
            cw = int((H * sin_a - W * cos_a) / (-cos2a))
            ch = int((W * sin_a - H * cos_a) / (-cos2a))
        # Ensure crop stays within rotated canvas and is positive/even
        cw = max(2, min(cw, rw - 4))
        ch = max(2, min(ch, rh - 4))
        if cw % 2:
            cw -= 1
        if ch % 2:
            ch -= 1
        return cw, ch

    def _check_encoder_limits(self, w: int, h: int) -> None:
        max_w, max_h = ENCODER_MAX_DIMS.get(self.codec, (4096, 4096))
        problems = []
        if w > max_w or h > max_h:
            problems.append(f"resolution {w}x{h} exceeds {self.codec} maximum {max_w}x{max_h}")
        if self.codec.startswith("h264") and self.level:
            mb = ((w + 15) // 16) * ((h + 15) // 16)
            budget = H264_LEVEL_MAX_MB.get(str(self.level))
            if budget and mb > budget:
                problems.append(f"resolution {w}x{h} exceeds H.264 level {self.level} limit "
                                f"(max {budget} macroblocks = {budget * 256} pixels)")
        if problems:
            print(f"\nWarning: Output frame will be {w}x{h}, which is likely too large for {self.codec}.", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            print("  -> Use -resize (e.g., -resize 1920) to fit inside the encoder limits, or switch codec "
                  "(e.g., hevc_nvenc).", file=sys.stderr)

    def build_ffmpeg_command(self, files: List[Path]) -> List[str]:
        cmd = ["ffmpeg", "-y"]

        # When frame_range is specified, use concat demuxer to ensure only selected frames are processed
        use_concat = self.frame_range is not None

        if sys.platform == "win32" or use_concat:
            if use_concat:
                # For NVENC, use image2 demuxer with explicit pattern instead of concat demuxer
                # to avoid frame dropping issues with complex filter chains
                if "nvenc" in self.codec:
                    pattern, detected_start, is_sequence = self.detect_sequence_pattern(files)
                    if is_sequence:
                        start = self.start_number if self.start_number is not None else detected_start
                        pattern = str(self.input_dir / pattern)
                        cmd.extend(["-framerate", str(self.framerate), "-start_number", str(start), "-i", pattern])
                    else:
                        # Fallback to concat demuxer
                        file_list = self.input_dir / "filelist.txt"
                        with open(file_list, "w", encoding="utf-8") as f:
                            for img in files:
                                f.write(f"file '{img.name}'\n")
                        cmd.extend(["-f", "concat", "-safe", "0", "-i", str(file_list)])
                else:
                    # Force concat demuxer for frame range selection
                    file_list = self.input_dir / "filelist.txt"
                    with open(file_list, "w", encoding="utf-8") as f:
                        for img in files:
                            f.write(f"file '{img.name}'\n")
                    cmd.extend(["-f", "concat", "-safe", "0", "-i", str(file_list)])
            else:
                # No -frames option on Windows: use image2 demuxer to read ALL jpg files
                pattern, detected_start, is_sequence = self.detect_sequence_pattern(files)
                if is_sequence:
                    start = self.start_number if self.start_number is not None else detected_start
                    pattern = str(self.input_dir / pattern)
                    cmd.extend(["-framerate", str(self.framerate), "-start_number", str(start), "-i", pattern])
                else:
                    pattern = str(self.input_dir / "*.[jJ][pP][gG]")
                    cmd.extend(["-pattern_type", "glob", "-i", pattern])
        else:
            if self.pattern_type == "glob":
                pattern = str(self.input_dir / "*.[jJ][pP][gG]")
                cmd.extend(["-pattern_type", "glob", "-i", pattern])
            else:
                pattern, detected_start, is_sequence = self.detect_sequence_pattern(files)
                if is_sequence:
                    start = self.start_number if self.start_number is not None else detected_start
                    cmd.extend(["-start_number", str(start), "-i", str(self.input_dir / pattern)])
                else:
                    pattern = str(self.input_dir / "*.jpg")
                    cmd.extend(["-pattern_type", "glob", "-i", pattern])

        # Add audio input if specified
        if self.addsound:
            if self._needs_audio_loop:
                cmd.extend(["-stream_loop", "-1", "-i", self.addsound])
            else:
                cmd.extend(["-i", self.addsound])

        cmd.extend(["-framerate", str(self.framerate)])
        # Set output framerate to match input
        cmd.extend(["-r", str(self.framerate)])

        vf_filters = []
        scale_flags = "bilinear" if self.fast_scale else "lanczos"

        # Scale is applied ONLY when a resize option was given; otherwise keep original size.
        # (Scale runs BEFORE rotate so far fewer pixels are processed.)
        if self.resize_percent:
            vf_filters.append(f"scale=iw*{self.resize_percent}:ih*{self.resize_percent}:flags={scale_flags}")
        elif self.resize_width:
            vf_filters.append(f"scale={self.resize_width}:-2:flags={scale_flags}")
        elif self.resize_height:
            vf_filters.append(f"scale=-2:{self.resize_height}:flags={scale_flags}")
        elif self.target_resolution:
            w, h = self.target_resolution
            vf_filters.append(f"scale={w}:{h}:flags={scale_flags}")

        if self.rotate_flip:
            if self.rotate_flip == "H":
                vf_filters.append("hflip")
            elif self.rotate_flip == "V":
                vf_filters.append("vflip")
            elif self.rotate_flip == "HV":
                vf_filters.append("hflip,vflip")

        if self.rotate_angle is not None:
            import math
            radians = math.radians(self.rotate_angle)
            vf_filters.append(f"rotate={radians}:ow=rotw({radians}):oh=roth({radians})")
            if self.rotate_cut:
                # Calculate crop dimensions for largest inscribed rectangle using post-resize dimensions
                if files:
                    probe = self.probe_first_image(files)
                    if probe:
                        W0 = probe.get('width', 1920)
                        H0 = probe.get('height', 1080)
                        W, H = self._compute_scaled_dims(W0, H0)
                        cw, ch = self._compute_rotate_crop(W, H, radians)
                        vf_filters.append(f"crop={cw}:{ch}")

        vf_filters.append("format=" + self.pix_fmt)

        if self.fadein is not None or self.fadeout is not None:
            total_frames = len(files)
            duration = total_frames / self.framerate if self.framerate > 0 else 0
            if self.fadein is not None:
                vf_filters.append(f"fade=t=in:st=0:d={self.fadein}")
            if self.fadeout is not None:
                start = max(0, duration - self.fadeout)
                vf_filters.append(f"fade=t=out:st={start}:d={self.fadeout}")

        if self.text_overlays:
            import tempfile
            import os
            import shutil
            self._text_files = []
            for i, overlay in enumerate(self.text_overlays):
                text = overlay["text"].replace("\\n", "\n")
                start = overlay["start"]
                end = overlay["end"]
                fontsize = int(48 * overlay["scale"] / 100)
                color = overlay["color"] if overlay.get("color") else "white"
                lines = text.split("\n")
                for j, line in enumerate(lines):
                    if not line:
                        continue
                    line = line.replace("'", r"\'").replace(":", r"\:")
                    vf_filters.append(
                        f"drawtext=text='{line}':fontcolor={color}:fontsize={fontsize}:"
                        f"x=(w-text_w)/2:y=(h-text_h)/2+(lh*{j - (len(lines) - 1) / 2}):line_spacing=0:"
                        f"enable='between(t,{start},{end})'"
                    )

        # Add fps filter for NVENC to prevent frame drops with complex filter chains
        if "nvenc" in self.codec:
            vf_filters.append(f"fps={self.framerate}:round=up")

        cmd.extend(["-vf", ",".join(vf_filters)])

        # Add audio filter if audio is specified
        if self.addsound:
            af_filters = []
            total_frames = len(files)
            duration = total_frames / self.framerate if self.framerate > 0 else 0
            if self.fadein is not None:
                af_filters.append(f"afade=t=in:st=0:d={self.fadein}")
            if self.fadeout is not None:
                start = max(0, duration - self.fadeout)
                af_filters.append(f"afade=t=out:st={start}:d={self.fadeout}")
            if af_filters:
                cmd.extend(["-af", ",".join(af_filters)])

        cmd.extend(["-c:v", self.codec])

        is_nvenc = "nvenc" in self.codec
        is_qsv = "qsv" in self.codec
        is_amf = "amf" in self.codec
        is_videotoolbox = "videotoolbox" in self.codec

        if is_nvenc or is_qsv or is_amf or is_videotoolbox:
            if self.codec in ("h264_nvenc", "hevc_nvenc"):
                cmd.extend(["-preset", self.preset])
                if self.rate_control:
                    cmd.extend(["-rc", self.rate_control])
                if self.const_qp is not None:
                    cmd.extend(["-cq", str(self.const_qp)])
                elif self.crf:
                    cmd.extend(["-cq", str(self.crf)])
                # Force constant frame rate mode for NVENC to prevent frame drops
                cmd.extend(["-fps_mode", "cfr"])
            elif self.codec in ("h264_qsv", "hevc_qsv", "av1_qsv"):
                cmd.extend(["-preset", self.preset])
                if self.crf:
                    cmd.extend(["-global_quality", str(self.crf)])
            elif self.codec in ("h264_amf", "hevc_amf"):
                cmd.extend(["-quality", self.preset])
                if self.crf:
                    cmd.extend(["-qp_i", str(self.crf), "-qp_p", str(self.crf + 1), "-qp_b", str(self.crf + 2)])
            elif "videotoolbox" in self.codec:
                if self.crf:
                    cmd.extend(["-q:v", str(self.crf)])
        else:
            cmd.extend(["-preset", self.preset])
            cmd.extend(["-crf", str(self.crf)])

        if self.tune and not (is_nvenc or is_qsv or is_amf or is_videotoolbox):
            cmd.extend(["-tune", self.tune])

        if self.profile:
            cmd.extend(["-profile:v", self.profile])

        if self.level:
            cmd.extend(["-level:v", self.level])

        if self.colorspace:
            cmd.extend(["-colorspace", self.colorspace])
        if self.color_primaries:
            cmd.extend(["-color_primaries", self.color_primaries])
        if self.color_transfer:
            cmd.extend(["-color_trc", self.color_transfer])

        cmd.extend(["-movflags", self.movflags])

        # Add audio codec options if audio is specified
        if self.addsound:
            cmd.extend(["-c:a", "aac"])
            if self.addsound_bitrate:
                cmd.extend(["-b:a", f"{self.addsound_bitrate}k"])

        # Limit output duration to video duration (not audio)
        total_frames = len(files)
        video_duration = total_frames / self.framerate if self.framerate > 0 else 0
        if video_duration > 0:
            cmd.extend(["-t", str(video_duration)])
            # Also add -shortest as safety net to stop when shortest stream ends
            cmd.extend(["-shortest"])

        # Force constant frame rate output to prevent NVENC frame drops
        cmd.extend(["-vsync", "cfr"])

        if self.verbose:
            cmd.extend(["-loglevel", "info"])
        else:
            cmd.extend(["-loglevel", "warning", "-stats"])

        cmd.append(str(self.output_file))

        return cmd

    def run(self) -> int:
        self.parse_args()

        if not check_dependencies():
            return 1

        print(f"{SCRIPT_NAME} v{SCRIPT_VER} - {SCRIPT_AUTHOR}")
        print(f"GitHub: {SCRIPT_GIT}")
        print()

        files = self.find_jpg_files()
        if not files:
            print(f"Error: No JPG files found in {self.input_dir}", file=sys.stderr)
            return 1

        print(f"Found {len(files)} JPG files")
        if self.verbose:
            for f in files[:5]:
                print(f"  {f.name}")
            if len(files) > 5:
                print(f"  ... and {len(files) - 5} more")
        print(f"Sort: {self.sort_by.capitalize()}")

        probe = self.probe_first_image(files)
        if probe:
            print(f"Source: {probe.get('width')}x{probe.get('height')}, pix_fmt: {probe.get('pix_fmt')}")
            if probe.get("color_space"):
                print(f"  Colorspace: {probe['color_space']}, Primaries: {probe.get('color_primaries')}, Transfer: {probe.get('color_transfer')}")

        if self.target_resolution:
            print(f"Target resolution: {self.target_resolution[0]}x{self.target_resolution[1]}")
        elif self.resize_percent:
            print(f"Resize: {self.resize_percent * 100:.0f}%")
        elif self.resize_width:
            print(f"Resize: width={self.resize_width} (height auto)")
        elif self.resize_height:
            print(f"Resize: height={self.resize_height} (width auto)")
        else:
            print("Resize: none (keeping original image size)")

        # Estimate final frame size and warn if it exceeds encoder limits
        if probe:
            ew = probe.get('width', 1920)
            eh = probe.get('height', 1080)
            ew, eh = self._compute_scaled_dims(ew, eh)
            if self.rotate_angle is not None:
                import math
                rad = math.radians(self.rotate_angle)
                rw = int(ew * math.cos(rad) + eh * math.sin(rad))
                rh = int(ew * math.sin(rad) + eh * math.cos(rad))
                if self.rotate_cut:
                    ew, eh = self._compute_rotate_crop(ew, eh, rad)
                else:
                    ew, eh = rw, rh
            self._check_encoder_limits(ew, eh)

        print(f"Codec: {self.codec}, Preset: {self.preset}, CRF/CQ: {self.crf}")
        if self.rotate_flip:
            print(f"Flip: {self.rotate_flip} ({'horizontal flip' if self.rotate_flip=='H' else 'vertical flip' if self.rotate_flip=='V' else '180° rotation'})")
        if self.rotate_angle is not None:
            direction = "right (clockwise)" if self.rotate_angle > 0 else "left (counter-clockwise)"
            print(f"Rotate angle: {abs(self.rotate_angle):.1f}° {direction}")
        if "nvenc" in self.codec or "qsv" in self.codec or "amf" in self.codec or "videotoolbox" in self.codec:
            print(f"  -> Hardware encoding enabled via {self.codec}")
        print(f"Framerate: {self.framerate} fps, Pixel format: {self.pix_fmt}")
        if self.frame_range:
            print(f"Frames: {self._frame_start + 1}-{self._frame_end} of {self._total_files}")
        print(f"Output: {self.output_file}")

        # Check audio duration if audio is specified (must be done before building command)
        if self.addsound:
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", self.addsound],
                    capture_output=True, text=True, check=True
                )
                audio_duration = float(result.stdout.strip())
                total_frames = len(files)
                video_duration = total_frames / self.framerate if self.framerate > 0 else 0
                if audio_duration < video_duration and not self.loopsound:
                    diff = video_duration - audio_duration
                    print(f"\nWarning: Audio file ({audio_duration:.1f}s) is shorter than video ({video_duration:.1f}s) by {diff:.1f}s")
                    if not self.dry_run:
                        response = input("Audio is shorter than video. Continue anyway? [y/N]: ").strip().lower()
                        if response != 'y' and response != 'yes':
                            print("Aborted.")
                            return 1
                        self._needs_audio_loop = True
                elif audio_duration < video_duration and self.loopsound:
                    print(f"\nInfo: Audio file ({audio_duration:.1f}s) is shorter than video ({video_duration:.1f}s). Audio will be looped (--loopsound enabled).")
                    self._needs_audio_loop = True
                else:
                    self._needs_audio_loop = False
            except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
                print(f"Warning: Could not determine audio duration: {e}")

        cmd = self.build_ffmpeg_command(files)

        if self.dry_run:
            print("\nFFmpeg command:")
            print(" ".join(cmd))
            # Estimate duration and file size
            total_frames = len(files)
            duration_sec = total_frames / self.framerate if self.framerate > 0 else 0
            h = int(duration_sec // 3600)
            m = int((duration_sec % 3600) // 60)
            s = int(duration_sec % 60)
            ms = int((duration_sec - int(duration_sec)) * 1000)
            print(f"Estimated duration: {h:02d}:{m:02d}:{s:02d}.{ms:03d}")
            # Rough file size estimate based on codec and resolution
            # Very rough estimate: ~0.1-0.5 MB per second for 1080p, more for 4K
            probe = self.probe_first_image(files)
            if probe:
                w = probe.get('width', 1920)
                h = probe.get('height', 1080)
            else:
                w, h = 1920, 1080
            # Rough estimate: bits per pixel * frames per second * duration / 8 / 1024 / 1024
            # Assuming ~0.15 bits per pixel for typical timelapse compression
            bpp = 0.15
            est_mb = (w * h * bpp * self.framerate * duration_sec) / (8 * 1024 * 1024)
            if est_mb < 1:
                print(f"Estimated size: {est_mb * 1024:.0f} kB")
            else:
                print(f"Estimated size: {est_mb:.1f} MB")
            return 0

        print("\nEncoding...")
        total_frames = len(files)
        start_time = time.time()
        last_frame = 0
        last_update = 0

        frame_pattern = re.compile(r"frame=\s*(\d+)")
        fps_pattern = re.compile(r"fps=\s*([\d.]+)")
        speed_pattern = re.compile(r"speed=\s*([\d.]+)x")

        # Non-blocking stdout reader (in a thread) so a stuck FFmpeg can be detected
        progress = {"frame": None, "speed": None}

        def read_output(proc: subprocess.Popen) -> None:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                m = frame_pattern.search(line)
                if m:
                    progress["frame"] = int(m.group(1))
                sp = speed_pattern.search(line)
                if sp:
                    try:
                        progress["speed"] = float(sp.group(1))
                    except ValueError:
                        pass

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )

            reader = threading.Thread(target=read_output, args=(process,), daemon=True)
            reader.start()

            stall_warned = False
            last_progress_time = time.time()

            while reader.is_alive():
                current_frame = progress["frame"]
                if current_frame is not None:
                    last_progress_time = time.time()
                    progress["frame"] = None
                    now = time.time()

                    # Update every 1 second or every 100 frames
                    if now - last_update >= 1.0 or current_frame - last_frame >= 100:
                        elapsed = now - start_time
                        if current_frame > 0 and elapsed > 0:
                            fps = current_frame / elapsed
                            remaining = total_frames - current_frame
                            if fps > 0:
                                eta_seconds = remaining / fps
                                eta_str = self.format_time(eta_seconds)
                                pct = (current_frame / total_frames) * 100
                                speed_str = ""
                                if progress["speed"] is not None:
                                    speed_str = f" {progress['speed']:.2f}x"
                                print(
                                    f"\r  Frame {current_frame}/{total_frames} ({pct:.1f}%) "
                                    f"~{fps:.1f} fps{speed_str}  ETA: {eta_str}   ",
                                    end="",
                                    flush=True,
                                )
                        last_frame = current_frame
                        last_update = now
                else:
                    idle = time.time() - last_progress_time
                    if idle > STALL_KILL_SEC:
                        print(f"\nError: No progress for {STALL_KILL_SEC}s. FFmpeg seems stuck - terminating.", file=sys.stderr)
                        process.kill()
                        process.wait()
                        self._cleanup_output()
                        return 1
                    elif idle > STALL_WARN_SEC and not stall_warned:
                        print(f"\nWarning: No progress for {STALL_WARN_SEC}s. Encoding may be stuck...", file=sys.stderr)
                        stall_warned = True
                time.sleep(0.25)

            process.wait()
            print()  # newline after progress
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd)

            self._verify_output()
            print(f"\nDone! Output: {self.output_file}")
            if hasattr(self, '_text_files'):
                for f in self._text_files:
                    try:
                        os.unlink(f)
                    except OSError:
                        pass
            return process.returncode

        except subprocess.CalledProcessError as e:
            if hasattr(self, '_text_files'):
                for f in self._text_files:
                    try:
                        os.unlink(f)
                    except OSError:
                        pass
            self._cleanup_output()
            print(f"\nError: FFmpeg exited with code {e.returncode}. Incomplete output removed.", file=sys.stderr)
            return e.returncode
        except FileNotFoundError:
            if hasattr(self, '_text_files'):
                for f in self._text_files:
                    try:
                        os.unlink(f)
                    except OSError:
                        pass
            print("Error: ffmpeg not found in PATH", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            if hasattr(self, '_text_files'):
                for f in self._text_files:
                    try:
                        os.unlink(f)
                    except OSError:
                        pass
            print("\nInterrupted.")
            self._cleanup_output()
            return 130

    def _verify_output(self) -> None:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=codec_name",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(self.output_file)],
                capture_output=True, text=True, timeout=30,
            )
            video_ok = result.returncode == 0 and bool(result.stdout.strip())
            if not video_ok:
                self._cleanup_output()
                raise subprocess.CalledProcessError(1, "ffprobe")
            if self.addsound:
                aresult = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "a:0",
                     "-show_entries", "stream=codec_name",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(self.output_file)],
                    capture_output=True, text=True, timeout=30,
                )
                if aresult.returncode != 0 or not aresult.stdout.strip():
                    raise subprocess.CalledProcessError(1, "ffprobe")
        except subprocess.CalledProcessError:
            print(f"Error: Output file is invalid (missing streams / no moov atom). Re-run encoding.", file=sys.stderr)
            raise

    def _cleanup_output(self) -> None:
        try:
            if self.output_file.exists():
                self.output_file.unlink()
                print(f"Removed incomplete output: {self.output_file.name}", file=sys.stderr)
        except OSError:
            pass

    def format_time(self, seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            m = int(seconds // 60)
            s = int(seconds % 60)
            return f"{m}m {s}s"
        else:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            return f"{h}h {m}m"


def main():
    builder = TimelapseBuilder()
    sys.exit(builder.run())


if __name__ == "__main__":
    main()