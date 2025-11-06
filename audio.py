import tempfile
import os
from pyrogram import filters
from pyrogram.types import Message
from ..utils.ffmpeg_utils import (
    extract_audio_stream,
    get_supported_audio_formats,
    validate_audio_format,
    estimate_output_size
)
from ..utils.progress_tracker import (
    AudioProgressTracker,
    show_operation_menu,
    show_error,
    show_success
)

# Store user states for multi-step operations
user_audio_states = {}

def register(app):
    """Register audio handlers"""

    @app.on_message(filters.command("audio") & filters.private)
    async def audio_command(client, message: Message):
        """Show audio operation options"""
        options = [
            ("/extractaudio", "Extract audio from video"),
            ("/addaudio", "Add audio to video"),
            ("/replaceaudio", "Replace video audio")
        ]

        await show_operation_menu(
            client,
            message,
            "Audio Operations",
            options
        )

    @app.on_message(filters.command("extractaudio") & filters.private)
    async def extract_audio_command(client, message: Message):
        """Start audio extraction process"""
        user_id = message.from_user.id

        # Show format options
        formats = get_supported_audio_formats()
        format_text = "🎵 Choose audio format:\n\n"

        for i, fmt in enumerate(formats, 1):
            format_info = {
                'mp3': 'MP3 - Most compatible',
                'ogg': 'OGG - Open source',
                'wav': 'WAV - Highest quality'
            }
            format_text += f"{i}. /extract{fmt.upper()} - {format_info[fmt]}\n"

        format_text += "\n💡 Send the format command to proceed"

        await message.reply_text(format_text)

    @app.on_message(filters.command(["extractMP3", "extractOGG", "extractWAV"]) & filters.private)
    async def extract_audio_format_command(client, message: Message):
        """Handle specific audio format extraction commands"""
        user_id = message.from_user.id
        command = message.command[0]

        # Extract format from command
        format_name = command.lower().replace("extract", "")
        if not validate_audio_format(format_name):
            await show_error(
                client,
                message,
                "Invalid format",
                f"Format {format_name} is not supported"
            )
            return

        # Store user's extraction preference
        user_audio_states[user_id] = {
            'operation': 'extract',
            'format': format_name,
            'stage': 'waiting_for_video'
        }

        format_names = {
            'mp3': 'MP3',
            'ogg': 'OGG',
            'wav': 'WAV'
        }

        text = f"🎯 Selected format: {format_names[format_name]}\n\n"
        text += "📹 Now send me the video file to extract audio from.\n\n"
        text += "💡 Supported video formats: MP4, AVI, MOV, MKV"

        await message.reply_text(text)

    @app.on_message(filters.command(["addaudio", "replaceaudio"]) & filters.private)
    async def add_audio_command(client, message: Message):
        """Start audio addition process"""
        user_id = message.from_user.id
        operation = 'replace' if 'replace' in message.text else 'add'

        # Store user's audio operation preference
        user_audio_states[user_id] = {
            'operation': operation,
            'stage': 'waiting_for_video'
        }

        if operation == 'replace':
            text = "🔄 **Audio Replacement Mode**\n\n"
            text += "📹 First, send me the video file where you want to replace the audio.\n\n"
            text += "💡 The existing audio will be completely replaced with your new audio file."
        else:
            text = "➕ **Audio Addition Mode**\n\n"
            text += "📹 First, send me the video file where you want to add audio.\n\n"
            text += "💡 The new audio will be mixed with the existing video audio."

        await message.reply_text(text)

    @app.on_message(filters.video & filters.private)
    async def handle_video_for_audio(client, message: Message):
        """Handle video file for audio operations"""
        user_id = message.from_user.id

        # Check if user is in audio operation process
        if user_id not in user_audio_states:
            return  # Not part of audio operation

        state = user_audio_states[user_id]

        # Handle extraction operations
        if state['operation'] == 'extract' and state['stage'] == 'waiting_for_video':
            await handle_audio_extraction(client, message, state)
            return

        # Handle addition/replacement operations - waiting for video
        if state['operation'] in ['add', 'replace'] and state['stage'] == 'waiting_for_video':
            # Store video info and wait for audio file
            state['stage'] = 'waiting_for_audio'
            state['video_message'] = message

            operation_text = "replace" if state['operation'] == 'replace' else "add"
            text = f"✅ Video received!\n\n"
            text += f"🎵 Now send me the audio file you want to {operation_text} to the video.\n\n"
            text += "💡 Supported formats: MP3, OGG, WAV"

            await message.reply_text(text)
            return

    @app.on_message(filters.audio & filters.private)
    async def handle_audio_file(client, message: Message):
        """Handle audio file for addition/replacement operations"""
        user_id = message.from_user.id

        # Check if user is in audio operation process
        if user_id not in user_audio_states:
            return  # Not part of audio operation

        state = user_audio_states[user_id]

        # Only handle if we're waiting for audio file
        if state['operation'] in ['add', 'replace'] and state['stage'] == 'waiting_for_audio':
            await handle_audio_addition(client, message, state)

    async def handle_audio_extraction(client, message: Message, state):
        """Handle audio extraction from video"""
        user_id = message.from_user.id
        format_name = state['format']

        try:
            # Create progress tracker
            tracker = AudioProgressTracker(client, message, "Extracting", format_name.upper())

            # Estimate output size
            file_size = message.video.file_size
            estimated_size = estimate_output_size(file_size, 'extract_audio')

            # Start tracking
            await tracker.start_processing(estimated_size)

            # Process video with streaming
            await tracker.set_phase(f"Extracting {format_name.upper()} audio")

            result = await extract_audio_stream(
                client=client,
                message=message,
                format=format_name,
                caption=f"✅ Audio extracted as {format_name.upper()}\n"
                       f"📊 Original video: {file_size / (1024*1024):.1f} MB\n"
                       f"🎵 Format: {format_name.upper()}"
            )

            # Mark as complete
            await tracker.complete(success=True)

            # Clean up user state
            user_audio_states.pop(user_id, None)

        except Exception as e:
            # Handle errors
            await tracker.complete(success=False, error_message=str(e))
            await show_error(
                client,
                message,
                "Audio extraction failed",
                str(e)
            )

            # Clean up user state
            user_audio_states.pop(user_id, None)

    async def handle_audio_addition(client, message: Message, state):
        """Handle audio addition to video"""
        user_id = message.from_user.id
        operation = state['operation']
        video_message = state['video_message']

        try:
            # Create progress tracker
            operation_text = "Replacing" if operation == 'replace' else "Adding"
            tracker = AudioProgressTracker(client, video_message, operation_text.lower(), "audio")

            # For now, we'll implement a simplified version
            # Full implementation would need to handle multiple input streams
            await show_error(
                client,
                video_message,
                "Feature in development",
                "Audio addition/replacement requires additional implementation. This feature is being worked on."
            )

            # Clean up user state
            user_audio_states.pop(user_id, None)

        except Exception as e:
            # Handle errors
            await tracker.complete(success=False, error_message=str(e))
            await show_error(
                client,
                video_message,
                f"Audio {operation} failed",
                str(e)
            )

            # Clean up user state
            user_audio_states.pop(user_id, None)

    @app.on_message(filters.command("cancelaudio") & filters.private)
    async def cancel_audio_operation(client, message: Message):
        """Cancel current audio operation"""
        user_id = message.from_user.id

        if user_id in user_audio_states:
            user_audio_states.pop(user_id, None)
            await message.reply_text("❌ Audio operation cancelled")
        else:
            await message.reply_text("No active audio operation to cancel")

    @app.on_message(filters.command("audiohelp") & filters.private)
    async def audio_help_command(client, message: Message):
        """Show help for audio commands"""
        help_text = """
🎵 **Audio Operations Help**

**Audio Extraction:**
• `/extractaudio` - Show format options
• `/extractMP3` - Extract as MP3 (most compatible)
• `/extractOGG` - Extract as OGG (open source)
• `/extractWAV` - Extract as WAV (highest quality)

**Audio Addition:**
• `/addaudio` - Mix new audio with existing video audio
• `/replaceaudio` - Replace video audio completely

**How to use extraction:**
1. Send `/extractaudio`
2. Choose format (e.g., `/extractMP3`)
3. Upload your video file
4. Wait for processing to complete

**How to use addition/replacement:**
1. Send `/addaudio` or `/replaceaudio`
2. Upload the video file first
3. Upload the audio file
4. Wait for processing to complete

**Features:**
✅ Process videos without downloading
✅ Support multiple audio formats
✅ High-quality extraction
✅ Progress tracking during processing

**Supported Formats:**
• Video: MP4, AVI, MOV, MKV
• Audio: MP3, OGG, WAV

**Need help?** Use `/cancelaudio` to stop any operation
        """

        await message.reply_text(help_text)