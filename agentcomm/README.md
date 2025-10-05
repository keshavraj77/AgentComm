# A2A Client with Base LLM Integration

A Python-based application designed to interact with A2A (Agent-to-Agent) protocol-compliant agents while also providing direct access to various Large Language Models (LLMs).

## Features

- **A2A Protocol Support**: Full implementation of the A2A protocol including streaming responses and push notifications
- **Multi-Agent Support**: Ability to interact with multiple agents and switch between them
- **Base LLM Integration**: Direct access to multiple LLM providers (OpenAI, Google Gemini, Anthropic, etc.)
- **Minimal UI**: Clean, intuitive interface focused on the chat experience
- **Hybrid Agent Discovery**: Built-in default agents plus ability to add custom agents

## Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Install the package:
   ```
   pip install -e .
   ```

## Usage

Run the client:
```
a2a_client
```

Or run directly:
```
python -m a2a_client.main
```

## Running and Testing

### Prerequisites

Before running the application, make sure you have:

1. Python 3.8 or higher installed
2. PyQt6 installed (`pip install PyQt6`)
3. API keys for any LLM providers you want to use (OpenAI, Google Gemini, Anthropic)

### Configuration

1. Set up your LLM API keys in `a2a_client/config/llm_config.json`:
   ```json
   {
     "default_provider": "OpenAI",
     "providers": {
       "OpenAI": {
         "api_key": "your-openai-api-key",
         "default_model": "gpt-3.5-turbo",
         "temperature": 0.7
       },
       "Google Gemini": {
         "api_key": "your-gemini-api-key",
         "default_model": "gemini-1.5-pro",
         "temperature": 0.7
       },
       "Anthropic Claude": {
         "api_key": "your-anthropic-api-key",
         "default_model": "claude-3-sonnet-20240229",
         "temperature": 0.7
       },
       "Local LLM": {
         "host": "http://localhost:11434",
         "default_model": "llama3",
         "temperature": 0.7
       }
     }
   }
   ```

2. Configure your agents in `a2a_client/config/agents.json`:
   ```json
   [
     {
       "id": "example-agent",
       "name": "Example Agent",
       "description": "An example A2A agent",
       "url": "https://example.com/agent",
       "capabilities": {
         "streaming": true,
         "push_notifications": true,
         "file_upload": false,
         "tool_use": true
       },
       "authentication": {
         "auth_type": "bearer",
         "token": "your-auth-token"
       },
       "default_input_modes": ["text/plain"],
       "default_output_modes": ["text/plain"],
       "is_default": true,
       "is_built_in": true
     }
   ]
   ```

### Running the Application

1. From the project root directory, run:
   ```
   python -m a2a_client.main
   ```

2. The application will start and display the main window with:
   - Agent selector panel on the left
   - Chat interface on the right
   - Menu and toolbar at the top

### Testing the Application

#### Testing LLM Integration

1. Select an LLM provider from the left panel
2. Type a message in the input box and click "Send"
3. The LLM should respond with a generated message

#### Testing Agent Communication

1. Select an agent from the left panel
2. Type a message in the input box and click "Send"
3. The agent should respond according to its capabilities

#### Testing Settings

1. Click on "Settings" in the menu or toolbar
2. Navigate through the tabs to configure agents, LLMs, and general settings
3. Make changes and click "Apply" or "OK" to save them

### Troubleshooting

If you encounter issues:

1. Check the terminal output for error messages
2. Verify your API keys are correct
3. Ensure the agent URLs are accessible
4. Check that PyQt6 is properly installed

## Configuration

Configuration files are stored in the `config` directory:
- `agents.json`: Registry of available agents
- `llm_config.json`: Configuration for LLM providers

## License

This project is licensed under the MIT License - see the LICENSE file for details.