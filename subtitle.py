import tempfile
import os
from pyrogram import filters
from pyrogram.types import Message
from ..utils.ffmpeg_utils import (
    extract_subtitles_stream,
    embed_subtitles_stream,
    check_video_has_subtitles,
    get_supported_subtitle_formats,
    validate_subtitle_format,
    estimate_output_size
)
from ..utils.progress_tracker import (
    SubtitleProgressTracker,
    show_operation_menu,
    show_error,
    show_success
)

# Store user states for multi-step operations
user_subtitle_states = {}

def register(app):
    """Register subtitle handlers"""

    @app.on_message(filters.command("subtitle") & filters.private)
    async def subtitle_command(client, message: Message):
        """Show subtitle operation options"""
        options = [
            ("/extractsub", "Extract subtitles from video"),
            ("/addsub", "Add subtitles to video")
        ]

        await show_operation_menu(
            client,
            message,
            "Subtitle Operations",
            options
        )

    @app.on_message(filters.command("extractsub") & filters.private)
    async def extract_subtitle_command(client, message: Message):
        """Start subtitle extraction process"""
        user_id = message.from_user.id

        # Store user's extraction preference
        user_subtitle_states[user_id] = {
            'operation': 'extract',
            'stage': 'waiting_for_video'
        }

        text = "🎯 **Subtitle Extraction Mode**\n\n"
        text += "📹 Send me the video file to extract subtitles from.\n\n"
        text += "💡 Supported video formats: MP4, AVI, MOV, MKV\n"
        text += "📝 Output format: SRT (SubRip)\n"
        text += "ℹ️ The bot will extract all subtitle tracks found in the video"

        await message.reply_text(text)

    @app.on_message(filters.command("addsub") & filters.private)
    async def add_subtitle_command(client, message: Message):
        """Start subtitle embedding process"""
        user_id = message.from_user.id

        # Store user's addition preference
        user_subtitle_states[user_id] = {
            'operation': 'add',
            'stage': 'waiting_for_subtitle'
        }

        text = "🎯 **Subtitle Embedding Mode**\n\n"
        text += "📝 First, send me the subtitle file (SRT format).\n\n"
        text += "💡 After sending the subtitle file, I'll ask for the video file.\n"
        text += "📋 The subtitle file should be in SRT format"

        await message.reply_text(text)

    @app.on_message(filters.video & filters.private)
    async def handle_video_for_subtitle(client, message: Message):
        """Handle video file for subtitle operations"""
        user_id = message.from_user.id

        # Check if user is in subtitle operation process
        if user_id not in user_subtitle_states:
            return  # Not part of subtitle operation

        state = user_subtitle_states[user_id]

        # Handle extraction operations
        if state['operation'] == 'extract' and state['stage'] == 'waiting_for_video':
            await handle_subtitle_extraction(client, message, state)
            return

        # Handle addition operations - waiting for video
        if state['operation'] == 'add' and state['stage'] == 'waiting_for_video':
            await handle_subtitle_embedding(client, message, state)
            return

    @app.on_message(filters.document & filters.private)
    async def handle_subtitle_file(client, message: Message):
        """Handle subtitle file for embedding operations"""
        user_id = message.from_user.id

        # Check if user is in subtitle operation process
        if user_id not in user_subtitle_states:
            return  # Not part of subtitle operation

        state = user_subtitle_states[user_id]

        # Only handle if we're waiting for subtitle file
        if state['operation'] == 'add' and state['stage'] == 'waiting_for_subtitle':
            await handle_subtitle_file_upload(client, message, state)

    async def handle_subtitle_extraction(client, message: Message, state):
        """Handle subtitle extraction from video"""
        user_id = message.from_user.id

        try:
            # Create progress tracker
            tracker = SubtitleProgressTracker(client, message, "Extracting")

            # Check if video has subtitles
            has_subtitles = await check_video_has_subtitles(client, message)

            if not has_subtitles:
                await show_error(
                    client,
                    message,
                    "No subtitles found",
                    "This video doesn't contain any subtitle tracks"
                )
                user_subtitle_states.pop(user_id, None)
                return

            # Estimate output size (subtitles are usually small)
            file_size = message.video.file_size
            estimated_size = estimate_output_size(file_size, 'extract_subtitles')

            # Start tracking
            await tracker.start_processing(estimated_size)

            # Process video with streaming
            await tracker.set_phase("Extracting subtitles")

            result = await extract_subtitles_stream(
                client=client,
                message=message,
                caption=f"✅ Subtitles extracted\n"
                       f"📊 Source video: {file_size / (1024*1024):.1f} MB\n"
                       f"📝 Format: SRT (SubRip)"
            )

            # Mark as complete
            await tracker.complete(success=True)

            # Clean up user state
            user_subtitle_states.pop(user_id, None)

        except Exception as e:
            # Handle errors
            await tracker.complete(success=False, error_message=str(e))
            await show_error(
                client,
                message,
                "Subtitle extraction failed",
                str(e)
            )

            # Clean up user state
            user_subtitle_states.pop(user_id, None)

    async def handle_subtitle_file_upload(client, message: Message, state):
        """Handle uploaded subtitle file"""
        user_id = message.from_user.id

        # Validate subtitle file
        if not message.document:
            await show_error(
                client,
                message,
                "Invalid file",
                "Please send a subtitle file in SRT format"
            )
            return

        file_name = message.document.file_name.lower()
        if not file_name.endswith('.srt'):
            await show_error(
                client,
                message,
                "Invalid format",
                "Subtitle file must be in SRT format"
            )
            return

        # Download subtitle file temporarily
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.srt', delete=False) as temp_file:
                subtitle_path = temp_file.name

                # Download subtitle file
                await message.download(subtitle_path)

            # Update state to wait for video
            state['stage'] = 'waiting_for_video'
            state['subtitle_path'] = subtitle_path

            text = "✅ Subtitle file received!\n\n"
            text += "📹 Now send me the video file to embed the subtitles into.\n\n"
            text += "💡 Supported video formats: MP4, AVI, MOV, MKV"

            await message.reply_text(text)

        except Exception as e:
            await show_error(
                client,
                message,
                "Failed to process subtitle file",
                str(e)
            )
            # Clean up user state
            user_subtitle_states.pop(user_id, None)

    async def handle_subtitle_embedding(client, message: Message, state):
        """Handle subtitle embedding into video"""
        user_id = message.from_user.id
        subtitle_path = state['subtitle_path']

        try:
            # Create progress tracker
            tracker = SubtitleProgressTracker(client, message, "Embedding")

            # Estimate output size
            file_size = message.video.file_size
            estimated_size = estimate_output_size(file_size, 'embed_subtitles')

            # Start tracking
            await tracker.start_processing(estimated_size)

            # Process video with streaming
            await tracker.set_phase("Embedding subtitles")

            result = await embed_subtitles_stream(
                client=client,
                message=message,
                subtitle_file_path=subtitle_path,
                caption=f"✅ Subtitles embedded into video\n"
                       f"📊 Original video: {file_size / (1024*1024):.1f} MB\n"
                       f"📝 Subtitles: Added successfully"
            )

            # Mark as complete
            await tracker.complete(success=True)

            # Clean up temporary subtitle file
            try:
                os.unlink(subtitle_path)
            except:
                pass

            # Clean up user state
            user_subtitle_states.pop(user_id, None)

        except Exception as e:
            # Handle errors
            await tracker.complete(success=False, error_message=str(e))
            await show_error(
                client,
                message,
                "Subtitle embedding failed",
                str(e)
            )

            # Clean up temporary files and state
            try:
                if 'subtitle_path' in state:
                    os.unlink(state['subtitle_path'])
            except:
                pass
            user_subtitle_states.pop(user_id, None)

    @app.on_message(filters.command("cancelsub") & filters.private)
    async def cancel_subtitle_operation(client, message: Message):
        """Cancel current subtitle operation"""
        user_id = message.from_user.id

        if user_id in user_subtitle_states:
            # Clean up temporary files
            state = user_subtitle_states[user_id]
            if 'subtitle_path' in state:
                try:
                    os.unlink(state['subtitle_path'])
                except:
                    pass

            user_subtitle_states.pop(user_id, None)
            await message.reply_text("❌ Subtitle operation cancelled")
        else:
            await message.reply_text("No active subtitle operation to cancel")

    @app.on_message(filters.command("subtitlehelp") & filters.private)
    async def subtitle_help_command(client, message: Message):
        """Show help for subtitle commands"""
        help_text = """
📝 **Subtitle Operations Help**

**Subtitle Extraction:**
• `/extractsub` - Extract subtitles from video
• Output format: SRT (SubRip)

**Subtitle Embedding:**
• `/addsub` - Add subtitles to video
• Input format: SRT (SubRip)

**How to extract subtitles:**
1. Send `/extractsub`
2. Upload your video file
3. Wait for processing to complete
4. Receive SRT subtitle file

**How to embed subtitles:**
1. Send `/addsub`
2. Upload your SRT subtitle file first
3. Upload the video file
4. Wait for processing to complete
5. Receive video with embedded subtitles

**Features:**
✅ Process videos without downloading
✅ Support for multiple subtitle tracks
✅ High-quality subtitle extraction
✅ Embedded subtitles with proper styling
✅ Progress tracking during processing

**Supported Formats:**
• Video: MP4, AVI, MOV, MKV
• Subtitles: SRT (SubRip)

**Notes:**
• Extraction only works if video contains subtitle tracks
• Embedding requires SRT subtitle files
• Embedded subtitles are compatible with most video players

**Need help?** Use `/cancelsub` to stop any operation
        """

        await message.reply_text(help_text)