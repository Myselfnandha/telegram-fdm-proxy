import os
import re
import asyncio
import socket
import logging
from aiohttp import web
from telethon import TelegramClient, events, Button
from dotenv import load_dotenv

# Global state for batch mode
batch_mode = False
batch_queue = []

# Configuration
ALLOWED_EXTENSIONS = None  # None means allow all

def ensure_env():
    """Checks for .env variables and prompts for setup if missing."""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    
    # Reload to ensure we have the latest
    load_dotenv(env_path)
    
    api_id = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    bot_token = os.getenv("BOT_TOKEN", "").strip()

    if not all([api_id, api_hash, bot_token]):
        print("\n" + "="*50)
        print("🛠️  TELEGRAM FDM PROXY SETUP")
        print("="*50)
        print("It looks like your .env file is missing or incomplete.")
        print("You can get these from https://my.telegram.org and @BotFather.\n")
        
        try:
            if not api_id:
                api_id = input("1. Enter your API_ID: ").strip()
            if not api_hash:
                api_hash = input("2. Enter your API_HASH: ").strip()
            if not bot_token:
                bot_token = input("3. Enter your BOT_TOKEN: ").strip()
            
            with open(env_path, 'w') as f:
                f.write(f"API_ID={api_id}\n")
                f.write(f"API_HASH={api_hash}\n")
                f.write(f"BOT_TOKEN={bot_token}\n")
            
            print(f"\n✅ Configuration saved to: {env_path}")
            load_dotenv(env_path) # Reload once more
            return api_id, api_hash, bot_token
            
        except KeyboardInterrupt:
            print("\n❌ Setup cancelled.")
            exit(1)
            
    return api_id, api_hash, bot_token

# Initialization
API_ID, API_HASH, BOT_TOKEN = ensure_env()
API_ID = int(API_ID)

# Initialize Telethon Client as a Bot
client = TelegramClient('fdm_proxy_bot_session', API_ID, API_HASH)

config = {'port': 8080}

