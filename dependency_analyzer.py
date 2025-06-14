#!/usr/bin/env python3
"""
Dependency Analyzer
Analyzes prototype dependencies, detects conflicts, and generates solutions
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
from pathlib import Path

from data_models import (
    ConflictSeverity, DependencyType, PrototypeDependency, ConflictIssue,
    AvailabilityContext, PrototypeAnalysis, ModCompatibilityReport, PatchSuggestion,
    create_prototype_key, parse_prototype_key
)
from modification_tracker import ModificationTracker, PrototypeHistory

class DependencyAnalyzer:
    """Analyzes prototype dependencies and detects conflicts"""
    
    def __init__(self, modification_tracker: ModificationTracker):
        self.tracker = modification_tracker
        self.logger = logging.getLogger(__name__)
        
        # Analysis results
        self.dependency_graph: Dict[str, List[PrototypeDependency]] = {}
        self.prototype_analyses: Dict[str, PrototypeAnalysis] = {}
        self.all_issues: List[ConflictIssue] = []
        
        # Planet/context data (simplified for now)
        self.planet_resources = {
            "nauvis": {"iron-ore", "copper-ore", "coal", "stone", "crude-oil", "uranium-ore", "wood"},
            "vulcanus": {"tungsten-ore", "sulfuric-acid", "lava", "calcite"},
            "fulgora": {"scrap", "heavy-oil", "light-oil"},
            "gleba": {"iron-bacteria", "copper-bacteria", "nutrients", "spoilage"},
            "aquilo": {"ammonia", "fluorine", "lithium-brine"},
            "lignumis": {"wood", "lignumis-wood", "tree-seed"}  # Wood planet
        }
    
    def analyze_dependencies(self) -> ModCompatibilityReport:
        """Perform comprehensive dependency analysis"""
        self.logger.info("Starting dependency analysis...")
        
        # Step 1: Build dependency graph
        self._build_dependency_graph()
        
        # Step 2: Analyze each prototype
        self._analyze_prototypes()
        
        # Step 3: Detect conflicts and issues
        self._detect_conflicts()
        
        # Step 4: Generate compatibility report
        report = self._generate_report()
        
        self.logger.info(f"Analysis complete. Found {len(self.all_issues)} issues.")
        return report
    
    def _build_dependency_graph(self):
        """Build the dependency graph from tracked prototypes"""
        self.logger.info("Building dependency graph...")
        
        for key, history in self.tracker.prototype_histories.items():
            prototype_type, prototype_name = parse_prototype_key(key)
            current_data = history.current_value
            
            if not current_data or not isinstance(current_data, dict):
                self.logger.debug(f"Skipping {key}: invalid data type {type(current_data)}")
                continue
            
            dependencies = []
            
            # Analyze based on prototype type
            if prototype_type == "recipe":
                dependencies.extend(self._analyze_recipe_dependencies(current_data))
            elif prototype_type == "technology":
                dependencies.extend(self._analyze_technology_dependencies(current_data))
            elif prototype_type == "item":
                dependencies.extend(self._analyze_item_dependencies(current_data))
            
            if dependencies:
                self.dependency_graph[key] = dependencies
                self.logger.debug(f"Found {len(dependencies)} dependencies for {key}")
    
    def _analyze_recipe_dependencies(self, recipe_data: Dict[str, Any]) -> List[PrototypeDependency]:
        """Analyze dependencies for a recipe"""
        dependencies = []
        recipe_name = recipe_data.get('name', '')
        
        # Ingredient dependencies
        ingredients = recipe_data.get('ingredients', [])
        if isinstance(ingredients, list):
            for ingredient in ingredients:
                if isinstance(ingredient, dict):
                    item_name = ingredient.get('name')
                    item_type = ingredient.get('type', 'item')
                    amount = ingredient.get('amount', 1)
                elif isinstance(ingredient, list) and len(ingredient) >= 2:
                    # Old format: ["item-name", amount]
                    item_name = ingredient[0]
                    item_type = 'item'
                    amount = ingredient[1]
                else:
                    continue
                
                if item_name:
                    dep = PrototypeDependency(
                        source_type="recipe",
                        source_name=recipe_name,
                        target_type=item_type,
                        target_name=item_name,
                        dependency_type=DependencyType.RECIPE_INGREDIENT,
                        amount=amount
                    )
                    dependencies.append(dep)
        
        # Crafting category dependency
        category = recipe_data.get('category', 'crafting')
        if category != 'crafting':  # Default category
            dep = PrototypeDependency(
                source_type="recipe",
                source_name=recipe_name,
                target_type="recipe-category",
                target_name=category,
                dependency_type=DependencyType.CRAFTING_CATEGORY
            )
            dependencies.append(dep)
        
        return dependencies
    
    def _analyze_technology_dependencies(self, tech_data: Dict[str, Any]) -> List[PrototypeDependency]:
        """Analyze dependencies for a technology"""
        dependencies = []
        tech_name = tech_data.get('name', '')
        
        # Prerequisites
        prerequisites = tech_data.get('prerequisites', [])
        for prereq in prerequisites:
            dep = PrototypeDependency(
                source_type="technology",
                source_name=tech_name,
                target_type="technology",
                target_name=prereq,
                dependency_type=DependencyType.TECHNOLOGY_PREREQUISITE
            )
            dependencies.append(dep)
        
        return dependencies
    
    def _analyze_item_dependencies(self, item_data: Dict[str, Any]) -> List[PrototypeDependency]:
        """Analyze dependencies for an item"""
        dependencies = []
        item_name = item_data.get('name', '')
        
        # Fuel category
        fuel_category = item_data.get('fuel_category')
        if fuel_category:
            dep = PrototypeDependency(
                source_type="item",
                source_name=item_name,
                target_type="fuel-category",
                target_name=fuel_category,
                dependency_type=DependencyType.FUEL_CATEGORY
            )
            dependencies.append(dep)
        
        return dependencies
    
    def _analyze_prototypes(self):
        """Analyze each prototype for conflicts and issues"""
        self.logger.info("Analyzing individual prototypes...")
        
        for key, history in self.tracker.prototype_histories.items():
            prototype_type, prototype_name = parse_prototype_key(key)
            
            # Get modification info
            modifying_mods = [record.mod_name for record in history.modifications]
            is_conflicted = len(set(modifying_mods)) > 1
            
            # Get dependencies
            dependencies = self.dependency_graph.get(key, [])
            
            # Check for missing dependencies
            missing_deps = self._check_missing_dependencies(dependencies)
            
            # Analyze availability contexts
            available_contexts, unavailable_contexts = self._analyze_availability(key, dependencies)
            
            # Create analysis
            analysis = PrototypeAnalysis(
                prototype_key=key,
                prototype_type=prototype_type,
                prototype_name=prototype_name,
                modification_count=len(history.modifications),
                modifying_mods=modifying_mods,
                is_conflicted=is_conflicted,
                dependencies=dependencies,
                dependents=[],  # Will be filled in later
                missing_dependencies=missing_deps,
                available_contexts=available_contexts,
                unavailable_contexts=unavailable_contexts
            )
            
            self.prototype_analyses[key] = analysis
    
    def _check_missing_dependencies(self, dependencies: List[PrototypeDependency]) -> List[PrototypeDependency]:
        """Check which dependencies are missing from the game"""
        missing = []
        
        for dep in dependencies:
            target_key = create_prototype_key(dep.target_type, dep.target_name)
            
            # Check if target exists in our tracked prototypes
            if target_key not in self.tracker.prototype_histories:
                # Special handling for built-in categories
                if dep.target_type in ["recipe-category", "fuel-category"]:
                    continue  # Assume these exist
                
                missing.append(dep)
                self.logger.warning(f"Missing dependency: {target_key} required by {dep.source_type}.{dep.source_name}")
        
        return missing
    
    def _analyze_availability(self, prototype_key: str, dependencies: List[PrototypeDependency]) -> Tuple[List[AvailabilityContext], List[AvailabilityContext]]:
        """Analyze in which contexts this prototype is available"""
        available_contexts = []
        unavailable_contexts = []
        
        # Check each planet
        for planet, resources in self.planet_resources.items():
            context = AvailabilityContext(
                planet=planet,
                available_resources=resources,
                mod_context=set()
            )
            
            # Check if all dependencies are available
            is_available = True
            for dep in dependencies:
                if dep.dependency_type == DependencyType.RECIPE_INGREDIENT:
                    # Check if ingredient is available on this planet
                    if not self._is_item_available_on_planet(dep.target_name, planet):
                        is_available = False
                        break
            
            if is_available:
                available_contexts.append(context)
            else:
                unavailable_contexts.append(context)
        
        return available_contexts, unavailable_contexts
    
    def _is_item_available_on_planet(self, item_name: str, planet: str) -> bool:
        """Check if an item is available on a specific planet"""
        # Check if it's a basic resource
        if item_name in self.planet_resources.get(planet, set()):
            return True
        
        # Check if there's a recipe that produces this item and is available on the planet
        item_key = create_prototype_key("item", item_name)
        
        # Look for recipes that produce this item
        for key, history in self.tracker.prototype_histories.items():
            if not key.startswith("recipe."):
                continue
            
            recipe_data = history.current_value
            if not recipe_data or not isinstance(recipe_data, dict):
                continue
            
            # Check if this recipe produces the item
            results = recipe_data.get('results', recipe_data.get('result'))
            if isinstance(results, str) and results == item_name:
                # Simple result format
                return self._is_recipe_available_on_planet(key, planet)
            elif isinstance(results, list):
                for result in results:
                    if isinstance(result, dict) and result.get('name') == item_name:
                        return self._is_recipe_available_on_planet(key, planet)
        
        return False
    
    def _is_recipe_available_on_planet(self, recipe_key: str, planet: str) -> bool:
        """Check if a recipe is available on a specific planet (recursive check)"""
        dependencies = self.dependency_graph.get(recipe_key, [])
        
        for dep in dependencies:
            if dep.dependency_type == DependencyType.RECIPE_INGREDIENT:
                if not self._is_item_available_on_planet(dep.target_name, planet):
                    return False
        
        return True
    
    def _detect_conflicts(self):
        """Detect conflicts and generate issues"""
        self.logger.info("Detecting conflicts...")
        
        # Get conflicts from modification tracker
        conflicts = self.tracker.get_conflicts()
        
        for prototype_key, conflicting_mods in conflicts:
            prototype_type, prototype_name = parse_prototype_key(prototype_key)
            
            # Analyze the specific conflict
            issues = self._analyze_prototype_conflict(prototype_key, conflicting_mods)
            
            # Add issues to prototype analysis
            if prototype_key in self.prototype_analyses:
                self.prototype_analyses[prototype_key].issues.extend(issues)
            
            self.all_issues.extend(issues)
    
    def _analyze_prototype_conflict(self, prototype_key: str, conflicting_mods: List[str]) -> List[ConflictIssue]:
        """Analyze a specific prototype conflict"""
        issues = []
        prototype_type, prototype_name = parse_prototype_key(prototype_key)
        
        history = self.tracker.get_prototype_history(prototype_type, prototype_name)
        if not history:
            return issues
        
        # Special handling for critical recipe conflicts
        if prototype_type == "recipe" and prototype_name in ["burner-inserter", "inserter", "transport-belt"]:
            # These are critical early-game items
            issue = self._create_critical_recipe_conflict(prototype_key, conflicting_mods, history)
            if issue:
                issues.append(issue)
        
        # Check for availability conflicts
        analysis = self.prototype_analyses.get(prototype_key)
        if analysis and analysis.unavailable_contexts:
            issue = self._create_availability_conflict(prototype_key, conflicting_mods, analysis)
            if issue:
                issues.append(issue)
        
        # Generic conflict for other cases
        if not issues:
            issue = self._create_generic_conflict(prototype_key, conflicting_mods, history)
            if issue:
                issues.append(issue)
        
        return issues
    
    def _create_critical_recipe_conflict(self, prototype_key: str, conflicting_mods: List[str], history: PrototypeHistory) -> Optional[ConflictIssue]:
        """Create a critical recipe conflict issue"""
        prototype_type, prototype_name = parse_prototype_key(prototype_key)
        
        # Analyze ingredient changes
        ingredient_changes = []
        for record in history.modifications:
            if record.field_path == "ingredients":
                ingredient_changes.append(record)
        
        if not ingredient_changes:
            return None
        
        # Check if ingredients are problematic
        final_ingredients = ingredient_changes[-1].new_value if ingredient_changes else []
        problematic_ingredients = []
        
        for ingredient in final_ingredients:
            if isinstance(ingredient, dict):
                item_name = ingredient.get('name')
                if item_name and not self._is_item_widely_available(item_name):
                    problematic_ingredients.append(item_name)
        
        severity = ConflictSeverity.CRITICAL if problematic_ingredients else ConflictSeverity.HIGH
        
        issue = ConflictIssue(
            issue_id=f"CRITICAL_RECIPE_{prototype_name.upper()}",
            severity=severity,
            title=f"Critical Recipe Conflict: {prototype_name}",
            description=f"Essential recipe '{prototype_name}' modified by multiple mods with potentially incompatible ingredients",
            affected_prototypes=[prototype_key],
            conflicting_mods=conflicting_mods,
            root_cause=f"Multiple mods modify the {prototype_name} recipe, potentially making it uncraftable on certain planets",
            suggested_fixes=[
                "Create conditional recipe based on available items",
                "Add alternative recipes for different planets",
                "Use compatibility patch to resolve ingredient conflicts"
            ],
            field_path="ingredients"
        )
        
        if problematic_ingredients:
            issue.description += f". Problematic ingredients: {', '.join(problematic_ingredients)}"
        
        return issue
    
    def _create_availability_conflict(self, prototype_key: str, conflicting_mods: List[str], analysis: PrototypeAnalysis) -> Optional[ConflictIssue]:
        """Create an availability conflict issue"""
        unavailable_planets = [ctx.planet for ctx in analysis.unavailable_contexts if ctx.planet]
        
        if not unavailable_planets:
            return None
        
        severity = ConflictSeverity.CRITICAL if "lignumis" in unavailable_planets else ConflictSeverity.HIGH
        
        issue = ConflictIssue(
            issue_id=f"AVAILABILITY_{analysis.prototype_name.upper()}",
            severity=severity,
            title=f"Availability Conflict: {analysis.prototype_name}",
            description=f"Recipe/item '{analysis.prototype_name}' not available on planets: {', '.join(unavailable_planets)}",
            affected_prototypes=[prototype_key],
            conflicting_mods=conflicting_mods,
            root_cause="Recipe requires ingredients not available on certain planets",
            suggested_fixes=[
                "Add planet-specific alternative recipes",
                "Modify ingredients to use locally available items",
                "Add resource processing chains for missing items"
            ]
        )
        
        return issue
    
    def _create_generic_conflict(self, prototype_key: str, conflicting_mods: List[str], history: PrototypeHistory) -> ConflictIssue:
        """Create a generic conflict issue"""
        prototype_type, prototype_name = parse_prototype_key(prototype_key)
        
        # Determine severity based on prototype type
        severity_map = {
            "recipe": ConflictSeverity.HIGH,
            "item": ConflictSeverity.MEDIUM,
            "technology": ConflictSeverity.MEDIUM,
            "entity": ConflictSeverity.LOW
        }
        severity = severity_map.get(prototype_type, ConflictSeverity.LOW)
        
        issue = ConflictIssue(
            issue_id=f"CONFLICT_{prototype_type.upper()}_{prototype_name.upper()}",
            severity=severity,
            title=f"{prototype_type.title()} Conflict: {prototype_name}",
            description=f"{prototype_type.title()} '{prototype_name}' modified by multiple mods",
            affected_prototypes=[prototype_key],
            conflicting_mods=conflicting_mods,
            root_cause=f"Multiple mods modify the same {prototype_type}",
            suggested_fixes=[
                "Review modification order",
                "Create compatibility patch",
                "Use conditional modifications"
            ]
        )
        
        return issue
    
    def _is_item_widely_available(self, item_name: str) -> bool:
        """Check if an item is widely available across planets"""
        available_count = 0
        total_planets = len(self.planet_resources)
        
        for planet in self.planet_resources:
            if self._is_item_available_on_planet(item_name, planet):
                available_count += 1
        
        # Consider widely available if available on 75% of planets
        return available_count >= (total_planets * 0.75)
    
    def _generate_report(self) -> ModCompatibilityReport:
        """Generate the final compatibility report"""
        analyzed_mods = list(set(
            record.mod_name 
            for history in self.tracker.prototype_histories.values()
            for record in history.modifications
        ))
        
        # Count issues by severity
        critical_count = sum(1 for issue in self.all_issues if issue.severity == ConflictSeverity.CRITICAL)
        high_count = sum(1 for issue in self.all_issues if issue.severity == ConflictSeverity.HIGH)
        medium_count = sum(1 for issue in self.all_issues if issue.severity == ConflictSeverity.MEDIUM)
        low_count = sum(1 for issue in self.all_issues if issue.severity == ConflictSeverity.LOW)
        
        report = ModCompatibilityReport(
            analyzed_mods=analyzed_mods,
            analysis_timestamp=datetime.now().isoformat(),
            total_prototypes=len(self.prototype_analyses),
            conflicted_prototypes=sum(1 for analysis in self.prototype_analyses.values() if analysis.is_conflicted),
            critical_issues=critical_count,
            high_issues=high_count,
            medium_issues=medium_count,
            low_issues=low_count,
            prototype_analyses=self.prototype_analyses,
            all_issues=self.all_issues,
            dependency_graph=self.dependency_graph,
            mod_load_order=analyzed_mods,  # Simplified
            mod_dependencies={}  # TODO: Extract from mod info
        )
        
        return report
    
    def generate_patch_suggestions(self, report: ModCompatibilityReport) -> List[PatchSuggestion]:
        """Generate patch suggestions for critical issues"""
        patches = []
        
        critical_issues = report.get_critical_issues()
        
        for issue in critical_issues:
            if issue.issue_id.startswith("CRITICAL_RECIPE_"):
                patch = self._create_recipe_patch(issue, report)
                if patch:
                    patches.append(patch)
            elif issue.issue_id.startswith("AVAILABILITY_"):
                patch = self._create_availability_patch(issue, report)
                if patch:
                    patches.append(patch)
        
        return patches
    
    def _create_recipe_patch(self, issue: ConflictIssue, report: ModCompatibilityReport) -> Optional[PatchSuggestion]:
        """Create a patch for recipe conflicts"""
        if not issue.affected_prototypes:
            return None
        
        prototype_key = issue.affected_prototypes[0]
        prototype_type, prototype_name = parse_prototype_key(prototype_key)
        
        # Generate conditional recipe modification
        lua_code = f'''
-- Compatibility patch for {prototype_name}
-- Fixes conflict between: {", ".join(issue.conflicting_mods)}

if data.raw.recipe["{prototype_name}"] then
    local recipe = data.raw.recipe["{prototype_name}"]
    
    -- Check available ingredients and choose appropriate version
    if data.raw.item["wood-gear-wheel"] and not data.raw.item["kr-steel-gear-wheel"] then
        -- Lignumis context: use wood gear
        recipe.ingredients = {{
            {{type = "item", name = "iron-plate", amount = 1}},
            {{type = "item", name = "wood-gear-wheel", amount = 1}}
        }}
    elseif data.raw.item["kr-steel-gear-wheel"] then
        -- Krastorio2 context: use steel gear but add fallback
        recipe.ingredients = {{
            {{type = "item", name = "iron-plate", amount = 1}},
            {{type = "item", name = "kr-steel-gear-wheel", amount = 1}}
        }}
        
        -- Add alternative recipe for wood planets
        if data.raw.item["wood-gear-wheel"] then
            data:extend({{{{
                type = "recipe",
                name = "{prototype_name}-wood",
                enabled = true,
                ingredients = {{
                    {{type = "item", name = "iron-plate", amount = 1}},
                    {{type = "item", name = "wood-gear-wheel", amount = 1}}
                }},
                results = {{{{type = "item", name = "{prototype_name}", amount = 1}}}}
            }}}})
        end
    end
end
'''
        
        patch = PatchSuggestion(
            patch_id=f"PATCH_{prototype_name.upper()}_COMPAT",
            target_mod="factorio-harmonizer-patch",
            target_file="data-final-fixes.lua",
            issue_ids=[issue.issue_id],
            patch_type="recipe_modification",
            description=f"Conditional recipe modification for {prototype_name} to resolve mod conflicts",
            lua_code=lua_code,
            estimated_impact=ConflictSeverity.HIGH
        )
        
        return patch
    
    def _create_availability_patch(self, issue: ConflictIssue, report: ModCompatibilityReport) -> Optional[PatchSuggestion]:
        """Create a patch for availability conflicts"""
        # This would create alternative recipes or resource processing chains
        # Implementation depends on specific conflict details
        return None

# Test functions
def test_dependency_analyzer():
    """Test the dependency analyzer with real mod data"""
    print("🧪 Testing Dependency Analyzer...")
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Import required modules
    from mod_info import ModDiscovery
    from lua_environment import FactorioLuaEnvironment
    from modification_tracker import ModificationTracker
    
    # Set up the full pipeline
    factorio_mods_path = Path(r"C:\Users\eysen\AppData\Roaming\Factorio\mods")
    discovery = ModDiscovery(factorio_mods_path)
    mods = discovery.discover_mods()
    
    # Filter to target mods
    target_mods = ["lignumis", "Krastorio2-spaced-out"]
    filtered_mods = [mod for mod in mods if any(target in mod.name for target in target_mods)]
    
    print(f"Found {len(filtered_mods)} target mods for analysis")
    
    # Set up tracking
    tracker = ModificationTracker()
    lua_env = FactorioLuaEnvironment()
    
    # Integrate tracker with lua environment
    def tracked_data_extend(json_string):
        try:
            import json
            prototypes = json.loads(json_string)
            
            for prototype in prototypes:
                ptype = prototype.get('type')
                name = prototype.get('name')
                
                if ptype and name:
                    tracker.track_prototype_addition(ptype, name, prototype)
                    
                    if ptype not in lua_env.data_raw:
                        lua_env.data_raw[ptype] = {}
                    lua_env.data_raw[ptype][name] = prototype
            
            return True
        except Exception as e:
            print(f"Error in tracked data:extend: {e}")
            return False
    
    lua_env.lua.globals().python_data_extend = tracked_data_extend
    
    # Simulate mod loading with realistic conflicts
    print("\n🌳 Simulating base game...")
    tracker.set_mod_context("base", "data/base/prototypes/recipe.lua", 100)
    
    base_code = '''
        data:extend({
            {
                type = "item",
                name = "iron-plate",
                stack_size = 100,
                icon = "__base__/graphics/icons/iron-plate.png"
            },
            {
                type = "item",
                name = "wood",
                stack_size = 50,
                icon = "__base__/graphics/icons/wood.png",
                fuel_value = "2MJ",
                fuel_category = "chemical"
            },
            {
                type = "recipe",
                name = "burner-inserter",
                enabled = true,
                ingredients = {
                    {type = "item", name = "iron-plate", amount = 1}
                },
                results = {
                    {type = "item", name = "burner-inserter", amount = 1}
                }
            }
        })
    '''
    lua_env.execute_lua_code(base_code)
    
    print("\n🌲 Simulating Lignumis mod...")
    tracker.set_mod_context("lignumis", "data.lua", 50)
    
    lignumis_code = '''
        data:extend({
            {
                type = "item",
                name = "wood-gear-wheel",
                stack_size = 100,
                icon = "__lignumis__/graphics/icons/wood-gear.png"
            },
            {
                type = "item",
                name = "lignumis-wood",
                stack_size = 100,
                icon = "__lignumis__/graphics/icons/wood.png",
                fuel_value = "3MJ",
                fuel_category = "chemical"
            }
        })
    '''
    lua_env.execute_lua_code(lignumis_code)
    
    # Simulate recipe modification
    tracker.track_prototype_modification(
        "recipe", "burner-inserter", "ingredients",
        [{"type": "item", "name": "iron-plate", "amount": 1}],
        [
            {"type": "item", "name": "iron-plate", "amount": 1},
            {"type": "item", "name": "wood-gear-wheel", "amount": 1}
        ]
    )
    
    print("\n⚙️  Simulating Krastorio2 mod...")
    tracker.set_mod_context("Krastorio2-spaced-out", "data-updates.lua", 200)
    
    krastorio_code = '''
        data:extend({
            {
                type = "item",
                name = "kr-steel-gear-wheel",
                stack_size = 100,
                icon = "__krastorio2__/graphics/icons/steel-gear.png"
            }
        })
    '''
    lua_env.execute_lua_code(krastorio_code)
    
    # Simulate Krastorio2 overriding the recipe
    tracker.track_prototype_modification(
        "recipe", "burner-inserter", "ingredients",
        [
            {"type": "item", "name": "iron-plate", "amount": 1},
            {"type": "item", "name": "wood-gear-wheel", "amount": 1}
        ],
        [
            {"type": "item", "name": "iron-plate", "amount": 1},
            {"type": "item", "name": "kr-steel-gear-wheel", "amount": 1}
        ]
    )
    
    # Now run the dependency analysis
    print("\n🔍 Running dependency analysis...")
    analyzer = DependencyAnalyzer(tracker)
    report = analyzer.analyze_dependencies()
    
    # Display results
    print(f"\n📊 Analysis Results:")
    print(f"  Total prototypes: {report.total_prototypes}")
    print(f"  Conflicted prototypes: {report.conflicted_prototypes}")
    print(f"  Critical issues: {report.critical_issues}")
    print(f"  High issues: {report.high_issues}")
    print(f"  Medium issues: {report.medium_issues}")
    print(f"  Low issues: {report.low_issues}")
    
    # Show critical issues
    critical_issues = report.get_critical_issues()
    if critical_issues:
        print(f"\n🚨 Critical Issues:")
        for issue in critical_issues:
            print(f"  {issue.title}")
            print(f"    Severity: {issue.severity.value}")
            print(f"    Mods: {', '.join(issue.conflicting_mods)}")
            print(f"    Description: {issue.description}")
            print(f"    Suggested fixes: {issue.suggested_fixes}")
    
    # Generate patches
    print(f"\n🔧 Generating patch suggestions...")
    patches = analyzer.generate_patch_suggestions(report)
    
    if patches:
        print(f"Generated {len(patches)} patch suggestions:")
        for patch in patches:
            print(f"  {patch.patch_id}: {patch.description}")
            print(f"    Target: {patch.target_mod}/{patch.target_file}")
            print(f"    Impact: {patch.estimated_impact.value}")
    
    # Export results
    output_path = Path("./logs/dependency_analysis.json")
    import json
    
    # Convert report to serializable format
    report_data = {
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
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Analysis results exported to: {output_path}")
    print("\n✅ Dependency Analyzer tests complete!")
    
    return report, patches

if __name__ == "__main__":
    test_dependency_analyzer() 