#!/usr/bin/env python3
"""
Script to push git commits with timed intervals
Pushes remaining commits every 10-9-10-9... minutes alternating pattern
"""

import subprocess
import time
from datetime import datetime

def run_git_command(command):
    """Run a git command and return the result"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def get_unpushed_commits():
    """Get list of unpushed commits"""
    success, output = run_git_command("git log origin/main..HEAD --oneline")
    if success:
        commits = [line for line in output.strip().split('\n') if line]
        commits.reverse()  # Reverse to get oldest first
        return commits
    return []

def push_next_commit(commit_hash):
    """Push up to the specified commit"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Pushing commit: {commit_hash}")
    success, output = run_git_command(f"git push origin {commit_hash}:main")
    if success:
        print(f"✓ Successfully pushed: {commit_hash}")
        return True
    else:
        print(f"✗ Failed to push: {commit_hash}")
        print(f"Error: {output}")
        return False

def main():
    print("=" * 70)
    print("Git Commit Pusher - Timed Interval Push")
    print("=" * 70)

    # Get unpushed commits
    unpushed = get_unpushed_commits()

    if not unpushed:
        print("\nNo unpushed commits found!")
        return

    print(f"\nFound {len(unpushed)} unpushed commits:")
    for i, commit in enumerate(unpushed, 1):
        print(f"  {i}. {commit}")

    # Confirm before starting
    response = input("\nDo you want to start pushing these commits? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Aborted.")
        return

    # Alternating intervals: 10, 9, 10, 9, ... minutes
    intervals = []
    for i in range(len(unpushed)):
        intervals.append(10 if i % 2 == 0 else 9)

    print(f"\nStarting timed push process...")
    print(f"Intervals (in minutes): {intervals}")
    print("=" * 70)

    # Push commits with intervals
    for i, commit in enumerate(unpushed):
        commit_hash = commit.split()[0]

        # Push the commit
        success = push_next_commit(commit_hash)

        if not success:
            print("\n⚠ Push failed. Stopping process.")
            break

        # Wait for interval before next push (except for last commit)
        if i < len(unpushed) - 1:
            wait_minutes = intervals[i]
            print(f"\n⏳ Waiting {wait_minutes} minutes before next push...")
            print(f"Next push at: {datetime.now().strftime('%H:%M:%S')} + {wait_minutes} min")

            # Wait in 1-minute intervals to show progress
            for minute in range(wait_minutes):
                time.sleep(60)
                remaining = wait_minutes - minute - 1
                if remaining > 0:
                    print(f"   {remaining} minute(s) remaining...")

    print("\n" + "=" * 70)
    print("✓ All commits pushed successfully!")
    print("=" * 70)

if __name__ == "__main__":
    main()
