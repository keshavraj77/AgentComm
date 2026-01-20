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

    @staticmethod
    def convert_openai_tools_to_gemini(openai_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert OpenAI-format tools to Gemini format

        OpenAI format: {"type": "function", "function": {...}}
        Gemini format: Just the function declaration {...}
        """
        gemini_tools = []
        for tool in openai_tools:
            if "function" in tool:
                # Extract just the function declaration
                gemini_tools.append(tool["function"])
            else:
                # Already in Gemini format or unknown format
                gemini_tools.append(tool)
        return gemini_tools

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
    
    async def generate(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> AsyncGenerator[str, None]:
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
                    return model_obj.generate_content(content, stream=True, generation_config=params, tools=tools)

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
    
    async def generate_complete(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs):
        """
        Generate text from Gemini, returning the complete response

        Args:
            prompt: The prompt to send to the model
            tools: Optional list of tool definitions
            **kwargs: Additional parameters including:
                - return_tool_calls: If True, returns Dict[str, Any] with 'content' and 'tool_calls'
                                     If False, returns str with just content

        Returns:
            Complete generated text (str) or structured response (dict) depending on return_tool_calls
        """
        if not self._genai_module:
            logger.error("Google Generative AI module not imported. Please install the google-generativeai package.")
            return "Error: Google Generative AI module not imported. Please install the google-generativeai package."

        if not self.api_key:
            logger.error("Google API key not provided. Please provide a valid API key.")
            return "Error: Google API key not provided. Please provide a valid API key."

        try:
            return_tool_calls = kwargs.get("return_tool_calls", False)
            
            # Prepare parameters
            model = kwargs.get("model", self.default_model)
            params = self.default_params.copy()
            params.update({k: v for k, v in kwargs.items() if k in self.default_params})

            logger.info(f"Gemini generate_complete - Model: {model}, Params: {params}")
            logger.debug(f"Prompt: {prompt[:100] if prompt else '(empty)'}...")

            # Convert tools from OpenAI format to Gemini format
            gemini_tools = None
            if tools and len(tools) > 0:
                gemini_tools = self.convert_openai_tools_to_gemini(tools)
                logger.info(f"Tools provided: {len(tools)} tools (converted to Gemini format)")
                logger.debug(f"First tool (OpenAI format): {json.dumps(tools[0], indent=2)}")
                logger.debug(f"First tool (Gemini format): {json.dumps(gemini_tools[0], indent=2)}")

            # Create the content
            # For tool calling loop, prompt may be empty (all context in history)
            content = prompt if prompt else ""

            # Add system message if provided
            system_message = kwargs.get("system")
            if system_message and content:
                content = f"{system_message}\n\n{content}"
                logger.debug(f"System message added: {system_message[:50]}...")
            elif system_message and not content:
                # Empty prompt with system message (tool calling loop)
                # Use a minimal prompt to avoid empty message
                content = "Please continue."
                logger.debug("Using minimal prompt for tool calling continuation")

            # Add chat history if provided
            history = kwargs.get("history") or kwargs.get("chat_history")
            chat_history = []
            if history and isinstance(history, list):
                logger.debug(f"Chat history provided with {len(history)} messages")
                # Convert history to Gemini format
                for msg in history:
                    role = msg.get("role", "user")
                    msg_content = msg.get("content", "")
                    
                    # Handle tool result messages
                    if role == "tool":
                        # Gemini expects function responses in a specific format
                        chat_history.append({
                            "role": "function",
                            "parts": [{
                                "function_response": {
                                    "name": msg.get("name", ""),
                                    "response": {"result": msg_content}
                                }
                            }]
                        })
                    # Handle assistant messages with tool calls
                    elif role == "assistant":
                        parts = []
                        if msg_content:
                            parts.append({"text": msg_content})
                        
                        # Add function calls if present
                        if "tool_calls" in msg:
                            for tool_call in msg["tool_calls"]:
                                if tool_call.get("type") == "function":
                                    func = tool_call.get("function", {})
                                    parts.append({
                                        "function_call": {
                                            "name": func.get("name", ""),
                                            "args": json.loads(func.get("arguments", "{}"))
                                        }
                                    })
                        
                        chat_history.append({"role": "model", "parts": parts})
                    elif role == "user":
                        chat_history.append({"role": "user", "parts": [{"text": msg_content}]})
                    elif role == "system":
                        # Add system message to the beginning of the first user message
                        if chat_history and chat_history[0]["role"] == "user":
                            chat_history[0]["parts"][0]["text"] = f"{msg_content}\n\n{chat_history[0]['parts'][0]['text']}"
                        else:
                            chat_history.insert(0, {"role": "user", "parts": [{"text": f"System: {msg_content}"}]})
            
            # Run in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            
            def create_model():
                return self._genai_module.GenerativeModel(model)
            
            # Create the model
            model_obj = await loop.run_in_executor(None, create_model)
            
            # Check if we have chat history
            if history and isinstance(history, list):
                logger.debug(f"Using chat history with {len(chat_history)} messages")
                if logger.isEnabledFor(logging.DEBUG):
                    for i, msg in enumerate(chat_history[:3]):  # Log first 3
                        logger.debug(f"  History[{i}]: role={msg.get('role')}, parts={len(msg.get('parts', []))}")

                # Create a chat session
                def create_chat():
                    chat = model_obj.start_chat(history=chat_history)
                    # Pass tools to send_message if provided
                    if gemini_tools and len(gemini_tools) > 0:
                        logger.debug(f"Sending message with {len(gemini_tools)} tools")
                        return chat.send_message(content, generation_config=params, tools=gemini_tools)
                    else:
                        return chat.send_message(content, generation_config=params)

                # Send the message and get the response
                response = await loop.run_in_executor(None, create_chat)
            else:
                # Generate content directly
                def generate_content():
                    # Pass converted Gemini tools
                    if gemini_tools and len(gemini_tools) > 0:
                        return model_obj.generate_content(content, generation_config=params, tools=gemini_tools)
                    else:
                        return model_obj.generate_content(content, generation_config=params)

                # Get the response
                response = await loop.run_in_executor(None, generate_content)
            
            # Extract the text and tool calls from the response
            text_content = ""
            tool_calls = []
            
            if hasattr(response, 'text'):
                text_content = response.text
            elif hasattr(response, 'parts'):
                for part in response.parts:
                    if hasattr(part, 'text'):
                        text_content += part.text
                    elif hasattr(part, 'function_call'):
                        # Convert Gemini function call to OpenAI format
                        func_call = part.function_call
                        tool_calls.append({
                            "id": f"call_{len(tool_calls)}",
                            "type": "function",
                            "function": {
                                "name": func_call.name,
                                "arguments": json.dumps(dict(func_call.args))
                            }
                        })
            
            # Return structured response if tool calls requested
            if return_tool_calls:
                return {
                    "content": text_content,
                    "tool_calls": tool_calls
                }
            
            # Otherwise return just content
            if text_content:
                logger.info(f"Gemini response complete. Response length: {len(text_content)}")
                logger.debug(f"Response: {text_content[:200]}...")
                return text_content
            
            # If only tool calls, indicate that
            if tool_calls:
                return "[Tool calls requested - use return_tool_calls=True to access them]"
            
            if return_tool_calls:
                return {"content": "Error: Could not extract content from response", "tool_calls": []}
            return "Error: Could not extract content from response"

        except Exception as e:
            logger.error(f"Error generating text from Gemini (complete): {e}")

            # Special handling for function call errors
            if "MALFORMED_FUNCTION_CALL" in str(e):
                logger.error("Gemini reported a malformed function call. This may be due to:")
                logger.error("  1. Tool format incompatibility (OpenAI vs Gemini format)")
                logger.error("  2. Invalid function arguments")
                logger.error("  3. Model limitations with function calling")
                if tools:
                    logger.debug(f"Tools provided: {len(tools)} tools")
                    for tool in tools[:3]:  # Log first 3 tools
                        logger.debug(f"  Tool: {tool.get('function', {}).get('name', 'unknown')}")
            error_msg = f"Error: {e}"
            if kwargs.get("return_tool_calls", False):
                return {"content": error_msg, "tool_calls": []}
            return error_msg
    
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


