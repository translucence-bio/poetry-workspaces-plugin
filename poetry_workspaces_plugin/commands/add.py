from poetry.console.commands.add import AddCommand as BaseAddCommand

from poetry_workspaces_plugin.context import Context


class AddCommand(BaseAddCommand):
    def __init__(self, context: Context) -> None:
        self.context = context

        super().__init__()

    def handle(self) -> int:
        group = self.option('group')

        if self.context.root_poetry.pyproject_path == self.context.target_poetry.pyproject_path:
            self.line_error(
                'Cannot call "add" from root directory of workspaces project. '
                'Use the "workspace" command or run from the target workspace.',
                'error',
            )

            return 1

        self.context.root_poetry.file.set_write_target(self.context.target_poetry.pyproject_path)

        return super().handle()

