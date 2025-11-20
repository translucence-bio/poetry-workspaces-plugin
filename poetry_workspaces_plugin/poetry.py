from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from cleo.io.null_io import NullIO
from poetry.__version__ import __version__ as poetry_version
from poetry.config.config import Config
from poetry.core.constraints.version.parser import parse_constraint
from poetry.core.constraints.version.version import Version
from poetry.core.factory import Factory as BaseFactory
from poetry.core.packages.project_package import ProjectPackage
from poetry.exceptions import PoetryError
from poetry.config.config import Config
from poetry.factory import Factory
from poetry.packages import Locker
from poetry.core.pyproject.toml import PyProjectTOML
from poetry.poetry import Poetry
from poetry.toml import TOMLFile
from tomlkit import TOMLDocument

from poetry_workspaces_plugin.utils import (
    dedupe,
    get_default_poetry,
    get_plugin_section,
    update_from_diff,
    get_workspaces_paths,
)


def merge_data(base_path: Path, workspaces_paths: list[Path]) -> dict[str, Any]:
    from mergedeep import Strategy, merge

    merged_data = TOMLFile(base_path).read().value
    workspaces_data = [TOMLFile(wp).read().value for wp in workspaces_paths]

    for workspace_data in workspaces_data:
        merged_data = merge(workspace_data, merged_data, strategy=Strategy.ADDITIVE)

    merged_data = cast(dict[str, Any], dedupe(merged_data))

    return merged_data


class PyProjectTOMLWorkspaces(PyProjectTOML):

    def __init__(self, path: Path, workspaces_paths: list[Path]) -> None:
        super().__init__(path)

        self._workspaces_paths = workspaces_paths

    @property
    def data(self) -> dict[str, Any]:
        if self._data is None:
            self._data = merge_data(self.path, self._workspaces_paths)

        return super().data

    @property
    def poetry_config(self) -> dict[str, Any]:
        try:
            return super().poetry_config
        except Exception:
            return {}


class TOMLFileWorkspaces(TOMLFile):

    def __init__(
        self,
        path: Path,
        workspaces_paths: list[Path],
        write_workspace_path: Path | None = None,
    ):
        super().__init__(path)

        self._last_read = None
        self._write_path = write_workspace_path
        self._workspaces_paths = workspaces_paths

    def set_write_path(self, target: Path):
        self._write_path = target

    def read(self) -> TOMLDocument:
        if self._write_path is None:
            self._write_path = self._path

        merged_data = merge_data(self._write_path, self._workspaces_paths)

        merged = TOMLDocument()
        merged.update(merged_data)

        self._last_read = deepcopy(merged)

        return merged

    def write(self, data: TOMLDocument) -> None:
        _path = None

        if self._write_path:
            if self._last_read:
                # Use the diff of the merged pyproject.toml to update the write target
                target = TOMLFile(self._write_path).read().value

                update_from_diff(self._last_read.value, data.value, target)

                data.clear()
                data.update(target)

            # Override the write path so that we write to the target workspace pyproject.toml
            _path = self._path
            self._path = self._write_path

        super().write(data)

        if _path:
            self._path = _path


class PoetryWorkspaces(Poetry):
    def __init__(
        self,
        file: Path,
        local_config: dict[str, Any],
        package: ProjectPackage,
        locker: Locker,
        config: Config,
        workspaces_paths: list[Path],
        disable_cache: bool = False,
    ) -> None:
        super().__init__(file, local_config, package, locker, config, disable_cache)

        self.pyproject._toml_file = TOMLFileWorkspaces(file, workspaces_paths)
        self.workspaces_paths = workspaces_paths

    @property
    def file(self) -> TOMLFileWorkspaces:
        return cast(TOMLFileWorkspaces, super().file)


def create_poetry_workspaces(pyproject_path: Path, with_groups: bool = True):
    """Modified version of Factory().create_poetry()"""
    io = NullIO()
    disable_cache = False

    workspaces_paths = get_workspaces_paths(pyproject_path)

    pyproject = PyProjectTOMLWorkspaces(pyproject_path, workspaces_paths)

    project = pyproject.data.get('project', {})
    name = project.get('name') or pyproject.poetry_config.get('name', 'non-package-mode')
    version = project.get('version') or pyproject.poetry_config.get('version', '0')

    package = ProjectPackage(name, version)

    BaseFactory.configure_package(package, pyproject, pyproject_path, with_groups=with_groups)

    if version_str := pyproject.poetry_config.get('requires-poetry'):
        version_constraint = parse_constraint(version_str)
        version = Version.parse(poetry_version)
        if not version_constraint.allows(version):
            raise PoetryError(
                f'This project requires Poetry {version_constraint},'
                f' but you are using Poetry {version}'
            )

    locker = Locker(pyproject_path.parent / 'poetry.lock', pyproject.data)

    # Loading global configuration
    config = Config.create()

    # Loading local configuration
    config.merge(pyproject.data)

    # Load local sources
    repositories = {}
    existing_repositories = config.get('repositories', {})
    for source in pyproject.poetry_config.get('source', []):
        name = source.get('name')
        url = source.get('url')
        if name and url and name not in existing_repositories:
            repositories[name] = {'url': url}

    config.merge({'repositories': repositories})

    poetry = PoetryWorkspaces(
        pyproject_path,
        pyproject.poetry_config,
        package,
        locker,
        config,
        workspaces_paths,
        disable_cache=disable_cache,
    )

    poetry.set_pool(
        Factory.create_pool(
            config,
            poetry.local_config.get('source', []),
            io,
            disable_cache=disable_cache,
        )
    )

    return poetry


def get_workspaces_poetry(cwd: str | Path | None = None):
    """Get the nearest ancestor poetry instance that has managed workspaces."""
    cwd = Path(cwd or Path.cwd()).resolve()

    candidates = [cwd, *cwd.parents]

    for path in candidates:
        poetry = get_default_poetry(path)

        if poetry and poetry.pyproject.is_poetry_project():
            if get_plugin_section(poetry.pyproject) is not None:
                workspaces_poetry = create_poetry_workspaces(poetry.pyproject_path)

                return workspaces_poetry
