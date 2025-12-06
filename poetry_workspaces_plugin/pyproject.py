import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from poetry.core.pyproject.exceptions import PyProjectError
from poetry.core.factory import Factory as BaseFactory
from poetry.pyproject.toml import PyProjectTOML as BasePyProjectTOML
from tomlkit import TOMLDocument
from tomlkit.items import Table

from poetry_workspaces_plugin.config import Config
from poetry_workspaces_plugin.constants import PYTHON_VERSION_RE, SECTION_KEY
from poetry_workspaces_plugin.utils import get_path, set_path


class PyProjectTOML(BasePyProjectTOML):

    def __init__(self, path: Path) -> None:
        super().__init__(path)

        self._workspaces: dict[str, str] = {}
        self._data_rendered: TOMLDocument | None = None

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, PyProjectTOML):
            return False

        return self.path == value.path

    @property
    def name(self) -> str:
        name = (
            get_path(self.data, 'project.name') or
            get_path(self.data, 'tool.poetry.name') or
            ''
        )

        return name

    @property
    def version(self) -> str:
        version = (
            get_path(self.data, 'project.version') or
            get_path(self.data, 'tool.poetry.version') or
            '0.0.0'
        )

        return version

    @property
    def plugin_section(self) -> Table | None:
        plugin_section = self.data.get('tool', {}).get(SECTION_KEY)

        return plugin_section

    @property
    def data_raw(self):
        return super().data

    @property
    def data(self) -> TOMLDocument:
        """Regular data object with workspace protocol references removed."""
        data_rendered = deepcopy(self.data_raw)

        project_dependencies = get_path(data_rendered, 'project.dependencies')

        if project_dependencies:
            rendered_dependencies = []

            for p in project_dependencies:
                if 'workspace:' in p:
                    rendered = render_workspace_pep_508(p, self._workspaces)

                    if rendered is not None:
                        rendered_dependencies.append(rendered)
                else:
                    rendered_dependencies.append(p)

            set_path(data_rendered, 'project.dependencies', project_dependencies)

        dependency_groups = get_path(data_rendered, 'project.dependency-groups')

        if dependency_groups:
            for group, dependencies in dependency_groups.items():
                rendered_dependencies = []

                for p in dependencies:
                    if 'workspace:' in p:
                        rendered = render_workspace_pep_508(p, self._workspaces)

                        if rendered is not None:
                            rendered_dependencies.append(rendered)
                    else:
                        rendered_dependencies.append(p)

                dependency_groups[group] = rendered_dependencies

        poetry_dependencies = get_path(data_rendered, 'tool.poetry.dependencies')

        if poetry_dependencies:
            filtered_dependencies = {}

            for name, spec in poetry_dependencies.items():
                if isinstance(spec, str) and 'workspace:' in spec:
                    rendered_version = render_workspace_version(name, spec, self._workspaces)

                    if rendered_version is not None:
                        filtered_dependencies[name] = rendered_version

                elif isinstance(spec, dict) and 'workspace:' in spec.get('version', ''):
                    version = spec['version']
                    rendered_version = render_workspace_version(name, version, self._workspaces)

                    if rendered_version is not None:
                        spec['version'] = rendered_version

                        filtered_dependencies[name] = spec

                else:
                    filtered_dependencies[name] = spec

            set_path(data_rendered, 'tool.poetry.dependencies', filtered_dependencies)

        group_section = get_path(data_rendered, 'tool.poetry.group')

        if group_section:
            for section in group_section.values():
                dependencies = section.get('dependencies')

                if dependencies:
                    filtered_dependencies = {}

                    for name, spec in dependencies.items():
                        if isinstance(spec, str) and 'workspace:' in spec:
                            rendered_version = render_workspace_version(name, spec, self._workspaces)

                            if rendered_version is not None:
                                filtered_dependencies[name] = rendered_version

                        elif isinstance(spec, dict) and 'workspace:' in spec.get('version', ''):
                            version = spec['version']
                            rendered_version = render_workspace_version(name, version, self._workspaces)

                            if rendered_version is not None:
                                spec['version'] = rendered_version

                                filtered_dependencies[name] = spec

                        else:
                            filtered_dependencies[name] = spec

                    section['dependencies'] = filtered_dependencies

        return data_rendered

    @property
    def project_dependencies(self) -> list[str] | None:
        project_dependencies = get_path(self.data, 'project.dependencies')

        return project_dependencies

    @property
    def project_dependency_groups(self) -> list[str] | None:
        group_dependencies = get_path(self.data, 'project.dependency-groups')

        return group_dependencies

    @property
    def poetry_dependencies(self) -> dict[str, str | dict[str, Any]] | None:
        poetry_dependencies = get_path(self.data, 'tool.poetry.dependencies')

        return poetry_dependencies

    @property
    def poetry_group(self) -> dict[str, dict[str, str | dict[str, Any]]] | None:
        group_section = get_path(self.data, 'tool.poetry.group')

        return group_section

    def set_workspaces(self, workspaces: dict):
        self._workspaces = workspaces


