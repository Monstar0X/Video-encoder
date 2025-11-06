import asyncio
import os
import tempfile
from typing import AsyncGenerator, Optional, Tuple
import subprocess
from pyrogram.types import Message
from pyrogram import Client


class VideoStreamProcessor:
    """Handles streaming video processing without local file downloads"""

    def __init__(self):
        self.chunk_size = 1024 * 1024  # 1MB chunks
        self.max_file_size = 2 * 1024 * 1024 * 1024  # 2GB
        self.processing_timeout = 300  # 5 minutes

    async def stream_from_telegram(self, client: Client, message: Message) -> AsyncGenerator[bytes, None]:
        """
        Stream video chunks directly from Telegram
        """
        try:
            file_size = message.video.file_size
            if file_size > self.max_file_size:
                raise ValueError(f"File too large. Maximum size: {self.max_file_size / (1024**3):.1f}GB")

            async for chunk in client.stream_media(message):
                yield chunk

        except Exception as e:
            raise RuntimeError(f"Failed to stream video from Telegram: {str(e)}")

    async def process_with_ffmpeg(
        self,
        input_stream: AsyncGenerator[bytes, None],
        ffmpeg_cmd: list,
        progress_callback: Optional[callable] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Process video stream through FFmpeg and yield output chunks
        """
        process = None
        try:
            # Start FFmpeg process
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Feed input stream to FFmpeg
            async def feed_input():
                total_bytes = 0
                async for chunk in input_stream:
                    if process.stdin:
                        process.stdin.write(chunk)
                        total_bytes += len(chunk)
                        if progress_callback:
                            await progress_callback(total_bytes, None)  # Progress for input
                if process.stdin:
                    process.stdin.close()

            # Start feeding input in background
            feed_task = asyncio.create_task(feed_input())

            # Read output from FFmpeg
            output_bytes = 0
            try:
                while True:
                    chunk = await process.stdout.read(self.chunk_size)
                    if not chunk:
                        break
                    output_bytes += len(chunk)
                    yield chunk
                    if progress_callback:
                        await progress_callback(None, output_bytes)  # Progress for output

            except Exception as e:
                raise RuntimeError(f"Failed to read FFmpeg output: {str(e)}")

            # Wait for input feeding to complete
            await feed_task

            # Wait for process to complete
            await asyncio.wait_for(process.wait(), timeout=self.processing_timeout)

            # Check for FFmpeg errors
            stderr_output = await process.stderr.read()
            if process.returncode != 0:
                error_msg = stderr_output.decode() if stderr_output else "Unknown FFmpeg error"
                raise RuntimeError(f"FFmpeg processing failed: {error_msg}")

        except asyncio.TimeoutError:
            if process:
                process.kill()
            raise RuntimeError(f"Processing timed out after {self.processing_timeout} seconds")
        except Exception as e:
            if process:
                process.kill()
            raise RuntimeError(f"Video processing failed: {str(e)}")

    async def send_processed_video(
        self,
        client: Client,
        message: Message,
        output_stream: AsyncGenerator[bytes, None],
        caption: str = "Processed video"
    ) -> Message:
        """
        Send the processed video back to user
        """
        try:
            # Create temporary file for output (Pyrogram needs file path for video upload)
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                temp_path = temp_file.name

                # Write all chunks to temp file
                async for chunk in output_stream:
                    temp_file.write(chunk)

            # Send video file
            result = await message.reply_video(
                video=temp_path,
                caption=caption
            )

            # Clean up temporary file
            os.unlink(temp_path)

            return result

        except Exception as e:
            # Clean up on error
            if 'temp_path' in locals():
                try:
                    os.unlink(temp_path)
                except:
                    pass
            raise RuntimeError(f"Failed to send processed video: {str(e)}")


# Global processor instance
video_processor = VideoStreamProcessor()


async def process_video_stream(
    client: Client,
    message: Message,
    ffmpeg_cmd: list,
    caption: str = "Processed video",
    progress_callback: Optional[callable] = None
) -> Message:
    """
    Complete pipeline: stream from telegram -> process with ffmpeg -> send back
    """
    # Create input stream
    input_stream = video_processor.stream_from_telegram(client, message)

    # Process with FFmpeg
    output_stream = video_processor.process_with_ffmpeg(input_stream, ffmpeg_cmd, progress_callback)

    # Send result back to user
    return await video_processor.send_processed_video(client, message, output_stream, caption)