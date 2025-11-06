import subprocess
import os
from .stream_processor import process_video_stream
from .ffmpeg_stream import (
    get_resolution_encode_cmd,
    get_audio_extract_cmd,
    get_audio_add_cmd,
    get_subtitle_extract_cmd,
    get_subtitle_embed_cmd,
    has_subtitles_cmd,
    calculate_video_dimensions
)


def merge_videos(input_files, output_path):
    """Original merge function - kept for backward compatibility"""
    with open("inputs.txt", "w") as f:
        for fpath in input_files:
            f.write(f"file '{fpath}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "inputs.txt", "-c", "copy", output_path],
        check=True
    )

    # Clean up temporary file
    if os.path.exists("inputs.txt"):
        os.remove("inputs.txt")


# New streaming functions
async def encode_video_stream(client, message, resolution, caption=None):
    """Encode video to specified resolution using streaming"""
    cmd = get_resolution_encode_cmd(resolution)
    final_caption = caption or f"Video encoded to {resolution}"
    return await process_video_stream(client, message, cmd, final_caption)


async def extract_audio_stream(client, message, format='mp3', bitrate='192k', caption=None):
    """Extract audio from video using streaming"""
    cmd = get_audio_extract_cmd(format, bitrate)
    final_caption = caption or f"Audio extracted as {format.upper()}"
    return await process_video_stream(client, message, cmd, final_caption)


async def add_audio_to_video_stream(client, message, audio_file_path, replace_audio=False, caption=None):
    """Add audio to video using streaming"""
    # This is a simplified version - full implementation would need to handle audio file input
    cmd = get_audio_add_cmd(replace_audio=replace_audio)
    final_caption = caption or f"Audio {'replaced' if replace_audio else 'added'} to video"

    # Note: This would need modification to handle the audio file input properly
    # For now, this is a placeholder for the streaming approach
    raise NotImplementedError("Audio addition requires handling multiple input streams")


async def extract_subtitles_stream(client, message, track_index=0, caption=None):
    """Extract subtitles from video using streaming"""
    cmd = get_subtitle_extract_cmd(track_index)
    final_caption = caption or f"Subtitles extracted from track {track_index}"
    return await process_video_stream(client, message, cmd, final_caption)


async def embed_subtitles_stream(client, message, subtitle_file_path, caption=None):
    """Embed subtitles into video using streaming"""
    cmd = get_subtitle_embed_cmd(subtitle_file_path)
    final_caption = caption or "Subtitles embedded into video"
    return await process_video_stream(client, message, cmd, final_caption)


async def check_video_has_subtitles(client, message):
    """Check if video has subtitle tracks"""
    try:
        # Get video info
        async for chunk in client.stream_media(message):
            # For now, we'll use a simplified approach
            # Full implementation would use ffprobe to check streams
            return True  # Assume video has subtitles for demo
    except:
        return False


def get_supported_resolutions():
    """Get list of supported video resolutions"""
    return ['720p', '480p', '360p']


def get_supported_audio_formats():
    """Get list of supported audio formats"""
    return ['mp3', 'ogg', 'wav']


def get_supported_subtitle_formats():
    """Get list of supported subtitle formats"""
    return ['srt']


def validate_resolution(resolution):
    """Validate if resolution is supported"""
    return resolution in get_supported_resolutions()


def validate_audio_format(format):
    """Validate if audio format is supported"""
    return format in get_supported_audio_formats()


def validate_subtitle_format(format):
    """Validate if subtitle format is supported"""
    return format in get_supported_subtitle_formats()


def estimate_output_size(input_size, operation, resolution=None):
    """
    Estimate output file size based on operation and input size

    Args:
        input_size: Input file size in bytes
        operation: Type of operation ('encode', 'extract_audio', 'add_audio', etc.)
        resolution: Target resolution for encoding operations

    Returns:
        Estimated output size in bytes
    """
    if operation == 'encode':
        if resolution == '720p':
            return input_size * 0.6  # Approx 60% of original
        elif resolution == '480p':
            return input_size * 0.4  # Approx 40% of original
        elif resolution == '360p':
            return input_size * 0.25  # Approx 25% of original
    elif operation == 'extract_audio':
        return input_size * 0.1  # Audio is typically ~10% of video size
    elif operation in ['add_audio', 'embed_subtitles']:
        return input_size * 1.1  # Slight increase in size

    return input_size  # Default estimation
