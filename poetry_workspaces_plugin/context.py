from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Context:
    root_path: Path = Path()
    target_path: Path = Path()
    workspaces_paths: list[Path] = field(default_factory=list)

    @property
    def target_is_root(self):
        return self.root_path == self.target_path

    @property
    def target_is_managed(self):
        return self.target_path in self.workspaces_paths

    @property
    def should_manage(self):
        return bool(self.target_is_root or self.target_is_managed)
