import contextlib
from pathlib import Path
from typing import Any, TypeVar

from poetry.factory import Factory
from poetry.pyproject.toml import PyProjectTOML
from poetry.core.pyproject.toml import PyProjectTOML
from tomlkit.api import array
from tomlkit.items import Table

from poetry_workspaces_plugin.constants import SECTION_KEY


T = TypeVar('T')


def dedupe(o: Any):
    """Recursively de-duplicate all lists in a dictionary."""
    if isinstance(o, dict):
        return {k: dedupe(v) for k, v in o.items()}
    elif isinstance(o, list):
        return list(set(dedupe(item) for item in o))
    else:
        return o


def update_from_diff(old_dict, new_dict, target_dict):
    """Update target_dict by applying differences between old_dict and new_dict."""
    # Handle added or modified keys
    for key in new_dict:
        new_val = new_dict[key]
        old_val = old_dict.get(key)

        if key not in old_dict:
            # Key was added - add to target
            target_dict[key] = new_val

        elif old_val != new_val:
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                # Recursively handle nested dictionaries
                if key not in target_dict:
                    target_dict[key] = {}

                update_from_diff(old_val, new_val, target_dict[key])

            elif isinstance(old_val, list) and isinstance(new_val, list):
                # Handle list differences - add new items, remove missing ones
                if key not in target_dict:
                    target_dict[key] = []

                # Remove items that are in old but not in new
                target_dict[key] = [item for item in target_dict[key] if item in new_val]

                # Add items that are in new but not in target
                for item in new_val:
                    if item not in target_dict[key]:
                        target_dict[key].append(item)
            else:
                # Simple value change
                target_dict[key] = new_val

    # Handle removed keys
    for key in old_dict:
        if key not in new_dict:
            target_dict.pop(key, None)


def get_plugin_section(pyproject: PyProjectTOML) -> Table | None:
    """Get the plugin configuration section from if it exists."""
    plugin_section = pyproject.data.get('tool', {}).get(SECTION_KEY)

    return plugin_section


def get_default_poetry(dir: Path):
    """Get the poetry instance for directory if it exists."""
    with contextlib.suppress(Exception):
        return Factory().create_poetry(dir)


def get_workspaces_paths(pyproject_path: Path) -> list[Path]:
    """Get all pyproject paths that belong to managed workspaces."""
    pyproject = PyProjectTOML(pyproject_path)

    plugin_section = get_plugin_section(pyproject)

    if not plugin_section:
        return []

    workspaces_globs = plugin_section.get('workspaces', array())

    workspace_paths = []

    for workspace_glob in workspaces_globs:
        for dir in pyproject_path.parent.glob(workspace_glob):
            workspace_poetry = get_default_poetry(dir)

            if workspace_poetry and workspace_poetry.pyproject.is_poetry_project():
                workspace_paths.append(workspace_poetry.pyproject_path)

    return workspace_paths
