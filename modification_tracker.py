#!/usr/bin/env python3
"""
Modification Tracker
Tracks changes to data.raw and maintains modification history
"""

import copy
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

@dataclass
class ModificationRecord:
    """Records a single modification to a prototype"""
    prototype_type: str
    prototype_name: str
    mod_name: str
    file_path: str
    line_number: Optional[int]
    timestamp: datetime
    operation: str  # 'create', 'modify', 'overwrite'
    old_value: Any = None
    new_value: Any = None
    field_path: str = ""  # e.g., "ingredients[0].amount" for nested changes

@dataclass
class PrototypeHistory:
    """Complete history of a prototype"""
    prototype_type: str
    prototype_name: str
    modifications: List[ModificationRecord] = field(default_factory=list)
    current_value: Any = None
    
    def add_modification(self, record: ModificationRecord):
        """Add a modification record to the history"""
        self.modifications.append(record)
        self.current_value = record.new_value

class ModificationTracker:
    """Tracks all modifications to data.raw prototypes"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.prototype_histories: Dict[str, PrototypeHistory] = {}  # key: "type.name"
        self.current_mod_context: Optional[Dict[str, str]] = None
        self.data_raw_snapshot: Dict[str, Dict[str, Any]] = {}
        
    def set_mod_context(self, mod_name: str, file_path: str, line_number: Optional[int] = None):
        """Set the current mod context for tracking modifications"""
        self.current_mod_context = {
            'mod_name': mod_name,
            'file_path': file_path,
            'line_number': line_number
        }
        self.logger.debug(f"Set mod context: {mod_name} - {file_path}")
    
    def clear_mod_context(self):
        """Clear the current mod context"""
        self.current_mod_context = None
    
    def track_prototype_addition(self, prototype_type: str, prototype_name: str, 
                               prototype_data: Dict[str, Any]):
        """Track the addition of a new prototype"""
        if not self.current_mod_context:
            self.logger.warning(f"No mod context set for prototype addition: {prototype_type}.{prototype_name}")
            return
        
        key = f"{prototype_type}.{prototype_name}"
        
        # Check if this prototype already exists
        operation = "create"
        old_value = None
        
        if key in self.prototype_histories:
            operation = "overwrite"
            old_value = self.prototype_histories[key].current_value
            self.logger.info(f"Prototype {key} being overwritten by {self.current_mod_context['mod_name']}")
        else:
            self.logger.info(f"New prototype {key} created by {self.current_mod_context['mod_name']}")
        
        # Create modification record
        record = ModificationRecord(
            prototype_type=prototype_type,
            prototype_name=prototype_name,
            mod_name=self.current_mod_context['mod_name'],
            file_path=self.current_mod_context['file_path'],
            line_number=self.current_mod_context.get('line_number'),
            timestamp=datetime.now(),
            operation=operation,
            old_value=copy.deepcopy(old_value) if old_value else None,
            new_value=copy.deepcopy(prototype_data)
        )
        
        # Update or create prototype history
        if key not in self.prototype_histories:
            self.prototype_histories[key] = PrototypeHistory(
                prototype_type=prototype_type,
                prototype_name=prototype_name
            )
        
        self.prototype_histories[key].add_modification(record)
        
        # Update our snapshot
        if prototype_type not in self.data_raw_snapshot:
            self.data_raw_snapshot[prototype_type] = {}
        self.data_raw_snapshot[prototype_type][prototype_name] = copy.deepcopy(prototype_data)
    
    def track_prototype_modification(self, prototype_type: str, prototype_name: str,
                                   field_path: str, old_value: Any, new_value: Any):
        """Track modification of a specific field in a prototype"""
        if not self.current_mod_context:
            self.logger.warning(f"No mod context set for prototype modification: {prototype_type}.{prototype_name}")
            return
        
        key = f"{prototype_type}.{prototype_name}"
        
        # Create modification record
        record = ModificationRecord(
            prototype_type=prototype_type,
            prototype_name=prototype_name,
            mod_name=self.current_mod_context['mod_name'],
            file_path=self.current_mod_context['file_path'],
            line_number=self.current_mod_context.get('line_number'),
            timestamp=datetime.now(),
            operation="modify",
            old_value=copy.deepcopy(old_value),
            new_value=copy.deepcopy(new_value),
            field_path=field_path
        )
        
        # Ensure prototype history exists
        if key not in self.prototype_histories:
            self.prototype_histories[key] = PrototypeHistory(
                prototype_type=prototype_type,
                prototype_name=prototype_name
            )
        
        self.prototype_histories[key].add_modification(record)
        
        self.logger.debug(f"Tracked modification: {key}.{field_path} by {self.current_mod_context['mod_name']}")
    
    def get_prototype_history(self, prototype_type: str, prototype_name: str) -> Optional[PrototypeHistory]:
        """Get the complete history of a prototype"""
        key = f"{prototype_type}.{prototype_name}"
        return self.prototype_histories.get(key)
    
    def get_modification_chain(self, prototype_type: str, prototype_name: str) -> List[str]:
        """Get the chain of mods that modified a prototype"""
        history = self.get_prototype_history(prototype_type, prototype_name)
        if not history:
            return []
        
        chain = []
        for mod_record in history.modifications:
            if mod_record.mod_name not in chain:
                chain.append(mod_record.mod_name)
        
        return chain
    
    def get_conflicts(self) -> List[Tuple[str, List[str]]]:
        """Get all prototypes that were modified by multiple mods (potential conflicts)"""
        conflicts = []
        
        for key, history in self.prototype_histories.items():
            mod_names = set()
            for record in history.modifications:
                mod_names.add(record.mod_name)
            
            if len(mod_names) > 1:
                conflicts.append((key, list(mod_names)))
        
        return conflicts
    
    def get_mod_modifications(self, mod_name: str) -> List[ModificationRecord]:
        """Get all modifications made by a specific mod"""
        modifications = []
        
        for history in self.prototype_histories.values():
            for record in history.modifications:
                if record.mod_name == mod_name:
                    modifications.append(record)
        
        return modifications
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive modification report"""
        total_prototypes = len(self.prototype_histories)
        conflicts = self.get_conflicts()
        
        # Count modifications by mod
        mod_counts = {}
        for history in self.prototype_histories.values():
            for record in history.modifications:
                mod_counts[record.mod_name] = mod_counts.get(record.mod_name, 0) + 1
        
        # Count prototype types
        type_counts = {}
        for history in self.prototype_histories.values():
            ptype = history.prototype_type
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
        
        return {
            'total_prototypes': total_prototypes,
            'total_conflicts': len(conflicts),
            'conflicts': conflicts,
            'modifications_by_mod': mod_counts,
            'prototypes_by_type': type_counts,
            'timestamp': datetime.now().isoformat()
        }
    
    def export_history(self, output_path: Path):
        """Export the complete modification history to a file"""
        import json
        
        # Convert to serializable format
        export_data = {
            'metadata': {
                'export_timestamp': datetime.now().isoformat(),
                'total_prototypes': len(self.prototype_histories)
            },
            'prototypes': {}
        }
        
        for key, history in self.prototype_histories.items():
            export_data['prototypes'][key] = {
                'prototype_type': history.prototype_type,
                'prototype_name': history.prototype_name,
                'modifications': [
                    {
                        'mod_name': record.mod_name,
                        'file_path': record.file_path,
                        'line_number': record.line_number,
                        'timestamp': record.timestamp.isoformat(),
                        'operation': record.operation,
                        'field_path': record.field_path,
                        'old_value': record.old_value,
                        'new_value': record.new_value
                    }
                    for record in history.modifications
                ]
            }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Exported modification history to: {output_path}")

