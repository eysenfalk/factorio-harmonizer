# 🎯 Factorio Mod Harmonizer

**Automatically detect and fix mod conflicts in Factorio**

The Factorio Mod Harmonizer analyzes your installed mods, detects compatibility issues, and generates patches to resolve conflicts automatically. No more unplayable mod combinations or missing recipes!

## 🚀 Features

- **🔍 Comprehensive Conflict Detection**
  - Missing ingredient conflicts (recipes requiring unavailable items)
  - Broken research chains (technologies becoming unreachable)
  - Recipe overwrites and modifications
  - Cross-mod dependency issues

- **🔧 Automatic Patch Generation**
  - Creates conditional recipes based on available ingredients
  - Fixes broken technology prerequisites
  - Generates alternative crafting paths
  - Maintains game balance and progression

- **📦 Seamless Integration**
  - Auto-installs patches to your Factorio mods directory
  - Creates backups before making changes
  - Works with any mod combination
  - No manual configuration required

- **📊 Rich Analysis & Visualization**
  - Detailed conflict reports
  - Interactive dependency graphs
  - Comprehensive logging
  - JSON export for advanced users

## 📋 Requirements

- **Python 3.8+**
- **Factorio** (with mods installed)
- **Windows/Linux/macOS** (tested on Windows)

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/factorio-harmonizer.git
   cd factorio-harmonizer
   ```

2. **Install dependencies:**
   ```bash
   pip install lupa pydantic typer rich networkx orjson pathlib
   ```

3. **Optional - Install visualization dependencies:**
   ```bash
   pip install matplotlib plotly
   ```

## 🎮 Quick Start

### Analyze All Your Mods
```bash
python mod_loader.py analyze
```
This will:
- Scan all mods in your Factorio directory
- Detect all conflicts automatically
- Generate and install compatibility patches
- Create backups of original files

### Analyze Specific Mods Only
```bash
python mod_loader.py analyze --filter bob --filter angel
```
Only analyzes mods containing "bob" or "angel" in their names.

### Custom Factorio Directory
```bash
python mod_loader.py analyze --mods-path "D:\Games\Factorio\mods"
```

### View Interactive Dependency Graph
```bash
python mod_loader.py analyze --graph
```

## 📖 Usage Guide

### Basic Commands

#### Full Analysis (Recommended)
```bash
python mod_loader.py analyze
```
- Analyzes **all installed mods**
- Detects **all types of conflicts**
- Generates **comprehensive patches**
- **Auto-installs** to Factorio

#### Filtered Analysis
```bash
python mod_loader.py analyze --filter krastorio --filter space
```
- Only analyzes mods matching the filters
- Useful for testing specific mod combinations
- Faster for large mod collections

#### Analysis Without Installation
```bash
python mod_loader.py analyze --no-install
```
- Generates patches but doesn't install them
- Useful for reviewing changes before applying
- Patches saved to `./output/` directory

### Advanced Options

#### Custom Output Directory
```bash
python mod_loader.py analyze --output "./my-patches"
```

#### Show Dependency Graph
```bash
python mod_loader.py analyze --graph
```
Opens an interactive web-based dependency visualization.

#### View Existing Analysis
```bash
python mod_loader.py graph --file "./output/analysis_data.json"
```

### Configuration

The program automatically detects your Factorio installation. Default paths:
- **Windows:** `C:\Users\[username]\AppData\Roaming\Factorio\mods`
- **Linux:** `~/.factorio/mods`
- **macOS:** `~/Library/Application Support/factorio/mods`

Override with `--mods-path` if your installation is elsewhere.

## 🔧 What Gets Fixed

### Recipe Conflicts
**Problem:** Burner inserter requires iron gear wheel, but you're on a wood-only planet.
**Solution:** Creates conditional recipe using wood gear wheel when iron isn't available.

### Broken Research Chains
**Problem:** Mod changes electronics prerequisites, breaking the path to advanced circuits.
**Solution:** Adds alternative research paths to restore technology accessibility.

### Missing Dependencies
**Problem:** Recipe requires items that don't exist with your mod combination.
**Solution:** Substitutes with equivalent items or creates missing items.

### Cross-Mod Incompatibilities
**Problem:** Two mods modify the same recipe in conflicting ways.
**Solution:** Creates compatibility layer that works with both mods.

## 📊 Understanding the Output

### Analysis Summary
```
📈 Analysis Summary
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric              ┃ Count ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Prototypes    │    28 │
│ Conflicted Prototypes│     2 │
│ Critical Issues     │     1 │
│ Generated Patches   │     1 │
└─────────────────────┴───────┘
```

### Critical Issues
Issues that would make the game unplayable:
- Essential recipes becoming uncraftable
- Technologies becoming unreachable
- Required items missing entirely

### Generated Files
- **`analysis_report.json`** - Detailed conflict analysis
- **`dependency_graph.json`** - Mod dependency data
- **`compatibility_patches/`** - Generated patch mods
- **`patch_backups/`** - Backups of installed patches

## 🛡️ Safety Features

### Automatic Backups
- Creates timestamped backups before installing patches
- Stored in `./patch_backups/` directory
- Includes README with installation details

### Non-Destructive Patches
- Patches only add new content, never remove existing
- Uses conditional logic to avoid conflicts
- Can be safely removed if issues occur

### Validation
- Patches are validated before installation
- Lua syntax checking
- Dependency verification

## 🐛 Troubleshooting

### Common Issues

#### "No mods found"
- Check your Factorio mods directory path
- Ensure mods are properly installed and enabled
- Use `--mods-path` to specify custom location

#### "Lua execution error"
- Some mods use complex Lua that can't be parsed
- The system will fall back to simulation mode
- Check logs in `./logs/harmonizer.log` for details

#### "Patch installation failed"
- Ensure Factorio is not running
- Check file permissions on mods directory
- Try running as administrator (Windows)

### Debug Mode
Enable detailed logging:
```bash
python mod_loader.py analyze --verbose
```

### Getting Help
1. Check the log file: `./logs/harmonizer.log`
2. Review the analysis report: `./output/analysis_report.json`
3. Create an issue with your log files and mod list

## 🔬 Advanced Usage

### Custom Mod Paths
```bash
python mod_loader.py analyze --mods-path "/path/to/mods"
```

### Batch Processing
```bash
# Analyze different mod combinations
python mod_loader.py analyze --filter bob --output "./bob-analysis"
python mod_loader.py analyze --filter angel --output "./angel-analysis"
python mod_loader.py analyze --filter space --output "./space-analysis"
```

### Integration with CI/CD
```bash
# Non-interactive mode for automated testing
python mod_loader.py analyze --no-install --output "./test-results"
```

## 📁 Project Structure

```
factorio-harmonizer/
├── mod_loader.py           # Main CLI interface
├── dependency_analyzer.py  # Conflict detection logic
├── modification_tracker.py # Tracks mod changes
├── lua_environment.py     # Lua code execution
├── data_models.py         # Data structures
├── graph_visualizer.py    # Dependency visualization
├── mod_info.py           # Mod discovery and parsing
├── output/               # Generated analysis files
├── patch_backups/        # Backup of installed patches
├── logs/                 # Application logs
└── README.md            # This file
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Factorio** team for creating an amazing game
- **Lupa** library for Lua integration in Python
- **Rich** library for beautiful terminal output
- The Factorio modding community for inspiration

## 🔗 Related Projects

- [Factorio Mod Portal](https://mods.factorio.com/)
- [Factorio Wiki](https://wiki.factorio.com/)
- [Factorio Mod Development](https://lua-api.factorio.com/)

---

**Happy Factory Building! 🏭**