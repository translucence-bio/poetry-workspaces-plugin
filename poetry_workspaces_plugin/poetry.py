from pathlib import Path
from typing import Any, cast

from poetry.config.config import Config
from poetry.core.packages.project_package import ProjectPackage
from poetry.packages import Locker
from poetry.toml import TOMLFile
from poetry.poetry import Poetry
from tomlkit import TOMLDocument, array, table

from poetry_workspaces_plugin.utils import get_default, get_workspace_poetries


class TOMLFileWorkspaces(TOMLFile):
    """Modified TOML file for working with workspaces.

    On read, the pyproject.toml files from all workspaces will be merged and returned.
    On write, the write will pass through to the pyproject.toml of the target workspace.
    """

    def __init__(
        self,
        path: Path,
        workspaces_paths: list[Path],
        write_workspace_path: Path | None = None,
    ):
        super().__init__(path)

        self._last_read = None
        self._write_target = write_workspace_path
        self._workspaces_files = [TOMLFile(wp) for wp in workspaces_paths]

    def set_write_target(self, target: Path):
        self._write_target = target

    def read(self) -> TOMLDocument:
        from mergedeep import Strategy, merge

        # Parse the root pyproject.toml to determine format
        root_content = super().read()

        project_content = root_content.get('project')
        poetry_content = root_content.get('tool', {}).get('poetry')

        if not (project_content or poetry_content):
            raise ValueError('No project or tool.poetry section found.')

        # Use the write target as the base
        if self._write_target is None:
            self._write_target = self._path

        merged_content = TOMLFile(self._write_target).read().value

        non_target_files = [wf for wf in self._workspaces_files if wf.path != self._write_target]

        for wf in non_target_files:
            content = wf.read().value

            merged_content = merge(content, merged_content, strategy=Strategy.ADDITIVE)

        #     project_content = get_default(content, 'project')

        #     proj_dependencies = project_content.get('dependencies')

        #     if proj_dependencies:
        #         merged_proj_dependencies = get_default(merged, 'project.dependencies', array())

        #         for dep in proj_dependencies:
        #             merged_proj_dependencies.append(dep)

        #     proj_groups = content.get('dependency-groups')

        #     if proj_groups:
        #         for group, deps in proj_groups.items():
        #             merged_proj_group_deps = get_default(merged, f'dependency-groups.{group}', array())

        #             for dep in deps:
        #                 merged_proj_group_deps.append(dep)

        #     poetry_content = get_default(content, 'tool.poetry')

        #     poetry_dependencies = poetry_content.get('dependencies')

        #     if poetry_dependencies:
        #         merged_poetry_dependencies = get_default(merged, 'tool.poetry.dependencies')

        #         for name, constraint in poetry_dependencies.items():
        #             if name in merged_poetry_dependencies:
        #                 raise ValueError(f'Package {name} specified in multiple workspaces.')

        #             merged_poetry_dependencies.update({name: constraint})

        #     poetry_groups = poetry_content.get('group')

        #     if poetry_groups:
        #         for group, deps in poetry_groups.items():
        #             merged_poetry_group_deps = get_default(merged, f'tool.poetry.{group}')

        #             for name, constraint in deps.items():
        #                 if name in merged_poetry_group_deps:
        #                     raise ValueError(f'Package {name} specified in multiple workspaces.')

        #                 merged_poetry_group_deps.update({name: constraint})

        merged = TOMLDocument()
        merged.update(merged_content)

        self._last_read =  merged

        return merged

    def write(self, data: TOMLDocument) -> None:
        # TODO: Probably need to diff what changed since the read and only apply that update.

        if self._write_target:
            _path = self._path
            self._path = self._write_target

        res = super().write(data)

        if self._write_target:
            self._path = _path  # type: ignore[reportPossiblyUnboundVariable]


class PoetryWorkspaces(Poetry):
    def __init__(
        self,
        file: Path,
        local_config: dict[str, Any],
        package: ProjectPackage,
        locker: Locker,
        config: Config,
        disable_cache: bool = False,
    ) -> None:
        super().__init__(file, local_config, package, locker, config, disable_cache)

        self.workspaces_poetries = get_workspace_poetries(self)

        workspace_paths = [wp.pyproject.path for wp in self.workspaces_poetries]

        self.pyproject._toml_file = TOMLFileWorkspaces(file, workspace_paths)

    @classmethod
    def from_poetry(cls, poetry: Poetry) -> 'PoetryWorkspaces':
        new_poetry = cls(
            file=poetry.pyproject_path,
            local_config=poetry.local_config,
            package=poetry.package,
            locker=poetry.locker,
            config=poetry.config,
        )
        new_poetry.set_pool(poetry.pool)

        return new_poetry

    @property
    def file(self) -> TOMLFileWorkspaces:
        return cast(TOMLFileWorkspaces, super().file)
