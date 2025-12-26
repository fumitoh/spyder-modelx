# Copilot Instructions for spyder-modelx

## Project Overview

spyder-modelx is a plugin for Spyder. It adds widgets and a custom IPython console to enable the use of Spyder for developing modelx models.

Because spyder-modelx depends on Spyder's source code, updates to Spyder can introduce compatibility issues. Therefore, for each component in spyder-modelx, different source files are included to support different Spyder versions.

## Version-Specific File Management

### File Naming Convention

To support multiple Spyder versions, components in spyder-modelx use version-specific file naming:

- Files without version suffix: Dispatcher files that detect Spyder version and import the appropriate implementation
- Files with version suffix (e.g., `_5.py`, `_5_3.py`, `_6_0.py`): Version-specific implementations

### Examples

In the `spyder_modelx/plugins/` directory:

- `mxplugin.py` - Main dispatcher that detects Spyder version and imports the correct implementation
- `mxplugin_4.py` - Implementation for Spyder 4.x
- `mxplugin_5.py` - Implementation for Spyder 5.0-5.1
- `mxplugin_5_2.py` - Implementation for Spyder 5.2.1+
- `mxplugin_5_3.py` - Implementation for Spyder 5.3+
- `mxplugin_6_0.py` - Implementation for Spyder 6.0+

### Version Detection Pattern

The dispatcher files use `spyder.version_info` to determine which implementation to load:

```python
import spyder

if spyder.version_info > (6,):
    from .mxplugin_6_0 import ModelxPlugin
elif spyder.version_info > (5, 3):
    from .mxplugin_5_3 import ModelxPlugin_5_3 as ModelxPlugin
elif spyder.version_info > (5, 2):
    from .mxplugin_5_2 import ModelxPlugin
elif spyder.version_info > (5,):
    from .mxplugin_5 import ModelxPlugin
else:
    from .mxplugin_4 import ModelxPlugin
```

## Key Components

The plugin consists of several main components, each with version-specific implementations:

1. **Main Plugin** (`mxplugin*.py`) - Core plugin integration with Spyder
2. **Console** (`mxconsole_5_3.py`, `mxconsole_6_0.py`) - Custom IPython console for modelx (integrated into main plugin for older versions)
3. **Analyzer Plugin** (`analyzer_plugin*.py`) - Code analysis features
4. **Data View Plugin** (`dataview_plugin*.py`) - Data visualization widgets
5. **Widgets** - Various UI components in the `widgets/` directory

## Development Guidelines

When modifying or adding features:

1. **Determine which Spyder versions are affected** by your changes
2. **Update the appropriate version-specific files** rather than creating new abstractions
3. **Test against multiple Spyder versions** if possible
4. **Maintain consistency** across version-specific implementations where feasible
5. **Follow the existing pattern** of version detection and conditional imports

## Dependencies

- `spyder>=4.0.0` - The IDE this plugin extends
- `modelx>=0.18.0` - The modeling library this plugin supports
- `spymx-kernels>=0.2.3` - Custom kernel support
- `asttokens` - Token utilities for code analysis
