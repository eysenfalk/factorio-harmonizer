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
        
        # Planet/context data - should be extracted from actual game data
        self.planet_resources = self._extract_planet_resources_from_mods()
    
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
        
        # Detect missing dependency conflicts
        self._detect_missing_dependency_conflicts()
        
        # Detect broken research chains
        self._detect_broken_research_chains()
        
        # Detect actual mod recipe conflicts
        self._detect_mod_recipe_conflicts()
    
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
        """Generate patch suggestions for ALL issues (not just critical ones)"""
        patches = []
        
        # Process ALL issues, not just critical ones
        all_issues = report.all_issues
        
        # Sort issues by type and priority for better organization
        recipe_issues = []
        research_issues = []
        other_issues = []
        
        for issue in all_issues:
            if any("recipe." in proto for proto in issue.affected_prototypes):
                recipe_issues.append(issue)
            elif any("technology." in proto for proto in issue.affected_prototypes):
                research_issues.append(issue)
            else:
                other_issues.append(issue)
        
        # Sort by severity (critical first, then high, medium, low)
        severity_order = [ConflictSeverity.CRITICAL, ConflictSeverity.HIGH, ConflictSeverity.MEDIUM, ConflictSeverity.LOW, ConflictSeverity.INFO]
        
        def sort_by_severity(issues):
            return sorted(issues, key=lambda x: severity_order.index(x.severity) if x.severity in severity_order else len(severity_order))
        
        recipe_issues = sort_by_severity(recipe_issues)
        research_issues = sort_by_severity(research_issues)
        other_issues = sort_by_severity(other_issues)
        
        # Track processed prototypes to avoid duplicates
        processed_prototypes = set()
        
        # Generate patches for recipe conflicts first (highest priority)
        for issue in recipe_issues:
            if not issue.affected_prototypes:
                continue
                
            prototype_key = issue.affected_prototypes[0]
            
            # Skip if we've already processed this prototype
            if prototype_key in processed_prototypes:
                continue
                
            processed_prototypes.add(prototype_key)
            
            patch = self._create_recipe_patch(issue, report)
            if patch:
                patches.append(patch)
        
        # Generate patches for research conflicts
        for issue in research_issues:
            if not issue.affected_prototypes:
                continue
                
            prototype_key = issue.affected_prototypes[0]
            
            # Skip if we've already processed this prototype
            if prototype_key in processed_prototypes:
                continue
                
            processed_prototypes.add(prototype_key)
            
            patch = self._create_research_patch(issue, report)
            if patch:
                patches.append(patch)
        
        # Generate patches for other conflicts
        for issue in other_issues:
            if not issue.affected_prototypes:
                continue
                
            prototype_key = issue.affected_prototypes[0]
            
            # Skip if we've already processed this prototype
            if prototype_key in processed_prototypes:
                continue
                
            processed_prototypes.add(prototype_key)
            
            # Determine patch type based on issue type
            if issue.severity == ConflictSeverity.CRITICAL:
                patch = self._create_availability_patch(issue, report)
            else:
                patch = self._create_generic_patch(issue, report)
            
            if patch:
                patches.append(patch)
        
        return patches
    
    def _create_recipe_patch(self, issue: ConflictIssue, report: ModCompatibilityReport) -> Optional[PatchSuggestion]:
        """Create patches that preserve ALL original mod recipes and add them as alternatives"""
        if not issue.affected_prototypes:
            return None
        
        prototype_key = issue.affected_prototypes[0]
        prototype_type, prototype_name = parse_prototype_key(prototype_key)
        
        # Get the modification history to extract ACTUAL recipe data from each mod
        history = self.tracker.get_prototype_history(prototype_type, prototype_name)
        if not history:
            return None
        
        # Extract the REAL recipe data from each mod's modifications
        mod_recipe_data = {}
        
        for record in history.modifications:
            mod_name = record.mod_name
            if mod_name not in mod_recipe_data:
                mod_recipe_data[mod_name] = {
                    'name': prototype_name,
                    'type': 'recipe',
                    'enabled': True
                }
            
            # Extract the actual recipe data from the modification
            if record.new_value and isinstance(record.new_value, dict):
                # Copy all fields from the new value
                for key, value in record.new_value.items():
                    if key not in ['modified_by', 'modifications']:
                        mod_recipe_data[mod_name][key] = value
                
                # Handle direct recipe fields
                if 'ingredients' in record.new_value:
                    mod_recipe_data[mod_name]['ingredients'] = record.new_value['ingredients']
                if 'results' in record.new_value:
                    mod_recipe_data[mod_name]['results'] = record.new_value['results']
                if 'energy_required' in record.new_value:
                    mod_recipe_data[mod_name]['energy_required'] = record.new_value['energy_required']
                if 'category' in record.new_value:
                    mod_recipe_data[mod_name]['category'] = record.new_value['category']
            
            # Handle field-specific modifications
            elif record.field_path == "ingredients" and record.new_value:
                mod_recipe_data[mod_name]['ingredients'] = record.new_value
            elif record.field_path == "results" and record.new_value:
                mod_recipe_data[mod_name]['results'] = record.new_value
            elif record.field_path == "energy_required" and record.new_value:
                mod_recipe_data[mod_name]['energy_required'] = record.new_value
            elif record.field_path == "category" and record.new_value:
                mod_recipe_data[mod_name]['category'] = record.new_value
        
        # Filter out mods that don't have meaningful recipe data
        valid_mod_data = {}
        for mod_name, recipe_data in mod_recipe_data.items():
            # Only include mods that have actual recipe ingredients or meaningful modifications
            if ('ingredients' in recipe_data and recipe_data['ingredients']) or \
               ('results' in recipe_data and recipe_data['results']) or \
               ('category' in recipe_data and recipe_data['category']):
                valid_mod_data[mod_name] = recipe_data
        
        # If no valid recipe data found, skip this patch
        if not valid_mod_data:
            self.logger.warning(f"No valid recipe data found for {prototype_name}, skipping patch generation")
            return None
        
        # Create mod-friendly names mapping
        mod_display_names = {
            "lignumis": "Lignumis",
            "bobassembly": "Bob's Assembly",
            "bobelectronics": "Bob's Electronics", 
            "bobpower": "Bob's Power",
            "Krastorio2": "Krastorio 2",
            "Krastorio2-spaced-out": "Krastorio 2 Spaced Out",
            "aai-industry": "AAI Industry",
            "base": "Base Game"
        }
        
        # Generate Lua patch that creates ADDITIONAL recipes alongside originals
        lua_code = f'''
-- Comprehensive recipe expansion for {prototype_name}
-- Adds mod-specific recipe variants alongside original recipes
-- Affected mods: {", ".join(valid_mod_data.keys())}
-- Severity: {issue.severity.value.upper()}

-- Create additional recipe variants for each mod
'''

        # Create additional recipes for each mod (don't disable originals!)
        for mod_name, recipe_data in valid_mod_data.items():
            clean_mod_name = mod_name.replace("-", "_").replace(" ", "_").lower()
            recipe_name = f"{prototype_name}-{clean_mod_name}-variant"
            display_name = mod_display_names.get(mod_name, mod_name)
            
            lua_code += f'''

-- {display_name} variant of {prototype_name}
if data.raw.recipe["{prototype_name}"] then
    local {clean_mod_name}_variant = table.deepcopy(data.raw.recipe["{prototype_name}"])
    {clean_mod_name}_variant.name = "{recipe_name}"
    {clean_mod_name}_variant.localised_name = {{"", "{prototype_name}", " ({display_name} Style)"}}
    {clean_mod_name}_variant.enabled = true
    {clean_mod_name}_variant.order = ({clean_mod_name}_variant.order or "a") .. "-{clean_mod_name}-variant"
    {clean_mod_name}_variant.hidden = false
'''
            
            # Set the ACTUAL ingredients from the mod
            if 'ingredients' in recipe_data and recipe_data['ingredients']:
                ingredients_lua = self._convert_ingredients_to_lua(recipe_data['ingredients'])
                lua_code += f'''
    {clean_mod_name}_variant.ingredients = {ingredients_lua}'''
            
            # Set results if specified
            if 'results' in recipe_data and recipe_data['results']:
                results_lua = self._convert_ingredients_to_lua(recipe_data['results'])
                lua_code += f'''
    {clean_mod_name}_variant.results = {results_lua}'''
            elif prototype_name:
                # Default result if not specified
                lua_code += f'''
    {clean_mod_name}_variant.results = {{{{type="item", name="{prototype_name}", amount=1}}}}'''
            
            # Set energy required if specified
            if 'energy_required' in recipe_data and recipe_data['energy_required']:
                lua_code += f'''
    {clean_mod_name}_variant.energy_required = {recipe_data['energy_required']}'''
            
            # Set category if specified
            if 'category' in recipe_data and recipe_data['category']:
                category = recipe_data['category'].strip('"\'')
                lua_code += f'''
    {clean_mod_name}_variant.category = "{category}"'''
            
            lua_code += f'''
    
    data:extend({{{clean_mod_name}_variant}})
end'''

        lua_code += f'''

-- Keep ALL original recipes active - no disabling!
-- Players can now choose between:
-- 1. Original {prototype_name} (current winner of mod conflicts)
'''
        
        for mod_name in valid_mod_data.keys():
            clean_mod_name = mod_name.replace("-", "_").replace(" ", "_").lower()
            display_name = mod_display_names.get(mod_name, mod_name)
            lua_code += f'''-- 2. {prototype_name}-{clean_mod_name}-variant ({display_name} style)
'''
        
        patch = PatchSuggestion(
            patch_id=f"PATCH_{prototype_name.upper()}_ALL_VARIANTS",
            target_mod="factorio-harmonizer-patch",
            target_file="data-final-fixes.lua",
            issue_ids=[issue.issue_id],
            patch_type="recipe_variant_expansion",
            description=f"Recipe expansion for {prototype_name} - adds all mod variants as additional recipes",
            lua_code=lua_code,
            settings_code="",  # No settings needed
            estimated_impact=issue.severity
        )
        
        return patch
    
    def _convert_ingredients_to_lua(self, ingredients) -> str:
        """Convert ingredients list to Lua table format (Factorio 2.0 compatible)"""
        if not ingredients:
            return "{}"
        
        if isinstance(ingredients, str):
            # Handle string format ingredients
            return ingredients
        
        if isinstance(ingredients, list):
            # Deduplicate ingredients first
            seen_ingredients = {}
            unique_ingredients = []
            
            for ingredient in ingredients:
                ingredient_key = None
                ingredient_data = None
                
                if isinstance(ingredient, dict):
                    if 'type' in ingredient and 'name' in ingredient and 'amount' in ingredient:
                        # New format: {type="item", name="iron-plate", amount=2}
                        ingredient_key = (ingredient["type"], ingredient["name"])
                        ingredient_data = ingredient
                    elif 'name' in ingredient and 'amount' in ingredient:
                        # Simple format: {name="iron-plate", amount=2} - add type
                        ingredient_key = ("item", ingredient["name"])
                        ingredient_data = {
                            "type": "item",
                            "name": ingredient["name"],
                            "amount": ingredient["amount"]
                        }
                elif isinstance(ingredient, list) and len(ingredient) >= 2:
                    # Old format: ["iron-plate", 2] - convert to new format
                    ingredient_key = ("item", ingredient[0])
                    ingredient_data = {
                        "type": "item",
                        "name": ingredient[0],
                        "amount": ingredient[1]
                    }
                elif isinstance(ingredient, str):
                    # String format - assume amount 1
                    ingredient_key = ("item", ingredient)
                    ingredient_data = {
                        "type": "item",
                        "name": ingredient,
                        "amount": 1
                    }
                
                # Only add if we haven't seen this ingredient before
                if ingredient_key and ingredient_key not in seen_ingredients:
                    seen_ingredients[ingredient_key] = True
                    unique_ingredients.append(ingredient_data)
            
            # Convert to Lua format
            lua_items = []
            for ingredient in unique_ingredients:
                lua_items.append(f'{{type="{ingredient["type"]}", name="{ingredient["name"]}", amount={ingredient["amount"]}}}')
            
            return "{" + ", ".join(lua_items) + "}"
        
        return str(ingredients)
    
    def _create_research_patch(self, issue: ConflictIssue, report: ModCompatibilityReport) -> Optional[PatchSuggestion]:
        """Create a comprehensive patch for research/technology conflicts with alternative research paths"""
        if not issue.affected_prototypes:
            return None
        
        prototype_key = issue.affected_prototypes[0]
        prototype_type, prototype_name = parse_prototype_key(prototype_key)
        
        # Get the modification history to understand what each mod did
        history = self.tracker.get_prototype_history(prototype_type, prototype_name)
        if not history:
            return None
        
        # Extract different technology versions from mod modifications
        mod_techs = {}
        base_tech = None
        
        for record in history.modifications:
            if record.field_path in ["prerequisites", "unit", "effects"]:
                if record.mod_name not in mod_techs:
                    mod_techs[record.mod_name] = {}
                mod_techs[record.mod_name][record.field_path] = record.new_value
                if not base_tech:
                    base_tech = record.old_value
        
        # Generate comprehensive technology compatibility patch
        lua_code = f'''
-- Comprehensive research compatibility patch for {prototype_name}
-- Fixes conflict between: {", ".join(issue.conflicting_mods)}
-- Severity: {issue.severity.value.upper()}

if data.raw.technology["{prototype_name}"] then
    local tech = data.raw.technology["{prototype_name}"]
    local original_prerequisites = tech.prerequisites or {{}}
    local original_unit = tech.unit
    local original_effects = tech.effects or {{}}
    
    -- Store original technology for reference
    local base_prerequisites = original_prerequisites
    local base_unit = original_unit
    local base_effects = original_effects
    
'''
        
        # Add conditional logic for each mod's version
        alternative_count = 0
        for mod_name, tech_data in mod_techs.items():
            if tech_data:
                alternative_count += 1
                lua_code += f'''    -- Alternative research path for {mod_name} context
    if mods["{mod_name}"] then
        -- Check if {mod_name} specific prerequisites are available
        local {mod_name.lower().replace("-", "_")}_prereqs_available = true
'''
                
                # Check prerequisite availability
                if "prerequisites" in tech_data:
                    for prereq in tech_data["prerequisites"]:
                        lua_code += f'        if not data.raw.technology["{prereq}"] then {mod_name.lower().replace("-", "_")}_prereqs_available = false end\n'
                
                lua_code += f'''        
        if {mod_name.lower().replace("-", "_")}_prereqs_available then
'''
                
                # Apply mod-specific changes
                if "prerequisites" in tech_data:
                    lua_code += f'            tech.prerequisites = {{'
                    for prereq in tech_data["prerequisites"]:
                        lua_code += f'"{prereq}", '
                    lua_code += '}\n'
                
                if "unit" in tech_data and tech_data["unit"]:
                    unit_data = tech_data["unit"]
                    if isinstance(unit_data, dict):
                        lua_code += f'''            tech.unit = {{
                count = {unit_data.get("count", 100)},
                ingredients = {{
'''
                        if "ingredients" in unit_data:
                            for ingredient in unit_data["ingredients"]:
                                if isinstance(ingredient, list) and len(ingredient) >= 2:
                                    lua_code += f'                    {{"{ingredient[0]}", {ingredient[1]}}},\n'
                        lua_code += '''                }},
                time = ''' + str(unit_data.get("time", 30)) + '''
            }
'''
                
                lua_code += f'''        end
        
        -- Create alternative research path for other contexts
            data:extend({{{{
            type = "technology",
            name = "{prototype_name}-{mod_name.lower()}",
            icon = tech.icon,
            icon_size = tech.icon_size or 256,
            prerequisites = base_prerequisites,
            unit = {{
                count = 50,
                ingredients = {{
                    {{"automation-science-pack", 1}},
                    {{"logistic-science-pack", 1}}
                }},
                time = 15
            }},
            effects = base_effects
            }}}})
        end
    
'''
        
        # Add fallback alternative research paths
        lua_code += f'''    -- Fallback: Create universal alternative research paths
    
    -- Skip creating alternatives if original technology has no icon (required for technologies)
    if not tech.icon then
        log("Factorio Harmonizer: Skipping alternatives for " .. "{prototype_name}" .. " - no icon found")
        return
    end
    
    -- Alternative 1: Basic research path
    local basic_tech = {{
        type = "technology",
        name = "{prototype_name}-basic",
        icon = tech.icon,
        icon_size = tech.icon_size or 256,
        prerequisites = {{"automation"}},
        unit = {{
            count = 25,
            ingredients = {{
                {{"automation-science-pack", 1}}
            }},
            time = 10
        }},
        effects = tech.effects or {{}}
    }}
    
    data:extend({{basic_tech}})
    
    -- Alternative 2: Advanced research path
    if data.raw.technology["logistic-science-pack"] then
        local advanced_tech = {{
            type = "technology",
            name = "{prototype_name}-advanced",
            icon = tech.icon,
            icon_size = tech.icon_size or 256,
            prerequisites = {{"automation", "logistic-science-pack"}},
            unit = {{
                count = 100,
                ingredients = {{
                    {{"automation-science-pack", 1}},
                    {{"logistic-science-pack", 1}}
                }},
                time = 30
            }},
            effects = tech.effects or {{}}
        }}
        
        data:extend({{advanced_tech}})
    end
    
    -- Alternative 3: Space-age compatible path
    if data.raw.technology["space-science-pack"] then
        local space_tech = {{
            type = "technology",
            name = "{prototype_name}-space",
            icon = tech.icon,
            icon_size = tech.icon_size or 256,
            prerequisites = {{"space-science-pack"}},
            unit = {{
                count = 200,
                ingredients = {{
                    {{"automation-science-pack", 1}},
                    {{"logistic-science-pack", 1}},
                    {{"chemical-science-pack", 1}},
                    {{"space-science-pack", 1}}
                }},
                time = 60
            }},
            effects = tech.effects or {{}}
        }}
        
        data:extend({{space_tech}})
    end
end
'''
        
        patch = PatchSuggestion(
            patch_id=f"PATCH_{prototype_name.upper()}_RESEARCH_COMPREHENSIVE",
            target_mod="factorio-harmonizer-patch",
            target_file="data-final-fixes.lua",
            issue_ids=[issue.issue_id],
            patch_type="comprehensive_research_modification",
            description=f"Comprehensive research compatibility patch for {prototype_name} with {alternative_count + 3} alternative research paths",
            lua_code=lua_code,
            estimated_impact=issue.severity
        )
        
        return patch
    
    def _create_availability_patch(self, issue: ConflictIssue, report: ModCompatibilityReport) -> Optional[PatchSuggestion]:
        """Create a patch for availability conflicts"""
        # This would create alternative recipes or resource processing chains
        # Implementation depends on specific conflict details
        return None
    
    def _create_generic_patch(self, issue: ConflictIssue, report: ModCompatibilityReport) -> Optional[PatchSuggestion]:
        """Create a generic compatibility patch for other types of conflicts"""
        if not issue.affected_prototypes:
            return None
        
        prototype_key = issue.affected_prototypes[0]
        prototype_type, prototype_name = parse_prototype_key(prototype_key)
        
        # Generate generic compatibility patch based on prototype type
        lua_code = f'''
-- Generic compatibility patch for {prototype_name}
-- Fixes conflict between: {", ".join(issue.conflicting_mods)}
-- Severity: {issue.severity.value.upper()}
-- Type: {prototype_type}

'''
        
        if prototype_type == "item":
            lua_code += f'''
if data.raw.item["{prototype_name}"] then
    local item = data.raw.item["{prototype_name}"]
    
    -- Skip creating alternatives if original item has no icon (required for items)
    if not item.icon then
        log("Factorio Harmonizer: Skipping alternatives for " .. "{prototype_name}" .. " - no icon found")
        return
    end
    
    -- Ensure item compatibility across mods
    -- Create alternative versions if needed
    
    -- Alternative 1: Basic version
    local basic_item = {{
        type = "item",
        name = "{prototype_name}-basic",
        icon = item.icon,
        icon_size = item.icon_size or 64,
        stack_size = item.stack_size or 100,
        subgroup = item.subgroup or "intermediate-product",
        order = (item.order or "a") .. "-basic"
    }}
    
    data:extend({{basic_item}})
    
    -- Alternative 2: Advanced version
    local advanced_item = {{
        type = "item",
        name = "{prototype_name}-advanced",
        icon = item.icon,
        icon_size = item.icon_size or 64,
        stack_size = math.max(1, math.floor((item.stack_size or 100) * 0.5)),
        subgroup = item.subgroup or "intermediate-product",
        order = (item.order or "a") .. "-advanced"
    }}
    
    data:extend({{advanced_item}})
end
'''
        elif prototype_type == "entity":
            lua_code += f'''
if data.raw["{prototype_type}"] and data.raw["{prototype_type}"]["{prototype_name}"] then
    local entity = data.raw["{prototype_type}"]["{prototype_name}"]
    
    -- Ensure entity compatibility across mods
    -- Create alternative versions if needed
    
    -- Alternative 1: Basic version
    local basic_entity = table.deepcopy(entity)
    basic_entity.name = "{prototype_name}-basic"
    basic_entity.minable = basic_entity.minable or {{mining_time = 0.1, result = "{prototype_name}-basic"}}
    
    -- Only modify icon if original has one
    if basic_entity.icon then
        -- Keep original icon
    end
    
    data:extend({{basic_entity}})
    
    -- Alternative 2: Advanced version  
    local advanced_entity = table.deepcopy(entity)
    advanced_entity.name = "{prototype_name}-advanced"
    advanced_entity.minable = advanced_entity.minable or {{mining_time = 0.1, result = "{prototype_name}-advanced"}}
    if advanced_entity.max_health then
        advanced_entity.max_health = advanced_entity.max_health * 2
    end
    
    -- Only modify icon if original has one
    if advanced_entity.icon then
        -- Keep original icon
    end
    
    data:extend({{advanced_entity}})
end
'''
        else:
            lua_code += f'''
if data.raw["{prototype_type}"] and data.raw["{prototype_type}"]["{prototype_name}"] then
    local prototype = data.raw["{prototype_type}"]["{prototype_name}"]
    
    -- Generic compatibility fixes
    -- Ensure prototype remains functional across mod combinations
    
    -- Log the conflict resolution
    log("Factorio Harmonizer: Applied generic compatibility patch for " .. "{prototype_type}.{prototype_name}")
end
'''
        
        patch = PatchSuggestion(
            patch_id=f"PATCH_{prototype_name.upper()}_GENERIC",
            target_mod="factorio-harmonizer-patch", 
            target_file="data-final-fixes.lua",
            issue_ids=[issue.issue_id],
            patch_type="generic_compatibility",
            description=f"Generic compatibility patch for {prototype_type} {prototype_name}",
            lua_code=lua_code,
            estimated_impact=issue.severity
        )
        
        return patch
    
    def _detect_missing_dependency_conflicts(self) -> None:
        """Detect conflicts caused by missing dependencies."""
        self.logger.info("Detecting missing dependency conflicts...")
        
        for key, analysis in self.prototype_analyses.items():
            if analysis.missing_dependencies:
                prototype_type, prototype_name = parse_prototype_key(key)
                
                # Create conflict for missing dependencies
                missing_deps = [dep.target_name for dep in analysis.missing_dependencies]
                
                conflict = ConflictIssue(
                    issue_id=f"MISSING_DEPS_{prototype_name.upper()}",
                    severity=ConflictSeverity.HIGH,
                    title=f"Missing Dependencies: {prototype_name}",
                    description=f"{prototype_type.title()} {prototype_name} has missing dependencies: {', '.join(missing_deps)}",
                    affected_prototypes=[key],
                    conflicting_mods=analysis.modifying_mods,
                    root_cause=f"Required dependencies not found: {', '.join(missing_deps)}",
                    suggested_fixes=[f"Add missing dependencies: {', '.join(missing_deps)}"]
                )
                self.all_issues.append(conflict)
                self.logger.info(f"Created missing dependency conflict for {key}")

    def _detect_broken_research_chains(self) -> None:
        """Detect research chains that have been broken by mod modifications."""
        self.logger.info("Detecting broken research chains...")
        
        # Build a map of what technologies are reachable from the base game
        reachable_techs = set()
        
        # Get all technology prototypes and their dependencies
        tech_dependencies = {}
        for key, history in self.tracker.prototype_histories.items():
            prototype_type, prototype_name = parse_prototype_key(key)
            if prototype_type == "technology":
                # Get dependencies from our dependency graph
                deps = self.dependency_graph.get(key, [])
                prereqs = [dep.target_name for dep in deps 
                          if dep.dependency_type == DependencyType.TECHNOLOGY_PREREQUISITE]
                tech_dependencies[prototype_name] = prereqs
        
        # Start with technologies that have no prerequisites (base techs)
        tech_queue = []
        for tech_name, prereqs in tech_dependencies.items():
            if not prereqs:
                tech_queue.append(tech_name)
                reachable_techs.add(tech_name)
        
        # BFS to find all reachable technologies
        while tech_queue:
            current_tech = tech_queue.pop(0)
            
            # Find technologies that depend on this one
            for tech_name, prereqs in tech_dependencies.items():
                if tech_name not in reachable_techs:
                    # Check if all prerequisites are reachable
                    all_prereqs_reachable = True
                    for prereq in prereqs:
                        if prereq not in reachable_techs:
                            all_prereqs_reachable = False
                            break
                    
                    if all_prereqs_reachable:
                        tech_queue.append(tech_name)
                        reachable_techs.add(tech_name)
        
        # Find technologies that should be reachable but aren't
        for tech_name, prereqs in tech_dependencies.items():
            if tech_name not in reachable_techs:
                # This technology is unreachable - create a conflict
                missing_prereqs = []
                for prereq in prereqs:
                    if prereq not in tech_dependencies:
                        missing_prereqs.append(prereq)
                
                if missing_prereqs:
                    # Get the prototype history to find which mods modified it
                    tech_key = create_prototype_key("technology", tech_name)
                    history = self.tracker.prototype_histories.get(tech_key)
                    affected_mods = [record.mod_name for record in history.modifications] if history else []
                    
                    conflict = ConflictIssue(
                        issue_id=f"BROKEN_CHAIN_{tech_name}",
                        severity=ConflictSeverity.HIGH,
                        title=f"Broken Research Chain: {tech_name}",
                        description=f"Technology {tech_name} is unreachable due to missing prerequisites: {', '.join(missing_prereqs)}",
                        affected_prototypes=[f"technology.{tech_name}"],
                        conflicting_mods=affected_mods,
                        root_cause=f"Missing prerequisite technologies: {', '.join(missing_prereqs)}",
                        suggested_fixes=[f"Add missing prerequisite technologies: {', '.join(missing_prereqs)}"]
                    )
                    self.all_issues.append(conflict)
                    self.logger.info(f"Created broken research chain conflict for technology.{tech_name}")
    
    def _detect_mod_recipe_conflicts(self) -> None:
        """Detect actual conflicts where multiple mods modify the same recipe with different ingredients."""
        self.logger.info("Detecting mod recipe conflicts...")
        
        # Get all conflicts from the modification tracker (this is what we were missing!)
        conflicts = self.tracker.get_conflicts()
        
        for prototype_key, conflicting_mods in conflicts:
            prototype_type, prototype_name = parse_prototype_key(prototype_key)
            
            # Focus on recipe conflicts
            if prototype_type == "recipe":
                # Get the modification history to see what each mod did
                history = self.tracker.get_prototype_history(prototype_type, prototype_name)
                
                if history and len(history.modifications) > 1:
                    # This recipe was modified by multiple mods - create detailed conflict
                    mod_recipes = {}
                    
                    # Extract what each mod did to the recipe
                    for modification in history.modifications:
                        mod_name = modification.mod_name
                        if modification.field_path == "ingredients":
                            mod_recipes[mod_name] = modification.new_value
                    
                    # Create conflict with detailed recipe information
                    conflict = ConflictIssue(
                        issue_id=f"MOD_RECIPE_CONFLICT_{prototype_name.upper()}",
                        severity=ConflictSeverity.CRITICAL if prototype_name in ["burner-inserter", "inserter", "transport-belt"] else ConflictSeverity.HIGH,
                        title=f"Mod Recipe Conflict: {prototype_name}",
                        description=f"Recipe '{prototype_name}' modified by multiple mods with different ingredients",
                        affected_prototypes=[prototype_key],
                        conflicting_mods=conflicting_mods,
                        root_cause=f"Multiple mods ({', '.join(conflicting_mods)}) modify the same recipe with incompatible changes",
                        suggested_fixes=[
                            "Create conditional recipe based on available items",
                            "Add alternative recipes for different mod contexts",
                            "Use compatibility patch to resolve ingredient conflicts"
                        ],
                        # Store the mod recipes in old_values for the visualizer to use
                        old_values={"mod_recipes": mod_recipes}
                    )
                    
                    self.all_issues.append(conflict)
                    self.logger.info(f"Created mod recipe conflict for {prototype_name} between mods: {', '.join(conflicting_mods)}")
        
        # ALSO detect when single mods completely replace base game recipes
        # This is what we were missing - single mod recipe replacements!
        for prototype_key, history in self.tracker.prototype_histories.items():
            prototype_type, prototype_name = parse_prototype_key(prototype_key)
            
            if prototype_type == "recipe" and history and len(history.modifications) >= 1:
                # Check if this is a significant recipe change (different ingredients)
                for modification in history.modifications:
                    if modification.field_path == "ingredients" or (not modification.field_path and 'ingredients' in str(modification.new_value)):
                        # This mod changed the recipe ingredients - create a recipe variant conflict
                        mod_name = modification.mod_name
                        
                        # Skip if we already created a multi-mod conflict for this recipe
                        existing_conflict = any(issue.issue_id == f"MOD_RECIPE_CONFLICT_{prototype_name.upper()}" for issue in self.all_issues)
                        if existing_conflict:
                            continue
                        
                        conflict = ConflictIssue(
                            issue_id=f"RECIPE_VARIANT_{prototype_name.upper()}",
                            severity=ConflictSeverity.HIGH if prototype_name in ["burner-inserter", "inserter", "transport-belt"] else ConflictSeverity.MEDIUM,
                            title=f"Recipe Variant: {prototype_name}",
                            description=f"Recipe '{prototype_name}' has different variants between base game and mod '{mod_name}'",
                            affected_prototypes=[prototype_key],
                            conflicting_mods=[mod_name],
                            root_cause=f"Mod '{mod_name}' replaces base game recipe with different ingredients",
                            suggested_fixes=[
                                "Create alternative recipes for both base game and mod variants",
                                "Add conditional recipe based on available items",
                                "Preserve both recipe variants for player choice"
                            ],
                            # Store the modification info
                            old_values={"mod_modification": modification.new_value, "mod_name": mod_name}
                        )
                        
                        self.all_issues.append(conflict)
                        self.logger.info(f"Created recipe variant conflict for {prototype_name} modified by mod: {mod_name}")
                        break  # Only create one conflict per recipe
            
            # Also handle technology conflicts
            elif prototype_type == "technology":
                # Get conflicts for this specific technology
                tech_conflicts = [c for c in conflicts if c[0] == prototype_key]
                if tech_conflicts:
                    conflicting_mods = tech_conflicts[0][1]
                    if len(conflicting_mods) > 1:
                        conflict = ConflictIssue(
                            issue_id=f"MOD_TECH_CONFLICT_{prototype_name.upper()}",
                            severity=ConflictSeverity.HIGH,
                            title=f"Mod Technology Conflict: {prototype_name}",
                            description=f"Technology '{prototype_name}' modified by multiple mods",
                            affected_prototypes=[prototype_key],
                            conflicting_mods=conflicting_mods,
                            root_cause=f"Multiple mods ({', '.join(conflicting_mods)}) modify the same technology",
                            suggested_fixes=[
                                "Review technology prerequisites",
                                "Create compatibility patch for technology tree",
                                "Use conditional technology modifications"
                            ]
                        )
                        
                        self.all_issues.append(conflict)
                        self.logger.info(f"Created mod technology conflict for {prototype_name} between mods: {', '.join(conflicting_mods)}")

    def export_recipes_per_mod(self, output_dir: Path) -> Dict[str, Path]:
        """Export all recipes organized by mod to separate files with full recipe data"""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # Group recipes by mod with full data
        recipes_by_mod = {}
        
        # Get all recipe prototypes and their modification history
        for prototype_key, history in self.tracker.prototype_histories.items():
            prototype_type, prototype_name = parse_prototype_key(prototype_key)
            
            if prototype_type != "recipe":
                continue
                
            # Track which mods modified this recipe with full data
            for record in history.modifications:
                mod_name = record.mod_name
                if mod_name not in recipes_by_mod:
                    recipes_by_mod[mod_name] = {}
                
                if prototype_name not in recipes_by_mod[mod_name]:
                    recipes_by_mod[mod_name][prototype_name] = {
                        'name': prototype_name,
                        'type': 'recipe',
                        'enabled': True,
                        'ingredients': [],
                        'results': [],
                        'energy_required': 0.5,
                        'category': 'crafting',
                        'modifications': []
                    }
                
                # Extract full recipe data from modifications
                recipe_data = recipes_by_mod[mod_name][prototype_name]
                
                # Store the modification details
                modification_info = {
                    'field': record.field_path,
                    'old_value': record.old_value,
                    'new_value': record.new_value,
                    'operation': record.operation
                }
                recipe_data['modifications'].append(modification_info)
                
                # Extract specific recipe properties
                if record.new_value and isinstance(record.new_value, dict):
                    # Direct recipe data
                    if 'ingredients' in record.new_value:
                        recipe_data['ingredients'] = record.new_value['ingredients']
                    if 'results' in record.new_value:
                        recipe_data['results'] = record.new_value['results']
                    if 'energy_required' in record.new_value:
                        recipe_data['energy_required'] = record.new_value['energy_required']
                    if 'category' in record.new_value:
                        recipe_data['category'] = record.new_value['category']
                    if 'enabled' in record.new_value:
                        recipe_data['enabled'] = record.new_value['enabled']
                
                # Handle field-specific modifications
                elif record.field_path == "ingredients" and record.new_value:
                    recipe_data['ingredients'] = record.new_value
                elif record.field_path == "results" and record.new_value:
                    recipe_data['results'] = record.new_value
                elif record.field_path == "energy_required" and record.new_value:
                    recipe_data['energy_required'] = record.new_value
                elif record.field_path == "category" and record.new_value:
                    recipe_data['category'] = record.new_value
                elif record.field_path == "enabled" and record.new_value is not None:
                    recipe_data['enabled'] = record.new_value
        
        # Write recipe files for each mod
        exported_files = {}
        for mod_name, recipes in recipes_by_mod.items():
            if not recipes:
                continue
                
            clean_mod_name = mod_name.replace("-", "_").replace(" ", "_")
            file_path = output_dir / f"recipes_{clean_mod_name}.txt"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# Recipes from {mod_name}\n")
                f.write(f"# Total recipes: {len(recipes)}\n")
                f.write("=" * 60 + "\n\n")
                
                for recipe_name, recipe_data in sorted(recipes.items()):
                    f.write(f"## Recipe: {recipe_name}\n")
                    f.write("-" * 40 + "\n")
                    f.write(f"Type: {recipe_data.get('type', 'recipe')}\n")
                    f.write(f"Category: {recipe_data.get('category', 'crafting')}\n")
                    f.write(f"Energy Required: {recipe_data.get('energy_required', 0.5)}\n")
                    f.write(f"Enabled: {recipe_data.get('enabled', True)}\n")
                    
                    # Ingredients
                    ingredients = recipe_data.get('ingredients', [])
                    if ingredients:
                        f.write(f"Ingredients:\n")
                        for ingredient in ingredients:
                            if isinstance(ingredient, dict):
                                if 'name' in ingredient and 'amount' in ingredient:
                                    f.write(f"  - {ingredient['name']}: {ingredient['amount']}\n")
                                elif 'type' in ingredient and 'name' in ingredient and 'amount' in ingredient:
                                    f.write(f"  - {ingredient['name']} ({ingredient['type']}): {ingredient['amount']}\n")
                            elif isinstance(ingredient, list) and len(ingredient) >= 2:
                                f.write(f"  - {ingredient[0]}: {ingredient[1]}\n")
                            else:
                                f.write(f"  - {ingredient}\n")
                    else:
                        f.write("Ingredients: None specified\n")
                    
                    # Results
                    results = recipe_data.get('results', [])
                    if results:
                        f.write(f"Results:\n")
                        for result in results:
                            if isinstance(result, dict):
                                if 'name' in result and 'amount' in result:
                                    f.write(f"  - {result['name']}: {result['amount']}\n")
                                elif 'type' in result and 'name' in result and 'amount' in result:
                                    f.write(f"  - {result['name']} ({result['type']}): {result['amount']}\n")
                            elif isinstance(result, list) and len(result) >= 2:
                                f.write(f"  - {result[0]}: {result[1]}\n")
                            else:
                                f.write(f"  - {result}\n")
                    else:
                        f.write("Results: None specified\n")
                    
                    # Modifications
                    modifications = recipe_data.get('modifications', [])
                    if modifications:
                        f.write(f"Modifications by {mod_name}:\n")
                        for mod in modifications:
                            f.write(f"  - Field: {mod['field']}\n")
                            f.write(f"    Operation: {mod['operation']}\n")
                            f.write(f"    Old Value: {mod['old_value']}\n")
                            f.write(f"    New Value: {mod['new_value']}\n")
                    
                    f.write("\n")
            
            exported_files[mod_name] = file_path
            self.logger.info(f"Exported {len(recipes)} recipes for {mod_name} to {file_path}")
        
        return exported_files

    def _extract_planet_resources_from_mods(self) -> Dict[str, Set[str]]:
        """Extract planet resources from actual mod data instead of hardcoding"""
        planet_resources = {}
        
        # Look for planet and resource prototypes in tracked data
        for key, history in self.tracker.prototype_histories.items():
            prototype_type, prototype_name = parse_prototype_key(key)
            current_data = history.current_value
            
            if not current_data or not isinstance(current_data, dict):
                continue
            
            # Look for planet prototypes
            if prototype_type == "planet":
                planet_name = prototype_name
                # Extract resources from planet data
                map_gen_settings = current_data.get('map_gen_settings', {})
                autoplace_controls = map_gen_settings.get('autoplace_controls', {})
                
                resources = set()
                for resource_name in autoplace_controls.keys():
                    resources.add(resource_name)
                
                if resources:
                    planet_resources[planet_name] = resources
            
            # Look for resource prototypes and their planet associations
            elif prototype_type == "resource":
                resource_name = prototype_name
                # Check if resource has planet restrictions
                autoplace = current_data.get('autoplace', {})
                if autoplace:
                    # This is a simplified approach - in reality, autoplace rules are complex
                    # For now, assume resources without specific restrictions are available on nauvis
                    if 'nauvis' not in planet_resources:
                        planet_resources['nauvis'] = set()
                    planet_resources['nauvis'].add(resource_name)
        
        # If no planet data found, return empty dict (no hardcoded fallback)
        if not planet_resources:
            self.logger.warning("No planet resource data found in mods - availability analysis may be limited")
        
        return planet_resources

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
    
    # Test data should be extracted from actual mod files, not hardcoded
    print("⚠️  Test function disabled - no hardcoded content allowed")
    print("All test data should be extracted from actual mod files")
    return None, []

if __name__ == "__main__":
    test_dependency_analyzer() 