import asyncio
import time
from typing import Optional
from pyrogram import Client
from pyrogram.types import Message


class ProgressTracker:
    """Handles progress reporting for video processing operations"""

    def __init__(self, client: Client, message: Message, operation_name: str):
        self.client = client
        self.message = message
        self.operation_name = operation_name
        self.start_time = time.time()
        self.total_input_bytes = 0
        self.total_output_bytes = 0
        self.last_update_time = 0
        self.update_interval = 5  # Update every 5 seconds
        self.progress_message = None
        self.estimated_file_size = None
        self.processing_phase = "Initializing"

    async def start_processing(self, estimated_file_size: Optional[int] = None):
        """Initialize progress tracking"""
        self.estimated_file_size = estimated_file_size
        self.processing_phase = "Starting"

        text = f"⚙️ {self.operation_name}\n"
        text += f"📊 Status: {self.processing_phase}\n"
        text += f"⏱️ Time elapsed: 0s"

        self.progress_message = await self.message.reply_text(text)
        self.last_update_time = time.time()

    async def update_progress(self, input_bytes: Optional[int] = None, output_bytes: Optional[int] = None):
        """Update progress information"""
        if input_bytes is not None:
            self.total_input_bytes = input_bytes
        if output_bytes is not None:
            self.total_output_bytes = output_bytes

        current_time = time.time()
        time_since_last_update = current_time - self.last_update_time

        # Only update if enough time has passed
        if time_since_last_update < self.update_interval and not (input_bytes or output_bytes):
            return

        elapsed_time = int(current_time - self.start_time)

        # Build progress message
        text = f"⚙️ {self.operation_name}\n"
        text += f"📊 Status: {self.processing_phase}\n"
        text += f"⏱️ Time elapsed: {elapsed_time}s\n"

        # Add file size information
        if self.total_input_bytes > 0:
            input_mb = self.total_input_bytes / (1024 * 1024)
            text += f"📥 Input processed: {input_mb:.1f} MB\n"

        if self.total_output_bytes > 0:
            output_mb = self.total_output_bytes / (1024 * 1024)
            text += f"📤 Output generated: {output_mb:.1f} MB\n"

            # Calculate processing speed
            if elapsed_time > 0:
                speed_mbps = output_mb / elapsed_time
                text += f"🚀 Processing speed: {speed_mbps:.1f} MB/s\n"

        # Add estimated completion if we have file size
        if self.estimated_file_size and self.total_input_bytes > 0:
            progress_percent = min(100, (self.total_input_bytes / self.estimated_file_size) * 100)
            text += f"📈 Progress: {progress_percent:.1f}%\n"

            if elapsed_time > 10 and progress_percent > 0:  # Only estimate after some time
                estimated_total_time = elapsed_time / (progress_percent / 100)
                estimated_remaining = int(estimated_total_time - elapsed_time)
                text += f"⏳ Estimated time remaining: {estimated_remaining}s\n"

        # Edit the progress message
        try:
            await self.progress_message.edit_text(text)
            self.last_update_time = current_time
        except Exception:
            # Message might have been deleted or edited by user
            pass

    async def set_phase(self, phase: str):
        """Update the processing phase"""
        self.processing_phase = phase
        await self.update_progress()

    async def complete(self, success: bool = True, error_message: Optional[str] = None):
        """Mark processing as complete"""
        elapsed_time = int(time.time() - self.start_time)

        if success:
            text = f"✅ {self.operation_name} completed!\n"
            text += f"⏱️ Total time: {elapsed_time}s\n"

            if self.total_output_bytes > 0:
                output_mb = self.total_output_bytes / (1024 * 1024)
                text += f"📦 Final size: {output_mb:.1f} MB"
        else:
            text = f"❌ {self.operation_name} failed!\n"
            text += f"⏱️ Time elapsed: {elapsed_time}s\n"
            if error_message:
                text += f"🔍 Error: {error_message}"

        try:
            if self.progress_message:
                await self.progress_message.edit_text(text)
            else:
                await self.message.reply_text(text)
        except Exception:
            # Fallback if message editing fails
            await self.message.reply_text(text)


def create_progress_callback(tracker: ProgressTracker):
    """Create a callback function for progress tracking"""

    async def progress_callback(input_bytes: Optional[int] = None, output_bytes: Optional[int] = None):
        await tracker.update_progress(input_bytes, output_bytes)

    return progress_callback


# Operation-specific tracker classes
class EncodeProgressTracker(ProgressTracker):
    """Progress tracker specifically for video encoding"""

    def __init__(self, client: Client, message: Message, target_resolution: str):
        super().__init__(client, message, f"Encoding to {target_resolution}")
        self.target_resolution = target_resolution

    async def start_processing(self, estimated_file_size: Optional[int] = None):
        await super().start_processing(estimated_file_size)
        await self.set_phase("Encoding video")

    async def complete(self, success: bool = True, error_message: Optional[str] = None):
        if success:
            await self.set_phase(f"Encoding to {self.target_resolution} complete")
        await super().complete(success, error_message)


class AudioProgressTracker(ProgressTracker):
    """Progress tracker for audio operations"""

    def __init__(self, client: Client, message: Message, operation: str, format: str):
        super().__init__(client, message, f"{operation} audio ({format})")
        self.operation = operation
        self.format = format

    async def start_processing(self, estimated_file_size: Optional[int] = None):
        await super().start_processing(estimated_file_size)
        await self.set_phase(f"Processing audio ({self.format})")

    async def complete(self, success: bool = True, error_message: Optional[str] = None):
        if success:
            await self.set_phase(f"Audio {self.operation} complete")
        await super().complete(success, error_message)


class SubtitleProgressTracker(ProgressTracker):
    """Progress tracker for subtitle operations"""

    def __init__(self, client: Client, message: Message, operation: str):
        super().__init__(client, message, f"{operation} subtitles")
        self.operation = operation

    async def start_processing(self, estimated_file_size: Optional[int] = None):
        await super().start_processing(estimated_file_size)
        await self.set_phase(f"Processing subtitles")

    async def complete(self, success: bool = True, error_message: Optional[str] = None):
        if success:
            await self.set_phase(f"Subtitle {self.operation} complete")
        await super().complete(success, error_message)


async def show_operation_menu(client: Client, message: Message, title: str, options: list) -> Message:
    """
    Show a formatted menu of operation options

    Args:
        client: Pyrogram client
        message: Original message
        title: Menu title
        options: List of tuples (command, description)

    Returns:
        The sent menu message
    """
    text = f"🎬 {title}\n\n"
    text += "Available options:\n\n"

    for i, (command, description) in enumerate(options, 1):
        text += f"{i}. {command} - {description}\n"

    text += "\n💡 Send the command or file to proceed"

    return await message.reply_text(text)


async def show_error(client: Client, message: Message, operation: str, error: str) -> Message:
    """
    Show a formatted error message

    Args:
        client: Pyrogram client
        message: Original message
        operation: Operation that failed
        error: Error description

    Returns:
        The sent error message
    """
    text = f"❌ {operation} failed!\n\n"
    text += f"🔍 Error: {error}\n\n"
    text += "💡 Please try again or contact support if the issue persists"

    return await message.reply_text(text)


async def show_success(client: Client, message: Message, operation: str, details: Optional[str] = None) -> Message:
    """
    Show a formatted success message

    Args:
        client: Pyrogram client
        message: Original message
        operation: Operation that succeeded
        details: Additional details (optional)

    Returns:
        The sent success message
    """
    text = f"✅ {operation} completed successfully!"

    if details:
        text += f"\n\n{details}"

    return await message.reply_text(text)