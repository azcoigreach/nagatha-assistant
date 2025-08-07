# Discord Voice Connection Troubleshooting

## Error 4006: Connection Closed

This error occurs when the Discord bot lacks the necessary permissions to connect to voice channels.

## Complete Discord Setup Checklist

### 1. Discord Developer Portal Settings

#### Bot Section
- [ ] **Message Content Intent** - ENABLED
- [ ] **Server Members Intent** - ENABLED  
- [ ] **Presence Intent** - ENABLED (optional but recommended)

#### OAuth2 > URL Generator
- [ ] **Scopes**: `bot` and `applications.commands`
- [ ] **Bot Permissions**:
  - [ ] **Administrator** (grants all permissions, but sometimes voice permissions need to be explicit)
  - [ ] **Connect** - Join voice channels (explicitly select this)
  - [ ] **Speak** - Transmit audio in voice channels (explicitly select this)
  - [ ] **Use Voice Activity** - Use voice activity detection (explicitly select this)
  - [ ] **View Channels** - See voice channels
  - [ ] **Send Messages** - Respond to voice commands
  - [ ] **Read Message History** - Read previous messages
  - [ ] **Use Slash Commands** - Use slash commands
  - [ ] **Priority Speaker** - Optional: Get priority in voice

### 2. Server-Specific Permissions

In your Discord server settings:

#### Bot Role Permissions
- [ ] **Connect** - Join voice channels
- [ ] **Speak** - Transmit audio in voice channels
- [ ] **Use Voice Activity** - Use voice activity detection
- [ ] **View Channels** - See voice channels
- [ ] **Send Messages** - Respond to voice commands

#### Voice Channel Permissions
- [ ] Bot role has **Connect** permission for the voice channel
- [ ] Bot role has **Speak** permission for the voice channel
- [ ] Bot role has **Use Voice Activity** permission for the voice channel

### 3. Environment Variables

Check your `.env` file:
```bash
DISCORD_BOT_TOKEN=your_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
```

### 4. Bot Invitation

Make sure you used the correct invitation URL with all required permissions.

## Debug Steps

### Step 1: Check Bot Status
```bash
nagatha discord status
```

### Step 2: Test Voice Commands
Try these commands in Discord:
- `/voice-status` - Check voice capabilities
- `/join` - Try to join voice channel

### Step 3: Check Logs
```bash
tail -f nohup.out | grep -i voice
```

### Step 4: Verify Bot Permissions
1. Go to your Discord server settings
2. Navigate to "Roles" > "Bot Role"
3. Verify all voice permissions are enabled

### Step 5: Re-invite the Bot
If permissions are still missing:
1. Go to Discord Developer Portal
2. OAuth2 > URL Generator
3. Select all required scopes and permissions
4. Generate new invitation URL
5. Re-invite the bot to your server

## Common Solutions

### Solution 1: Re-invite with Correct Permissions
The most common fix is to re-invite the bot with the correct permissions:

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application
3. Go to OAuth2 > URL Generator
4. Select scopes: `bot` and `applications.commands`
5. **IMPORTANT**: Even if you select "Administrator", also explicitly select these voice permissions:
   - **Connect**
   - **Speak**
   - **Use Voice Activity**
6. Copy the generated URL
7. Open the URL and re-invite the bot

### Solution 2: Check Server Permissions
1. In Discord, go to Server Settings > Roles
2. Find the bot's role
3. Ensure it has all voice permissions enabled

### Solution 3: Check Voice Channel Permissions
1. Right-click on the voice channel
2. Select "Edit Channel"
3. Go to "Permissions" tab
4. Ensure the bot role has Connect, Speak, and Use Voice Activity permissions

### Solution 4: Administrator Permission Issue
Sometimes the "Administrator" permission doesn't properly grant voice permissions. Try:

1. **Explicit Voice Permissions**: In the OAuth2 URL Generator, explicitly select voice permissions even if Administrator is selected
2. **Role Hierarchy**: Ensure the bot's role is high enough in the server's role hierarchy
3. **Channel Overrides**: Check if there are any channel-specific permission overrides that might be denying voice access

## Still Having Issues?

If you're still getting 4006 errors after following all steps:

1. **Check bot token**: Ensure `DISCORD_BOT_TOKEN` is correct
2. **Restart the bot**: `nagatha discord stop && nagatha discord start`
3. **Check Discord status**: Visit [Discord Status](https://status.discord.com/)
4. **Verify intents**: Ensure all required intents are enabled in Developer Portal
5. **Try explicit permissions**: Even with Administrator, explicitly select voice permissions in OAuth2

## Test Commands

Once permissions are fixed, test with:
- `/voice-status` - Should show voice capabilities
- `/join` - Should successfully join voice channel
- `/speak "Hello"` - Should make Nagatha speak
- `/leave` - Should leave voice channel

## Advanced Troubleshooting

### If Administrator Permission Isn't Working
Sometimes the Administrator permission doesn't properly grant voice permissions. In this case:

1. **Explicit Voice Permissions**: In OAuth2 URL Generator, explicitly select:
   - Connect
   - Speak
   - Use Voice Activity
   - View Channels
   - Send Messages

2. **Role Hierarchy**: Make sure the bot's role is above any roles that might have denied permissions

3. **Channel-Specific Permissions**: Check if the voice channel has specific permission overrides that might be denying access

### Network/Firewall Issues
If permissions are correct but connection still fails:
1. Check if your network/firewall is blocking Discord voice connections
2. Try connecting from a different network
3. Check if Discord voice servers are having issues 