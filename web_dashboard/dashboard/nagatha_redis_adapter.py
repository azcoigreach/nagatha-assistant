"""
Redis-based Nagatha Adapter for Django Web Dashboard.

This adapter uses Redis for storage instead of SQLAlchemy, eliminating
the greenlet issues and providing fast, reliable async operations.
"""

import os
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from django.conf import settings

from .redis_storage import NagathaRedisStorage

logger = logging.getLogger(__name__)


class NagathaRedisAdapter:
    """
    Redis-based adapter for Nagatha Assistant functionality.
    
    This provides a bridge between the Django web application and
    Nagatha's core features using Redis for storage instead of SQLAlchemy.
    """
    
    def __init__(self):
        self._storage = NagathaRedisStorage()
        self._initialized = False
        self._initialization_error = None
    
    async def _ensure_initialized(self):
        """Ensure the adapter is initialized."""
        if self._initialized:
            return
            
        if self._initialization_error:
            raise Exception(f"Previous initialization failed: {self._initialization_error}")
            
        try:
            # Test Redis connection
            status = await self._storage.get_system_status()
            if not status.get("redis_connected", False):
                raise Exception("Redis connection failed")
            
            self._initialized = True
            logger.info("Nagatha Redis adapter initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Nagatha Redis adapter: {e}")
            self._initialization_error = str(e)
            raise
    
    async def start_session(self) -> str:
        """Create a new conversation session."""
        await self._ensure_initialized()
        session_id = await self._storage.create_session()
        logger.info(f"Created new session: {session_id}")
        return session_id
    
    async def send_message(self, session_id: Optional[str], message: str) -> str:
        """Send a message and get a response."""
        try:
            await self._ensure_initialized()
            
            # Create session if none provided
            if session_id is None:
                session_id = await self.start_session()
            
            # Store user message
            import uuid
            message_id = str(uuid.uuid4())
            await self._storage.store_message(session_id, message_id, "user", message)
            
            # Update session activity
            await self._storage.update_session_activity(session_id)
            
            # Generate response using AI
            response = await self._generate_ai_response(session_id, message)
            
            # Store assistant response
            response_id = str(uuid.uuid4())
            await self._storage.store_message(session_id, response_id, "assistant", response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Return a helpful error response
            return f"I'm sorry, I encountered an error while processing your message: {str(e)}"
    
    async def _generate_ai_response(self, session_id: str, user_message: str) -> str:
        """Generate an AI response using OpenAI."""
        try:
            import openai
            from openai import AsyncOpenAI
            
            # Get OpenAI API key
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return "I'm sorry, but I'm not configured with an OpenAI API key."
            
            # Initialize OpenAI client
            client = AsyncOpenAI(api_key=api_key)
            
            # Get conversation history
            messages = await self._storage.get_session_messages(session_id)
            
            # Build conversation context
            conversation = []
            
            # Add system message
            system_prompt = self._get_system_prompt()
            conversation.append({"role": "system", "content": system_prompt})
            
            # Add recent conversation history (last 10 messages to avoid token limits)
            recent_messages = messages[-10:] if len(messages) > 10 else messages
            for msg in recent_messages:
                conversation.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Add current user message
            conversation.append({"role": "user", "content": user_message})
            
            # Get model from environment
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            
            # Make API call
            response = await client.chat.completions.create(
                model=model,
                messages=conversation,
                max_tokens=1000,
                temperature=0.7
            )
            
            # Extract response content
            ai_response = response.choices[0].message.content
            
            # Store conversation context in memory
            await self._storage.store_memory(
                "conversation_context", 
                f"session:{session_id}:last_context",
                {
                    "user_message": user_message,
                    "ai_response": ai_response,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                session_id=session_id,
                ttl_seconds=3600  # Keep context for 1 hour
            )
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            # Fallback to simple response
            return self._get_fallback_response(user_message)
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for Nagatha."""
        return """You are Nagatha Assistant, a helpful and intelligent AI assistant. 

Your personality:
- You are named after Agatha Christie, the famous mystery writer
- You are helpful, knowledgeable, and have a slight British charm
- You can help with a wide variety of tasks including writing, analysis, problem-solving, and general assistance
- You are running in a web dashboard environment with Redis-based storage
- You maintain conversation context and can remember information across sessions

Current capabilities:
- You can engage in natural conversations
- You can help with writing, analysis, and problem-solving
- You can store and retrieve information using your memory system
- You are connected to a web dashboard for user interaction

Please be helpful, clear, and engaging in your responses. If you encounter any technical issues, explain them clearly to the user."""
    
    def _get_fallback_response(self, message: str) -> str:
        """Provide a fallback response when AI is unavailable."""
        message_lower = message.lower()
        
        # Simple keyword-based responses
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'greetings']):
            return "Hello! I'm Nagatha Assistant. I'm currently running in a limited mode, but I'm here to help with basic questions. How can I assist you today?"
        
        elif any(word in message_lower for word in ['help', 'assist', 'support']):
            return "I'm here to help! I can assist with basic questions and provide information. While my full capabilities are currently limited, I'm working to get everything fully operational. What would you like to know?"
        
        elif any(word in message_lower for word in ['what', 'how', 'why', 'when', 'where']):
            return "That's an interesting question! I'm currently operating in a limited mode while we resolve some technical configuration issues with my core systems. I'd be happy to help with basic information, but for more complex queries, you might want to try again once the full system is online."
        
        elif any(word in message_lower for word in ['status', 'working', 'broken', 'error']):
            return "I'm currently running in a limited mode. My core systems are partially operational, but there are some technical configuration issues that need to be resolved. The team is working on getting everything fully functional. I can still help with basic questions though!"
        
        elif any(word in message_lower for word in ['thanks', 'thank you', 'appreciate']):
            return "You're welcome! I'm glad I could help, even in this limited mode. Once the technical issues are resolved, I'll be able to provide much more comprehensive assistance."
        
        else:
            return "I understand your message. I'm currently operating in a limited mode while we resolve some technical configuration issues with my core systems. I can help with basic questions and provide general assistance. What would you like to know?"
    
    async def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a session."""
        await self._ensure_initialized()
        return await self._storage.get_session_messages(session_id)
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status information."""
        try:
            await self._ensure_initialized()
            status = await self._storage.get_system_status()
            
            # Add additional Nagatha-specific status info
            status.update({
                "nagatha_version": "1.0.0",
                "storage_backend": "redis",
                "adapter_type": "redis",
                "mcp_servers_connected": 0,  # Not using MCP in this mode
                "total_tools_available": 0,
                "active_sessions": 0,  # Could be calculated from Redis
                "system_health": status.get("status", "unknown")
            })
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "redis_connected": False,
                "error": str(e),
                "storage_backend": "redis",
                "adapter_type": "redis",
                "status": "error",
                "system_health": "error"
            }
    
    async def get_available_tools(self) -> Dict[str, Any]:
        """Get available tools (simplified for Redis adapter)."""
        return {
            "tools": [],
            "total": 0,
            "note": "Tools not available in Redis-only mode"
        }
    
    async def close(self):
        """Close the adapter and clean up resources."""
        if self._storage:
            await self._storage.close() 