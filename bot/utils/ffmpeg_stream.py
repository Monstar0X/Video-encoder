"""
FFmpeg command builders for streaming video processing operations
"""

from typing import List, Optional, Tuple


def get_resolution_encode_cmd(resolution: str) -> List[str]:
    """
    Build FFmpeg command for resolution encoding

    Args:
        resolution: Target resolution ('720p', '480p', '360p')

    Returns:
        FFmpeg command list
    """
    # Define resolution settings
    resolution_settings = {
        '720p': {'width': 1280, 'height': 720, 'bitrate': '2000k'},
        '480p': {'width': 854, 'height': 480, 'bitrate': '1000k'},
        '360p': {'width': 640, 'height': 360, 'bitrate': '500k'}
    }

    if resolution not in resolution_settings:
        raise ValueError(f"Unsupported resolution: {resolution}. Use '720p', '480p', or '360p'")

    settings = resolution_settings[resolution]

    cmd = [
        'ffmpeg', '-i', 'pipe:0',  # Read from stdin
        '-vf', f'scale={settings["width"]}:{settings["height"]}',  # Scale to target resolution
        '-c:v', 'libx264',  # Video codec
        '-preset', 'medium',  # Encoding speed vs quality balance
        '-crf', '23',  # Quality (lower = better quality)
        '-maxrate', settings['bitrate'],  # Maximum bitrate
        '-bufsize', f'{int(settings["bitrate"][:-1]) * 2}k',  # Buffer size
        '-pix_fmt', 'yuv420p',  # Pixel format for compatibility
        '-c:a', 'aac',  # Audio codec (preserve audio)
        '-b:a', '128k',  # Audio bitrate
        '-ar', '44100',  # Audio sample rate
        '-f', 'mp4',  # Output format
        '-movflags', 'faststart',  # Optimize for streaming
        'pipe:1'  # Write to stdout
    ]

    return cmd


def get_audio_extract_cmd(format: str = 'mp3', bitrate: str = '192k') -> List[str]:
    """
    Build FFmpeg command for audio extraction

    Args:
        format: Output audio format ('mp3', 'ogg', 'wav')
        bitrate: Audio bitrate

    Returns:
        FFmpeg command list
    """
    # Format-specific settings
    format_settings = {
        'mp3': {'codec': 'libmp3lame', 'extension': 'mp3'},
        'ogg': {'codec': 'libvorbis', 'extension': 'ogg'},
        'wav': {'codec': 'pcm_s16le', 'extension': 'wav'}
    }

    if format not in format_settings:
        raise ValueError(f"Unsupported audio format: {format}. Use 'mp3', 'ogg', or 'wav'")

    settings = format_settings[format]

    cmd = [
        'ffmpeg', '-i', 'pipe:0',  # Read from stdin
        '-vn',  # No video output
        '-c:a', settings['codec'],  # Audio codec
        '-b:a', bitrate,  # Audio bitrate
        '-ar', '44100',  # Sample rate
        '-ac', '2',  # Stereo channels
        '-f', format,  # Output format
        'pipe:1'  # Write to stdout
    ]

    return cmd


def get_audio_add_cmd(video_stream: bool = True, replace_audio: bool = False, mix_volume: float = 1.0) -> List[str]:
    """
    Build FFmpeg command for adding audio to video

    Args:
        video_stream: Whether input includes video stream
        replace_audio: Whether to replace existing audio or mix
        mix_volume: Volume level for mixed audio (0.0 to 1.0)

    Returns:
        FFmpeg command list for processing main video first
    """
    # This is a base command - actual implementation will handle audio file separately
    cmd = [
        'ffmpeg', '-i', 'pipe:0',  # Main video input
        '-c:v', 'copy',  # Copy video stream without re-encoding
        '-c:a', 'aac',  # Audio codec
        '-b:a', '128k',  # Audio bitrate
        '-ar', '44100',  # Sample rate
    ]

    if replace_audio:
        cmd.extend(['-map', '0:v:0', '-map', '1:a:0'])  # Use video from first input, audio from second
    else:
        # Mix audio streams
        cmd.extend([
            '-filter_complex',
            f'[0:a][1:a]amix=inputs=2:weights=1 {mix_volume}:duration=longest'
        ])

    cmd.extend([
        '-f', 'mp4',
        'pipe:1'
    ])

    return cmd


