"""
Google Gemini Provider Implementation
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, List

from agentcomm.llm.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

class GeminiProvider(LLMProvider):
    """
    Google Gemini API provider implementation
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize the Gemini provider
        
        Args:
            api_key: Google API key (if None, will try to get from environment)
            **kwargs: Additional configuration parameters
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.default_model = kwargs.get("default_model", "gemini-1.5-pro")
        self.default_params = {
            "temperature": kwargs.get("temperature", 0.7),
            "max_output_tokens": kwargs.get("max_tokens", 1000),
            "top_p": kwargs.get("top_p", 1.0),
            "top_k": kwargs.get("top_k", 40)
        }
        
        # We'll initialize the client when needed to avoid import errors
        self._genai_module = None
        if self.api_key:
            try:
                import google.generativeai as genai
                self._genai_module = genai
                self._genai_module.configure(api_key=self.api_key)
                logger.info("Google Generative AI module imported successfully")
            except ImportError:
                logger.error("Failed to import google.generativeai package. Please install it with: pip install google-generativeai>=0.3.0")
    
    async def generate(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """
        Generate text from Gemini, streaming the response

        Args:
            prompt: The prompt to send to the model
            **kwargs: Additional parameters to pass to the API

        Yields:
            Generated text chunks
        """
        if not self._genai_module:
            logger.error("Google Generative AI module not imported. Please install the google-generativeai package.")
            yield "Error: Google Generative AI module not imported. Please install the google-generativeai package."
            return

        if not self.api_key:
            logger.error("Google API key not provided. Please provide a valid API key.")
            yield "Error: Google API key not provided. Please provide a valid API key."
            return

        try:
            # Prepare parameters
            model = kwargs.get("model", self.default_model)
            params = self.default_params.copy()
            params.update({k: v for k, v in kwargs.items() if k in self.default_params})

            logger.info(f"Gemini generate (streaming) - Model: {model}, Params: {params}")
            logger.debug(f"Prompt: {prompt[:100]}...")

            # Create the content
            content = prompt

            # Add system message if provided
            system_message = kwargs.get("system")
            if system_message:
                content = f"{system_message}\n\n{content}"
                logger.debug(f"System message added: {system_message[:50]}...")

            # Add chat history if provided
            history = kwargs.get("history") or kwargs.get("chat_history")
            chat_history = []
            if history and isinstance(history, list):
                logger.debug(f"Chat history provided with {len(history)} messages")
                # Convert history to Gemini format
                for msg in history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        chat_history.append({"role": "user", "parts": [{"text": content}]})
                    elif role == "assistant":
                        chat_history.append({"role": "model", "parts": [{"text": content}]})
                    elif role == "system":
                        # Add system message to the beginning of the first user message
                        if chat_history and chat_history[0]["role"] == "user":
                            chat_history[0]["parts"][0]["text"] = f"{content}\n\n{chat_history[0]['parts'][0]['text']}"
                        else:
                            chat_history.insert(0, {"role": "user", "parts": [{"text": f"System: {content}"}]})
            
            # Run in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            
            def create_model():
                return self._genai_module.GenerativeModel(model)
            
            # Create the model
            model_obj = await loop.run_in_executor(None, create_model)
            
            # Check if we have chat history
            if history and isinstance(history, list):
                # Create a chat session
                def create_chat():
                    chat = model_obj.start_chat(history=chat_history)
                    return chat.send_message(content, stream=True, generation_config=params)

                # Send the message and get the streaming response
                response = await loop.run_in_executor(None, create_chat)
            else:
                # Generate content directly
                def generate_content():
                    return model_obj.generate_content(content, stream=True, generation_config=params)

                # Get the streaming response
                response = await loop.run_in_executor(None, generate_content)
            
            # Process the streaming response
            full_response = ""
            for chunk in response:
                if hasattr(chunk, 'text'):
                    full_response += chunk.text
                    yield chunk.text
                elif hasattr(chunk, 'parts'):
                    for part in chunk.parts:
                        # Check for thought part (Gemini 2.0+)
                        if hasattr(part, 'thought') and part.thought:
                            yield f"<<<THINKING>>>{part.text}"
                        elif hasattr(part, 'text'):
                            full_response += part.text
                            yield part.text
                        elif hasattr(part, 'executable_code'):
                             # Handle executable code as text for now
                             # Or could yield special tag if we want to handle code execution
                             pass

            logger.info(f"Gemini streaming complete. Total response length: {len(full_response)}")
            logger.debug(f"Full response: {full_response[:200]}...")

        except Exception as e:
            logger.error(f"Error generating text from Gemini (streaming): {e}", exc_info=True)
            yield f"Error: {e}"
    
    async def generate_complete(self, prompt: str, **kwargs) -> str:
        """
        Generate text from Gemini, returning the complete response

        Args:
            prompt: The prompt to send to the model
            **kwargs: Additional parameters to pass to the API

        Returns:
            Complete generated text
        """
        if not self._genai_module:
            logger.error("Google Generative AI module not imported. Please install the google-generativeai package.")
            return "Error: Google Generative AI module not imported. Please install the google-generativeai package."

        if not self.api_key:
            logger.error("Google API key not provided. Please provide a valid API key.")
            return "Error: Google API key not provided. Please provide a valid API key."

        try:
            # Prepare parameters
            model = kwargs.get("model", self.default_model)
            params = self.default_params.copy()
            params.update({k: v for k, v in kwargs.items() if k in self.default_params})

            logger.info(f"Gemini generate_complete - Model: {model}, Params: {params}")
            logger.debug(f"Prompt: {prompt[:100]}...")

            # Create the content
            content = prompt

            # Add system message if provided
            system_message = kwargs.get("system")
            if system_message:
                content = f"{system_message}\n\n{content}"
                logger.debug(f"System message added: {system_message[:50]}...")

            # Add chat history if provided
            history = kwargs.get("history") or kwargs.get("chat_history")
            chat_history = []
            if history and isinstance(history, list):
                logger.debug(f"Chat history provided with {len(history)} messages")
                # Convert history to Gemini format
                for msg in history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        chat_history.append({"role": "user", "parts": [{"text": content}]})
                    elif role == "assistant":
                        chat_history.append({"role": "model", "parts": [{"text": content}]})
                    elif role == "system":
                        # Add system message to the beginning of the first user message
                        if chat_history and chat_history[0]["role"] == "user":
                            chat_history[0]["parts"][0]["text"] = f"{content}\n\n{chat_history[0]['parts'][0]['text']}"
                        else:
                            chat_history.insert(0, {"role": "user", "parts": [{"text": f"System: {content}"}]})
            
            # Run in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            
            def create_model():
                return self._genai_module.GenerativeModel(model)
            
            # Create the model
            model_obj = await loop.run_in_executor(None, create_model)
            
            # Check if we have chat history
            if history and isinstance(history, list):
                # Create a chat session
                def create_chat():
                    chat = model_obj.start_chat(history=chat_history)
                    return chat.send_message(content, generation_config=params)

                # Send the message and get the response
                response = await loop.run_in_executor(None, create_chat)
            else:
                # Generate content directly
                def generate_content():
                    return model_obj.generate_content(content, generation_config=params)

                # Get the response
                response = await loop.run_in_executor(None, generate_content)
            
            # Extract the text from the response
            result = ""
            if hasattr(response, 'text'):
                result = response.text
            elif hasattr(response, 'parts'):
                result = ''.join(part.text for part in response.parts if hasattr(part, 'text'))
            else:
                result = "Error: Could not extract text from response"

            logger.info(f"Gemini response complete. Response length: {len(result)}")
            logger.debug(f"Response: {result[:200]}...")
            return result

        except Exception as e:
            logger.error(f"Error generating text from Gemini (complete): {e}", exc_info=True)
            return f"Error: {e}"
    
    @property
    def available_models(self) -> List[str]:
        """
        Get a list of available models for this provider
        
        Returns:
            List of model names
        """
        return [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.0-pro",
            "gemini-1.0-pro-vision"
        ]
    
    async def close(self):
        """
        Close the client
        """
        # Google Generative AI client doesn't have a close method
        pass


