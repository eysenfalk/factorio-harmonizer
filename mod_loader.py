#!/usr/bin/env python3
"""
Mod Loader - Main Orchestrator
The main CLI interface that ties all components together
"""

import typer
import logging
import re
import json
import zipfile
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from mod_info import ModDiscovery
from lua_environment import FactorioLuaEnvironment
from modification_tracker import ModificationTracker
from dependency_analyzer import DependencyAnalyzer
from visualizer import ConflictVisualizer
from data_models import ConflictSeverity

app = typer.Typer(help="🎯 Factorio Mod Harmonizer - Analyze and fix mod conflicts")
console = Console()

class ModHarmonizer:
    """Main orchestrator class"""
    
    def __init__(self, mods_path: Path, output_dir: Path = None):
        self.mods_path = Path(mods_path)
        self.output_dir = Path(output_dir) if output_dir else Path("./output")
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.discovery = ModDiscovery(self.mods_path)
        self.tracker = ModificationTracker()
        self.lua_env = FactorioLuaEnvironment()
        self.analyzer = None
        self.visualizer = ConflictVisualizer()
        
        # Setup logging
        self._setup_logging()
        
        # Integrate tracker with lua environment
        self._setup_tracked_environment()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_dir = Path("./logs")
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "harmonizer.log", encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def _setup_tracked_environment(self):
        """Setup the tracked Lua environment"""
        def tracked_data_extend(json_string):
            try:
                import json
                prototypes = json.loads(json_string)
                
                for prototype in prototypes:
                    ptype = prototype.get('type')
                    name = prototype.get('name')
                    
                    if ptype and name:
                        self.tracker.track_prototype_addition(ptype, name, prototype)
                        
                        if ptype not in self.lua_env.data_raw:
                            self.lua_env.data_raw[ptype] = {}
                        self.lua_env.data_raw[ptype][name] = prototype
                
                return True
            except Exception as e:
                self.logger.error(f"Error in tracked data:extend: {e}")
                return False
        
        self.lua_env.lua.globals().python_data_extend = tracked_data_extend
    
    def discover_mods(self, filter_mods: List[str] = None, exclude_harmonizer_patch: bool = True, only_enabled: bool = True) -> List:
        """Discover mods in the directory"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("🔍 Discovering mods...", total=None)
            
            mods = self.discovery.discover_mods(only_enabled=only_enabled)
            
            # Exclude harmonizer patch if requested
            if exclude_harmonizer_patch:
                original_count = len(mods)
                mods = [mod for mod in mods if not mod.name.startswith("factorio-harmonizer-patch")]
                excluded_count = original_count - len(mods)
                if excluded_count > 0:
                    self.logger.info(f"Excluded {excluded_count} harmonizer patch mod(s) from analysis")
            
            if filter_mods:
                mods = [mod for mod in mods if any(f in mod.name for f in filter_mods)]
                progress.update(task, description=f"🔍 Found {len(mods)} filtered mods")
            else:
                if only_enabled:
                    progress.update(task, description=f"🔍 Found {len(mods)} enabled mods")
                else:
                    progress.update(task, description=f"🔍 Found {len(mods)} mods")
        
        return mods
    
    def analyze_conflicts(self, mods: List = None) -> tuple:
        """Analyze mod conflicts"""
        if not mods:
            mods = self.discover_mods()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            # Simulate mod loading
            task1 = progress.add_task("🌳 Loading base game...", total=None)
            self._simulate_base_game()
            
            task2 = progress.add_task("🔄 Processing mods...", total=len(mods))
            for i, mod in enumerate(mods):
                progress.update(task2, description=f"🔄 Processing {mod.name}...")
                self._simulate_mod_loading(mod)
                progress.advance(task2)
            
            task3 = progress.add_task("🔍 Analyzing dependencies...", total=None)
            self.analyzer = DependencyAnalyzer(self.tracker)
            report = self.analyzer.analyze_dependencies()
            
            task4 = progress.add_task("🔧 Generating patches...", total=None)
            patches = self.analyzer.generate_patch_suggestions(report)
        
        return report, patches
    
    def _simulate_base_game(self):
        """Load base game prototypes from actual base mod files"""
        # Find and load the actual base mod
        base_mod = None
        for mod in self.discovery.discover_mods(only_enabled=False):
            if mod.name == "base":
                base_mod = mod
                break
        
        if base_mod:
            self.logger.info("Loading base game prototypes from actual base mod files")
            self._parse_real_mod_files(base_mod)
        else:
            self.logger.warning("Base mod not found - analysis may be incomplete")
    
    def _simulate_mod_loading(self, mod):
        """Parse and load actual mod files instead of simulation"""
        self.tracker.set_mod_context(mod.name, str(mod.path))
        
        try:
            # Parse real mod files
            self._parse_real_mod_files(mod)
            
            # SIMULATE RESEARCH CHAIN BREAKS for testing
            # This simulates what would happen if mods modify technology prerequisites
            if "bob" in mod.name.lower():
                self._simulate_research_chain_breaks(mod)
                
        except Exception as e:
            self.logger.warning(f"Failed to parse mod {mod.name}: {e}")
            # Fallback to basic simulation for problematic mods
            self._fallback_simulation(mod)
        
        self.tracker.clear_mod_context()
    
    def _simulate_research_chain_breaks(self, mod):
        """Simulate research chain breaks for testing - REMOVED: No hardcoded content allowed"""
        # Research chain breaks should be detected from actual mod conflicts
        pass
    
    def _parse_real_mod_files(self, mod):
        """Parse actual mod files to extract real prototypes"""
        if mod.is_zipped:
            import zipfile
            with zipfile.ZipFile(mod.path, 'r') as zf:
                # Parse ALL Lua files that contain prototype definitions
                all_lua_files = [f for f in zf.namelist() if f.endswith('.lua')]
                
                # Filter out files that likely don't contain prototypes
                skip_patterns = ['locale/', 'graphics/', 'sounds/', 'migrations/', 'scenarios/', 'campaigns/', 'tutorials/', 'control.lua', 'settings.lua']
                relevant_files = [f for f in all_lua_files if not any(skip in f for skip in skip_patterns)]
                
                for file_path in relevant_files:
                        try:
                            lua_code = zf.read(file_path).decode('utf-8', errors='ignore')
                            self.logger.info(f"Parsing {mod.name}/{file_path} ({len(lua_code)} chars)")
                            
                            # Extract prototypes from the Lua code
                            prototypes = self._extract_prototypes_from_lua(lua_code, mod.name, file_path)
                            
                            # Track each prototype
                            for prototype in prototypes:
                                ptype = prototype.get('type')
                                name = prototype.get('name')
                                
                                if ptype and name:
                                    self.tracker.track_prototype_addition(ptype, name, prototype)
                                    
                                    # Also add to lua environment for dependency analysis
                                    if ptype not in self.lua_env.data_raw:
                                        self.lua_env.data_raw[ptype] = {}
                                    self.lua_env.data_raw[ptype][name] = prototype
                                    
                        except Exception as e:
                            self.logger.warning(f"Error parsing {file_path} in {mod.name}: {e}")
        else:
            # Handle directory-based mods - parse ALL Lua files
            mod_dir = Path(mod.path)
            
            # Find all Lua files recursively
            all_lua_files = list(mod_dir.rglob('*.lua'))
            
            # Filter out files that likely don't contain prototypes
            skip_patterns = ['locale', 'graphics', 'sounds', 'migrations', 'scenarios', 'campaigns', 'tutorials', 'control.lua', 'settings.lua']
            relevant_files = [f for f in all_lua_files if not any(skip in str(f) for skip in skip_patterns)]
            
            for file_path in relevant_files:
                    try:
                        lua_code = file_path.read_text(encoding='utf-8', errors='ignore')
                        self.logger.info(f"Parsing {mod.name}/{file_path.relative_to(mod_dir)} ({len(lua_code)} chars)")
                        
                        # Extract prototypes from the Lua code
                        prototypes = self._extract_prototypes_from_lua(lua_code, mod.name, str(file_path))
                        
                        # Track each prototype
                        for prototype in prototypes:
                            ptype = prototype.get('type')
                            name = prototype.get('name')
                            
                            if ptype and name:
                                self.tracker.track_prototype_addition(ptype, name, prototype)
                                
                                # Also add to lua environment
                                if ptype not in self.lua_env.data_raw:
                                    self.lua_env.data_raw[ptype] = {}
                                self.lua_env.data_raw[ptype][name] = prototype
                                
                    except Exception as e:
                        self.logger.warning(f"Error parsing {file_path}: {e}")
    
    def _extract_prototypes_from_lua(self, lua_code: str, mod_name: str, file_path: str):
        """Extract prototypes from Lua code using improved regex patterns"""
        
        prototypes = []
        
        # Pattern to match data:extend({ ... }) calls
        # This is a simplified parser - real Lua parsing would be more complex
        data_extend_pattern = r'data:extend\s*\(\s*\{(.*?)\}\s*\)'
        
        # Find all data:extend calls
        matches = re.finditer(data_extend_pattern, lua_code, re.DOTALL)
        
        for match in matches:
            extend_content = match.group(1)
            
            # Try to extract individual prototype definitions
            # Look for table definitions like { type = "item", name = "something", ... }
            prototype_pattern = r'\{[^{}]*type\s*=\s*["\']([^"\']+)["\'][^{}]*name\s*=\s*["\']([^"\']+)["\'][^{}]*\}'
            
            proto_matches = re.finditer(prototype_pattern, extend_content, re.DOTALL)
            
            for proto_match in proto_matches:
                ptype = proto_match.group(1)
                name = proto_match.group(2)
                
                # Extract the full prototype definition
                full_proto = proto_match.group(0)
                
                # Try to parse key-value pairs from the prototype
                prototype = self._parse_lua_table(full_proto, ptype, name)
                
                if prototype:
                    prototypes.append(prototype)
                    self.logger.debug(f"Extracted {ptype}.{name} from {mod_name}")
        
        # Also look for direct assignments like data.raw.recipe["something"] = { ... }
        assignment_pattern = r'data\.raw\.([^.]+)\[(["\'][^"\']+["\'])\]\s*=\s*(\{[^{}]*\})'
        
        assignment_matches = re.finditer(assignment_pattern, lua_code, re.DOTALL)
        
        for match in assignment_matches:
            ptype = match.group(1)
            name = match.group(2).strip('"\'')
            table_content = match.group(3)
            
            # Parse the assignment
            prototype = self._parse_lua_table(table_content, ptype, name)
            
            if prototype:
                prototypes.append(prototype)
                self.logger.debug(f"Extracted assignment {ptype}.{name} from {mod_name}")
        
        # Look for local variable assignments and property modifications
        # Pattern: local var = data.raw.type["name"] followed by var.property = value
        local_var_pattern = r'local\s+(\w+)\s*=\s*data\.raw\.([^.]+)\[(["\'][^"\']+["\'])\]'
        local_matches = re.finditer(local_var_pattern, lua_code)
        
        for match in local_matches:
            var_name = match.group(1)
            ptype = match.group(2)
            name = match.group(3).strip('"\'')
            
            # Look for modifications to this variable
            # Pattern: var_name.property = value
            modification_pattern = rf'{re.escape(var_name)}\.(\w+)\s*=\s*([^;\n]+)'
            mod_matches = re.finditer(modification_pattern, lua_code)
            
            modifications = {}
            for mod_match in mod_matches:
                property_name = mod_match.group(1)
                property_value = mod_match.group(2).strip()
                
                # Try to parse the property value more intelligently
                if property_name == 'ingredients':
                    # Parse ingredients table
                    ingredients = self._parse_ingredients_from_lua(property_value)
                    if ingredients:
                        modifications[property_name] = ingredients
                elif property_name == 'results':
                    # Parse results table
                    results = self._parse_results_from_lua(property_value)
                    if results:
                        modifications[property_name] = results
                elif property_name == 'category':
                    # Clean up category string
                    category = property_value.strip('"\'')
                    modifications[property_name] = category
                else:
                    modifications[property_name] = property_value
            
            if modifications:
                # Create a prototype representing the modification
                prototype = {
                    'type': ptype,
                    'name': name,
                    'modifications': modifications,
                    'modified_by': mod_name
                }
                prototypes.append(prototype)
                self.logger.debug(f"Extracted modification {ptype}.{name} from {mod_name}: {list(modifications.keys())}")
        
        # Look for direct property assignments like recipe_var.ingredients = { ... }
        # This handles patterns like: burner_inserter_recipe.ingredients = { ... }
        direct_assignment_pattern = r'(\w+)\.(\w+)\s*=\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'
        direct_matches = re.finditer(direct_assignment_pattern, lua_code, re.DOTALL)
        
        for match in direct_matches:
            var_name = match.group(1)
            property_name = match.group(2)
            property_value = match.group(3)
            
            # Try to find what this variable refers to
            var_ref_pattern = rf'local\s+{re.escape(var_name)}\s*=\s*data\.raw\.([^.]+)\[(["\'][^"\']+["\'])\]'
            var_ref_match = re.search(var_ref_pattern, lua_code)
            
            if var_ref_match:
                ptype = var_ref_match.group(1)
                name = var_ref_match.group(2).strip('"\'')
                
                # Parse the property value
                parsed_value = None
                if property_name == 'ingredients':
                    parsed_value = self._parse_ingredients_from_lua(property_value)
                elif property_name == 'results':
                    parsed_value = self._parse_results_from_lua(property_value)
                elif property_name == 'category':
                    parsed_value = property_value.strip('"\'')
                else:
                    parsed_value = property_value
                
                if parsed_value:
                    # Create a prototype representing the modification
                    prototype = {
                        'type': ptype,
                        'name': name,
                        property_name: parsed_value,
                        'modified_by': mod_name
                    }
                    prototypes.append(prototype)
                    self.logger.debug(f"Extracted direct assignment {ptype}.{name}.{property_name} from {mod_name}")
        
        # Look for table.insert operations on ingredients/results
        table_insert_pattern = r'table\.insert\s*\(\s*([^,]+)\.(\w+)\s*,\s*([^)]+)\)'
        insert_matches = re.finditer(table_insert_pattern, lua_code)
        
        for match in insert_matches:
            var_name = match.group(1)
            property_name = match.group(2)
            value = match.group(3).strip()
            
            # This indicates a modification to an existing prototype
            # We'll track this as a modification
            if property_name in ['ingredients', 'results']:
                # Try to find the prototype this refers to
                var_pattern = rf'local\s+{re.escape(var_name)}\s*=\s*data\.raw\.([^.]+)\[(["\'][^"\']+["\'])\]'
                var_match = re.search(var_pattern, lua_code)
                
                if var_match:
                    ptype = var_match.group(1)
                    name = var_match.group(2).strip('"\'')
                    
                    # Parse the inserted value
                    if property_name == 'ingredients':
                        ingredient = self._parse_single_ingredient(value)
                        if ingredient:
                            prototype = {
                                'type': ptype,
                                'name': name,
                                'modifications': {property_name: [ingredient]},
                                'modified_by': mod_name,
                                'operation': 'insert'
                            }
                            prototypes.append(prototype)
        
        return prototypes
    
    def _parse_ingredients_from_lua(self, lua_value: str):
        """Parse ingredients from a Lua table string"""
        try:
            # Remove outer braces if present
            lua_value = lua_value.strip()
            if lua_value.startswith('{') and lua_value.endswith('}'):
                lua_value = lua_value[1:-1]
            
            ingredients = []
            
            # Pattern for individual ingredients
            # Handles both {type="item", name="wood", amount=2} and {"wood", 2}
            # Also handles multi-line format with proper spacing
            ingredient_patterns = [
                # Full format: { type = "item", name = "wooden-gear-wheel", amount = 1 }
                r'\{\s*type\s*=\s*["\']([^"\']+)["\']\s*,\s*name\s*=\s*["\']([^"\']+)["\']\s*,\s*amount\s*=\s*(\d+)\s*\}',
                # Compact format: {type="item", name="wood", amount=2}
                r'\{\s*type\s*=\s*["\']([^"\']+)["\']\s*,\s*name\s*=\s*["\']([^"\']+)["\']\s*,\s*amount\s*=\s*(\d+)\s*\}',
                # Simple format: {"wood", 2}
                r'\{\s*["\']([^"\']+)["\']\s*,\s*(\d+)\s*\}',
                # Alternative simple format: { "wood", 2 }
                r'\{\s*["\']([^"\']+)["\']\s*,\s*(\d+)\s*\}'
            ]
            
            for pattern in ingredient_patterns:
                for match in re.finditer(pattern, lua_value, re.MULTILINE | re.DOTALL):
                    groups = match.groups()
                    if len(groups) == 3:
                        # Full format with type
                        ingredients.append({
                            'type': groups[0],
                            'name': groups[1],
                            'amount': int(groups[2])
                        })
                    elif len(groups) == 2:
                        # Simple format, assume item type
                        ingredients.append({
                            'type': 'item',
                            'name': groups[0],
                            'amount': int(groups[1])
                        })
            
            # If no matches found with the above patterns, try a more flexible approach
            if not ingredients:
                # Look for individual ingredient blocks more flexibly
                # This handles the Lignumis format:
                # {
                #     { type = "item", name = "wooden-gear-wheel", amount = 1 },
                #     { type = "item", name = "lumber",            amount = 1 }
                # }
                
                # Split by commas that are outside of braces
                ingredient_blocks = self._split_lua_table_entries(lua_value)
                
                for block in ingredient_blocks:
                    block = block.strip()
                    if not block:
                        continue
                    
                    # Try to extract name and amount from each block
                    name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', block)
                    amount_match = re.search(r'amount\s*=\s*(\d+)', block)
                    type_match = re.search(r'type\s*=\s*["\']([^"\']+)["\']', block)
                    
                    if name_match and amount_match:
                        ingredient = {
                            'type': type_match.group(1) if type_match else 'item',
                            'name': name_match.group(1),
                            'amount': int(amount_match.group(1))
                        }
                        ingredients.append(ingredient)
            
            return ingredients if ingredients else None
            
        except Exception as e:
            self.logger.warning(f"Error parsing ingredients from Lua: {e}")
            return None
    
    def _split_lua_table_entries(self, lua_table_content: str):
        """Split Lua table content by commas, respecting nested braces"""
        entries = []
        current_entry = ""
        brace_depth = 0
        
        for char in lua_table_content:
            if char == '{':
                brace_depth += 1
            elif char == '}':
                brace_depth -= 1
            elif char == ',' and brace_depth == 0:
                # This comma is at the top level, so it separates entries
                if current_entry.strip():
                    entries.append(current_entry.strip())
                current_entry = ""
                continue
            
            current_entry += char
        
        # Add the last entry
        if current_entry.strip():
            entries.append(current_entry.strip())
        
        return entries
    
    def _parse_results_from_lua(self, lua_value: str):
        """Parse results from a Lua table string"""
        # Same logic as ingredients
        return self._parse_ingredients_from_lua(lua_value)
    
    def _parse_single_ingredient(self, lua_value: str):
        """Parse a single ingredient from Lua"""
        try:
            lua_value = lua_value.strip()
            
            # Pattern for single ingredient
            patterns = [
                r'\{\s*type\s*=\s*["\']([^"\']+)["\']\s*,\s*name\s*=\s*["\']([^"\']+)["\']\s*,\s*amount\s*=\s*(\d+)\s*\}',
                r'\{\s*["\']([^"\']+)["\']\s*,\s*(\d+)\s*\}'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, lua_value)
                if match:
                    if len(match.groups()) == 3:
                        return {
                            'type': match.group(1),
                            'name': match.group(2),
                            'amount': int(match.group(3))
                        }
                    else:
                        return {
                            'type': 'item',
                            'name': match.group(1),
                            'amount': int(match.group(2))
                        }
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Error parsing single ingredient: {e}")
            return None
    
    def _parse_lua_table(self, lua_table: str, ptype: str, name: str):
        """Parse a Lua table string into a Python dictionary"""
        try:
            # Basic Lua table parsing - this is simplified
            # Real implementation would need a proper Lua parser
            
            prototype = {
                'type': ptype,
                'name': name
            }
            
            # Extract common fields using regex
            field_patterns = {
                'stack_size': r'stack_size\s*=\s*(\d+)',
                'enabled': r'enabled\s*=\s*(true|false)',
                'icon': r'icon\s*=\s*["\']([^"\']+)["\']',
                'energy_required': r'energy_required\s*=\s*([0-9.]+)',
                'category': r'category\s*=\s*["\']([^"\']+)["\']',
            }
            
            for field, pattern in field_patterns.items():
                match = re.search(pattern, lua_table)
                if match:
                    value = match.group(1)
                    if field in ['stack_size', 'energy_required']:
                        try:
                            prototype[field] = float(value) if '.' in value else int(value)
                        except ValueError:
                            prototype[field] = value
                    elif field == 'enabled':
                        prototype[field] = value == 'true'
                    else:
                        prototype[field] = value
            
            # Extract ingredients array
            ingredients_match = re.search(r'ingredients\s*=\s*\{([^{}]*)\}', lua_table)
            if ingredients_match:
                ingredients_str = ingredients_match.group(1)
                ingredients = self._parse_ingredients(ingredients_str)
                if ingredients:
                    prototype['ingredients'] = ingredients
            
            # Extract results array
            results_match = re.search(r'results?\s*=\s*\{([^{}]*)\}', lua_table)
            if results_match:
                results_str = results_match.group(1)
                results = self._parse_results(results_str)
                if results:
                    prototype['results'] = results
            
            # Extract prerequisites array for technologies
            prereq_match = re.search(r'prerequisites\s*=\s*\{([^{}]*)\}', lua_table)
            if prereq_match:
                prereq_str = prereq_match.group(1)
                prerequisites = self._parse_string_array(prereq_str)
                if prerequisites:
                    prototype['prerequisites'] = prerequisites
            
            return prototype
            
        except Exception as e:
            self.logger.warning(f"Error parsing Lua table for {ptype}.{name}: {e}")
            return None
    
    def _parse_ingredients(self, ingredients_str: str):
        """Parse ingredients array from Lua"""
        ingredients = []
        
        # Pattern for ingredients like {"iron-plate", 2} or {type="item", name="iron-plate", amount=2}
        simple_pattern = r'\{\s*["\']([^"\']+)["\']\s*,\s*(\d+)\s*\}'
        complex_pattern = r'\{\s*type\s*=\s*["\']([^"\']+)["\']\s*,\s*name\s*=\s*["\']([^"\']+)["\']\s*,\s*amount\s*=\s*(\d+)\s*\}'
        
        # Try simple format first
        for match in re.finditer(simple_pattern, ingredients_str):
            ingredients.append({
                'type': 'item',
                'name': match.group(1),
                'amount': int(match.group(2))
            })
        
        # Try complex format
        for match in re.finditer(complex_pattern, ingredients_str):
            ingredients.append({
                'type': match.group(1),
                'name': match.group(2),
                'amount': int(match.group(3))
            })
        
        return ingredients
    
    def _parse_results(self, results_str: str):
        """Parse results array from Lua"""
        results = []
        
        # Similar patterns as ingredients
        simple_pattern = r'\{\s*["\']([^"\']+)["\']\s*,\s*(\d+)\s*\}'
        complex_pattern = r'\{\s*type\s*=\s*["\']([^"\']+)["\']\s*,\s*name\s*=\s*["\']([^"\']+)["\']\s*,\s*amount\s*=\s*(\d+)\s*\}'
        
        # Try simple format first
        for match in re.finditer(simple_pattern, results_str):
            results.append({
                'type': 'item',
                'name': match.group(1),
                'amount': int(match.group(2))
            })
        
        # Try complex format
        for match in re.finditer(complex_pattern, results_str):
            results.append({
                'type': match.group(1),
                'name': match.group(2),
                'amount': int(match.group(3))
            })
        
        return results
    
    def _parse_string_array(self, array_str: str):
        """Parse array of strings like {"automation", "steel-processing"}"""
        strings = []
        
        pattern = r'["\']([^"\']+)["\']'
        for match in re.finditer(pattern, array_str):
            strings.append(match.group(1))
        
        return strings
    
    def _fallback_simulation(self, mod):
        """Fallback for mods that can't be parsed - REMOVED: No hardcoded content allowed"""
        # All mod content should be extracted from actual mod files
        self.logger.warning(f"Could not parse mod {mod.name} - skipping")
    
    def generate_outputs(self, report, patches):
        """Generate all output files and visualizations"""
        outputs = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            # Text report
            task1 = progress.add_task("📄 Generating text report...", total=None)
            text_report = self.visualizer.generate_conflict_report(report, patches)
            text_path = self.output_dir / "conflict_report.txt"
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text_report)
            outputs['text_report'] = text_path
            
            # JSON analysis
            task2 = progress.add_task("💾 Exporting analysis data...", total=None)
            json_path = self.output_dir / "analysis_data.json"
            self._export_analysis_json(report, patches, json_path)
            outputs['json_data'] = json_path
            
            # Export recipes per mod
            task3 = progress.add_task("📋 Exporting recipes per mod...", total=None)
            recipes_dir = self.output_dir / "recipes_per_mod"
            recipe_files = self.analyzer.export_recipes_per_mod(recipes_dir)
            outputs['recipe_files'] = list(recipe_files.values())
            
            # Patch files
            task4 = progress.add_task("🔧 Generating patch files...", total=None)
            patch_dir = self.output_dir / "patches"
            created_files = self.visualizer.generate_patch_files(patches, patch_dir)
            outputs['patch_files'] = created_files
            
            # Install patches
            task5 = progress.add_task("📦 Installing patches...", total=None)
            installed_patches = self._install_patches(patch_dir)
            outputs['installed_patches'] = installed_patches
        
        return outputs
    
    def _export_analysis_json(self, report, patches, output_path):
        """Export analysis data to JSON"""
        
        data = {
            'analyzed_mods': report.analyzed_mods,
            'analysis_timestamp': report.analysis_timestamp,
            'summary': {
                'total_prototypes': report.total_prototypes,
                'conflicted_prototypes': report.conflicted_prototypes,
                'critical_issues': report.critical_issues,
                'high_issues': report.high_issues,
                'medium_issues': report.medium_issues,
                'low_issues': report.low_issues
            },
            'issues': [
                {
                    'issue_id': issue.issue_id,
                    'severity': issue.severity.value,
                    'title': issue.title,
                    'description': issue.description,
                    'affected_prototypes': issue.affected_prototypes,
                    'conflicting_mods': issue.conflicting_mods,
                    'root_cause': issue.root_cause,
                    'suggested_fixes': issue.suggested_fixes
                }
                for issue in report.all_issues
            ],
            'patches': [patch.to_dict() for patch in patches]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _install_patches(self, patch_dir: Path) -> List[Path]:
        """Install patches to Factorio mods directory and create backups"""
        installed = []
        
        factorio_mods = Path(r"C:\Users\eysen\AppData\Roaming\Factorio\mods")
        backup_dir = Path("./patch_backups")
        backup_dir.mkdir(exist_ok=True)
        
        for mod_dir in patch_dir.iterdir():
            if mod_dir.is_dir():
                # Create backup with README
                backup_path = self._create_patch_backup(mod_dir, backup_dir)
                
                # Create zip for Factorio
                zip_path = self._create_patch_zip(mod_dir, factorio_mods)
                
                installed.append(zip_path)
                self.logger.info(f"Installed patch: {zip_path}")
                self.logger.info(f"Backup created: {backup_path}")
        
        return installed
    
    def _create_patch_backup(self, mod_dir: Path, backup_dir: Path) -> Path:
        """Create a backup of the patch with README"""
        import shutil
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{mod_dir.name}_{timestamp}"
        backup_path = backup_dir / backup_name
        
        # Copy the mod directory
        shutil.copytree(mod_dir, backup_path)
        
        # Create README
        readme_content = f"""# {mod_dir.name} - Compatibility Patch

Generated: {datetime.now().isoformat()}
Generator: Factorio Mod Harmonizer

## What this patch does:
This patch resolves mod conflicts by providing conditional recipe modifications
and alternative recipes based on available ingredients.

## Files:
- info.json: Mod metadata
- data-final-fixes.lua: Compatibility fixes that run after all other mods

## Installation:
1. Copy the entire folder to your Factorio mods directory
2. Or use the zipped version that was automatically installed

## Conflicts Resolved:
This patch addresses critical recipe conflicts that could make essential
items uncraftable on certain planets or with certain mod combinations.

## Safety:
This patch uses conditional logic to only apply fixes when needed,
minimizing impact on gameplay when conflicts don't exist.
"""
        
        with open(backup_path / "README.md", 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        return backup_path
    
    def _create_patch_zip(self, mod_dir: Path, target_dir: Path) -> Path:
        """Create a zipped version of the patch for Factorio"""
        
        # Read version from info.json - use the actual version from the file
        with open(mod_dir / "info.json", 'r', encoding='utf-8') as f:
            info = json.load(f)
            version = info.get("version", "1.0.0")
        
        zip_name = f"{mod_dir.name}_{version}.zip"
        zip_path = target_dir / zip_name
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in mod_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(mod_dir.parent)
                    zf.write(file_path, arcname)
        
        return zip_path

@app.command()
def analyze(
    mods_path: str = typer.Option(
        r"C:\Users\eysen\AppData\Roaming\Factorio\mods",
        "--mods-path", "-m",
        help="Path to Factorio mods directory"
    ),
    filter_mods: Optional[List[str]] = typer.Option(
        None, "--filter", "-f",
        help="Filter to specific mods (e.g., wood, steel, space, bob, angel)"
    ),
    output_dir: str = typer.Option(
        "./output",
        "--output", "-o",
        help="Output directory for results"
    ),
    install_patches: bool = typer.Option(
        True, "--install/--no-install",
        help="Automatically install patches to Factorio"
    ),
    show_graph: bool = typer.Option(
        False, "--graph/--no-graph",
        help="Show interactive dependency graph"
    ),
    exclude_harmonizer_patch: bool = typer.Option(
        True, "--exclude-patch/--include-patch",
        help="Exclude the harmonizer patch mod from analysis to see original conflicts"
    ),
    only_enabled: bool = typer.Option(
        True, "--enabled-only/--all-mods",
        help="Only analyze mods that are enabled in mod-list.json"
    )
):
    """🎯 Analyze mod conflicts and generate patches"""
    
    console.print(Panel.fit(
        "[bold blue]🎯 Factorio Mod Harmonizer[/bold blue]\n"
        "[dim]Analyzing mod conflicts and generating solutions...[/dim]",
        border_style="blue"
    ))
    
    # Initialize harmonizer
    harmonizer = ModHarmonizer(mods_path, output_dir)
    
    # Discover mods
    mods = harmonizer.discover_mods(filter_mods, exclude_harmonizer_patch, only_enabled)
    
    if not mods:
        console.print("[red]❌ No mods found![/red]")
        return
    
    # Show discovered mods
    table = Table(title="📦 Discovered Mods")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="magenta")
    table.add_column("Author", style="green")
    table.add_column("Type", style="yellow")
    
    for mod in mods:
        mod_type = "📁 Directory" if not mod.is_zipped else "📦 Zipped"
        table.add_row(mod.name, mod.version, mod.author, mod_type)
    
    console.print(table)
    
    # Analyze conflicts
    report, patches = harmonizer.analyze_conflicts(mods)
    
    # Generate outputs
    outputs = harmonizer.generate_outputs(report, patches)
    
    # Show results
    console.print("\n" + "="*60)
    console.print("[bold green]📊 ANALYSIS COMPLETE![/bold green]")
    console.print("="*60)
    
    # Summary table
    summary_table = Table(title="📈 Analysis Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Count", style="magenta", justify="right")
    
    summary_table.add_row("Total Prototypes", str(report.total_prototypes))
    summary_table.add_row("Conflicted Prototypes", str(report.conflicted_prototypes))
    summary_table.add_row("Critical Issues", str(report.critical_issues))
    summary_table.add_row("Generated Patches", str(len(patches)))
    
    console.print(summary_table)
    
    # Critical issues
    critical_issues = report.get_critical_issues()
    if critical_issues:
        console.print("\n[bold red]🚨 CRITICAL ISSUES:[/bold red]")
        for issue in critical_issues:
            console.print(f"  • [red]{issue.title}[/red]")
            console.print(f"    Mods: {' → '.join(issue.conflicting_mods)}")
    
    # Output files
    console.print(f"\n[bold blue]📁 Generated Files:[/bold blue]")
    for key, value in outputs.items():
        if isinstance(value, list):
            console.print(f"  {key}: {len(value)} files")
            for item in value[:3]:  # Show first 3
                console.print(f"    - {item}")
            if len(value) > 3:
                console.print(f"    ... and {len(value) - 3} more")
        else:
            console.print(f"  {key}: {value}")
    
    # Show graph if requested
    if show_graph:
        try:
            from graph_visualizer import show_dependency_graph
            show_dependency_graph(report, patches)
        except ImportError:
            console.print("[yellow]⚠️  Graph visualization not available (missing dependencies)[/yellow]")
    
    console.print(f"\n[bold green]✅ All done! Patches installed to Factorio mods directory.[/bold green]")

@app.command()
def graph(
    analysis_file: str = typer.Option(
        "./output/analysis_data.json",
        "--file", "-f",
        help="Analysis JSON file to visualize"
    )
):
    """📊 Show interactive dependency graph"""
    try:
        from graph_visualizer import show_dependency_graph_from_file
        show_dependency_graph_from_file(analysis_file)
    except ImportError:
        console.print("[red]❌ Graph visualization requires additional dependencies[/red]")
        console.print("Install with: pip install networkx matplotlib plotly")
    except FileNotFoundError:
        console.print(f"[red]❌ Analysis file not found: {analysis_file}[/red]")
        console.print("Run 'analyze' command first to generate analysis data")

if __name__ == "__main__":
    app() 