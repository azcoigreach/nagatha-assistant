"""
Voice Handler for Nagatha Assistant Discord Integration.

This module handles all voice-related functionality including:
- Joining and leaving voice channels
- Speech-to-text conversion using Whisper
- Text-to-speech conversion using OpenAI TTS
- Voice conversation management
- Audio capture from voice channels
- Speaking text channel responses in voice channels
"""
import asyncio
import io
import tempfile
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

import discord
from discord import FFmpegPCMAudio, PCMVolumeTransformer
import whisper
import openai
from openai import OpenAI

from nagatha_assistant.utils.logger import get_logger
from nagatha_assistant.core.agent import send_message, start_session

logger = get_logger()


class VoiceListener:
    """Handles listening to voice audio from Discord users."""
    
    def __init__(self, voice_handler):
        self.voice_handler = voice_handler
        self.listening_guilds: Dict[int, bool] = {}
        # Store buffered PCM audio per (guild_id, user_id)
        self.audio_buffers: Dict[tuple[int, int], List[bytes]] = {}
        self.speaking_users: Dict[int, bool] = {}
        
    async def start_listening(self, guild_id: int):
        """Start listening for voice in a guild."""
        try:
            self.listening_guilds[guild_id] = True
            logger.info(f"Started voice listening in guild {guild_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to start voice listening: {e}")
            return False
    
    async def stop_listening(self, guild_id: int):
        """Stop listening for voice in a guild."""
        try:
            self.listening_guilds[guild_id] = False
            logger.info(f"Stopped voice listening in guild {guild_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop voice listening: {e}")
            return False
    
    async def handle_voice_activity(self, user_id: int, guild_id: int, speaking: bool):
        """Handle voice activity from a user."""
        try:
            if guild_id not in self.listening_guilds or not self.listening_guilds[guild_id]:
                return
            
            if speaking:
                if not self.speaking_users.get(user_id, False):
                    self.speaking_users[user_id] = True
                    logger.info(f"User {user_id} started speaking in guild {guild_id}")
            else:
                if self.speaking_users.get(user_id, False):
                    self.speaking_users[user_id] = False
                    logger.info(f"User {user_id} stopped speaking in guild {guild_id}")
                    # Process any accumulated audio
                    await self._process_user_audio(user_id, guild_id)
                    
        except Exception as e:
            logger.error(f"Error handling voice activity: {e}")
    
    async def handle_voice_packet(self, user_id: int, guild_id: int, data: bytes):
        """Buffer raw PCM packets from Discord."""
        try:
            if guild_id not in self.listening_guilds or not self.listening_guilds[guild_id]:
                return
            key = (guild_id, user_id)
            self.audio_buffers.setdefault(key, []).append(data)
        except Exception as e:
            logger.error(f"Error buffering voice packet: {e}")

    async def _process_user_audio(self, user_id: int, guild_id: int):
        """Transcribe buffered audio and generate a spoken response."""
        try:
            key = (guild_id, user_id)
            if key not in self.audio_buffers or not self.audio_buffers[key]:
                return

            audio_data = b"".join(self.audio_buffers[key])
            # Clear buffer after reading
            self.audio_buffers[key] = []

            # Generate response from audio
            response = await self.voice_handler.handle_voice_message(
                audio_data, user_id, guild_id
            )

            if response:
                await self.voice_handler.speak_in_voice_channel(response, guild_id)

        except Exception as e:
            logger.error(f"Error processing user audio: {e}")


