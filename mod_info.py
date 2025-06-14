#!/usr/bin/env python3
"""
Mod Information Parser
Handles discovery and parsing of Factorio mod information
"""

import json
import zipfile
import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime

# Set up logging
def setup_logging():
    """Set up logging to both file and console"""
    # Create logs directory
    logs_dir = Path("./logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"mod_discovery_{timestamp}.log"
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging to: {log_file}")
    return logger

@dataclass
class ModInfo:
    """Parsed mod information from info.json"""
    name: str
    version: str
    title: str
    author: str
    dependencies: List[str] = field(default_factory=list)
    path: Path = None
    is_zipped: bool = False

class ModDiscovery:
    """Discovers and parses mod information"""
    
    def __init__(self, mods_path: Path):
        self.mods_path = Path(mods_path)
        self.logger = logging.getLogger(__name__)
    
    def discover_mods(self) -> List[ModInfo]:
        """Discover all mods in the directory"""
        mods = []
        
        if not self.mods_path.exists():
            self.logger.error(f"Mods directory not found: {self.mods_path}")
            return mods
        
        self.logger.info(f"Scanning for mods in: {self.mods_path}")
        
        # Process both zipped and unzipped mods
        for item in self.mods_path.iterdir():
            if item.is_dir():
                # Check for unzipped mod (directory with info.json)
                info_file = item / "info.json"
                if info_file.exists():
                    mod_info = self._parse_mod_info(info_file, item, is_zipped=False)
                    if mod_info:
                        mods.append(mod_info)
                        self.logger.info(f"Found unzipped mod: {mod_info.name}")
            
            elif item.suffix == '.zip':
                # Check for zipped mod
                try:
                    mod_info = self._parse_mod_info(item, item, is_zipped=True)
                    if mod_info:
                        mods.append(mod_info)
                        self.logger.info(f"Found zipped mod: {mod_info.name}")
                except zipfile.BadZipFile:
                    self.logger.warning(f"Skipping invalid zip file: {item}")
        
        self.logger.info(f"Discovery complete. Found {len(mods)} mods total.")
        return mods
    
    def _parse_mod_info(self, info_file: Path, mod_path: Path, is_zipped: bool) -> Optional[ModInfo]:
        """Parse mod info.json file"""
        try:
            if is_zipped:
                # For zipped mods, info_file is actually the zip path
                with zipfile.ZipFile(info_file, 'r') as zf:
                    # Find info.json in the zip
                    info_files = [f for f in zf.namelist() if f.endswith('info.json')]
                    if not info_files:
                        self.logger.warning(f"No info.json found in {info_file}")
                        return None
                    
                    content = zf.read(info_files[0]).decode('utf-8')
            else:
                # For unzipped mods, read the file directly
                with open(info_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            # Parse JSON content
            info = json.loads(content)
            
            mod_info = ModInfo(
                name=info['name'],
                version=info['version'],
                title=info.get('title', info['name']),
                author=info.get('author', 'Unknown'),
                dependencies=info.get('dependencies', []),
                path=mod_path,
                is_zipped=is_zipped
            )
            
            self.logger.debug(f"Parsed mod: {mod_info.name} v{mod_info.version}")
            return mod_info
            
        except Exception as e:
            self.logger.error(f"Failed to parse {info_file}: {e}")
            return None

# Test function
def test_mod_discovery():
    """Test the mod discovery functionality"""
    # Set up logging first
    logger = setup_logging()
    
    # Test with actual Factorio mods directory
    factorio_mods_path = Path(r"C:\Users\eysen\AppData\Roaming\Factorio\mods")
    
    logger.info("Testing with actual Factorio mods directory...")
    
    # Test discovery
    discovery = ModDiscovery(factorio_mods_path)
    mods = discovery.discover_mods()
    
    logger.info(f"Discovery Results: Found {len(mods)} mod(s)")
    
    for mod in mods:
        logger.info(f"Mod: {mod.name} v{mod.version} ({mod.title}) by {mod.author}")
        logger.info(f"  Dependencies: {mod.dependencies}")
        logger.info(f"  Path: {mod.path}")
        logger.info(f"  Zipped: {mod.is_zipped}")
    
    # Also create a simple test mod for future testing
    test_path = Path("./test_mods")
    test_path.mkdir(exist_ok=True)
    
    test_mod_path = test_path / "test-mod"
    test_mod_path.mkdir(exist_ok=True)
    
    info_json = {
        "name": "test-mod",
        "version": "1.0.0",
        "title": "Test Mod",
        "author": "Test Author",
        "dependencies": ["base", "? optional-mod >= 1.0.0"]
    }
    
    with open(test_mod_path / "info.json", 'w') as f:
        json.dump(info_json, f, indent=2)
    
    logger.info("Also created local test mod for future testing")
    
    return mods

if __name__ == "__main__":
    test_mod_discovery()
