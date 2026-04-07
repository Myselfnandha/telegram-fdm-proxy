# Telegram FDM Proxy

A powerful Telegram bot that acts as a proxy for Free Download Manager (FDM) to download files from Telegram chats with advanced features.

## Features

- 🔗 **Automatic Download Links**: Generates HTTP links for any media file sent to the bot
- 📦 **Batch Download Mode**: Queue multiple files with `/start_batch` and `/end_batch` commands
- 🎛️ **Web Dashboard**: Monitor status and get usage instructions at `http://127.0.0.1:{port}`
- 📏 **File Management**: Size limits (2GB default) and file type filtering
- 🔄 **Retry Logic**: Automatic retries for failed downloads with exponential backoff
- 🚀 **Performance Optimized**: Concurrent download limits and connection pooling
- 🎯 **Advanced Telegram Features**: Inline buttons for quick actions and file information
- 🌐 **Cross-Platform**: Docker support for Linux/Mac deployment
- 📱 **Portable Executable**: Standalone Windows .exe with all dependencies included
- 🔌 **Dynamic Port Selection**: Automatically finds available ports to avoid conflicts
- 📊 **Enhanced Logging**: Detailed logs with chat/message IDs for debugging

## Quick Start

### Windows (Portable)
1. Download `tg_fdm_proxy.exe` from releases
2. Run the executable
3. Enter your Telegram API credentials when prompted
4. Forward files to your bot and copy the download links to FDM

### Docker (Cross-Platform)
```bash
# Clone the repository
git clone https://github.com/Myselfnandha/telegram-fdm-proxy.git
cd telegram-fdm-proxy

# Create .env file with your credentials
echo "API_ID=your_api_id" > .env
echo "API_HASH=your_api_hash" >> .env
echo "BOT_TOKEN=your_bot_token" >> .env

# Run with Docker Compose
docker-compose up -d
```

## Setup

### Manual Setup
1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) and get the BOT_TOKEN
2. Get your API_ID and API_HASH from [https://my.telegram.org](https://my.telegram.org)
3. Run the executable/script
4. On first run, enter your credentials when prompted

### Configuration
The `.env` file contains:
```
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
```

## Usage

### Basic Downloads
1. Forward any media file to your bot on Telegram
2. The bot will reply with a download link and inline buttons
3. Click "📥 Open in FDM" or copy the link to Free Download Manager
4. FDM will download the file directly from Telegram servers

### Batch Downloads
```
/start_batch  # Start queuing files
# Send multiple files - they'll be added to queue
/end_batch    # Get all download links at once
```

### Web Dashboard
Visit `http://127.0.0.1:{port}` in your browser for:
- Current status and port information
- Usage instructions
- Links to documentation

## Advanced Configuration

### File Limits
- **Max File Size**: 2000 MB (configurable in source)
- **Concurrent Downloads**: 5 simultaneous downloads max
- **Allowed Extensions**: All types allowed by default

### Performance Tuning
- Connection pooling for multiple downloads
- Bandwidth throttling (configurable)
- Automatic retry with delays

## Development

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python tg_fdm_proxy.py
```

### Building Portable Executable
```bash
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller --onefile --add-data ".env;." tg_fdm_proxy.py
```

### Docker Build
```bash
# Build image
docker build -t tg-fdm-proxy .

# Run container
docker run -p 8080:8080 -v $(pwd)/.env:/app/.env tg-fdm-proxy
```

## Requirements

- Python 3.8+
- telethon
- aiohttp
- python-dotenv
- Docker (optional, for containerized deployment)

## Troubleshooting

- **Port conflicts**: The bot automatically selects available ports
- **Download failures**: Check logs for retry attempts and network issues
- **File size limits**: Large files may need FDM configuration adjustments
- **Session issues**: Delete `.session` files to re-authenticate

## License

MIT License - see LICENSE file for details

[Your License Here]

## Contributing

[Your Contributing Guidelines]