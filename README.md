# AgentComm - A2A Client with Multi-LLM Integration

A modern Python-based application for seamless interaction with A2A (Agent-to-Agent) protocol-compliant agents and direct access to multiple Large Language Models (LLMs). Built with PyQt6 for a clean, intuitive user experience.

## 🌟 Key Features

### A2A Protocol Support
- **Full A2A Protocol Implementation**: Complete support for the Agent-to-Agent communication protocol
- **Streaming Responses**: Real-time streaming of agent responses for better interactivity
- **Push Notifications**: Receive real-time updates from agents via webhooks (with ngrok support)
- **Task State Management**: Track and manage long-running agent tasks
- **Multi-Agent Support**: Interact with multiple agents and switch between them seamlessly

### LLM Integration
- **Multi-Provider Support**: Direct access to multiple LLM providers:
  - OpenAI (GPT-3.5, GPT-4, etc.)
  - Google Gemini (Gemini 1.5 Pro, etc.)
  - Anthropic Claude (Claude 3 Sonnet, etc.)
  - Local LLMs (via Ollama or similar)
- **Flexible Configuration**: Easy API key management and model selection
- **Provider Switching**: Switch between different LLM providers on the fly

### Modern UI/UX
- **Clean Interface**: Minimal, focused design centered on the chat experience
- **Thread Management**: Organize conversations into separate threads (max 4 per agent/LLM)
- **Interactive Walkthrough**: First-time user onboarding with step-by-step guidance
- **Agent Discovery**: Built-in default agents plus ability to add custom agents
- **Settings Dialog**: Comprehensive configuration for agents, LLMs, and app preferences

### Advanced Capabilities
- **Webhook Handler**: Built-in FastAPI server for receiving push notifications
- **ngrok Integration**: Secure tunneling for webhook access from remote agents
- **Session Management**: Persistent chat history and thread organization
- **Context Management**: Intelligent context handling for multi-turn conversations
- **Message Routing**: Smart routing between agents and LLMs

## 📋 Prerequisites

