from dataclasses import dataclass, field

from poetry_workspaces_plugin.pyproject import PyProjectTOML


@dataclass
class Context:
    root_pyproject: PyProjectTOML
    target_pyproject: PyProjectTOML
    workspaces_pyprojects: list[PyProjectTOML] = field(default_factory=list)

    @property
    def target_is_root(self):
        return self.root_pyproject == self.target_pyproject

    @property
    def target_is_managed(self):
        return self.target_pyproject in self.workspaces_pyprojects

    @property
    def should_manage(self):
        return bool(self.target_is_root or self.target_is_managed)
