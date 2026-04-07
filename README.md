# Telegram FDM Proxy

A simple Telegram bot that acts as a proxy for Free Download Manager (FDM) to download files from Telegram chats.

## Features

- Automatically generates download links for media files sent to the bot
- Supports range requests for multi-threaded downloads in FDM
- Portable executable for easy deployment
- Automatic port selection to avoid conflicts

## Setup

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) and get the BOT_TOKEN
2. Get your API_ID and API_HASH from [https://my.telegram.org](https://my.telegram.org)
3. Run the executable (or script if Python is installed)
4. On first run, enter your API_ID, API_HASH, and BOT_TOKEN when prompted
5. The bot will start and display the port it's using

## Usage

1. Forward any media file to your bot on Telegram
2. The bot will reply with a download link
3. Copy the link and paste it into Free Download Manager
4. FDM will download the file directly from Telegram servers

## Portable Version

The `dist/tg_fdm_proxy.exe` is a standalone executable that includes all dependencies. You can run it on any Windows machine without installing Python.

Place the `.env` file in the same directory as the executable for configuration.

## Development

To run from source:

```bash
pip install -r requirements.txt
python tg_fdm_proxy.py
```

### Requirements

- Python 3.8+
- telethon
- aiohttp
- python-dotenv

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines]