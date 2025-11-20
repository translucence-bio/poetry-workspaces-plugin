from dataclasses import dataclass

from poetry.poetry import Poetry

from poetry_workspaces_plugin.poetry import PoetryWorkspaces


@dataclass
class Context:
    root_poetry: PoetryWorkspaces
    target_poetry: Poetry

    @property
    def target_is_managed(self):
        workspaces_paths = [wp.pyproject_path for wp in self.root_poetry.workspaces_poetries]

        is_managed = self.target_poetry.pyproject_path in workspaces_paths

        return is_managed