# Set up logging
logging.basicConfig(
    filename='tg_fdm_proxy.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_free_port(start_port=8080, max_attempts=100):
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free ports found between {start_port} and {start_port + max_attempts - 1}")

async def handle_download(request):
    chat_id = int(request.match_info['chat_id'])
    message_id = int(request.match_info['message_id'])

    try:
            # Retrieve the specific message containing the media
            message = await client.get_messages(chat_id, ids=message_id)
            if not message or not message.media or not hasattr(message, 'file'):
                return web.Response(status=404, text="Message not found or does not contain media.")

            file_size = message.file.size
            # Sanitize filename (FDM expects normal filenames)
            file_name = message.file.name if message.file.name else f"tg_media_{message_id}.bin"
            file_name = "".join([c for c in file_name if (c.isalnum() or c in " .-_")]).strip()

            range_header = request.headers.get('Range', '')
            status = 200
            start = 0
            end = file_size - 1

            # Parse HTTP Range Header for multi-threaded downloading in FDM
            if range_header:
                match = re.search(r'bytes=(\d+)-(\d*)', range_header)
                if match:
                    start = int(match.group(1))
                    if match.group(2):
                        end = int(match.group(2))
                status = 206

            length = end - start + 1

            headers = {
                'Content-Type': 'application/octet-stream',
                'Content-Disposition': f'attachment; filename="{file_name}"',
                'Accept-Ranges': 'bytes',
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Content-Length': str(length)
            }

            response = web.StreamResponse(status=status, headers=headers)
            await response.prepare(request)

            # Stream chunks from Telegram server to FDM directly
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    async for chunk in client.iter_download(
                        message.media,
                        offset=start,
                        limit=length,
                        chunk_size=1024 * 1024  # 1 MB blocks
                    ):
                        await response.write(chunk)
                    break  # Success
                except Exception as chunk_e:
                    if attempt == max_retries - 1:
                        raise chunk_e
                    print(f"⚠️  Download attempt {attempt + 1} failed: {chunk_e}, retrying...")
                    await asyncio.sleep(1)  # Wait before retry

            return response

    except ConnectionResetError:
        # FDM closed a specific connection thread, standard behavior in multi-threading
        return response
    except Exception as e:
        print(f"❌ Error during download for chat {chat_id}, message {message_id}: {e}")
        logger.error(f"Download error for chat {chat_id}, message {message_id}: {e}")
        return web.Response(status=500, text=f"Download failed: {str(e)}")

async def dashboard(request):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Telegram FDM Proxy Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .stat {{ background: #f8f9fa; padding: 15px; margin: 10px 0; border-left: 4px solid #007bff; }}
            .header {{ text-align: center; color: #333; }}
            .status {{ color: #28a745; font-weight: bold; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; margin: 5px; }}
            .btn:hover {{ background: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="header">📥 Telegram FDM Proxy Dashboard</h1>
            
            <div class="stat">
                <h2>🚀 Status</h2>
                <p class="status">✅ Bot Connected & Running</p>
                <p>🌐 Server Port: <strong>{config['port']}</strong></p>
                <p>🔗 Dashboard URL: <code>http://127.0.0.1:{config['port']}</code></p>
            </div>
            
            <div class="stat">
                <h2>📋 How to Use</h2>
                <ol>
                    <li>Forward any media file (photo, video, document) to your Telegram bot</li>
                    <li>Copy the generated download link</li>
                    <li>Paste the link into Free Download Manager</li>
                    <li>Enjoy fast, multi-threaded downloads!</li>
                </ol>
            </div>
            
            <div class="stat">
                <h2>⚙️ Features</h2>
                <ul>
                    <li>✅ Automatic port selection</li>
                    <li>✅ Retry logic for failed downloads</li>
                    <li>✅ Enhanced error logging</li>
                    <li>✅ Portable executable</li>
                    <li>🔄 Batch download mode (coming soon)</li>
                    <li>🔄 Web dashboard (you're here!)</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin-top: 20px;">
                <a href="https://github.com/Myselfnandha/telegram-fdm-proxy" class="btn" target="_blank">View on GitHub</a>
                <a href="https://github.com/Myselfnandha/telegram-fdm-proxy/blob/main/README.md" class="btn" target="_blank">Documentation</a>
            </div>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

@client.on(events.CallbackQuery(pattern=r'info_(\d+)'))
async def info_callback(event):
    message_id = int(event.pattern_match.group(1))
    
    try:
        message = await client.get_messages(event.chat_id, ids=message_id)
        if message and message.file:
            info = "📄 **File Information**\n\n"
            info += f"**Name:** {message.file.name or 'Unknown'}\n"
            info += f"**Size:** {message.file.size / (1024*1024):.2f} MB\n"
            info += f"**MIME Type:** {message.file.mime_type or 'Unknown'}\n"
            if hasattr(message.file, 'duration') and message.file.duration:
                info += f"**Duration:** {message.file.duration} seconds\n"
            if hasattr(message.file, 'width') and message.file.width:
                info += f"**Dimensions:** {message.file.width}x{message.file.height}\n"
            
            await event.answer()
            await event.edit(info)
        else:
            await event.answer("File information not available")
    except Exception as e:
        await event.answer("Error retrieving file info")
        logger.error(f"Error in info callback: {e}")

@client.on(events.NewMessage(pattern='/start_batch'))
async def start_batch(event):
    global batch_mode, batch_queue
    batch_mode = True
    batch_queue = []
    await event.reply("📦 **Batch Mode Started!**\n\nSend me multiple files and they'll be queued. Use `/end_batch` when done to get all download links at once.")
    logger.info(f"Batch mode started by user {event.sender_id}")

@client.on(events.NewMessage(pattern='/end_batch'))
async def end_batch(event):
    global batch_mode, batch_queue
    if not batch_mode:
        await event.reply("❌ Batch mode is not active. Use `/start_batch` first.")
        return
    
    batch_mode = False
    if not batch_queue:
        await event.reply("📦 Batch completed - no files were queued.")
        return
    
    response = "**📦 Batch Download Links:**\n\n"
    total_size = 0
    for i, (file_name, file_size_mb, link) in enumerate(batch_queue, 1):
        response += f"{i}. **{file_name}** ({file_size_mb:.2f} MB)\n`{link}`\n\n"
        total_size += file_size_mb
    
    response += f"**Total: {len(batch_queue)} files ({total_size:.2f} MB)**\n\nCopy these links into Free Download Manager for batch download!"
    
    await event.reply(response)
    logger.info(f"Batch completed: {len(batch_queue)} files, {total_size:.2f} MB total")
    batch_queue = []

@client.on(events.NewMessage(incoming=True))
async def on_new_message(event):
    if event.message.media and event.message.file:
        chat_id = event.chat_id
        message_id = event.id
        link = f"http://127.0.0.1:{config['port']}/dl/{chat_id}/{message_id}"

        file_name = event.message.file.name if event.message.file.name else "Unknown File"
        file_size_mb = event.message.file.size / (1024 * 1024)

        print(f"\n📥 Received: {file_name} ({file_size_mb:.2f} MB)")
        print(f"🔗 FDM Link: {link}\n")
        logger.info(f"Received file: {file_name} ({file_size_mb:.2f} MB) from chat {chat_id}, message {message_id}")

        if batch_mode:
            # Add to batch queue
            batch_queue.append((file_name, file_size_mb, link))
            await event.reply(f"📦 **Added to Batch:** {file_name} ({file_size_mb:.2f} MB)\nQueue size: {len(batch_queue)} files")
        else:
            # Reply with the link and inline buttons
            buttons = [
                [Button.url("📥 Open in FDM", link)],
                [Button.inline("ℹ️ File Info", f"info_{message_id}")]
            ]
            await event.reply(
                f"**File Ready for FDM!**\n\n"
                f"📄 **{file_name}**\n"
                f"📏 **Size:** {file_size_mb:.2f} MB\n\n"
                f"`{link}`\n\n"
                f"_(Click the button above or copy the link into Free Download Manager)_",
                buttons=buttons
            )

async def main():
    print("⏳ Starting Telegram FDM Proxy...")
    logger.info("Starting Telegram FDM Proxy")
    await client.start(bot_token=BOT_TOKEN)
    print("✅ Bot connected successfully!")
    logger.info("Bot connected successfully")

    app = web.Application()
    app.router.add_get('/dl/{chat_id}/{message_id}', handle_download)
    app.router.add_get('/', dashboard)
    
    # Find an available port
    port = find_free_port()
    config['port'] = port
    print(f"🌐 Using port {port} for HTTP server")
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', port)
    await site.start()

    print(f"🌐 HTTP Server running on http://127.0.0.1:{port}")
    print("\n👉 To use: Forward any file to your Bot on Telegram, then copy the generated link into FDM.")

    try:
        # Keep script running
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        print("\n🛑 Stopping proxy server...")
    finally:
        await site.stop()
        await runner.cleanup()
        await client.disconnect()

if __name__ == '__main__':
    # Silence verbose access logs from aiohttp
    import logging
    logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
    
    asyncio.run(main())