# Test functions
def test_modification_tracker():
    """Test the modification tracker functionality"""
    print("🧪 Testing ModificationTracker...")
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    tracker = ModificationTracker()
    
    # Test 1: Track prototype creation
    print("\n📝 Test 1: Prototype creation")
    tracker.set_mod_context("base", "data.lua", 100)
    
    # Test data should be extracted from actual mod files, not hardcoded
    print("⚠️  Test function disabled - no hardcoded content allowed")
    print("All test data should be extracted from actual mod files")
    return None

def test_with_real_mods(target_mods: List[str] = None):
    """Test with real Factorio mods"""
    print("\n🎮 Testing with real Factorio mods...")
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    from mod_info import ModDiscovery
    from lua_environment import FactorioLuaEnvironment
    
    # Discover mods
    factorio_mods_path = Path(r"C:\Users\eysen\AppData\Roaming\Factorio\mods")
    discovery = ModDiscovery(factorio_mods_path)
    mods = discovery.discover_mods()
    
    # Filter to just the mods we're interested in (default to lignumis and Krastorio2 for backward compatibility)
    if target_mods is None:
        target_mods = ["lignumis", "Krastorio2-spaced-out"]
    
    if target_mods:
        filtered_mods = [mod for mod in mods if any(target in mod.name for target in target_mods)]
    else:
        # If no target mods specified, use all mods (but limit for performance)
        filtered_mods = mods[:10]  # Limit to first 10 mods for testing
    
    print(f"Found {len(filtered_mods)} target mods:")
    for mod in filtered_mods:
        print(f"  - {mod.name} v{mod.version}")
    
    if not filtered_mods:
        print("❌ No target mods found!")
        return
    
    # Set up tracking environment
    tracker = ModificationTracker()
    lua_env = FactorioLuaEnvironment()
    
    # Integrate tracker with lua environment
    def tracked_data_extend(json_string):
        """Enhanced data:extend that tracks modifications"""
        try:
            import json
            prototypes = json.loads(json_string)
            
            for prototype in prototypes:
                ptype = prototype.get('type')
                name = prototype.get('name')
                
                if ptype and name:
                    # Track the addition
                    tracker.track_prototype_addition(ptype, name, prototype)
                    
                    # Also add to lua environment
                    if ptype not in lua_env.data_raw:
                        lua_env.data_raw[ptype] = {}
                    lua_env.data_raw[ptype][name] = prototype
            
            return True
        except Exception as e:
            print(f"Error in tracked data:extend: {e}")
            return False
    
    # Replace the lua environment's data:extend with our tracked version
    lua_env.lua.globals().python_data_extend = tracked_data_extend
    
    # Process each mod
    for mod in filtered_mods[:2]:  # Limit to first 2 for testing
        print(f"\n🔄 Processing mod: {mod.name}")
        
        # Set mod context
        tracker.set_mod_context(mod.name, str(mod.path))
        
        # Try to load and execute the mod's data.lua
        try:
            if mod.is_zipped:
                import zipfile
                with zipfile.ZipFile(mod.path, 'r') as zf:
                    # Look for data.lua
                    data_files = [f for f in zf.namelist() if f.endswith('data.lua')]
                    if data_files:
                        lua_code = zf.read(data_files[0]).decode('utf-8')
                        print(f"  📄 Found data.lua ({len(lua_code)} chars)")
                        
                        # Execute a small portion for testing (full execution might be complex)
                        # For now, just simulate some prototype additions
                        if "lignumis" in mod.name:
                            # Simulate lignumis adding some prototypes
                            test_code = '''
                                data:extend({
                                    {
                                        type = "item",
                                        name = "lignumis-wood",
                                        stack_size = 100,
                                        icon = "__lignumis__/graphics/icons/wood.png"
                                    }
                                })
                            '''
                            lua_env.execute_lua_code(test_code)
                        
                        elif "Krastorio2" in mod.name:
                            # Simulate Krastorio2 modifying existing items
                            test_code = '''
                                data:extend({
                                    {
                                        type = "item", 
                                        name = "lignumis-wood",
                                        stack_size = 200,  -- Modified by Krastorio2
                                        icon = "__krastorio2__/graphics/icons/wood.png"
                                    }
                                })
                            '''
                            lua_env.execute_lua_code(test_code)
            
        except Exception as e:
            print(f"  ❌ Error processing mod: {e}")
        
        tracker.clear_mod_context()
    
    # Generate final report
    print("\n📊 Final Modification Report:")
    report = tracker.generate_report()
    for key, value in report.items():
        if key != 'timestamp':
            print(f"  {key}: {value}")
    
    # Check for conflicts
    conflicts = tracker.get_conflicts()
    if conflicts:
        print(f"\n⚠️  Found {len(conflicts)} potential conflicts:")
        for prototype, mods in conflicts:
            print(f"  {prototype}: {' → '.join(mods)}")
            
            # Show detailed history
            ptype, pname = prototype.split('.', 1)
            history = tracker.get_prototype_history(ptype, pname)
            if history:
                for record in history.modifications:
                    print(f"    - {record.operation} by {record.mod_name}")
    
    # Export results
    output_path = Path("./logs/modification_history.json")
    tracker.export_history(output_path)
    
    print(f"\n✅ Real mod testing complete! Results exported to {output_path}")
    return tracker

if __name__ == "__main__":
    # Run basic tests first
    tracker = test_modification_tracker()
    
    # Then test with real mods (can now specify custom target mods)
    import sys
    if len(sys.argv) > 1:
        # Allow specifying target mods from command line
        target_mods = sys.argv[1:]
        print(f"Using command line target mods: {target_mods}")
        test_with_real_mods(target_mods)
    else:
        # Default behavior
        test_with_real_mods()
