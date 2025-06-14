#!/usr/bin/env python3

from mod_loader import ModHarmonizer
from mod_info import ModInfo
import pathlib

def debug_research_chains():
    # Create harmonizer
    mods_path = r"C:\Users\eysen\AppData\Roaming\Factorio\mods"
    harmonizer = ModHarmonizer(mods_path)
    
    # Simulate base game
    print("=== SIMULATING BASE GAME ===")
    harmonizer._simulate_base_game()
    
    # Initialize analyzer
    from dependency_analyzer import DependencyAnalyzer
    harmonizer.analyzer = DependencyAnalyzer(harmonizer.tracker)
    harmonizer.analyzer.analyze_dependencies()
    
    # Check what technologies exist after base game
    print("\n=== BASE GAME TECHNOLOGIES ===")
    for key, analysis in harmonizer.analyzer.prototype_analyses.items():
        if analysis.prototype_type == 'technology':
            print(f"{analysis.prototype_name}: prerequisites={analysis.dependencies}")
    
    # Simulate research chain breaks
    print("\n=== SIMULATING RESEARCH CHAIN BREAKS ===")
    
    # Create fake mod objects for testing
    class FakeMod:
        def __init__(self, name):
            self.name = name
    
    bobassembly = FakeMod("bobassembly")
    bobelectronics = FakeMod("bobelectronics")
    
    # Apply the chain breaks
    harmonizer._simulate_research_chain_breaks(bobassembly)
    harmonizer._simulate_research_chain_breaks(bobelectronics)
    
    # RE-ANALYZE after chain breaks to pick up the changes
    print("\n=== RE-ANALYZING AFTER CHAIN BREAKS ===")
    harmonizer.analyzer = DependencyAnalyzer(harmonizer.tracker)
    harmonizer.analyzer.analyze_dependencies()
    
    # Check technologies after chain breaks
    print("\n=== TECHNOLOGIES AFTER CHAIN BREAKS ===")
    for key, analysis in harmonizer.analyzer.prototype_analyses.items():
        if analysis.prototype_type == 'technology':
            print(f"{analysis.prototype_name}: prerequisites={analysis.dependencies}")
    
    # Run broken research chain detection
    print("\n=== RUNNING BROKEN RESEARCH CHAIN DETECTION ===")
    harmonizer.analyzer._detect_broken_research_chains()
    
    # Check for broken chain issues
    print("\n=== BROKEN CHAIN ISSUES ===")
    broken_chain_issues = [issue for issue in harmonizer.analyzer.all_issues 
                          if "BROKEN_CHAIN" in issue.issue_id]
    
    if broken_chain_issues:
        for issue in broken_chain_issues:
            print(f"Found broken chain: {issue.title}")
            print(f"  Description: {issue.description}")
    else:
        print("No broken research chains detected")
    
    print(f"\nTotal issues found: {len(harmonizer.analyzer.all_issues)}")

if __name__ == "__main__":
    debug_research_chains() 