def parse_workspace_pep_508(constraint: str):
    name_re = r'(?P<name>[A-Za-z-]+)(?P<extras>\[[\w\s,]+\]?)'
    match = re.search(
        rf'^{name_re}\s+@\s+workspace:(?P<token>[\^~*]?)(?P<version>{PYTHON_VERSION_RE}?)\s*',
        constraint,
    )

    return match


def parse_workspace_version(version: str):
    match = re.search(
        rf'workspace:(?P<token>[\^~*]?)(?P<version>{PYTHON_VERSION_RE}?)\s*',
        version,
    )

    return match


def render_version(parsed_dict: dict, name: str, workspaces: dict):
    workspace_version = workspaces.get(name)

    if not workspace_version:
        return

    token = parsed_dict['token']
    version = parsed_dict['version']

    if token == '*' or '':
        rendered_version = f'=={version or workspace_version}'
    else:
        rendered_version = f'{token}{version or workspace_version}'

    return rendered_version


def render_workspace_pep_508(constraint: str, workspaces: dict):
    parsed = parse_workspace_pep_508(constraint)

    if parsed is None:
        return

    parsed_dict = parsed.groupdict()

    name = parsed_dict['name']

    rendered_version = render_version(parsed_dict, name, workspaces)

    if rendered_version is None:
        return

    extras = parsed_dict['extras']

    rendered = constraint.replace(parsed.group().strip(), f'{name}{extras} ({rendered_version})')

    return rendered


def render_workspace_version(name: str, version: str, workspaces: dict):
    parsed = parse_workspace_version(version)

    if parsed is None:
        return

    parsed_dict = parsed.groupdict()

    rendered_version = render_version(parsed_dict, name, workspaces)

    if rendered_version is None:
        return

    return rendered_version


def create_pyproject(dir: Path):
    """Attempt to create a pyproject instance for directory."""
    path = dir / 'pyproject.toml'

    if path.exists():
        pyproject = PyProjectTOML(path)

        BaseFactory.validate(pyproject.data)

        return pyproject


def locate_poetry_pyproject(
    cwd: str | Path | None = None,
    condition: Callable[[PyProjectTOML], bool] | None = None,
):
    """Get the path of the nearest ancestor pyproject.toml that matches an optional condition."""
    cwd = Path(cwd or Path.cwd()).resolve()

    candidates = [cwd, *cwd.parents]

    for path in candidates:
        pyproject = create_pyproject(path)

        if pyproject and pyproject.is_poetry_project():
            if condition is not None:
                if condition(pyproject):
                    return pyproject
            else:
                return pyproject


def get_root_pyproject(cwd: str | Path | None = None):
    """Get the path of the nearest ancestor pyproject.toml that has managed workspaces."""
    root_pyproject = locate_poetry_pyproject(cwd, lambda p: p.plugin_section is not None)

    return root_pyproject


def get_workspaces_pyprojects(config: Config, root_path: Path) -> list[PyProjectTOML]:
    """Get all managed workspace pyprojects."""
    workspaces_pyprojects = []

    for workspace_glob in config.workspaces:
        for dir in root_path.parent.glob(workspace_glob):
            try:
                workspace_pyproject = create_pyproject(dir)
            except Exception as e:
                raise PyProjectError(
                    f'Workspace "{dir.name}" pyproject.toml is invalid.\n\n{e}'
                )

            if workspace_pyproject and workspace_pyproject.is_poetry_project():
                workspaces_pyprojects.append(workspace_pyproject)

    return workspaces_pyprojects
