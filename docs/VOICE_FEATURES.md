# Voice Features for Nagatha Assistant

This document describes Nagatha's voice capabilities, including Discord voice channel integration, speech-to-text, and text-to-speech functionality.

## Overview

Nagatha now supports voice interactions through Discord voice channels! She can:

- **Join and leave voice channels** using slash commands
- **Listen to speech** and convert it to text using OpenAI Whisper
- **Speak responses** using OpenAI's text-to-speech with a warm, professional voice
- **Maintain conversation context** in voice channels just like text chat
- **Handle mixed interactions** - voice conversations with text responses for URLs, images, etc.

## Voice Characteristics

Nagatha's voice is designed to match her personality - warm, professional, and engaging:

- **Voice Model**: OpenAI TTS with "alloy" voice (closest to Julia Child-like warmth)
- **Personality**: Professional yet approachable, like a brilliant librarian
- **Communication Style**: Clear, engaging, and encouraging
- **Context Awareness**: Remembers conversation history and builds relationships

## Setup Requirements

### 1. Install Dependencies

The voice features require additional dependencies:

```bash
pip install PyNaCl ffmpeg-python openai-whisper
```

### 2. System Requirements

- **FFmpeg**: Required for audio processing
  ```bash
  # Ubuntu/Debian
  sudo apt update && sudo apt install ffmpeg
  
  # macOS
  brew install ffmpeg
  
  # Windows
  # Download from https://ffmpeg.org/download.html
  ```

- **OpenAI API Key**: Required for text-to-speech
  ```bash
  export OPENAI_API_KEY="your-openai-api-key"
  ```

### 3. Discord Bot Permissions

Your Discord bot needs these permissions:

- **Connect**: Join voice channels
- **Speak**: Play audio in voice channels
- **Use Voice Activity**: Detect when users are speaking
- **View Channels**: See voice channels
- **Send Messages**: Send text responses when needed

## Voice Commands

### `/join [channel]`
Join a voice channel and start voice conversation.

**Parameters:**
- `channel` (optional): Specific voice channel to join. If not specified, joins your current channel.

**Examples:**
```
/join                    # Join your current voice channel
/join #General Voice     # Join a specific voice channel
```

**Response:**
```
🎤 **Joined voice channel:** General Voice

I'm now ready for voice conversation! Just speak naturally and I'll respond. 
Use `/leave` when you're done.
```

### `/leave`
Leave the current voice channel.

**Response:**
```
👋 **Left voice channel**

Thanks for the conversation!
```

### `/voice-status`
Check voice channel status and capabilities.

**Response:**
```
🎤 **Voice Status**

**Connected to:** General Voice
**Members:** 3
**Conversations:** 5

**Capabilities:**
• Speech-to-Text: ✅
• Text-to-Speech: ✅

**Commands:**
• `/join` - Join a voice channel
• `/leave` - Leave current voice channel
• `/voice-status` - Show this status
```

### `/speak <message>`
Make Nagatha speak a specific message in the current voice channel.

**Parameters:**
- `message` (required): Text for Nagatha to speak

**Example:**
```
/speak Hello everyone! I'm Nagatha, your AI assistant.
```

## Voice Conversation Flow

### 1. Starting a Voice Session

1. **Join a voice channel** using `/join`
2. **Speak naturally** - Nagatha will listen and respond
3. **Use text commands** when needed for complex interactions

### 2. Voice Interaction

- **Speech-to-Text**: Your voice is converted to text using Whisper
- **AI Processing**: Nagatha processes your message like any text conversation
- **Text-to-Speech**: Nagatha's response is converted to speech using OpenAI TTS
- **Context Preservation**: Conversation history is maintained throughout the session

### 3. Mixed Interactions

When Nagatha needs to share URLs, images, or complex information:

1. **Voice Response**: "I found that information for you. Let me share the details in text chat."
2. **Text Response**: Sends the full information with links/images to the text channel
3. **Voice Continuation**: Continues the voice conversation naturally

