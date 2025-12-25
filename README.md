# Streamerphile

A Discord bot that monitors Twitch streams for specific games and sends notifications when new streams matching your criteria are found.

## Requirements

- Python 3.7 or higher
- Twitch API credentials
- Discord Bot Token

## Installation

1. Clone or download this repository

2. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the example config file:
```bash
cp config.json.example config.json
```

5. Edit `config.json` with your credentials (see Configuration section below)

## Configuration

### Getting Twitch API Credentials

1. Go to [Twitch Developers](https://dev.twitch.tv/)
2. Create a new application
3. Copy your **Client ID** and **Client Secret**

### Getting Discord Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section
4. Create a bot and copy the **Token**
5. Enable the following bot permissions:
   - Send Messages
   - Embed Links
   - Use Slash Commands

### Getting Discord Channel ID

1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click on the channel where you want notifications
3. Click "Copy ID"

### Configuration File

Edit `config.json` with your settings:

```json
{
  "twitch_client_id": "your_twitch_client_id",
  "twitch_client_secret": "your_twitch_client_secret",
  "discord_bot_token": "your_discord_bot_token",
  "discord_channel_id": "your_discord_channel_id",
  "max_viewers": 20,
  "min_viewers": 0,
  "game_ids": [],
  "required_tags": [],
  "exclude_tags": [],
  "ignored_channels": [],
  "languages": ["en"],
  "search_interval_minutes": 30,
  "debug": false
}
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `twitch_client_id` | Your Twitch API Client ID | Required |
| `twitch_client_secret` | Your Twitch API Client Secret | Required |
| `discord_bot_token` | Your Discord bot token | Required |
| `discord_channel_id` | Discord channel ID for notifications | Required |
| `max_viewers` | Maximum viewer count to notify | 20 |
| `min_viewers` | Minimum viewer count to notify | 0 |
| `game_ids` | List of Twitch game IDs to monitor | [] |
| `required_tags` | Streams must have ALL these tags | [] |
| `exclude_tags` | Streams with ANY of these tags are excluded (case-insensitive) | [] |
| `ignored_channels` | List of channel usernames/IDs to ignore | [] |
| `languages` | List of language codes (e.g., "en", "es") | [] |
| `search_interval_minutes` | How often to check for new streams | 30 |
| `debug` | Enable debug logging | false |

## Usage

### Starting the Bot

Run the bot:
```bash
python bot.py
```