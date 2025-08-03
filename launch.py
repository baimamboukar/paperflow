#!/usr/bin/env python3
"""
Paperflow Launcher
Launches the web configurator interface
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Launch the web configurator."""
    try:
        # Run the web configurator
        configurator_path = Path(__file__).parent / "web-configurator" / "server.py"
        print(f"🌐 Starting Paperflow web configurator...")
        print(f"🌐 Open http://localhost:8113 in your browser")
        
        result = subprocess.run([sys.executable, str(configurator_path)], 
                              cwd=configurator_path.parent)
        return result.returncode
        
    except KeyboardInterrupt:
        print("\n👋 Paperflow configurator stopped")
        return 0
    except Exception as e:
        print(f"❌ Error starting configurator: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())