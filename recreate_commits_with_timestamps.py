#!/usr/bin/env python3
"""
Script to recreate git commits with custom timestamps
Recreates commits from yesterday 10 PM IST to today 7:30 AM IST with intervals
"""

import subprocess
import sys
from datetime import datetime, timedelta

# Commit data (title|||body)
COMMITS = [
    {
        "title": "Initial project setup",
        "body": "Add core project configuration files including .gitignore, setup.py, and package structure for AgentComm - an A2A protocol client with multi-LLM integration support.",
        "files": [".gitignore", "setup.py", "agentcomm/requirements.txt", "agentcomm/__init__.py", "agentcomm/setup.py"]
    },
    {
        "title": "Add core configuration system",
        "body": "Implement configuration management with settings storage and config store for managing application preferences, API keys, and agent/LLM configurations.",
        "files": ["agentcomm/config/"]
    },
    {
        "title": "Add core session and context management",
        "body": "Implement session manager for handling agent/LLM sessions, config store for persistent settings, and context manager for conversation tracking.",
        "files": ["agentcomm/core/"]
    },
    {
        "title": "Add LLM provider infrastructure",
        "body": "Implement abstract LLM provider interface, router for managing multiple providers, and configuration system for LLM settings.",
        "files": ["agentcomm/llm/__init__.py", "agentcomm/llm/llm_provider.py", "agentcomm/llm/llm_router.py", "agentcomm/llm/llm_config.py", "agentcomm/llm/providers/__init__.py"]
    },
    {
        "title": "Add LLM provider implementations",
        "body": "Implement concrete providers for OpenAI, Google Gemini, Anthropic Claude, and local LLM support with streaming capabilities.",
        "files": ["agentcomm/llm/providers/openai.py", "agentcomm/llm/providers/gemini.py", "agentcomm/llm/providers/anthropic.py", "agentcomm/llm/providers/local.py"]
    },
    {
        "title": "Add LLM chat history management",
        "body": "Implement chat history storage and retrieval for LLM conversations with SQLite backend.",
        "files": ["agentcomm/llm/chat_history.py"]
    },
    {
        "title": "Add agent registry and discovery",
        "body": "Implement agent registry for managing A2A agents and discovery service for fetching agent capabilities from endpoints.",
        "files": ["agentcomm/agents/__init__.py", "agentcomm/agents/agent_registry.py", "agentcomm/agents/agent_discovery.py"]
    },
    {
        "title": "Add A2A protocol implementation",
        "body": "Implement A2A protocol client for JSON-RPC communication with streaming support and agent communication manager.",
        "files": ["agentcomm/agents/a2a_client.py", "agentcomm/agents/agent_comm.py"]
    },
    {
        "title": "Add webhook handler for async notifications",
        "body": "Implement FastAPI-based webhook server for receiving push notifications from A2A agents during asynchronous processing.",
        "files": ["agentcomm/agents/webhook_handler.py"]
    },
    {
        "title": "Add UI foundation",
        "body": "Implement PyQt6-based main window and chat widget for message display and interaction with streaming support.",
        "files": ["agentcomm/ui/__init__.py", "agentcomm/ui/main_window.py", "agentcomm/ui/chat_widget.py"]
    },
    {
        "title": "Add UI components",
        "body": "Implement agent selector for switching between agents/LLMs and settings dialog for API key and configuration management.",
        "files": ["agentcomm/ui/agent_selector.py", "agentcomm/ui/settings_dialog.py"]
    },
    {
        "title": "Add application entry point",
        "body": "Implement main entry point for AgentComm application with initialization of core components and PyQt6 event loop.",
        "files": ["agentcomm/main.py"]
    },
    {
        "title": "Add documentation",
        "body": "Add README with project overview and usage instructions.",
        "files": ["agentcomm/README.md"]
    }
]