- Python 3.8 or higher
- PyQt6
- API keys for desired LLM providers (OpenAI, Google Gemini, Anthropic)
- (Optional) ngrok account for push notification support

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd AgentComm
```

### 2. Install Dependencies
```bash
pip install -r agentcomm/requirements.txt
```

### 3. Install the Package
```bash
pip install -e .
```

## 🎯 Quick Start

### Launch the Application
```bash
a2a_client
```

Or run directly:
```bash
python -m agentcomm.main
```

### First-Time Setup

When you first launch AgentComm, you'll see an **interactive walkthrough** that guides you through:
- Agent selection
- Thread management
- Chat interface
- Settings configuration
- Advanced features

You can skip the walkthrough and access it later from **Help → Show Walkthrough**.

## ⚙️ Configuration

### LLM Configuration

Configure your LLM providers in `agentcomm/config/llm_config.json`:

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

### Agent Configuration

Configure agents in `agentcomm/config/agents.json`:

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

### Push Notifications with ngrok

To enable push notifications from remote agents:

1. **Install pyngrok**:
   ```bash
   pip install pyngrok
   ```

2. **Get ngrok Auth Token**:
   - Sign up at [ngrok.com](https://ngrok.com)
   - Copy your auth token from the dashboard

3. **Configure in AgentComm**:
   - Open Settings (gear icon)
   - Go to "General" tab
   - In "Push Notifications (ngrok)" section:
     - ✅ Enable push notifications via ngrok
     - Paste your auth token
     - Select your region (us, eu, ap, au, sa, jp, in)
   - Click "Apply"

4. **Verify Setup**:
   Check the logs for:
   ```
   INFO - ngrok tunnel established: https://xxxx-xx-xx-xx-xx.ngrok-free.app
   ```

## 💡 Usage Guide

### Working with Agents

1. **Select an Agent**: Click on an agent in the left panel
2. **Create a Thread**: Click "New Thread" to start a new conversation
3. **Send Messages**: Type your message and click "Send" or press Enter
4. **View Responses**: Agent responses appear in the chat area with streaming support
5. **Manage Threads**: Rename or delete threads as needed (max 4 per agent)

### Working with LLMs

1. **Select an LLM Provider**: Choose from OpenAI, Gemini, Claude, or Local LLM
2. **Start Chatting**: Send messages just like with agents
3. **Switch Providers**: Change providers anytime from the left panel
4. **Configure Models**: Adjust settings in the Settings dialog

### Thread Management

- **Create Thread**: Click "New Thread" button
- **Switch Thread**: Click on any thread in the list
- **Rename Thread**: Right-click → Rename (or use thread menu)
- **Delete Thread**: Right-click → Delete (or use thread menu)
- **Thread Limit**: Maximum 4 threads per agent/LLM

### Advanced Features

- **Clear Chat**: Clear current thread's messages without deleting the thread
- **Refresh Agents**: Update the list of available agents
- **Settings**: Configure agents, LLMs, and general preferences
- **Walkthrough**: Access the interactive guide from Help menu

## 🔧 Architecture

### Core Components

- **SessionManager**: Manages communication between UI and backend
- **AgentComm**: Handles A2A protocol communication with agents
- **LLMRouter**: Routes requests to appropriate LLM providers
- **WebhookHandler**: FastAPI server for receiving push notifications
- **NgrokManager**: Manages ngrok tunnels for secure webhook access
- **Thread**: Represents individual conversation contexts
- **ChatHistory**: Manages message history and context

### UI Components

- **MainWindow**: Primary application window
- **ChatWidget**: Chat interface with message display and input
- **AgentSelector**: Agent and LLM selection panel
- **SettingsDialog**: Configuration interface
- **WalkthroughOverlay**: Interactive onboarding system

## 📚 Documentation

- **[Push Notification Implementation](PUSH_NOTIFICATION_IMPLEMENTATION.md)**: Detailed guide on push notification setup
- **[ngrok Push Notifications](NGROK_PUSH_NOTIFICATIONS.md)**: Complete ngrok integration documentation
- **[User Walkthrough Guide](USER_WALKTHROUGH_GUIDE.md)**: Comprehensive user guide and tips
- **[Webhook Notification Flow](WEBHOOK_NOTIFICATION_FLOW.md)**: Technical details on webhook handling

## 🔐 Security Features

### Authentication
- **Multiple Auth Schemes**: Support for Bearer tokens, Basic auth, and API keys
- **Token Validation**: Webhook handler validates tokens before processing
- **Secure Storage**: API keys stored in configuration files (not in code)

### Network Security
- **HTTPS Enforcement**: ngrok provides automatic HTTPS for webhooks
- **Token-Based Auth**: Unique tokens generated per request
- **Credential Parsing**: Proper handling of authentication headers

## 🐛 Troubleshooting

### Common Issues

**LLM not responding:**
- Verify API key is correct in Settings
- Check internet connection
- Ensure the selected model is available

**Agent connection failed:**
- Verify agent URL is accessible
- Check authentication credentials
- Ensure agent supports A2A protocol

**Push notifications not working:**
- Enable ngrok in Settings
- Verify ngrok auth token is correct
- Check that agent supports push notifications
- Review logs for ngrok tunnel URL

**Walkthrough not appearing:**
- Delete `~/.agentcomm/user_preferences.json` to reset
- Or access manually from Help → Show Walkthrough

### Debug Mode

Enable detailed logging by setting environment variable:
```bash
export LOG_LEVEL=DEBUG
a2a_client
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.


## 🙏 Acknowledgments

- Built on the A2A (Agent-to-Agent) protocol specification
- Uses PyQt6 for the user interface
- Integrates with multiple LLM providers (OpenAI, Google, Anthropic)
- ngrok for secure webhook tunneling

## 📞 Support

For help and support:
- Check the interactive walkthrough (Help → Show Walkthrough)
- Review documentation files in the repository
- Open an issue on GitHub

---

**Version**: 1.0  
**Last Updated**: 2026-01-12