class VoiceHandler:
    """
    Handles voice channel interactions for Nagatha.
    
    This class manages:
    - Joining and leaving voice channels
    - Speech-to-text conversion
    - Text-to-speech conversion
    - Voice conversation sessions
    - Audio capture from voice channels
    - Speaking text channel responses in voice channels
    """

    def __init__(self, discord_plugin):
        self.discord_plugin = discord_plugin
        self.voice_clients: Dict[int, discord.VoiceClient] = {}
        self.whisper_model = None
        self.openai_client = None
        self.voice_sessions: Dict[int, Dict[str, Any]] = {}
        self.voice_listener = VoiceListener(self)
        # Track which text channels are linked to voice sessions
        self.text_channel_voice_links: Dict[str, int] = {}  # text_channel_id -> guild_id

        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.openai_client = OpenAI(api_key=api_key)

        try:
            self.whisper_model = whisper.load_model("base")
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")

    async def join_voice_channel(self, voice_channel: discord.VoiceChannel, guild_id: int, text_channel_id: Optional[str] = None) -> bool:
        """
        Join a voice channel.
        
        Args:
            voice_channel: The voice channel to join
            guild_id: The guild ID
            text_channel_id: Optional text channel ID to link with this voice session
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Leave any existing voice channel
            if guild_id in self.voice_clients:
                await self.leave_voice_channel(guild_id)
            
            # Join the voice channel
            voice_client = await voice_channel.connect()
            self.voice_clients[guild_id] = voice_client
            
            # Initialize voice session
            self.voice_sessions[guild_id] = {
                'channel_id': voice_channel.id,
                'guild_id': guild_id,
                'joined_at': datetime.now(),
                'session_id': await start_session(),
                'conversation_history': [],
                'text_channel_id': text_channel_id
            }
            
            # Link text channel to voice session if provided
            if text_channel_id:
                self.text_channel_voice_links[text_channel_id] = guild_id
                logger.info(f"Linked text channel {text_channel_id} to voice session in guild {guild_id}")
            
            logger.info(f"Joined voice channel: {voice_channel.name} in guild {guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}")
            return False
    
    async def speak_text_channel_response(self, text_channel_id: str, response_text: str) -> bool:
        """
        Speak a text channel response in the linked voice channel.
        
        Args:
            text_channel_id: The text channel ID
            response_text: The text to speak
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if this text channel is linked to a voice session
            if text_channel_id not in self.text_channel_voice_links:
                logger.debug(f"Text channel {text_channel_id} not linked to any voice session")
                return False
            
            guild_id = self.text_channel_voice_links[text_channel_id]
            
            # Check if we're still in the voice channel
            if not await self.is_in_voice_channel(guild_id):
                logger.warning(f"Voice session for guild {guild_id} no longer active")
                # Clean up the link
                del self.text_channel_voice_links[text_channel_id]
                return False
            
            # Speak the response
            success = await self.speak_in_voice_channel(response_text, guild_id)
            if success:
                logger.info(f"Spoke text channel response in voice channel: {response_text[:50]}...")
            return success
            
        except Exception as e:
            logger.error(f"Failed to speak text channel response: {e}")
            return False
    
    async def start_voice_listening(self, guild_id: int):
        """Start listening for voice input in a guild."""
        return await self.voice_listener.start_listening(guild_id)
    
    async def stop_voice_listening(self, guild_id: int):
        """Stop listening for voice input in a guild."""
        return await self.voice_listener.stop_listening(guild_id)
    
    async def handle_voice_activity(self, user_id: int, guild_id: int, speaking: bool):
        """Handle voice activity from a user."""
        await self.voice_listener.handle_voice_activity(user_id, guild_id, speaking)

    async def handle_voice_packet(self, user_id: int, data: bytes, guild_id: int):
        """Forward raw voice data to the listener for buffering."""
        await self.voice_listener.handle_voice_packet(user_id, guild_id, data)
    
    async def leave_voice_channel(self, guild_id: int) -> bool:
        """
        Leave a voice channel.
        
        Args:
            guild_id: The guild ID to leave voice channel in
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if guild_id in self.voice_clients:
                voice_client = self.voice_clients[guild_id]
                await voice_client.disconnect()
                del self.voice_clients[guild_id]
                
                # Clean up session
                if guild_id in self.voice_sessions:
                    session = self.voice_sessions[guild_id]
                    # Remove text channel link if it exists
                    text_channel_id = session.get('text_channel_id')
                    if text_channel_id and text_channel_id in self.text_channel_voice_links:
                        del self.text_channel_voice_links[text_channel_id]
                    del self.voice_sessions[guild_id]
                
                logger.info(f"Left voice channel in guild {guild_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to leave voice channel: {e}")
            return False
    
    async def is_in_voice_channel(self, guild_id: int) -> bool:
        """Check if Nagatha is currently in a voice channel."""
        return guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected()
    
    async def get_voice_channel_info(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get information about the current voice channel."""
        if guild_id not in self.voice_clients:
            return None
        
        voice_client = self.voice_clients[guild_id]
        if not voice_client.is_connected():
            return None
        
        session = self.voice_sessions.get(guild_id, {})
        return {
            'channel_name': voice_client.channel.name,
            'channel_id': voice_client.channel.id,
            'guild_id': guild_id,
            'member_count': len(voice_client.channel.members),
            'joined_at': session.get('joined_at'),
            'text_channel_id': session.get('text_channel_id')
        }
    
    async def process_speech_to_text(self, audio_data: bytes) -> Optional[str]:
        """
        Convert speech audio to text using Whisper.
        
        Args:
            audio_data: Raw audio data
            
        Returns:
            Transcribed text or None if failed
        """
        if not self.whisper_model:
            logger.error("Whisper model not available")
            return None
        
        try:
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            # Transcribe with Whisper
            result = self.whisper_model.transcribe(temp_file_path)
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            transcribed_text = result["text"].strip()
            if transcribed_text:
                logger.info(f"Speech transcribed: {transcribed_text}")
                return transcribed_text
            else:
                logger.warning("Speech transcription returned empty text")
                return None
                
        except Exception as e:
            logger.error(f"Speech-to-text failed: {e}")
            return None
    
    async def process_text_to_speech(self, text: str, guild_id: int) -> Optional[bytes]:
        """
        Convert text to speech using OpenAI TTS.
        
        Args:
            text: Text to convert to speech
            guild_id: Guild ID for voice session context
            
        Returns:
            Audio data or None if failed
        """
        if not self.openai_client:
            logger.error("OpenAI client not available for TTS")
            return None
        
        try:
            # Get voice session to determine voice characteristics
            voice_session = self.voice_sessions.get(guild_id, {})
            
            # Use a warm, professional voice (alloy is closest to Julia Child-like warmth)
            voice = "alloy"  # Options: alloy, echo, fable, onyx, nova, shimmer
            
            response = self.openai_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )
            
            # Read the audio data
            audio_data = response.content
            logger.info(f"Text-to-speech generated for: {text[:50]}...")
            return audio_data
            
        except Exception as e:
            logger.error(f"Text-to-speech failed: {e}")
            return None
    
    async def handle_voice_message(self, audio_data: bytes, user_id: int, guild_id: int) -> Optional[str]:
        """
        Handle incoming voice message from a user.
        
        Args:
            audio_data: Raw audio data from user
            user_id: Discord user ID
            guild_id: Guild ID
            
        Returns:
            Nagatha's response text or None if failed
        """
        try:
            # Convert speech to text
            transcribed_text = await self.process_speech_to_text(audio_data)
            if not transcribed_text:
                return "I'm sorry, I couldn't understand what you said. Could you please repeat that?"
            
            # Get voice session
            if guild_id not in self.voice_sessions:
                logger.error(f"No voice session found for guild {guild_id}")
                return None
            
            session = self.voice_sessions[guild_id]
            
            # Add to conversation history
            session['conversation_history'].append({
                'user_id': user_id,
                'message': transcribed_text,
                'timestamp': datetime.now()
            })
            
            # Get AI response
            response = await send_message(session['session_id'], transcribed_text)
            
            # Add response to history
            session['conversation_history'].append({
                'user_id': 'nagatha',
                'message': response,
                'timestamp': datetime.now()
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to handle voice message: {e}")
            return None
    
    async def speak_in_voice_channel(self, text: str, guild_id: int) -> bool:
        """
        Make Nagatha speak in a voice channel.
        
        Args:
            text: Text for Nagatha to speak
            guild_id: Guild ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if guild_id not in self.voice_clients:
                logger.error(f"No voice client for guild {guild_id}")
                return False
            
            voice_client = self.voice_clients[guild_id]
            if not voice_client.is_connected():
                logger.error(f"Voice client not connected for guild {guild_id}")
                return False
            
            # Generate speech
            audio_data = await self.process_text_to_speech(text, guild_id)
            if not audio_data:
                return False
            
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            # Create audio source
            audio_source = FFmpegPCMAudio(temp_file_path)
            audio_source = PCMVolumeTransformer(audio_source, volume=0.8)
            
            # Play audio
            voice_client.play(audio_source)
            
            # Clean up file after playing starts
            def cleanup():
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            
            # Schedule cleanup
            asyncio.create_task(self._cleanup_after_play(cleanup))
            
            logger.info(f"Speaking in voice channel: {text[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to speak in voice channel: {e}")
            return False
    
    async def _cleanup_after_play(self, cleanup_func):
        """Clean up temporary files after audio finishes playing."""
        await asyncio.sleep(1)  # Give time for audio to start
        cleanup_func()
    
    async def get_voice_status(self, guild_id: int) -> Dict[str, Any]:
        """Get comprehensive voice status for a guild."""
        is_connected = await self.is_in_voice_channel(guild_id)
        channel_info = await self.get_voice_channel_info(guild_id)
        session = self.voice_sessions.get(guild_id, {})
        
        return {
            'is_connected': is_connected,
            'channel_info': channel_info,
            'session_active': bool(session),
            'conversation_count': len(session.get('conversation_history', [])),
            'whisper_available': self.whisper_model is not None,
            'tts_available': self.openai_client is not None
        } 