def run_command(command, check=True):
    """Run a shell command"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=check
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def calculate_timestamps():
    """Calculate timestamps from yesterday 10 PM IST to today 7:30 AM IST"""
    # Working with local system time (assuming it's set to IST)

    # End time: Today at 7:30 AM
    now = datetime.now()
    end_time = now.replace(hour=7, minute=30, second=0, microsecond=0)

    # Start time: Yesterday at 10:00 PM (9.5 hours before 7:30 AM)
    start_time = end_time - timedelta(hours=9, minutes=30)

    # Calculate intervals (alternating 10 and 9 minutes backward from end)
    # Total 13 commits, so 12 intervals needed
    timestamps = [end_time]

    current_time = end_time
    for i in range(12):
        # Going backward: subtract intervals (alternating 9, 10, 9, 10...)
        interval = 9 if i % 2 == 0 else 10
        current_time = current_time - timedelta(minutes=interval)
        timestamps.insert(0, current_time)

    return timestamps

def recreate_commits():
    """Recreate all commits with new timestamps"""
    print("=" * 70)
    print("Git Commit Recreation with Custom Timestamps")
    print("=" * 70)

    # Calculate timestamps
    timestamps = calculate_timestamps()

    print(f"\nWill recreate {len(COMMITS)} commits with following timestamps:")
    print(f"Start: {timestamps[0].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"End:   {timestamps[-1].strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    for i, (commit, ts) in enumerate(zip(COMMITS, timestamps), 1):
        print(f"  {i}. {ts.strftime('%Y-%m-%d %H:%M:%S')} - {commit['title']}")

    # Warning
    print("\n" + "!" * 70)
    print("WARNING: This will reset your branch and recreate all commits!")
    print("!" * 70)
    response = input("\nDo you want to proceed? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Aborted.")
        return

    # Check if we have uncommitted changes
    success, output = run_command("git status --porcelain", check=False)
    if success and output.strip():
        print("\n⚠ You have uncommitted changes. Please commit or stash them first.")
        return

    # Get current branch
    success, current_branch = run_command("git branch --show-current")
    if not success:
        print("Failed to get current branch")
        return
    current_branch = current_branch.strip()

    # Create a temporary branch to save current state
    print(f"\n📦 Saving current state...")
    run_command("git branch -D temp_backup", check=False)  # Delete if exists
    run_command("git branch temp_backup")

    # Go back to empty state (before any commits)
    print(f"\n🔄 Resetting to empty repository...")
    success, output = run_command("git update-ref -d HEAD")
    if not success:
        print(f"Failed to reset: {output}")
        return

    # Clear the index
    run_command("git rm -rf .", check=False)

    print("✓ Reset complete\n")

    # Recreate ALL commits with custom timestamps (including first one)
    for i, (commit, timestamp) in enumerate(zip(COMMITS, timestamps), 1):
        print(f"[{i}/{len(COMMITS)}] Creating commit: {commit['title']}")

        # Restore files from temp_backup
        for file in commit['files']:
            run_command(f'git checkout temp_backup -- "{file}"', check=False)
            run_command(f'git add "{file}"', check=False)

        # Create commit with custom timestamp
        commit_message = f"{commit['title']}\n\n{commit['body']}"
        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')

        # Set both author and committer date
        env_vars = f'GIT_AUTHOR_DATE="{timestamp_str}" GIT_COMMITTER_DATE="{timestamp_str}"'

        success, output = run_command(
            f'{env_vars} git commit -m "{commit_message}"',
            check=False
        )

        if success:
            print(f"  ✓ Committed at {timestamp_str}")
        else:
            print(f"  ✗ Failed: {output}")
            return

    print("\n" + "=" * 70)
    print("✓ All commits recreated successfully!")
    print("=" * 70)

    # Clean up temp branch
    run_command("git branch -D temp_backup", check=False)

    print("\n📋 Next steps:")
    print("  1. Review the commit history: git log --format='%ai %s'")
    print("  2. Force push to remote: git push --force origin main")
    print("     (This will overwrite the first commit with new timestamp!)")

if __name__ == "__main__":
    recreate_commits()
