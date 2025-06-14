#!/usr/bin/env python3
"""
Visualizer
Generates visual representations of conflicts, dependencies, and patches
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
import json

from data_models import (
    ConflictSeverity, DependencyType, ModCompatibilityReport, PatchSuggestion,
    VisualizationData, severity_to_color, dependency_to_edge_style,
    create_prototype_key, parse_prototype_key
)

class ConflictVisualizer:
    """Creates visual representations of mod conflicts and solutions"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_conflict_report(self, report: ModCompatibilityReport, patches: List[PatchSuggestion]) -> str:
        """Generate a comprehensive text-based conflict report"""
        lines = []
        
        # Header
        lines.append("🎯 FACTORIO MOD HARMONIZER - CONFLICT ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append(f"Analysis Date: {report.analysis_timestamp}")
        lines.append(f"Analyzed Mods: {', '.join(report.analyzed_mods)}")
        lines.append("")
        
        # Summary
        lines.append("📊 SUMMARY")
        lines.append("-" * 30)
        lines.append(f"Total Prototypes Analyzed: {report.total_prototypes}")
        lines.append(f"Conflicted Prototypes: {report.conflicted_prototypes}")
        lines.append(f"Critical Issues: {report.critical_issues}")
        lines.append(f"High Priority Issues: {report.high_issues}")
        lines.append(f"Medium Priority Issues: {report.medium_issues}")
        lines.append(f"Low Priority Issues: {report.low_issues}")
        lines.append("")
        
        # All Issues Detail (grouped by severity)
        all_issues = report.all_issues
        if all_issues:
            # Group issues by type and severity for better organization
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
            severity_order = [ConflictSeverity.CRITICAL, ConflictSeverity.HIGH, ConflictSeverity.MEDIUM, ConflictSeverity.LOW]
            recipe_issues.sort(key=lambda x: severity_order.index(x.severity) if x.severity in severity_order else 999)
            research_issues.sort(key=lambda x: severity_order.index(x.severity) if x.severity in severity_order else 999)
            other_issues.sort(key=lambda x: severity_order.index(x.severity) if x.severity in severity_order else 999)
            
            # Show Recipe Conflicts (sorted by priority)
            if recipe_issues:
                lines.append("🍳 RECIPE CONFLICTS (Sorted by Priority)")
                lines.append("=" * 45)
                
                for i, issue in enumerate(recipe_issues, 1):
                    severity_icon = {
                        ConflictSeverity.CRITICAL: "🚨",
                        ConflictSeverity.HIGH: "🔶", 
                        ConflictSeverity.MEDIUM: "📋",
                        ConflictSeverity.LOW: "ℹ️"
                    }.get(issue.severity, "❓")
                    
                    lines.append(f"{i}. {severity_icon} {issue.title}")
                    lines.append(f"   Severity: {issue.severity.value.upper()}")
                    lines.append(f"   Affected: {', '.join(issue.affected_prototypes)}")
                    lines.append(f"   Conflicting Mods: {' → '.join(issue.conflicting_mods)}")
                    lines.append(f"   Problem: {issue.description}")
                    lines.append(f"   Root Cause: {issue.root_cause}")
                    
                    # Add recipe visualization for affected prototypes
                    for prototype_key in issue.affected_prototypes:
                        if prototype_key in report.prototype_analyses:
                            analysis = report.prototype_analyses[prototype_key]
                            recipe_info = self._get_recipe_visualization(prototype_key, analysis, report)
                            if recipe_info:
                                lines.append(f"   📋 Recipe Details:")
                                lines.extend([f"     {line}" for line in recipe_info])
                    
                    lines.append("   Suggested Solutions:")
                    for fix in issue.suggested_fixes:
                        lines.append(f"     • {fix}")
                    lines.append("")
            
            # Show Research Conflicts (sorted by priority)  
            if research_issues:
                lines.append("🔬 RESEARCH CONFLICTS (Sorted by Priority)")
                lines.append("=" * 45)
                
                for i, issue in enumerate(research_issues, 1):
                    severity_icon = {
                        ConflictSeverity.CRITICAL: "🚨",
                        ConflictSeverity.HIGH: "🔶",
                        ConflictSeverity.MEDIUM: "📋", 
                        ConflictSeverity.LOW: "ℹ️"
                    }.get(issue.severity, "❓")
                    
                    lines.append(f"{i}. {severity_icon} {issue.title}")
                    lines.append(f"   Severity: {issue.severity.value.upper()}")
                    lines.append(f"   Affected: {', '.join(issue.affected_prototypes)}")
                    lines.append(f"   Conflicting Mods: {' → '.join(issue.conflicting_mods)}")
                    lines.append(f"   Problem: {issue.description}")
                    lines.append(f"   Root Cause: {issue.root_cause}")
                    lines.append("   Suggested Solutions:")
                    for fix in issue.suggested_fixes:
                        lines.append(f"     • {fix}")
                    lines.append("")
            
            # Show Other Conflicts (sorted by priority)
            if other_issues:
                lines.append("⚙️ OTHER CONFLICTS (Sorted by Priority)")
                lines.append("=" * 40)
                
                for i, issue in enumerate(other_issues, 1):
                    severity_icon = {
                        ConflictSeverity.CRITICAL: "🚨",
                        ConflictSeverity.HIGH: "🔶",
                        ConflictSeverity.MEDIUM: "📋",
                        ConflictSeverity.LOW: "ℹ️"
                    }.get(issue.severity, "❓")
                    
                    lines.append(f"{i}. {severity_icon} {issue.title}")
                    lines.append(f"   Severity: {issue.severity.value.upper()}")
                    lines.append(f"   Affected: {', '.join(issue.affected_prototypes)}")
                    lines.append(f"   Conflicting Mods: {' → '.join(issue.conflicting_mods)}")
                    lines.append(f"   Problem: {issue.description}")
                    lines.append(f"   Root Cause: {issue.root_cause}")
                    lines.append("   Suggested Solutions:")
                    for fix in issue.suggested_fixes:
                        lines.append(f"     • {fix}")
                    lines.append("")
        
        # Patch Solutions
        if patches:
            lines.append("🔧 GENERATED PATCH SOLUTIONS")
            lines.append("-" * 40)
            
            for i, patch in enumerate(patches, 1):
                lines.append(f"{i}. {patch.patch_id}")
                lines.append(f"   Description: {patch.description}")
                lines.append(f"   Target: {patch.target_mod}/{patch.target_file}")
                lines.append(f"   Impact Level: {patch.estimated_impact.value.upper()}")
                lines.append(f"   Fixes Issues: {', '.join(patch.issue_ids)}")
                lines.append("")
                lines.append("   Generated Lua Code:")
                lines.append("   " + "-" * 30)
                for line in patch.lua_code.split('\n'):
                    lines.append(f"   {line}")
                lines.append("")
        
        # Recommendations
        lines.append("💡 RECOMMENDATIONS")
        lines.append("-" * 25)
        
        if report.critical_issues > 0:
            lines.append("⚠️  URGENT: Apply generated patches immediately to resolve critical conflicts")
        
        if report.high_issues > 0:
            lines.append("🔶 HIGH: Review high-priority issues for potential gameplay impact")
        
        if report.conflicted_prototypes > 0:
            lines.append("📋 GENERAL: Consider mod load order optimization")
        
        lines.append("✅ TESTING: Test all patches in a development environment before production use")
        lines.append("")
        
        # Footer
        lines.append("=" * 70)
        lines.append("Generated by Factorio Mod Harmonizer")
        
        return "\n".join(lines)
    
    def generate_patch_files(self, patches: List[PatchSuggestion], output_dir: Path) -> List[Path]:
        """Generate actual patch files that can be used as Factorio mods"""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        created_files = []
        
        # Group patches by target mod
        patches_by_mod = {}
        for patch in patches:
            if patch.target_mod not in patches_by_mod:
                patches_by_mod[patch.target_mod] = []
            patches_by_mod[patch.target_mod].append(patch)
        
        for mod_name, mod_patches in patches_by_mod.items():
            mod_dir = output_dir / mod_name
            mod_dir.mkdir(exist_ok=True)
            
            # Create info.json
            info_json = {
                "name": mod_name,
                "version": "1.0.0",
                "title": "Factorio Harmonizer Compatibility Patch",
                "description": f"Auto-generated compatibility patch resolving {len(mod_patches)} conflicts",
                "contact": "https://github.com/factorio-harmonizer/factorio-harmonizer",
                "homepage": "https://github.com/factorio-harmonizer/factorio-harmonizer",
                "author": "Factorio Harmonizer",
                "factorio_version": "2.0",
                "dependencies": [
                    "base >= 2.0.47",
                    "space-age >= 2.0.47",
                    "quality >= 2.0.47"
                ],
                "quality_required": True,
                "space_travel_required": True,
                "spoiling_required": True,
                "freezing_required": True,
                "segmented_units_required": True
            }
            
            info_file = mod_dir / "info.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(info_json, f, indent=2)
            created_files.append(info_file)
            
            # Group patches by target file
            patches_by_file = {}
            for patch in mod_patches:
                if patch.target_file not in patches_by_file:
                    patches_by_file[patch.target_file] = []
                patches_by_file[patch.target_file].append(patch)
            
            # Create patch files
            for file_name, file_patches in patches_by_file.items():
                patch_file = mod_dir / file_name
                
                lua_content = []
                lua_content.append("-- Auto-generated compatibility patch")
                lua_content.append("-- Generated by Factorio Mod Harmonizer")
                lua_content.append(f"-- Resolves {len(file_patches)} conflict(s)")
                lua_content.append("")
                
                for patch in file_patches:
                    lua_content.append(f"-- Patch: {patch.patch_id}")
                    lua_content.append(f"-- Description: {patch.description}")
                    lua_content.append(f"-- Fixes: {', '.join(patch.issue_ids)}")
                    lua_content.append("")
                    lua_content.append(patch.lua_code)
                    lua_content.append("")
                
                with open(patch_file, 'w', encoding='utf-8') as f:
                    f.write("\n".join(lua_content))
                created_files.append(patch_file)
        
        self.logger.info(f"Generated {len(created_files)} patch files in {output_dir}")
        return created_files
    
    def _get_recipe_visualization(self, prototype_key: str, analysis, report: ModCompatibilityReport) -> List[str]:
        """Generate a visual representation of how a recipe looks in different mods"""
        lines = []
        
        prototype_type, prototype_name = parse_prototype_key(prototype_key)
        
        if prototype_type != "recipe":
            return lines
        
        # Check if this is a mod recipe conflict with stored mod recipes
        for issue in report.all_issues:
            if prototype_key in issue.affected_prototypes and "mod_recipes" in issue.old_values:
                mod_recipes = issue.old_values["mod_recipes"]
                
                lines.append(f"📋 Recipe Versions by Mod:")
                for mod_name, ingredients in mod_recipes.items():
                    if ingredients:
                        ingredient_strs = []
                        for ingredient in ingredients:
                            if isinstance(ingredient, dict):
                                name = ingredient.get('name', 'unknown')
                                amount = ingredient.get('amount', 1)
                                amount_str = f" x{amount}" if amount > 1 else ""
                                ingredient_strs.append(f"{name}{amount_str}")
                            else:
                                ingredient_strs.append(str(ingredient))
                        
                        lines.append(f"  🔧 {mod_name}: {' + '.join(ingredient_strs)} → {prototype_name}")
                
                return lines
        
        # Fallback to dependency analysis if no mod recipes stored
        if hasattr(analysis, 'dependencies') and analysis.dependencies:
            # Show current recipe ingredients
            ingredients = []
            for dep in analysis.dependencies:
                if dep.dependency_type.value == "recipe_ingredient":
                    amount = f" x{dep.amount}" if dep.amount and dep.amount > 1 else ""
                    ingredients.append(f"{dep.target_name}{amount}")
            
            if ingredients:
                lines.append(f"Current Recipe: {' + '.join(ingredients)} → {prototype_name}")
        
        # Show which mods modified this recipe
        if hasattr(analysis, 'modifying_mods') and analysis.modifying_mods:
            lines.append(f"Modified by: {', '.join(analysis.modifying_mods)}")
        
        return lines

# Test function
def test_visualizer():
    """Test the visualizer with real analysis data"""
    print("🧪 Testing Visualizer...")
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Import and run the full analysis pipeline
    from dependency_analyzer import test_dependency_analyzer
    
    print("\n🔍 Running full analysis pipeline...")
    report, patches = test_dependency_analyzer()
    
    print("\n🎨 Generating visualizations...")
    visualizer = ConflictVisualizer()
    
    # Generate text report
    print("\n📄 Generating text report...")
    text_report = visualizer.generate_conflict_report(report, patches)
    
    # Save text report
    text_output = Path("./logs/conflict_report.txt")
    with open(text_output, 'w', encoding='utf-8') as f:
        f.write(text_report)
    print(f"Text report saved to: {text_output}")
    
    # Generate patch files
    print("\n🔧 Generating patch files...")
    patch_dir = Path("./generated_patches")
    created_files = visualizer.generate_patch_files(patches, patch_dir)
    
    print(f"Generated {len(created_files)} patch files:")
    for file_path in created_files:
        print(f"  - {file_path}")
    
    # Display summary
    print(f"\n📋 VISUALIZATION SUMMARY:")
    print(f"  Text Report: {text_output}")
    print(f"  Patch Files: {patch_dir}")
    print(f"  Critical Issues: {report.critical_issues}")
    print(f"  Generated Patches: {len(patches)}")
    
    print("\n✅ Visualizer tests complete!")
    print("\n🎯 WHAT YOU NEED TO PATCH:")
    
    critical_issues = report.get_critical_issues()
    for issue in critical_issues:
        print(f"\n🚨 {issue.title}")
        print(f"   Problem: {issue.description}")
        print(f"   Mods: {' → '.join(issue.conflicting_mods)}")
        print(f"   Solution: Apply patch {patches[0].patch_id if patches else 'N/A'}")
    
    return report, patches, visualizer

if __name__ == "__main__":
    test_visualizer() 