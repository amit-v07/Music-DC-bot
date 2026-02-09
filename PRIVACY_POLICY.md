# Privacy Policy

**Last Updated:** February 9, 2026

Your privacy is important to us. This policy explains how the **Music Bot** collects, uses, and protects your data.

## 1. Information We Collect

### 1.1 Automatically Collected Data
When you use the bot, we may collect the following data necessary for operation:
- **Discord User ID**: To identify who is running commands (e.g., who added a song).
- **Discord Guild (Server) ID**: To manage settings and queues for specific servers.
- **Voice Channel ID**: To connect and play music.

### 1.2 User-Provided Data
- **Search Queries**: When you use `!play`, we process your search terms to find songs.
- **Commands**: We process command messages to execute actions.

## 2. How We Use Your Information

We use this data solely to provide the services of the bot:
- **Playing Music**: Using voice channel IDs to join and stream audio.
- **Queue Management**: Tracking which user requested which song.
- **Recommendations**: Using song history (titles only) to provide Autoplay recommendations.
- **Permissions**: Checking User IDs against Discord permissions (e.g., Admin checks).

## 3. Data Storage

### 3.1 Temporary Data
Most data (queue, volume, session stats) is stored in **RAM** and is lost when the bot restarts or leaves the voice channel.

### 3.2 Persistent Data
The bot currently operates **without a database**.
- **Listening History**: We store a localized history of recently played song titles in `listening_history.json` solely for the purpose of the Autoplay feature. This data is not linked to specific user behaviors for tracking purposes.
- **Logs**: Technical logs (errors, debug info) are stored locally for troubleshooting but are regularly rotated/deleted.

## 4. Third-Party Services

The bot interacts with:
- **Discord API**: To receive events and send messages.
- **YouTube / YouTube Music**: To search and stream audio.
- **Spotify**: To resolve playlist URLs.

These services have their own privacy policies which govern their data usage.

## 5. Data Sharing

We do **not** sell, trade, or transfer your data to outside parties. Data is only used internally for the bot's functionality.

## 6. Your Rights

Since we do not store persistent user profiles or a database, most data is ephemeral. However, you can:
- **Clear Data**: Use `!leave` or kick the bot to clear the current session and queue.
- **Request Removal**: Contact the developer to request deletion of any server-specific configuration files (if applicable).

## 7. Contact

If you have questions about this Privacy Policy, please contact the bot developer via Discord.