def get_subtitle_extract_cmd(track_index: int = 0) -> List[str]:
    """
    Build FFmpeg command for subtitle extraction

    Args:
        track_index: Which subtitle track to extract

    Returns:
        FFmpeg command list
    """
    cmd = [
        'ffmpeg', '-i', 'pipe:0',  # Read from stdin
        '-map', f'0:s:{track_index}',  # Extract subtitle track
        '-c:s', 'srt',  # Subtitle format
        '-f', 'srt',  # Output format
        'pipe:1'  # Write to stdout
    ]

    return cmd


def get_subtitle_embed_cmd(
    subtitle_file_path: str,
    subtitle_style: Optional[str] = None
) -> List[str]:
    """
    Build FFmpeg command for embedding subtitles into video

    Args:
        subtitle_file_path: Path to subtitle file
        subtitle_style: Custom subtitle styling (optional)

    Returns:
        FFmpeg command list
    """
    # Default subtitle style
    default_style = (
        "FontSize=20,"
        "PrimaryColour=&Hffffff,"
        "SecondaryColour=&Hffffff,"
        "OutlineColour=&H0,"
        "BackColour=&H80000000,"
        "Bold=0,"
        "Italic=0,"
        "Underline=0,"
        "StrikeOut=0,"
        "Spacing=0,"
        "Angle=0,"
        "BorderStyle=1,"
        "Outline=1,"
        "Shadow=0,"
        "Alignment=2,"
        "MarginL=0,"
        "MarginR=0,"
        "MarginV=0"
    )

    style = subtitle_style or default_style

    cmd = [
        'ffmpeg', '-i', 'pipe:0',  # Video input
        '-i', subtitle_file_path,  # Subtitle input
        '-c:v', 'copy',  # Copy video without re-encoding
        '-c:a', 'copy',  # Copy audio without re-encoding
        '-c:s', 'mov_text',  # Subtitle codec for MP4
        '-disposition:s:0', 'default',  # Make subtitles default
        '-metadata:s:s:0', 'language=eng',  # Set subtitle language
        '-f', 'mp4',  # Output format
        'pipe:1'  # Write to stdout
    ]

    return cmd


def get_video_info_cmd() -> List[str]:
    """
    Build FFmpeg command to get video information

    Returns:
        FFmpeg command list
    """
    return [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        'pipe:0'
    ]


def has_subtitles_cmd() -> List[str]:
    """
    Build FFmpeg command to check if video has subtitles

    Returns:
        FFmpeg command list
    """
    return [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 's',
        '-show_entries', 'stream=codec_name',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        'pipe:0'
    ]


def calculate_video_dimensions(original_width: int, original_height: int, target_resolution: str) -> Tuple[int, int]:
    """
    Calculate output dimensions maintaining aspect ratio

    Args:
        original_width: Original video width
        original_height: Original video height
        target_resolution: Target resolution ('720p', '480p', '360p')

    Returns:
        Tuple of (width, height)
    """
    target_heights = {
        '720p': 720,
        '480p': 480,
        '360p': 360
    }

    if target_resolution not in target_heights:
        raise ValueError(f"Unsupported resolution: {target_resolution}")

    target_height = target_heights[target_resolution]
    aspect_ratio = original_width / original_height
    target_width = int(target_height * aspect_ratio)

    # Ensure even dimensions for better compatibility
    if target_width % 2 != 0:
        target_width += 1
    if target_height % 2 != 0:
        target_height += 1

    return (target_width, target_height)