### 4. Ending a Session

- **Manual**: Use `/leave` to end the session
- **Automatic**: Nagatha may leave if the channel becomes empty
- **Session Cleanup**: Conversation history is preserved for future interactions

## Voice Features

### Speech Recognition
- **Model**: OpenAI Whisper (base model)
- **Accuracy**: High accuracy for clear speech
- **Languages**: Supports multiple languages
- **Noise Handling**: Good performance in typical Discord voice environments

### Text-to-Speech
- **Model**: OpenAI TTS-1
- **Voice**: "Alloy" - warm, professional, engaging
- **Quality**: High-quality, natural-sounding speech
- **Speed**: Real-time generation and playback

### Conversation Management
- **Session Tracking**: Maintains conversation context per voice channel
- **History**: Remembers previous interactions
- **Context Switching**: Handles multiple voice channels independently
- **Memory Integration**: Uses Nagatha's memory system for continuity

## Best Practices

### For Users

1. **Clear Speech**: Speak clearly for better recognition
2. **Natural Pace**: Speak at a normal conversational pace
3. **Mixed Communication**: Use text for complex queries, voice for conversation
4. **Patience**: Allow time for speech processing and response generation

### For Server Administrators

1. **Permissions**: Ensure bot has necessary voice permissions
2. **Channel Setup**: Create dedicated voice channels for AI interaction
3. **User Guidelines**: Provide clear instructions for voice interaction
4. **Monitoring**: Monitor voice channel usage and bot performance

## Troubleshooting

### Common Issues

#### "Voice functionality not available"
- **Cause**: Missing dependencies or configuration
- **Solution**: Install PyNaCl, ffmpeg-python, and openai-whisper

#### "Failed to join voice channel"
- **Cause**: Missing permissions or channel issues
- **Solution**: Check bot permissions and channel settings

#### "Speech-to-Text: ❌"
- **Cause**: Whisper model not loaded
- **Solution**: Check internet connection and model download

#### "Text-to-Speech: ❌"
- **Cause**: OpenAI API key not configured
- **Solution**: Set OPENAI_API_KEY environment variable

#### Poor speech recognition
- **Cause**: Background noise or unclear speech
- **Solution**: Speak clearly in a quiet environment

#### Audio quality issues
- **Cause**: Discord audio settings or network issues
- **Solution**: Check Discord voice settings and internet connection

### Syncing Commands

If voice commands don't appear, sync the slash commands:

**From Discord (Admin only):**
```
/sync
```

**From CLI (provides guidance):**
```bash
nagatha discord sync
```

**Note:** Commands are automatically synced when the bot starts. If you've added new voice commands, restart the bot:
```bash
nagatha discord stop && nagatha discord start
```

### Debug Mode

Enable debug logging to troubleshoot voice issues:

```bash
export LOG_LEVEL=DEBUG
nagatha discord start
```

### Voice Status Check

Use `/voice-status` to check:
- Connection status
- Capability availability
- Session information
- Error diagnostics

## Advanced Configuration

### Voice Settings

You can customize voice behavior through environment variables:

```bash
# OpenAI TTS voice selection
export NAGATHA_TTS_VOICE="alloy"  # Options: alloy, echo, fable, onyx, nova, shimmer

# Whisper model size
export NAGATHA_WHISPER_MODEL="base"  # Options: tiny, base, small, medium, large

# Audio quality settings
export NAGATHA_AUDIO_VOLUME="0.8"  # Volume level (0.0-1.0)
export NAGATHA_AUDIO_SAMPLE_RATE="48000"  # Sample rate for audio processing
```

### Performance Optimization

For better performance:

1. **Use smaller Whisper models** for faster processing
2. **Optimize network settings** for Discord voice
3. **Monitor system resources** during voice sessions
4. **Use dedicated voice channels** to reduce interference

## Security Considerations

