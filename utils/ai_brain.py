"""
AI Brain Module for Music Bot
Uses Google GenAI SDK (new unified SDK) for dynamic, funny Hinglish responses.
"""
from google import genai
from google.genai import types
from config import config
from utils.logger import logger

class AIBrain:
    """Handles AI text generation for the bot"""
    
    def __init__(self):
        self.enabled = False
        self.client = None
        
        if config.google_api_key:
            try:
                # Initialize the new GenAI client
                self.client = genai.Client(api_key=config.google_api_key)
                
                # Test with available models (2.5-flash is current stable model)
                self.model_name = 'gemini-2.5-flash'
                
                self.enabled = True
                logger.info(f"🧠 AI Brain initialized successfully ({self.model_name})")
            except Exception as e:
                logger.error("ai_init_failed", e)
                logger.warning("🧠 AI Brain disabled: Failed to initialize GenAI client")
        else:
            logger.warning("🧠 AI Brain disabled: No Google API Key found")

    async def get_response(self, action: str, context: dict = None) -> str:
        """
        Generate a response based on an action and context.
        
        Args:
            action: The event triggering the response (e.g., 'skip', 'play', 'error')
            context: Dictionary containing relevant data (e.g., song title, user name)
        """
        if not self.enabled or not self.client:
            return self._get_fallback_response(action)

        try:
            prompt = self._build_prompt(action, context or {})
            
            # Use the new SDK's generate_content method
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            return response.text.strip()
            
        except Exception as e:
            # Check for 429 Resource Exhausted
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                logger.warning(f"🧠 AI Quota Exceeded (Free Tier Limit). Using fallback for '{action}'.")
            else:
                logger.error(f"ai_generation_failed ({action})", e)
            
            return self._get_fallback_response(action)

    def _build_prompt(self, action: str, context: dict) -> str:
        """Constructs the prompt for the AI"""
        
        song = context.get('song', 'music')
        user = context.get('user', 'yaar')
        count = context.get('count', 0)
        
        # Base persona instruction
        system_instruction = (
            "You are a funny, high-energy Discord Music Bot for a group of Indian friends. "
            "You speak in 'Hinglish' (Hindi + English mix). "
            "You love Bollywood references, slang (like 'yaar', 'bhai', 'mast', 'bakwaas'), and being slightly dramatic. "
            "Keep your response SHORT (max 1-2 sentences). No hashtags. Use emojis sparingly."
        )

        # Scenario specific instructions
        scenarios = {
            'play': f"User '{user}' just added the song '{song}'. Hype it up!",
            'skip': f"User '{user}' skipped the song '{song}'. Make a funny comment about their bad taste or impatience.",
            'stop': "User stopped the music. Say goodbye dramatically.",
            'queue_end': "The queue ended. Suggest they add more songs or mention you're finding more.",
            'error': "An error occurred. Apologize in a funny way (blame the internet or wifi).",
            'autoplay_start': f"Autoplay is starting. You picked '{song}' and {count} total songs automatically. Brag about your excellent taste.",
            'join': "You just joined the voice channel. Greet everyone loudly.",
            'leave': "You are leaving. Say bye nicely."
        }

        specific_instruction = scenarios.get(action, f"Event: {action}. Context: {context}")
        
        return f"{system_instruction}\n\nScenario: {specific_instruction}\n\nYour response:"

    def _get_fallback_response(self, action: str) -> str:
        """Fallback static responses if AI fails"""
        fallbacks = {
            'play': "Bajate raho! 🎵",
            'skip': "Chalo next! ⏭️",
            'stop': "Music band. Shanti. 🤫",
            'error': "Arre yaar, kuch gadbad ho gayi. ❌",
            'join': "Hello ji! Main aa gayi! 👋",
            'leave': "Chalti hoon, dua mein yaad rakhna. 👋",
            'queue_end': "Queue khatam? Tension mat lo, main aur gaane dhoondh rahi hoon! 🔎",
            'autoplay_start': "Lo ji! Mast gaane ready kar diye! 🔥"
        }
        return fallbacks.get(action, "Oye hoye! 🎵")

# Global instance
ai_brain = AIBrain()
