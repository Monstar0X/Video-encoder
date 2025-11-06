from pyrogram import filters
from pyrogram.types import Message
from ..utils.ffmpeg_utils import (
    encode_video_stream,
    get_supported_resolutions,
    validate_resolution,
    estimate_output_size
)
from ..utils.progress_tracker import (
    EncodeProgressTracker,
    show_operation_menu,
    show_error,
    show_success
)

# Store user states for multi-step operations
user_encoding_states = {}

def register(app):
    """Register encode handlers"""

    @app.on_message(filters.command("encode") & filters.private)
    async def encode_command(client, message: Message):
        """Show encoding options"""
        user_id = message.from_user.id

        options = [
            ("/encode720", "Encode to 720p (HD)"),
            ("/encode480", "Encode to 480p (SD)"),
            ("/encode360", "Encode to 360p (Mobile)")
        ]

        await show_operation_menu(
            client,
            message,
            "Video Resolution Encoding",
            options
        )

    @app.on_message(filters.command(["encode720", "encode480", "encode360"]) & filters.private)
    async def encode_resolution_command(client, message: Message):
        """Handle specific resolution encoding commands"""
        user_id = message.from_user.id
        command = message.command[0]

        # Extract resolution from command
        resolution = command.replace("encode", "")
        if not validate_resolution(resolution):
            await show_error(
                client,
                message,
                "Invalid resolution",
                f"Resolution {resolution} is not supported"
            )
            return

        # Store user's encoding preference
        user_encoding_states[user_id] = {
            'resolution': resolution,
            'stage': 'waiting_for_video'
        }

        resolution_names = {
            '720p': '720p (HD)',
            '480p': '480p (SD)',
            '360p': '360p (Mobile)'
        }

        text = f"🎯 Selected resolution: {resolution_names[resolution]}\n\n"
        text += "📹 Now send me the video file you want to encode.\n\n"
        text += "💡 Supported formats: MP4, AVI, MOV, MKV"

        await message.reply_text(text)

    @app.on_message(filters.video & filters.private)
    async def handle_video_encoding(client, message: Message):
        """Handle video file for encoding"""
        user_id = message.from_user.id

        # Check if user is in encoding process
        if user_id not in user_encoding_states:
            return  # Not part of encoding operation

        state = user_encoding_states[user_id]
        if state['stage'] != 'waiting_for_video':
            return

        resolution = state['resolution']

        # Validate video file
        if not message.video:
            await show_error(
                client,
                message,
                "Invalid file",
                "Please send a video file"
            )
            return

        # Check file size
        file_size = message.video.file_size
        max_size = 2 * 1024 * 1024 * 1024  # 2GB

        if file_size > max_size:
            await show_error(
                client,
                message,
                "File too large",
                f"Maximum file size is {max_size / (1024**3):.1f}GB"
            )
            return

        # Start processing
        try:
            # Create progress tracker
            tracker = EncodeProgressTracker(client, message, resolution)

            # Estimate output size
            estimated_size = estimate_output_size(file_size, 'encode', resolution)

            # Start tracking
            await tracker.start_processing(estimated_size)

            # Create progress callback
            progress_callback = tracker.update_progress

            # Process video with streaming
            await tracker.set_phase("Encoding video")

            result = await encode_video_stream(
                client=client,
                message=message,
                resolution=resolution,
                caption=f"✅ Video encoded to {resolution}\n"
                       f"📊 Original: {file_size / (1024*1024):.1f} MB\n"
                       f"📹 Resolution: {resolution}"
            )

            # Mark as complete
            await tracker.complete(success=True)

            # Clean up user state
            user_encoding_states.pop(user_id, None)

        except Exception as e:
            # Handle errors
            await tracker.complete(success=False, error_message=str(e))
            await show_error(
                client,
                message,
                "Encoding failed",
                str(e)
            )

            # Clean up user state
            user_encoding_states.pop(user_id, None)

    @app.on_message(filters.command("cancel") & filters.private)
    async def cancel_encoding(client, message: Message):
        """Cancel current encoding operation"""
        user_id = message.from_user.id

        if user_id in user_encoding_states:
            user_encoding_states.pop(user_id, None)
            await message.reply_text("❌ Encoding operation cancelled")
        else:
            await message.reply_text("No active encoding operation to cancel")

    @app.on_message(filters.command("encodehelp") & filters.private)
    async def encode_help_command(client, message: Message):
        """Show help for encoding commands"""
        help_text = """
🎬 **Video Encoding Help**

**Resolution Options:**
• `/encode720` - Convert to 720p (HD Quality)
• `/encode480` - Convert to 480p (SD Quality)
• `/encode360` - Convert to 360p (Mobile Friendly)

**How to use:**
1. Send the resolution command (e.g., `/encode720`)
2. Upload your video file
3. Wait for processing to complete

**Features:**
✅ Process videos without downloading to device
✅ Maintain original audio quality
✅ Preserve aspect ratio
✅ Support for MP4, AVI, MOV, MKV formats
✅ Progress tracking during processing

**Limitations:**
• Maximum file size: 2GB
• Processing time varies with file size
• Video quality will be adjusted to match resolution

**Need help?** Use `/cancel` to stop any operation
        """

        await message.reply_text(help_text)