#!/usr/bin/env python3
"""
Progress Calculator for Kubernetes Interview Prep

Reads PROGRESS.md, calculates completion percentage based on modules marked "Done",
and updates the progress bar and percentage at the top of the file.

Usage:
    python scripts/progress.py
"""

import re
import sys
from pathlib import Path


def parse_progress_md(content):
    """Parse PROGRESS.md and extract module completion status."""
    modules = []
    
    # Find the table rows (skip header and separator)
    table_pattern = r'\|\s*(\d+)\s*\|[^|]+\|\s*(\d+)%\s*\|\s*([^|]+?)\s*\|'
    
    for match in re.finditer(table_pattern, content):
        module_num = match.group(1)
        weight = int(match.group(2))
        status = match.group(3).strip()
        
        modules.append({
            'number': module_num,
            'weight': weight,
            'status': status,
            'is_done': status.lower() == 'done'
        })
    
    return modules


def calculate_progress(modules):
    """Calculate total progress percentage."""
    total_weight = sum(m['weight'] for m in modules)
    completed_weight = sum(m['weight'] for m in modules if m['is_done'])
    
    if total_weight == 0:
        return 0
    
    return int((completed_weight / total_weight) * 100)


def generate_progress_bar(percentage, width=20):
    """Generate a text progress bar."""
    filled = int((percentage / 100) * width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {percentage}/100"


def update_progress_md(file_path):
    """Read, calculate, and update PROGRESS.md."""
    
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        sys.exit(1)
    
    content = file_path.read_text()
    
    # Parse modules
    modules = parse_progress_md(content)
    
    if not modules:
        print("Error: No modules found in PROGRESS.md")
        sys.exit(1)
    
    # Calculate progress
    percentage = calculate_progress(modules)
    progress_bar = generate_progress_bar(percentage)
    
    # Update the percentage line
    content = re.sub(
        r'\*\*Overall Completion: \d+%\*\*',
        f'**Overall Completion: {percentage}%**',
        content
    )
    
    # Update the progress bar
    content = re.sub(
        r'```\n\[.*?\] \d+/100\n```',
        f'```\n{progress_bar}\n```',
        content,
        flags=re.DOTALL
    )
    
    # Write back
    file_path.write_text(content)
    
    # Print summary
    print(f"✓ Progress updated: {percentage}% complete")
    print(f"  {progress_bar}")
    
    completed_modules = [m for m in modules if m['is_done']]
    if completed_modules:
        print(f"\n  Completed modules: {', '.join(m['number'] for m in completed_modules)}")
    else:
        print("\n  No modules completed yet. Keep going!")


def main():
    """Main entry point."""
    repo_root = Path(__file__).parent.parent
    progress_file = repo_root / "PROGRESS.md"
    
    try:
        update_progress_md(progress_file)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
