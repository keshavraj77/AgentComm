
import json
import os
import sys
from pathlib import Path

# Paths
base_dir = Path("/Users/keshavraj/personal/AgentComm")
settings_file = base_dir / "agentcomm/config/settings.json"

print(f"Checking settings file: {settings_file}")

if settings_file.exists():
    try:
        with open(settings_file, "r") as f:
            settings = json.load(f)
        print("Settings loaded:")
        print(json.dumps(settings.get("ngrok", {}), indent=2))
        
        ngrok_config = settings.get("ngrok", {})
        if not ngrok_config.get("enabled"):
            print("WARNING: ngrok is NOT enabled in settings.")
        else:
            print("ngrok is enabled.")
            
        if not ngrok_config.get("auth_token"):
            print("WARNING: ngrok auth_token is missing.")
        else:
            print("ngrok auth_token is present.")
            
    except Exception as e:
        print(f"Error reading settings file: {e}")
else:
    print("Settings file does not exist. Using defaults (ngrok disabled).")

# Check pyngrok installation
try:
    import pyngrok
    from pyngrok import ngrok, conf
    print(f"pyngrok version: {pyngrok.__version__}")
    print("pyngrok is installed.")
except ImportError:
    print("WARNING: pyngrok is NOT installed.")

