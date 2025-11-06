from pyrogram import filters
from pyrogram.types import Message

def register(app):
    @app.on_message(filters.command("start") & filters.private)
    async def start_command(client, message: Message):
        welcome_text = """
🎬 **Welcome to Video Editor Bot!**

Edit videos directly on Telegram without downloading to your device!

🚀 **New Features:**
• Encode videos to different resolutions
• Extract and add audio tracks
• Extract and embed subtitles
• All processing done in-memory

📋 **Get Started:**
• `/help` - See all available commands
• `/encode` - Video resolution encoding
• `/audio` - Audio operations
• `/subtitle` - Subtitle operations
• `/merge` - Merge multiple videos

💡 **Tip:** All operations are performed without downloading files to your device!
        """
        await message.reply_text(welcome_text)

    @app.on_message(filters.command("help") & filters.private)
    async def help_command(client, message: Message):
        help_text = """
🎬 **Video Editor Bot Commands**

📹 **Video Processing:**
• `/encode` - Change video resolution
  `/encode720` - Convert to 720p (HD)
  `/encode480` - Convert to 480p (SD)
  `/encode360` - Convert to 360p (Mobile)

🎵 **Audio Operations:**
• `/audio` - Audio operations menu
• `/extractaudio` - Extract audio from video
• `/addaudio` - Add audio to video
• `/replaceaudio` - Replace video audio

📝 **Subtitle Operations:**
• `/subtitle` - Subtitle operations menu
• `/extractsub` - Extract subtitles from video
• `/addsub` - Add subtitles to video

🔄 **Other Features:**
• `/merge` - Merge multiple videos
• `/archive` - Create archives
• `/download_link` - Download from links
• `/url_uploader` - Upload to URLs

🆘 **Help Commands:**
• `/encodehelp` - Encoding help
• `/audiohelp` - Audio operations help
• `/subtitlehelp` - Subtitle operations help
• `/cancel` - Cancel current operation

✨ **Features:**
✅ Process videos without downloading
✅ Support for MP4, AVI, MOV, MKV
✅ Progress tracking during processing
✅ Multiple audio formats (MP3, OGG, WAV)
✅ SRT subtitle support

💡 **Tip:** Send a command to see detailed instructions!
        """
        await message.reply_text(help_text)
