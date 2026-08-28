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
import time
from pathlib import Path
from typing import Optional, Tuple, List


SCRIPT_VER = '0.0.1'
SCRIPT_DATE = '28.08.2026'
SCRIPT_AUTHOR = 'Igor Brzezek'
SCRIPT_GIT = 'https://github.com/IgorBrzezek'

SCRIPT_NAME = "Timelapse Creator"


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
        self.rotate: Optional[str] = None
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
        print("  -rotate H|V|HV        Flip: horizontal, vertical, or both")
        print("  -resize VAL           Resize: 50%%, 1920, or 1080Y")
        print("  -frames VAL           Frames: N, N-M, or -X (last X)")
        print("  -sort NAME|DATE       Sort by name (default) or date")
        print("  --fadein N            Fade in duration in seconds")
        print("  --fadeout N           Fade out duration in seconds")
        print("  --text 'T,S,E[,S]'    Text overlay: text, start sec, end sec, scale% (repeatable)")
        print("  --overwrite           Overwrite output file if exists")
        print("  --dry-run             Show FFmpeg command without executing")
        print("  -v, --verbose         Verbose output")
        print("  -h                    Show this short help")
        print("  --help                Show full help with examples")

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
        print("  -rotate:               H | V | HV")
        print("  -resize:               NN% (1-100) | NNNN (width) | NNNNY (height)")
        print("  -frames:               N (first N) | N-M (range) | -X (last X)")
        print("  -sort:                 NAME | DATE")
        print("  --fadein:              float (seconds, e.g., 2)")
        print("  --fadeout:             float (seconds, e.g., 2)")
        print("  --text:                'TEXT,START,END[,SCALE]' scale% (1-1000, default 100), \\n for new line")
        print("  --overwrite:           flag (overwrite existing output file)")
        print()
        print("Examples:")
        print("  pylapse -d ./photos -outfile timelapse.mp4 -framerate 24")
        print("  pylapse -d ./photos -outfile timelapse.mp4 -framerate 30 -resolution 1920x1080 -codec libx265 -crf 20")
        print("  pylapse -d ./photos -outfile timelapse.mp4 -framerate 60 -preset veryslow -tune film -profile high -level 4.2")
        print("  pylapse -d ./photos -outfile timelapse.mp4 -framerate 30 -codec h264_nvenc -preset p7 -crf 22")
        print("  pylapse -d ./photos -outfile timelapse.mp4 -resize 50% -frames 10-100 -sort DATE")

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
        parser.add_argument("-rotate", choices=["H", "V", "HV"], help="Flip each image: H=horizontal, V=vertical, HV=both (180°)")
        parser.add_argument("-resize", help="Resize images: percentage (e.g., 50), width (e.g., 1920), or height (e.g., 1080Y)")
        parser.add_argument("-frames", help="Frame selection: N (first N), N-M (range), -X (last X)")
        parser.add_argument("-sort", choices=["NAME", "DATE"], default="NAME", help="Sort images by name (default) or date")
        parser.add_argument("--fadein", type=float, help="Fade in duration in seconds (e.g., 2)")
        parser.add_argument("--fadeout", type=float, help="Fade out duration in seconds (e.g., 2)")
        parser.add_argument("--text", action="append", help="Text overlay: 'TEXT,START,END' (seconds). Can be used multiple times.")
        parser.add_argument("--overwrite", action="store_true", help="Overwrite output file if it exists")
        parser.add_argument("--dry-run", action="store_true", help="Show FFmpeg command without executing")
        parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

        args = parser.parse_args()

        self.input_dir = Path(args.dir).resolve()
        self.output_file = Path(args.output).resolve()
        self.framerate = args.framerate
        self.codec = args.codec
        self.crf = args.crf
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
        self.rotate = args.rotate
        self.dry_run = args.dry_run
        self.verbose = args.verbose
        self.sort_by = args.sort.lower()
        self.fadein = args.fadein
        self.fadeout = args.fadeout
        self.overwrite = args.overwrite

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
            parts = v.split(",", 3)
            if len(parts) < 3:
                raise argparse.ArgumentTypeError("Text format: 'TEXT,START,END[,SCALE]' (e.g., 'Hello,5,10,200')")
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
            if len(parts) == 4:
                try:
                    scale = int(parts[3])
                    if scale <= 0 or scale > 1000:
                        raise ValueError
                except ValueError:
                    raise argparse.ArgumentTypeError("SCALE must be a positive integer (1-1000)")
            self.text_overlays.append({"text": text, "start": start, "end": end, "scale": scale})

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

    def build_ffmpeg_command(self, files: List[Path]) -> List[str]:
        cmd = ["ffmpeg", "-y"]

        if sys.platform == "win32":
            pattern, detected_start, is_sequence = self.detect_sequence_pattern(files)
            if is_sequence:
                start = self.start_number if self.start_number is not None else detected_start
                cmd.extend(["-start_number", str(start), "-i", str(self.input_dir / pattern)])
            else:
                file_list = self.input_dir / "filelist.txt"
                with open(file_list, "w", encoding="utf-8") as f:
                    for img in files:
                        f.write(f"file '{img.name}'\n")
                cmd.extend(["-f", "concat", "-safe", "0", "-i", str(file_list)])
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

        cmd.extend(["-framerate", str(self.framerate)])

        vf_filters = []
        if self.rotate:
            if self.rotate == "H":
                vf_filters.append("hflip")
            elif self.rotate == "V":
                vf_filters.append("vflip")
            elif self.rotate == "HV":
                vf_filters.append("hflip,vflip")

        if self.resize_percent:
            vf_filters.append(f"scale=iw*{self.resize_percent}:ih*{self.resize_percent}:flags=lanczos")
        elif self.resize_width:
            vf_filters.append(f"scale={self.resize_width}:-2:flags=lanczos")
        elif self.resize_height:
            vf_filters.append(f"scale=-2:{self.resize_height}:flags=lanczos")
        elif self.target_resolution:
            w, h = self.target_resolution
            vf_filters.append(f"scale={w}:{h}:flags=lanczos")
        else:
            vf_filters.append("scale='if(gt(iw,ih),-2,min(1920,iw))':'if(gt(iw,ih),min(1080,ih),-2)':flags=lanczos")

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
                lines = text.split("\n")
                for j, line in enumerate(lines):
                    if not line:
                        continue
                    line = line.replace("'", r"\'").replace(":", r"\:")
                    vf_filters.append(
                        f"drawtext=text='{line}':fontcolor=white:fontsize={fontsize}:"
                        f"x=(w-text_w)/2:y=(h-text_h)/2+(lh*{j - (len(lines) - 1) / 2}):line_spacing=0:"
                        f"enable='between(t,{start},{end})'"
                    )

        cmd.extend(["-vf", ",".join(vf_filters)])

        cmd.extend(["-c:v", self.codec])

        is_nvenc = "nvenc" in self.codec
        is_qsv = "qsv" in self.codec
        is_amf = "amf" in self.codec
        is_videotoolbox = "videotoolbox" in self.codec

        if is_nvenc or is_qsv or is_amf or is_videotoolbox:
            if self.codec in ("h264_nvenc", "hevc_nvenc"):
                cmd.extend(["-preset", self.preset])
                if self.crf:
                    cmd.extend(["-cq", str(self.crf)])
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
            print("Target resolution: Auto (max 1920x1080, preserving aspect)")

        print(f"Codec: {self.codec}, Preset: {self.preset}, CRF/CQ: {self.crf}")
        if self.rotate:
            print(f"Rotate: {self.rotate} ({'horizontal flip' if self.rotate=='H' else 'vertical flip' if self.rotate=='V' else '180° rotation'})")
        if "nvenc" in self.codec or "qsv" in self.codec or "amf" in self.codec or "videotoolbox" in self.codec:
            print(f"  -> Hardware encoding enabled via {self.codec}")
        print(f"Framerate: {self.framerate} fps, Pixel format: {self.pix_fmt}")
        if self.frame_range:
            print(f"Frames: {self._frame_start + 1}-{self._frame_end} of {self._total_files}")
        print(f"Output: {self.output_file}")

        cmd = self.build_ffmpeg_command(files)

        if self.dry_run:
            print("\nFFmpeg command:")
            print(" ".join(cmd))
            return 0

        print("\nEncoding...")
        total_frames = len(files)
        start_time = time.time()
        last_frame = 0
        last_update = 0

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )

            frame_pattern = re.compile(r"frame=\s*(\d+)")
            fps_pattern = re.compile(r"fps=\s*([\d.]+)")
            speed_pattern = re.compile(r"speed=\s*([\d.]+)x")

            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                # Parse frame, fps, speed from ffmpeg stats line
                frame_match = frame_pattern.search(line)
                fps_match = fps_pattern.search(line)
                speed_match = speed_pattern.search(line)

                if frame_match:
                    current_frame = int(frame_match.group(1))
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
                                if speed_match:
                                    speed_str = f" {float(speed_match.group(1)):.2f}x"
                                print(
                                    f"\r  Frame {current_frame}/{total_frames} ({pct:.1f}%) "
                                    f"~{fps:.1f} fps{speed_str}  ETA: {eta_str}   ",
                                    end="",
                                    flush=True,
                                )
                        last_frame = current_frame
                        last_update = now

            process.wait()
            print()  # newline after progress
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd)

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
            print(f"\nError: FFmpeg exited with code {e.returncode}", file=sys.stderr)
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
            return 130

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