### Privacy
- **Voice Data**: Audio is processed locally when possible
- **Transcription**: Speech-to-text results may be logged for debugging
- **Storage**: No voice recordings are permanently stored
- **Sharing**: Voice conversations follow the same privacy rules as text

### Permissions
- **Bot Permissions**: Only grant necessary voice permissions
- **User Access**: Control who can use voice features
- **Channel Access**: Limit voice features to appropriate channels

## Troubleshooting

### Common Voice Connection Issues

#### Error 4006: Connection Closed
- **Cause**: Bot lacks proper voice permissions
- **Solution**: 
  1. Check bot permissions in Discord server settings
  2. Ensure bot has "Connect", "Speak", and "Use Voice Activity" permissions
  3. Verify Server Members Intent is enabled in Discord Developer Portal
  4. Re-invite the bot with proper permissions

#### Error 1006: Network Issues
- **Cause**: Unstable internet connection or Discord server issues
- **Solution**: Check internet connection and Discord status

#### Error 4001: Authentication Issues
- **Cause**: Invalid bot token or expired credentials
- **Solution**: Regenerate bot token in Discord Developer Portal

### Permission Checklist

Ensure your bot has these permissions:
- ✅ **Connect** - Join voice channels
- ✅ **Speak** - Transmit audio in voice channels
- ✅ **Use Voice Activity** - Use voice activity detection
- ✅ **View Channels** - See voice channels
- ✅ **Send Messages** - Respond to voice commands

### Discord Developer Portal Settings

In your Discord application settings:
1. **Bot Section**: Enable "Server Members Intent"
2. **OAuth2 Scopes**: Include `bot` and `applications.commands`
3. **Bot Permissions**: Include all voice-related permissions

### Debug Steps

1. **Check Bot Status**:
   ```bash
   nagatha discord status
   ```

2. **Test Voice Permissions**:
   - Try `/voice-status` command
   - Check if bot can see voice channels

3. **Verify Intents**:
   - Server Members Intent enabled
   - Voice States Intent enabled

4. **Check Logs**:
   ```bash
   tail -f nohup.out | grep -i voice
   ```

## Future Enhancements

Planned voice features:

- **Voice Activity Detection**: Automatic conversation management
- **Multiple Voices**: Different voice options for different contexts
- **Voice Commands**: Direct voice commands for bot control
- **Audio Effects**: Background music and sound effects
- **Translation**: Real-time voice translation
- **Voice Cloning**: Custom voice training for users

## Support

For voice feature support:

1. **Check the troubleshooting section** above
2. **Review Discord bot permissions**
3. **Verify system requirements**
4. **Check Nagatha logs** for error messages
5. **Test with basic commands** first
6. **Create an issue** on GitHub with detailed information

## Examples

### Basic Voice Session
```
User: /join
Nagatha: 🎤 **Joined voice channel:** General Voice

User: [speaks] "Hello Nagatha, how are you today?"
Nagatha: [speaks] "Hello! I'm doing wonderfully, thank you for asking. I'm excited to help you with whatever you need today."

User: [speaks] "Can you help me find information about Python programming?"
Nagatha: [speaks] "Of course! I'd be happy to help you with Python programming. Let me search for some great resources and share them with you in text chat so you can easily access the links."
Nagatha: [text] Here are some excellent Python programming resources:
• Official Python Documentation: https://docs.python.org/
• Real Python Tutorials: https://realpython.com/
• Python.org Tutorial: https://docs.python.org/3/tutorial/
```

### Voice Status Check
```
User: /voice-status
Nagatha: 🎤 **Voice Status**

**Connected to:** Development Team
**Members:** 4
**Conversations:** 12

**Capabilities:**
• Speech-to-Text: ✅
• Text-to-Speech: ✅

**Commands:**
• `/join` - Join a voice channel
• `/leave` - Leave current voice channel
• `/voice-status` - Show this status
```

Voice features bring Nagatha's warm, engaging personality to life through natural conversation while maintaining all her powerful AI capabilities! 