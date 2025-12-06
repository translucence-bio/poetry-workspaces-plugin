from dataclasses import dataclass, field

from tomlkit import array
from tomlkit.items import Table


@dataclass
class Config:
    workspaces: list[str] = field(default_factory=list)
    unified_version: bool = False

    def load(self, plugin_section: Table):
        self.workspaces = plugin_section.get('workspaces', array())
        self.unified_version = plugin_section.get('unified-version', False)
