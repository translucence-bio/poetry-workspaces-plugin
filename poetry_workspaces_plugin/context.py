from dataclasses import dataclass

from poetry.poetry import Poetry

from poetry_workspaces_plugin.poetry import PoetryWorkspaces


@dataclass
class Context:
    root_poetry: PoetryWorkspaces
    target_poetry: Poetry

    @property
    def target_is_root(self):
        is_root = self.target_poetry.pyproject_path == self.root_poetry.pyproject_path

        return is_root

    @property
    def target_is_managed(self):
        is_managed = self.target_poetry.pyproject_path in self.root_poetry.workspaces_paths

        return is_managed
