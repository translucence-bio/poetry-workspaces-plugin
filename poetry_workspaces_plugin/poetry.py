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

from poetry_workspaces_plugin.utils import dedupe, update_from_diff


def merge_data(base: Path | dict[str, Any], *workspaces_paths: Path) -> dict[str, Any]:
    from mergedeep import Strategy, merge

    merged_data = TOMLFile(base).read().value if isinstance(base, Path) else base
    workspaces_data = [TOMLFile(wp).read().value for wp in workspaces_paths]

    for workspace_data in workspaces_data:
        merged_data = merge(workspace_data, merged_data, strategy=Strategy.ADDITIVE)

    merged_data = cast(dict[str, Any], dedupe(merged_data))

    return merged_data


class TOMLFileMerged(TOMLFile):

    def __init__(self, path: Path, write_path: Path, workspaces_paths: list[Path]):
        super().__init__(path)

        self._last_read = None
        self._write_path = write_path
        self._workspaces_paths = workspaces_paths

    def set_workspace_write(self, path: Path | None):
        self._workspace_write = path

    def read(self) -> TOMLDocument:
        data = merge_data(self._write_path, self._path, *self._workspaces_paths)
        # data = merge_data(self._write_path, *self._workspaces_paths)

        content = TOMLDocument()
        content.update(data)

        self._last_read = deepcopy(content)

        return content

    def write(self, data: TOMLDocument) -> None:
        if self._last_read:
            # Use the diff of the merged pyproject.toml to update the write target
            target = TOMLFile(self._write_path).read().value

            update_from_diff(self._last_read.value, data.value, target)

            data.clear()
            data.update(target)

        _path = self._path
        self._path = self._write_path

        super().write(data)

        self._path = _path


class PyProjectMerged(PyProjectTOML):

    def __init__(self, path: Path, root_path: Path, workspaces_paths: list[Path]):
        super().__init__(path)

        self._root_path = root_path
        self._workspaces_paths = workspaces_paths

    @property
    def data(self) -> dict[str, Any]:
        if self._data is None:
            self._data = merge_data(self.path, self._root_path, *self._workspaces_paths)

        return super().data


class LockerMerged(Locker):
    def __init__(
        self,
        lock: Path,
        pyproject_data: dict[str, Any],
        write_path: Path,
        workspaces_paths: list[Path],
    ) -> None:
        super().__init__(lock, pyproject_data)

        self._write_path = write_path
        self._workspaces_paths = workspaces_paths

    def set_pyproject_data(self, pyproject_data: dict[str, Any]) -> None:
        # This method is only called in the add/remove commands, and we intercept for scenarios
        # where the same dependency is listed in more than one workspace. If it is, then don't
        # want to modify the lockfile.
        non_target_paths = [wp for wp in self._workspaces_paths if wp != self._write_path]

        data = merge_data(pyproject_data, *non_target_paths)

        return super().set_pyproject_data(data)


class PoetryWorkspaces(Poetry):

    def __init__(
        self,
        file: Path,
        local_config: dict[str, Any],
        package: ProjectPackage,
        locker: Locker,
        config: Config,
        workspaces_paths: list[Path],
        toml_file: TOMLFileMerged,
        disable_cache: bool = False,
    ) -> None:
        super().__init__(file, local_config, package, locker, config, disable_cache)

        self._toml_file = toml_file
        self.workspaces_paths = workspaces_paths

    @property
    def file(self) -> TOMLFileMerged:
        return self._toml_file


def create_poetry_workspaces(
    root_path: Path,
    target_path: Path,
    workspaces_paths: list[Path],
):
    """Modified version of Factory().create_poetry()"""
    # venv location = poetry.file.path.parent
    # add/remove = poetry.file.read and poetry.file.write
    # poetry.lock = poetry.locker.lock

    with_groups = True
    disable_cache = False
    io = NullIO()

    pyproject_root = PyProjectTOML(root_path)
    # pyproject_target = PyProjectTOML(target_path)
    pyproject_merged = PyProjectMerged(target_path, root_path, workspaces_paths)

    # Workspaces project is never in package mode
    if target_path == root_path:
        pyproject_merged.data.setdefault('tool', {}).setdefault('poetry', {})['package-mode'] = False

    def validate(pyproject):
        check_result = BaseFactory.validate(pyproject.data)

        if check_result["errors"]:
            message = ""
            for error in check_result["errors"]:
                message += f"  - {error}\n"

            raise RuntimeError("The Poetry configuration is invalid:\n" + message)

    validate(pyproject_root)
    validate(pyproject_merged)

    project = pyproject_merged.data.get('project', {})
    name = project.get('name') or pyproject_merged.poetry_config.get('name', 'non-package-mode')
    version = project.get('version') or pyproject_merged.poetry_config.get('version', '0')

    package = ProjectPackage(name, version)

    BaseFactory.configure_package(
        package,
        pyproject_merged,
        target_path.parent,
        with_groups=with_groups,
    )

    if version_str := pyproject_root.poetry_config.get('requires-poetry'):
        version_constraint = parse_constraint(version_str)
        version = Version.parse(poetry_version)

        if not version_constraint.allows(version):
            raise PoetryError(
                f'This project requires Poetry {version_constraint},'
                f' but you are using Poetry {version}'
            )

    locker = LockerMerged(
        root_path.parent / 'poetry.lock',
        pyproject_merged.data,
        target_path,
        workspaces_paths,
    )

    # Loading global configuration
    config = Config.create()

    # Loading local configuration
    config.merge(pyproject_root.data)

    # Load local sources
    repositories = {}
    existing_repositories = config.get('repositories', {})

    for source in pyproject_root.poetry_config.get('source', []):
        name = source.get('name')
        url = source.get('url')
        if name and url and name not in existing_repositories:
            repositories[name] = {'url': url}

    config.merge({'repositories': repositories})

    # toml_file = TOMLFileMerged(root_path, target_path, workspaces_paths)
    toml_file = TOMLFileMerged(root_path, target_path, [])

    poetry = PoetryWorkspaces(
        target_path,
        pyproject_merged.poetry_config,
        package,
        locker,
        config,
        workspaces_paths,
        toml_file,
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
