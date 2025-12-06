from poetry_workspaces_plugin.commands.base import BaseCommand


class WorkspacesListCommand(BaseCommand):
    name: str = 'workspaces list'
    description = 'List all available workspaces.'

    def _handle(self):
        for pyproject in self.context.workspaces_pyprojects:
            self.line(f' <c1>{pyproject.name}</c1> {pyproject.path.parent.as_posix()}')

        return 0
