from poetry_workspaces_plugin.commands.base import BaseCommand


class WorkspacesListCommand(BaseCommand):
    name: str = 'workspaces list'
    description = 'List all available workspaces.'

    def _handle(self):
        for path in self.context.workspaces_paths:
            project_root = path.parent

            self.line(f' <question>{project_root.name}</question> {project_root.as_posix()}')

        return 0
