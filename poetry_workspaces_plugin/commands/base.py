from abc import abstractmethod

from poetry.console.commands.command import Command

from poetry_workspaces_plugin.context import Context


class BaseCommand(Command):
    name: str  # type: ignore[reportIncompatibleVariableOverride]

    def __init__(self, context: Context) -> None:
        self.context = context

        super().__init__()

    @abstractmethod
    def _handle(self) -> int: ...

    def handle(self):
        if not self.context.root_path.name == 'pyproject.toml':
            self.line_error(
                'Could not find a pyproject.toml file with plugin configuration in '
                'current directory or its parents.',
                'error',
            )

            return 1

        return self._handle()
