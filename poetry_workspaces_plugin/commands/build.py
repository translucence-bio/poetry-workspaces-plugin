from poetry.console.commands.build import BuildCommand as BaseBuildCommand

from poetry_workspaces_plugin.context import Context
from poetry_workspaces_plugin.factory import Factory


class BuildCommand(BaseBuildCommand):

    def __init__(self, context: Context | None) -> None:
        super().__init__()

        self.context = context

    def handle(self) -> int:
        if self.context and self.context.should_manage:
            workspaces = {wp.name: wp.version for wp in self.context.workspaces_pyprojects}

            self.context.target_pyproject.set_workspaces(workspaces)

            poetry = Factory().create_poetry(self.context)

            self.set_poetry(poetry)

        return super().handle()

