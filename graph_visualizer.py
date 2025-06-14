#!/usr/bin/env python3
"""
Graph Visualizer
Interactive GUI visualization of mod dependencies and conflicts (like Obsidian.md)
"""

import json
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path

try:
    import networkx as nx
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.widgets import Button, CheckButtons
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    import plotly.offline as pyo
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False
    nx = None
    plt = None
    go = None

from data_models import (
    ConflictSeverity, ModCompatibilityReport, PatchSuggestion,
    severity_to_color, parse_prototype_key
)

class InteractiveDependencyGraph:
    """Interactive dependency graph visualizer like Obsidian.md"""
    
    def __init__(self, report: ModCompatibilityReport, patches: List[PatchSuggestion]):
        self.report = report
        self.patches = patches
        self.logger = logging.getLogger(__name__)
        
        if not VISUALIZATION_AVAILABLE:
            raise ImportError("Visualization libraries not available. Install with: pip install networkx matplotlib plotly")
        
        # Create the graph
        self.graph = nx.DiGraph()
        self.node_data = {}
        self.edge_data = {}
        
        self._build_graph()
    
    def _build_graph(self):
        """Build the NetworkX graph from analysis data"""
        self.logger.info("Building dependency graph...")
        
        # Add nodes for each prototype
        for key, analysis in self.report.prototype_analyses.items():
            prototype_type, prototype_name = parse_prototype_key(key)
            
            # Determine node properties
            node_color = self._get_node_color(analysis)
            node_size = self._get_node_size(analysis)
            node_shape = self._get_node_shape(prototype_type)
            
            self.graph.add_node(key, 
                name=prototype_name,
                type=prototype_type,
                color=node_color,
                size=node_size,
                shape=node_shape,
                conflicted=analysis.is_conflicted,
                mod_count=len(analysis.modifying_mods),
                mods=analysis.modifying_mods,
                issues=len(analysis.issues)
            )
            
            self.node_data[key] = {
                'analysis': analysis,
                'display_name': f"{prototype_type}.{prototype_name}",
                'tooltip': self._create_node_tooltip(analysis)
            }
        
        # Add edges for dependencies
        for key, dependencies in self.report.dependency_graph.items():
            for dep in dependencies:
                target_key = f"{dep.target_type}.{dep.target_name}"
                
                if target_key in self.graph:
                    edge_color = self._get_edge_color(dep.dependency_type)
                    edge_width = 2 if dep.required else 1
                    
                    self.graph.add_edge(key, target_key,
                        dependency_type=dep.dependency_type.value,
                        required=dep.required,
                        amount=dep.amount,
                        color=edge_color,
                        width=edge_width
                    )
                    
                    self.edge_data[(key, target_key)] = {
                        'dependency': dep,
                        'tooltip': f"{dep.dependency_type.value}: {dep.source_name} → {dep.target_name}"
                    }
        
        self.logger.info(f"Graph built: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")
    
    def _get_node_color(self, analysis) -> str:
        """Get node color based on conflict status"""
        if not analysis.issues:
            return "#4CAF50"  # Green - no issues
        
        max_severity = max(issue.severity for issue in analysis.issues)
        return severity_to_color(max_severity)
    
    def _get_node_size(self, analysis) -> int:
        """Get node size based on importance"""
        base_size = 20
        
        # Larger for conflicted prototypes
        if analysis.is_conflicted:
            base_size += 10
        
        # Larger for more modifications
        base_size += min(analysis.modification_count * 2, 20)
        
        # Larger for critical issues
        if any(issue.severity == ConflictSeverity.CRITICAL for issue in analysis.issues):
            base_size += 15
        
        return base_size
    
    def _get_node_shape(self, prototype_type: str) -> str:
        """Get node shape based on prototype type"""
        shape_map = {
            'item': 'circle',
            'recipe': 'square',
            'technology': 'diamond',
            'entity': 'triangle-up',
            'fluid': 'circle'
        }
        return shape_map.get(prototype_type, 'circle')
    
    def _get_edge_color(self, dependency_type) -> str:
        """Get edge color based on dependency type"""
        color_map = {
            'recipe_ingredient': '#FF6B6B',
            'recipe_result': '#4ECDC4',
            'technology_prerequisite': '#45B7D1',
            'technology_unlock': '#96CEB4',
            'crafting_category': '#FFEAA7',
            'fuel_category': '#DDA0DD',
            'resource_category': '#98D8C8'
        }
        return color_map.get(dependency_type.value if hasattr(dependency_type, 'value') else str(dependency_type), '#808080')
    
    def _create_node_tooltip(self, analysis) -> str:
        """Create tooltip text for a node"""
        lines = [
            f"<b>{analysis.prototype_type}.{analysis.prototype_name}</b>",
            f"Modifications: {analysis.modification_count}",
            f"Modifying Mods: {', '.join(analysis.modifying_mods)}",
            f"Dependencies: {len(analysis.dependencies)}",
            f"Issues: {len(analysis.issues)}"
        ]
        
        if analysis.issues:
            lines.append("<br><b>Issues:</b>")
            for issue in analysis.issues:
                lines.append(f"• {issue.severity.value.upper()}: {issue.title}")
        
        return "<br>".join(lines)
    
    def show_plotly_graph(self, output_file: str = None):
        """Show interactive graph using Plotly"""
        self.logger.info("Generating Plotly visualization...")
        
        # Use spring layout for better visualization
        pos = nx.spring_layout(self.graph, k=3, iterations=50)
        
        # Prepare node traces
        node_traces = self._create_plotly_node_traces(pos)
        
        # Prepare edge traces
        edge_traces = self._create_plotly_edge_traces(pos)
        
        # Create figure
        fig = go.Figure(data=edge_traces + node_traces)
        
        # Update layout
        fig.update_layout(
            title={
                'text': "🎯 Factorio Mod Dependency Graph",
                'x': 0.5,
                'font': {'size': 24}
            },
            showlegend=True,
            hovermode='closest',
            margin=dict(b=20,l=5,r=5,t=40),
            annotations=[
                dict(
                    text="🔴 Critical Issues | 🟡 Medium Issues | 🟢 No Issues<br>" +
                         "🔵 Items | 🟦 Recipes | 🔶 Technologies | 🔺 Entities",
                    showarrow=False,
                    xref="paper", yref="paper",
                    x=0.005, y=-0.002,
                    xanchor='left', yanchor='bottom',
                    font=dict(size=12)
                )
            ],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        # Add buttons for filtering
        fig.update_layout(
            updatemenus=[
                dict(
                    type="buttons",
                    direction="left",
                    buttons=list([
                        dict(
                            args=[{"visible": [True] * len(fig.data)}],
                            label="Show All",
                            method="restyle"
                        ),
                        dict(
                            args=[{"visible": self._get_conflict_filter()}],
                            label="Conflicts Only",
                            method="restyle"
                        ),
                        dict(
                            args=[{"visible": self._get_critical_filter()}],
                            label="Critical Only",
                            method="restyle"
                        )
                    ]),
                    pad={"r": 10, "t": 10},
                    showactive=True,
                    x=0.01,
                    xanchor="left",
                    y=1.02,
                    yanchor="top"
                ),
            ]
        )
        
        # Show or save
        if output_file:
            pyo.plot(fig, filename=output_file, auto_open=True)
            self.logger.info(f"Graph saved to: {output_file}")
        else:
            fig.show()
    
    def _create_plotly_node_traces(self, pos) -> List[go.Scatter]:
        """Create Plotly node traces grouped by type"""
        traces = []
        
        # Group nodes by type
        node_groups = {}
        for node, data in self.graph.nodes(data=True):
            node_type = data['type']
            if node_type not in node_groups:
                node_groups[node_type] = []
            node_groups[node_type].append((node, data))
        
        # Create trace for each type
        for node_type, nodes in node_groups.items():
            x_coords = []
            y_coords = []
            colors = []
            sizes = []
            texts = []
            hovertexts = []
            
            for node, data in nodes:
                x, y = pos[node]
                x_coords.append(x)
                y_coords.append(y)
                colors.append(data['color'])
                sizes.append(data['size'])
                texts.append(data['name'])
                hovertexts.append(self.node_data[node]['tooltip'])
            
            # Map shape
            symbol_map = {
                'item': 'circle',
                'recipe': 'square',
                'technology': 'diamond',
                'entity': 'triangle-up'
            }
            symbol = symbol_map.get(node_type, 'circle')
            
            trace = go.Scatter(
                x=x_coords,
                y=y_coords,
                mode='markers+text',
                marker=dict(
                    size=sizes,
                    color=colors,
                    symbol=symbol,
                    line=dict(width=2, color='white')
                ),
                text=texts,
                textposition="middle center",
                textfont=dict(size=8, color='white'),
                hovertext=hovertexts,
                hoverinfo='text',
                name=f"{node_type.title()}s",
                showlegend=True
            )
            traces.append(trace)
        
        return traces
    
    def _create_plotly_edge_traces(self, pos) -> List[go.Scatter]:
        """Create Plotly edge traces"""
        edge_traces = []
        
        # Group edges by type
        edge_groups = {}
        for edge in self.graph.edges(data=True):
            source, target, data = edge
            edge_type = data.get('dependency_type', 'unknown')
            if edge_type not in edge_groups:
                edge_groups[edge_type] = []
            edge_groups[edge_type].append((source, target, data))
        
        # Create trace for each edge type
        for edge_type, edges in edge_groups.items():
            x_coords = []
            y_coords = []
            
            for source, target, data in edges:
                x0, y0 = pos[source]
                x1, y1 = pos[target]
                
                x_coords.extend([x0, x1, None])
                y_coords.extend([y0, y1, None])
            
            color = self._get_edge_color_by_type(edge_type)
            
            trace = go.Scatter(
                x=x_coords,
                y=y_coords,
                mode='lines',
                line=dict(width=1, color=color),
                hoverinfo='none',
                name=edge_type.replace('_', ' ').title(),
                showlegend=True,
                opacity=0.6
            )
            edge_traces.append(trace)
        
        return edge_traces
    
    def _get_edge_color_by_type(self, edge_type: str) -> str:
        """Get edge color by type string"""
        color_map = {
            'recipe_ingredient': '#FF6B6B',
            'recipe_result': '#4ECDC4',
            'technology_prerequisite': '#45B7D1',
            'technology_unlock': '#96CEB4',
            'crafting_category': '#FFEAA7',
            'fuel_category': '#DDA0DD',
            'resource_category': '#98D8C8'
        }
        return color_map.get(edge_type, '#808080')
    
    def _get_conflict_filter(self) -> List[bool]:
        """Get visibility filter for conflicted nodes only"""
        # This would need to be implemented based on the specific trace structure
        return [True] * len(self.graph.nodes)  # Simplified for now
    
    def _get_critical_filter(self) -> List[bool]:
        """Get visibility filter for critical issues only"""
        # This would need to be implemented based on the specific trace structure
        return [True] * len(self.graph.nodes)  # Simplified for now
    
    def show_matplotlib_graph(self, output_file: str = None):
        """Show graph using matplotlib (fallback option)"""
        self.logger.info("Generating matplotlib visualization...")
        
        plt.figure(figsize=(16, 12))
        
        # Use spring layout
        pos = nx.spring_layout(self.graph, k=2, iterations=50)
        
        # Draw edges
        nx.draw_networkx_edges(self.graph, pos, 
                              edge_color='lightgray',
                              alpha=0.6,
                              arrows=True,
                              arrowsize=10)
        
        # Draw nodes by type
        node_types = set(data['type'] for _, data in self.graph.nodes(data=True))
        colors = plt.cm.Set3(range(len(node_types)))
        
        for i, node_type in enumerate(node_types):
            nodes = [node for node, data in self.graph.nodes(data=True) if data['type'] == node_type]
            node_colors = [self.graph.nodes[node]['color'] for node in nodes]
            node_sizes = [self.graph.nodes[node]['size'] * 10 for node in nodes]  # Scale for matplotlib
            
            nx.draw_networkx_nodes(self.graph, pos,
                                  nodelist=nodes,
                                  node_color=node_colors,
                                  node_size=node_sizes,
                                  alpha=0.8,
                                  label=node_type)
        
        # Draw labels
        labels = {node: data['name'] for node, data in self.graph.nodes(data=True)}
        nx.draw_networkx_labels(self.graph, pos, labels, font_size=8)
        
        plt.title("Factorio Mod Dependency Graph", size=16)
        plt.legend()
        plt.axis('off')
        
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            self.logger.info(f"Graph saved to: {output_file}")
        else:
            plt.show()
    
    def export_graph_data(self, output_file: str):
        """Export graph data for external visualization tools"""
        graph_data = {
            'nodes': [
                {
                    'id': node,
                    'label': data['name'],
                    'type': data['type'],
                    'color': data['color'],
                    'size': data['size'],
                    'conflicted': data['conflicted'],
                    'mods': data['mods'],
                    'issues': data['issues']
                }
                for node, data in self.graph.nodes(data=True)
            ],
            'edges': [
                {
                    'source': source,
                    'target': target,
                    'type': data['dependency_type'],
                    'required': data['required'],
                    'color': data['color'],
                    'width': data['width']
                }
                for source, target, data in self.graph.edges(data=True)
            ]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Graph data exported to: {output_file}")

def show_dependency_graph(report: ModCompatibilityReport, patches: List[PatchSuggestion], 
                         output_file: str = None, format: str = 'plotly'):
    """Show interactive dependency graph"""
    if not VISUALIZATION_AVAILABLE:
        print("❌ Visualization libraries not available!")
        print("Install with: pip install networkx matplotlib plotly")
        return
    
    try:
        graph_viz = InteractiveDependencyGraph(report, patches)
        
        if format == 'plotly':
            if not output_file:
                output_file = "./output/dependency_graph.html"
            graph_viz.show_plotly_graph(output_file)
        elif format == 'matplotlib':
            if not output_file:
                output_file = "./output/dependency_graph.png"
            graph_viz.show_matplotlib_graph(output_file)
        
        # Also export raw data
        graph_viz.export_graph_data("./output/graph_data.json")
        
        print(f"✅ Graph visualization complete!")
        if output_file:
            print(f"📁 Saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error creating graph: {e}")
        import traceback
        traceback.print_exc()

def show_dependency_graph_from_file(analysis_file: str, output_file: str = None):
    """Show dependency graph from saved analysis file"""
    try:
        with open(analysis_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Reconstruct report and patches from JSON
        # This is a simplified version - full reconstruction would need more work
        print(f"📊 Loading analysis from: {analysis_file}")
        print(f"Found {len(data.get('issues', []))} issues and {len(data.get('patches', []))} patches")
        
        # For now, just show a message
        print("🚧 Graph visualization from file not yet implemented")
        print("Run the full analysis with --graph flag instead")
        
    except FileNotFoundError:
        print(f"❌ Analysis file not found: {analysis_file}")
    except Exception as e:
        print(f"❌ Error loading analysis: {e}")

# Test function
def test_graph_visualizer():
    """Test the graph visualizer"""
    print("🧪 Testing Graph Visualizer...")
    
    if not VISUALIZATION_AVAILABLE:
        print("❌ Visualization libraries not available!")
        print("Install with: pip install networkx matplotlib plotly")
        return
    
    # Import and run analysis
    from dependency_analyzer import test_dependency_analyzer
    
    print("🔍 Running analysis for graph...")
    report, patches = test_dependency_analyzer()
    
    print("📊 Creating graph visualization...")
    show_dependency_graph(report, patches, "./output/test_graph.html", 'plotly')
    
    print("✅ Graph visualizer test complete!")

if __name__ == "__main__":
    test_graph_visualizer() 