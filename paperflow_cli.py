#!/usr/bin/env python3
"""
Paperflow CLI - Real Overleaf Integration
Handles PyOverleaf authentication and project management
"""

import os
import sys
import json
import subprocess
import tempfile
import webbrowser
from pathlib import Path
import argparse
from datetime import datetime
from typing import List, Dict, Optional

try:
    import pyoverleaf
except ImportError:
    print("❌ PyOverleaf not installed. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "git+https://github.com/jkulhanek/pyoverleaf.git"])
    import pyoverleaf

class PaperflowCLI:
    def __init__(self):
        self.config_dir = Path.home() / ".paperflow"
        self.config_file = self.config_dir / "config.json"
        self.auth_file = self.config_dir / "auth.json"
        self.config_dir.mkdir(exist_ok=True)
        
        self.api = None
        self.projects = []
        
    def load_auth(self) -> bool:
        """Load existing PyOverleaf authentication"""
        if not self.auth_file.exists():
            return False
            
        try:
            with open(self.auth_file, 'r') as f:
                auth_data = json.load(f)
            
            # Try to initialize API with saved session
            self.api = pyoverleaf.Api()
            # Note: PyOverleaf uses browser cookies, so we need to check if still valid
            return True
        except Exception as e:
            print(f"⚠️ Existing auth invalid: {e}")
            return False
    
    def authenticate(self) -> bool:
        """Authenticate with Overleaf using PyOverleaf"""
        print("🔐 Authenticating with Overleaf...")
        print("\n📝 PyOverleaf uses your existing browser session.")
        print("   Please follow these steps:\n")
        print("   1. Open Chrome or Firefox")
        print("   2. Go to https://www.overleaf.com and log in")
        print("   3. Keep the browser open")
        print("   4. Press Enter here to continue...")
        
        input()
        
        try:
            self.api = pyoverleaf.Api()
            
            # This reads cookies from your browser
            print("\n🔍 Reading authentication from browser cookies...")
            self.api.login_from_browser()
            
            # Test authentication by getting projects
            print("📂 Fetching your projects...")
            test_projects = self.api.get_projects()
            
            print(f"\n✅ Authentication successful! Found {len(test_projects)} projects")
            
            # Save auth status
            auth_data = {
                "authenticated": True,
                "timestamp": str(datetime.now().isoformat()),
                "project_count": len(test_projects)
            }
            
            with open(self.auth_file, 'w') as f:
                json.dump(auth_data, f, indent=2)
                
            return True
            
        except Exception as e:
            print(f"\n❌ Authentication failed: {e}")
            print("\n💡 Troubleshooting tips:")
            print("   - Make sure you're logged into Overleaf in Chrome or Firefox")
            print("   - Try logging out and back in to Overleaf")
            print("   - Ensure cookies are enabled in your browser")
            print("   - PyOverleaf only supports Chrome and Firefox")
            return False
    
    def get_projects(self) -> List[Dict]:
        """Get list of user's Overleaf projects"""
        if not self.api:
            if not self.load_auth():
                print("❌ Not authenticated. Run 'paperflow auth' first")
                return []
        
        try:
            print("📂 Fetching your Overleaf projects...")
            raw_projects = self.api.get_projects()
            
            self.projects = []
            for project in raw_projects:
                # Convert to our format
                project_data = {
                    "id": str(project.id),
                    "name": project.name,
                    "owner": getattr(project, 'owner', 'Unknown'),
                    "last_modified": getattr(project, 'last_modified', 'Unknown'),
                    "url": f"https://www.overleaf.com/project/{project.id}"
                }
                self.projects.append(project_data)
            
            print(f"✅ Found {len(self.projects)} projects")
            return self.projects
            
        except Exception as e:
            print(f"❌ Failed to fetch projects: {e}")
            print("💡 Try running 'paperflow auth' to re-authenticate")
            return []
    
    def list_projects(self):
        """List all user projects"""
        projects = self.get_projects()
        
        if not projects:
            print("No projects found")
            return
            
        print("\n📋 Your Overleaf Projects:")
        print("-" * 80)
        
        for i, project in enumerate(projects, 1):
            print(f"{i:2d}. {project['name']}")
            print(f"    ID: {project['id']}")
            print(f"    Owner: {project['owner']}")
            print(f"    Modified: {project['last_modified']}")
            print(f"    URL: {project['url']}")
            print()
    
    def download_project(self, project_id: str, output_dir: Optional[str] = None) -> bool:
        """Download a specific project"""
        if not self.api:
            if not self.load_auth():
                print("❌ Not authenticated. Run 'paperflow auth' first")
                return False
        
        try:
            print(f"📥 Downloading project {project_id}...")
            
            # Create output directory
            if output_dir:
                output_path = Path(output_dir)
            else:
                output_path = Path.cwd() / f"overleaf-project-{project_id}"
            
            output_path.mkdir(exist_ok=True)
            
            # Get project files
            project_io = pyoverleaf.ProjectIO(self.api, project_id)
            
            # List all files
            files = list(project_io.listdir(''))
            print(f"📁 Found {len(files)} files")
            
            # Download each file
            downloaded = 0
            for file_entity in files:
                if hasattr(file_entity, 'name') and not file_entity.name.startswith('.'):
                    try:
                        file_path = output_path / file_entity.name
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Read file content
                        content = project_io.read_file(file_entity.name)
                        
                        # Write to local file
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        print(f"  ✅ {file_entity.name}")
                        downloaded += 1
                        
                    except Exception as e:
                        print(f"  ❌ Failed to download {file_entity.name}: {e}")
            
            print(f"\n✅ Downloaded {downloaded} files to {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False
    
    def init_project(self):
        """Initialize a new Paperflow project"""
        print("🚀 Initializing Paperflow project...")
        
        # Check authentication
        if not self.load_auth():
            print("🔐 Authentication required")
            if not self.authenticate():
                print("❌ Authentication failed. Cannot continue.")
                return False
        
        # Get projects
        projects = self.get_projects()
        if not projects:
            print("❌ No projects found")
            return False
        
        # Show project selection
        print("\n📋 Select an Overleaf project:")
        for i, project in enumerate(projects, 1):
            print(f"{i:2d}. {project['name']}")
        
        try:
            choice = int(input("\nEnter project number: ")) - 1
            if 0 <= choice < len(projects):
                selected_project = projects[choice]
                print(f"✅ Selected: {selected_project['name']}")
                
                # Launch web configurator with project data
                self.launch_configurator(selected_project)
                return True
            else:
                print("❌ Invalid selection")
                return False
                
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Selection cancelled")
            return False
    
    def launch_configurator(self, project_data: Dict):
        """Launch the web configurator with project data"""
        print("🌐 Launching Paperflow configurator...")
        
        # Save project data for web configurator
        temp_data = {
            "selected_project": project_data,
            "all_projects": self.projects,
            "authenticated": True
        }
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        with open(temp_file.name, 'w') as f:
            json.dump(temp_data, f, indent=2)
        
        # Set environment variable for web server
        os.environ['PAPERFLOW_PROJECT_DATA'] = temp_file.name
        
        # Launch web server
        web_server_path = Path(__file__).parent / "web-configurator" / "server.py"
        if web_server_path.exists():
            print("🖥️ Starting web configurator...")
            subprocess.run([sys.executable, str(web_server_path)])
        else:
            print("❌ Web configurator not found")
    
    def reconfigure(self):
        """Reconfigure existing project"""
        print("🔧 Reconfiguring Paperflow project...")
        
        # Look for existing config
        config_files = list(Path.cwd().glob("paperflow*.yml")) + list(Path.cwd().glob("paperflow*.yaml"))
        
        if config_files:
            print(f"📄 Found existing config: {config_files[0]}")
            # Load and launch configurator with existing config
            self.launch_configurator({})
        else:
            print("❌ No Paperflow configuration found in current directory")
            print("💡 Run 'paperflow init' to create a new project")

def main():
    parser = argparse.ArgumentParser(description="Paperflow - Academic Paper Website Generator")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Auth command
    auth_parser = subparsers.add_parser('auth', help='Authenticate with Overleaf')
    
    # Init command  
    init_parser = subparsers.add_parser('init', help='Initialize new Paperflow project')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List Overleaf projects')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download Overleaf project')
    download_parser.add_argument('project_id', help='Project ID to download')
    download_parser.add_argument('-o', '--output', help='Output directory')
    
    # Reconfigure command
    reconfig_parser = subparsers.add_parser('reconfigure', help='Reconfigure existing project')
    
    # Parse arguments
    args = parser.parse_args()
    
    cli = PaperflowCLI()
    
    if args.command == 'auth':
        cli.authenticate()
    elif args.command == 'init':
        cli.init_project()
    elif args.command == 'list':
        cli.list_projects()
    elif args.command == 'download':
        cli.download_project(args.project_id, args.output)
    elif args.command == 'reconfigure':
        cli.reconfigure()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()