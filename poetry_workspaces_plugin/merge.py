from copy import deepcopy
from typing import cast

from poetry.pyproject.toml import PyProjectTOML as BasePyProjectTOML
from poetry.toml import TOMLFile
from tomlkit import TOMLDocument

from poetry_workspaces_plugin.context import Context
from poetry_workspaces_plugin.utils import dedupe, delete_path, get_path, set_path, update_from_diff


def merge_data(context: Context) -> TOMLDocument:
    from mergedeep import Strategy, merge

    # 'project.name' or 'tool.poetry.name' = target
    # 'project.version' or 'tool.poetry.version' = target
    # 'project.dependencies' = all
    # 'project.dependency-groups' = all
    # 'tool.poetry.dependencies' = all
    # 'tool.poetry.group' = all
    # 'all remaining' = root

    merged_data = TOMLDocument()

    project = get_path(context.target_pyproject.data, 'project')

    if project:
        set_path(merged_data, 'project', project)

    poetry = get_path(context.target_pyproject.data, 'tool.poetry')

    if poetry:
        set_path(merged_data, 'tool.poetry', poetry)

    for workspace_pyproject in context.workspaces_pyprojects:
        if workspace_pyproject.project_dependencies is not None:
            set_path(
                merged_data, 'project.dependencies',
                merge(
                    {'dependencies': get_path(merged_data, 'project.dependencies') or []},
                    {'dependencies': workspace_pyproject.project_dependencies},
                    strategy=Strategy.ADDITIVE,
                )['dependencies'],
            )

        if workspace_pyproject.poetry_dependencies is not None:
            set_path(
                merged_data,
                'tool.poetry.dependencies',
                merge(
                    get_path(merged_data, 'tool.poetry.dependencies') or {},
                    workspace_pyproject.poetry_dependencies,
                    strategy=Strategy.ADDITIVE,
                ),
            )

        if workspace_pyproject.project_dependency_groups:
            set_path(
                merged_data,
                'project.dependency-groups',
                merge(
                    {'dependency-groups': get_path(merged_data, 'project.dependency-groups') or []},
                    {'dependency-groups': workspace_pyproject.project_dependency_groups},
                    strategy=Strategy.ADDITIVE,
                )['dependency-groups'],
            )

        if workspace_pyproject.poetry_group:
            set_path(
                merged_data,
                'tool.poetry.group',
                merge(
                    get_path(merged_data, 'tool.poetry.group') or {},
                    workspace_pyproject.poetry_group,
                    strategy=Strategy.ADDITIVE,
                ),
            )

    delete_path(merged_data, 'tool.poetry.source')

    poetry_sources = get_path(context.root_pyproject.data, 'tool.poetry.source')

    if poetry_sources:
        set_path(merged_data, 'tool.poetry.source', poetry_sources)

    merged_data = cast(TOMLDocument, dedupe(merged_data))

    return merged_data


class TOMLFileMerged(TOMLFile):

    def __init__(self, context: Context):
        super().__init__(context.root_pyproject.path)

        self._context = context
        self._last_read = None

    def read(self) -> TOMLDocument:
        data = merge_data(self._context)

        self._last_read = deepcopy(data)

        return data

    def write(self, data: TOMLDocument) -> None:
        if self._last_read:
            # Use the diff of the last read to update the write target
            target = deepcopy(self._context.target_pyproject.data)

            update_from_diff(self._last_read.value, data.value, target)

            data.clear()
            data.update(target)

        self._path = self._context.target_pyproject.path

        super().write(data)

        self._path = self._context.root_pyproject.path


class PyProjectMerged(BasePyProjectTOML):

    def __init__(self, context):
        super(BasePyProjectTOML, self).__init__(context.target_pyproject.path)

        self._toml_file = TOMLFileMerged(context)
        self._toml_document: TOMLDocument | None = None
        self._context = context
