#!/usr/bin/env python3
"""
Data Models
Defines structured data types for prototypes, dependencies, and analysis results
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple
from enum import Enum
from pathlib import Path

class ConflictSeverity(Enum):
    """Severity levels for conflicts"""
    CRITICAL = "critical"      # Game-breaking, prevents progression
    HIGH = "high"             # Major gameplay impact
    MEDIUM = "medium"         # Noticeable but workable
    LOW = "low"              # Minor inconsistencies
    INFO = "info"            # Just informational

class DependencyType(Enum):
    """Types of dependencies between prototypes"""
    RECIPE_INGREDIENT = "recipe_ingredient"    # Recipe requires this item
    RECIPE_RESULT = "recipe_result"           # Recipe produces this item
    TECHNOLOGY_PREREQUISITE = "tech_prereq"   # Technology requires this tech
    TECHNOLOGY_UNLOCK = "tech_unlock"         # Technology unlocks this recipe/item
    CRAFTING_CATEGORY = "crafting_category"   # Recipe requires this machine type
    FUEL_CATEGORY = "fuel_category"           # Item can fuel this type
    RESOURCE_CATEGORY = "resource_category"   # Mining requires this resource type

@dataclass
class PrototypeDependency:
    """Represents a dependency between two prototypes"""
    source_type: str          # e.g., "recipe"
    source_name: str          # e.g., "iron-plate"
    target_type: str          # e.g., "item"
    target_name: str          # e.g., "iron-ore"
    dependency_type: DependencyType
    required: bool = True     # Is this dependency mandatory?
    amount: Optional[int] = None  # Amount required (for ingredients)

@dataclass
class ConflictIssue:
    """Represents a specific conflict issue"""
    issue_id: str
    severity: ConflictSeverity
    title: str
    description: str
    affected_prototypes: List[str]  # ["type.name", ...]
    conflicting_mods: List[str]
    root_cause: str
    suggested_fixes: List[str]
    
    # Technical details
    field_path: str = ""
    old_values: Dict[str, Any] = field(default_factory=dict)
    new_values: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AvailabilityContext:
    """Context for checking item/recipe availability"""
    planet: Optional[str] = None
    technology_level: Set[str] = field(default_factory=set)
    available_resources: Set[str] = field(default_factory=set)
    available_machines: Set[str] = field(default_factory=set)
    mod_context: Set[str] = field(default_factory=set)

@dataclass
class PrototypeAnalysis:
    """Analysis results for a single prototype"""
    prototype_key: str  # "type.name"
    prototype_type: str
    prototype_name: str
    
    # Modification tracking
    modification_count: int
    modifying_mods: List[str]
    is_conflicted: bool
    
    # Dependency analysis
    dependencies: List[PrototypeDependency]
    dependents: List[PrototypeDependency]  # What depends on this
    missing_dependencies: List[PrototypeDependency]
    
    # Availability analysis
    available_contexts: List[AvailabilityContext]
    unavailable_contexts: List[AvailabilityContext]
    
    # Issues
    issues: List[ConflictIssue] = field(default_factory=list)

@dataclass
class ModCompatibilityReport:
    """Comprehensive compatibility report for a set of mods"""
    analyzed_mods: List[str]
    analysis_timestamp: str
    
    # Summary statistics
    total_prototypes: int
    conflicted_prototypes: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    
    # Detailed analysis
    prototype_analyses: Dict[str, PrototypeAnalysis]  # key: "type.name"
    all_issues: List[ConflictIssue]
    dependency_graph: Dict[str, List[PrototypeDependency]]
    
    # Mod-specific data
    mod_load_order: List[str]
    mod_dependencies: Dict[str, List[str]]
    
    def get_critical_issues(self) -> List[ConflictIssue]:
        """Get all critical issues"""
        return [issue for issue in self.all_issues if issue.severity == ConflictSeverity.CRITICAL]
    
    def get_issues_by_mod(self, mod_name: str) -> List[ConflictIssue]:
        """Get all issues involving a specific mod"""
        return [issue for issue in self.all_issues if mod_name in issue.conflicting_mods]
    
    def get_prototype_conflicts(self) -> List[str]:
        """Get list of all conflicted prototype keys"""
        return [key for key, analysis in self.prototype_analyses.items() if analysis.is_conflicted]

@dataclass
class PatchSuggestion:
    """Represents a suggested patch to fix a conflict"""
    patch_id: str
    target_mod: str
    target_file: str
    issue_ids: List[str]  # Issues this patch would fix
    
    # Patch details
    patch_type: str  # "recipe_modification", "item_creation", "dependency_fix"
    description: str
    
    # Technical implementation
    lua_code: str = ""
    settings_code: str = ""  # Mod settings code
    json_data: Dict[str, Any] = field(default_factory=dict)
    
    # Impact assessment
    estimated_impact: ConflictSeverity = ConflictSeverity.LOW
    side_effects: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'patch_id': self.patch_id,
            'target_mod': self.target_mod,
            'target_file': self.target_file,
            'issue_ids': self.issue_ids,
            'patch_type': self.patch_type,
            'description': self.description,
            'lua_code': self.lua_code,
            'settings_code': self.settings_code,
            'json_data': self.json_data,
            'estimated_impact': self.estimated_impact.value,
            'side_effects': self.side_effects
        }

@dataclass
class VisualizationData:
    """Data structure for visualization components"""
    # Graph data
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    
    # Conflict highlighting
    conflict_nodes: Set[str] = field(default_factory=set)
    conflict_edges: Set[Tuple[str, str]] = field(default_factory=set)
    
    # Grouping information
    mod_groups: Dict[str, List[str]] = field(default_factory=dict)
    type_groups: Dict[str, List[str]] = field(default_factory=dict)
    
    # Metadata
    title: str = ""
    description: str = ""
    layout_hints: Dict[str, Any] = field(default_factory=dict)

# Utility functions for working with data models

def create_prototype_key(prototype_type: str, prototype_name: str) -> str:
    """Create a standardized prototype key"""
    return f"{prototype_type}.{prototype_name}"

def parse_prototype_key(prototype_key: str) -> Tuple[str, str]:
    """Parse a prototype key into type and name"""
    if '.' not in prototype_key:
        raise ValueError(f"Invalid prototype key format: {prototype_key}")
    
    parts = prototype_key.split('.', 1)
    return parts[0], parts[1]

def severity_to_color(severity: ConflictSeverity) -> str:
    """Convert severity to color for visualization"""
    color_map = {
        ConflictSeverity.CRITICAL: "#FF0000",  # Red
        ConflictSeverity.HIGH: "#FF6600",      # Orange
        ConflictSeverity.MEDIUM: "#FFCC00",    # Yellow
        ConflictSeverity.LOW: "#66CC00",       # Light Green
        ConflictSeverity.INFO: "#0066CC"       # Blue
    }
    return color_map.get(severity, "#808080")  # Gray default

def dependency_to_edge_style(dependency_type: DependencyType) -> Dict[str, Any]:
    """Convert dependency type to edge styling"""
    style_map = {
        DependencyType.RECIPE_INGREDIENT: {"color": "#FF6B6B", "style": "solid", "width": 2},
        DependencyType.RECIPE_RESULT: {"color": "#4ECDC4", "style": "solid", "width": 2},
        DependencyType.TECHNOLOGY_PREREQUISITE: {"color": "#45B7D1", "style": "dashed", "width": 1},
        DependencyType.TECHNOLOGY_UNLOCK: {"color": "#96CEB4", "style": "dashed", "width": 1},
        DependencyType.CRAFTING_CATEGORY: {"color": "#FFEAA7", "style": "dotted", "width": 1},
        DependencyType.FUEL_CATEGORY: {"color": "#DDA0DD", "style": "dotted", "width": 1},
        DependencyType.RESOURCE_CATEGORY: {"color": "#98D8C8", "style": "dotted", "width": 1}
    }
    return style_map.get(dependency_type, {"color": "#808080", "style": "solid", "width": 1})

# Test functions
def test_data_models():
    """Test the data model functionality"""
    print("🧪 Testing Data Models...")
    
    # Test 1: Create prototype dependency
    print("\n📝 Test 1: Prototype dependency")
    dep = PrototypeDependency(
        source_type="recipe",
        source_name="iron-plate",
        target_type="item", 
        target_name="iron-ore",
        dependency_type=DependencyType.RECIPE_INGREDIENT,
        amount=1
    )
    print(f"Created dependency: {dep.source_type}.{dep.source_name} -> {dep.target_type}.{dep.target_name}")
    
    # Test 2: Create conflict issue
    print("\n📝 Test 2: Conflict issue")
    issue = ConflictIssue(
        issue_id="CONFLICT_001",
        severity=ConflictSeverity.CRITICAL,
        title="Burner Inserter Recipe Conflict",
        description="Recipe modified by multiple mods with incompatible ingredients",
        affected_prototypes=["recipe.burner-inserter"],
        conflicting_mods=["lignumis", "Krastorio2-spaced-out"],
        root_cause="Both mods modify the same recipe with different ingredient requirements",
        suggested_fixes=[
            "Create compatibility patch",
            "Use conditional recipe modification",
            "Add alternative recipe"
        ]
    )
    print(f"Created issue: {issue.title} (Severity: {issue.severity.value})")
    
    # Test 3: Create prototype analysis
    print("\n📝 Test 3: Prototype analysis")
    analysis = PrototypeAnalysis(
        prototype_key="recipe.burner-inserter",
        prototype_type="recipe",
        prototype_name="burner-inserter",
        modification_count=3,
        modifying_mods=["base", "lignumis", "Krastorio2-spaced-out"],
        is_conflicted=True,
        dependencies=[dep],
        dependents=[],
        missing_dependencies=[],
        available_contexts=[],
        unavailable_contexts=[],
        issues=[issue]
    )
    print(f"Created analysis for: {analysis.prototype_key}")
    print(f"  Conflicted: {analysis.is_conflicted}")
    print(f"  Issues: {len(analysis.issues)}")
    
    # Test 4: Create patch suggestion
    print("\n📝 Test 4: Patch suggestion")
    patch = PatchSuggestion(
        patch_id="PATCH_001",
        target_mod="compatibility-patch",
        target_file="data-final-fixes.lua",
        issue_ids=["CONFLICT_001"],
        patch_type="recipe_modification",
        description="Add conditional recipe modification based on available items",
        lua_code='''
-- Check if both wood-gear-wheel and kr-steel-gear-wheel exist
if data.raw.item["wood-gear-wheel"] and data.raw.item["kr-steel-gear-wheel"] then
    -- Use wood gear on Lignumis, steel gear elsewhere
    data.raw.recipe["burner-inserter"].ingredients = {
        {type = "item", name = "iron-plate", amount = 1},
        {type = "item", name = "wood-gear-wheel", amount = 1}
    }
end
        ''',
        estimated_impact=ConflictSeverity.MEDIUM
    )
    print(f"Created patch: {patch.description}")
    
    # Test 5: Utility functions
    print("\n📝 Test 5: Utility functions")
    key = create_prototype_key("recipe", "burner-inserter")
    ptype, pname = parse_prototype_key(key)
    color = severity_to_color(ConflictSeverity.CRITICAL)
    edge_style = dependency_to_edge_style(DependencyType.RECIPE_INGREDIENT)
    
    print(f"Prototype key: {key}")
    print(f"Parsed: type={ptype}, name={pname}")
    print(f"Critical color: {color}")
    print(f"Recipe ingredient edge style: {edge_style}")
    
    print("\n✅ Data Models tests complete!")
    return analysis, issue, patch

if __name__ == "__main__":
    test_data_models() 