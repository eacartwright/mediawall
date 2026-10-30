"""
Video memory estimates for loaded media, and the hardware video
decoding choices (Settings > Performance, the Media Memory window).

Qt doesn't report how much GPU memory each image or player uses, so
these are estimates from the decoded size: good for seeing which media
are the heavy ones, not for exact totals. Driver overhead (e.g. one
CUDA context per decoder) isn't counted.
"""

# Mipmaps add a third: each smaller level is a quarter of the one above.
MIPMAP_FACTOR = 4 / 3

# A hardware decoder keeps a pool of decoded frames (reference frames
# plus a few in flight), in NV12: 1.5 bytes per pixel. FFmpeg's NVDEC
# pool for H.264 is about this size.
HW_DECODE_SURFACES = 20
NV12_BYTES = 1.5

# The frame on screen, as an RGBA texture.
RGBA_BYTES = 4


def estimate_bytes(kind, width, height, hardware=True, mipmap=True):
    """
    Estimated GPU memory for one loaded media view. `kind` is "image",
    "animated" (GIF/WebP: only the current frame is on the GPU),
    "video", or anything else (audio, failed, nothing loaded) for 0.
    `hardware`: videos are decoded on the GPU.
    """
    if width <= 0 or height <= 0:
        return 0
    pixels = width * height
    if kind in ("image", "animated"):
        return int(pixels * RGBA_BYTES * (MIPMAP_FACTOR if mipmap else 1))
    if kind == "video":
        cost = pixels * RGBA_BYTES
        if hardware:
            cost += pixels * NV12_BYTES * HW_DECODE_SURFACES
        return int(cost)
    return 0


def format_bytes(n):
    """1536 -> "1.5 KB", 0 -> "0 B" (1024-based, as GPU tools show)."""
    n = float(n)
    for unit in ("B", "KB", "MB"):
        if abs(n) < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.2f} GB"


# ---- Hardware video decoding (Settings > Performance) ----

# Qt's FFmpeg backend reads this once, when it first decodes: a priority
# list of hardware backends, where "," (an empty list) turns them off.
HW_ENV = "QT_FFMPEG_DECODING_HW_DEVICE_TYPES"

HW_AUTO = "auto"
HW_SOFTWARE = "software"

# (value, label) per platform. "auto" leaves Qt's own choice.
_HW_CHOICES = {
    "linux": [(HW_AUTO, "Automatic"), (HW_SOFTWARE, "Off (software only)"),
              ("cuda", "CUDA only (NVIDIA)"), ("vaapi", "VA-API only")],
    "win32": [(HW_AUTO, "Automatic"), (HW_SOFTWARE, "Off (software only)"),
              ("d3d11va", "D3D11 only"), ("cuda", "CUDA only (NVIDIA)")],
}


def hw_choices(platform):
    """The hardware decoding choices offered on `platform` (sys.platform)."""
    key = "linux" if platform.startswith("linux") else platform
    return list(_HW_CHOICES.get(key, _HW_CHOICES["linux"][:2]))


def hw_env_value(mode):
    """The HW_ENV value for a setting, or None to leave Qt's default."""
    if mode == HW_SOFTWARE:
        return ","
    if not mode or mode == HW_AUTO:
        return None
    return mode


def hw_mode_from_env(value):
    """The setting an existing HW_ENV value amounts to (None if unset)."""
    if value is None:
        return None
    types = [t.strip() for t in value.split(",") if t.strip()]
    return ",".join(types) if types else HW_SOFTWARE


# ---- Hardware decoder messages in the log ----

def classify_log_line(line):
    """
    "fallback": FFmpeg couldn't set up a hardware decoder for a video and
    decodes it on the CPU instead. "oom": the GPU ran out of memory.
    None for anything else.
    """
    if "hwaccel initialisation returned error" in line:
        return "fallback"
    if "CUDA_ERROR_OUT_OF_MEMORY" in line or "out of memory" in line.lower():
        return "oom"
    return None


# ---- Measured GPU memory (nvidia-smi) ----

def parse_gpu_memory(text):
    """
    `nvidia-smi --query-gpu=memory.used,memory.total --format=csv,
    noheader,nounits` output -> (used, total) in bytes for the first
    GPU, or None. nvidia-smi reports MiB.
    """
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            try:
                return int(float(parts[0]) * 1024 ** 2), int(float(parts[1]) * 1024 ** 2)
            except ValueError:
                return None
    return None


def parse_process_memory(text, pid):
    """
    `nvidia-smi --query-compute-apps=pid,used_memory --format=csv,
    noheader,nounits` output -> bytes used by `pid` (summed over GPUs),
    or None if it isn't listed (or Windows reports "[N/A]").
    """
    total = None
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2 or parts[0] != str(pid):
            continue
        try:
            total = (total or 0) + int(float(parts[1]) * 1024 ** 2)
        except ValueError:
            pass
    return total
