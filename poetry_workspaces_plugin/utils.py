import contextlib
from pathlib import Path
from typing import TypeVar

from poetry.factory import Factory
from poetry.poetry import Poetry
from poetry.pyproject.toml import PyProjectTOML
from tomlkit import TOMLDocument, table
from tomlkit.api import array
from tomlkit.items import Table
from poetry.poetry import Poetry

from poetry_workspaces_plugin.constants import SECTION_KEY


T = TypeVar('T')


def get_default(container: TOMLDocument | Table, path: str, default: T = table()) -> T:
    *leading, primary = path.split('.')

    for key in leading:
        container = container.setdefault(key, table())

    value = container.setdefault(primary, default)

    return value


def get_plugin_section(pyproject: PyProjectTOML) -> Table | None:
    """Get the plugin configuration section from if it exists."""
    plugin_section = pyproject.data.get('tool', {}).get(SECTION_KEY)

    return plugin_section


def get_poetry(dir: str | Path):
    """Get the poetry instance for directory if it exists."""
    dir = Path(dir)

    pyproject_path = dir / 'pyproject.toml'

    if pyproject_path.exists():
        with contextlib.suppress(Exception):
            return Factory().create_poetry(dir)


def get_root_poetry(cwd: str | Path | None = None):
    """Get the nearest ancestor poetry instance that has managed workspaces."""
    cwd = Path(cwd or Path.cwd()).resolve()

    candidates = [cwd, *cwd.parents]

    for path in candidates:
        poetry = get_poetry(path)

        if poetry and poetry.pyproject.is_poetry_project():
            if get_plugin_section(poetry.pyproject) is not None:
                return poetry


def get_workspace_poetries(poetry: Poetry) -> list[Poetry]:
    """Get all poetry instances that belong to managed workspaces."""
    plugin_section = get_plugin_section(poetry.pyproject)

    if not plugin_section:
        return []

    workspaces_globs = plugin_section.get('workspaces', array())

    workspace_poetries = []

    for workspace_glob in workspaces_globs:
        for path in poetry.pyproject.path.parent.glob(workspace_glob):
            workspace_poetry = get_poetry(path)

            if workspace_poetry and workspace_poetry.pyproject.is_poetry_project():
                workspace_poetries.append(workspace_poetry)

    return workspace_poetries


