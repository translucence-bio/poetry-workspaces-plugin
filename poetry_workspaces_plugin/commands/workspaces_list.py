from poetry_workspaces_plugin.commands.base import BaseCommand


class WorkspacesListCommand(BaseCommand):
    name: str = 'workspaces list'
    description = 'List all available workspaces.'

    def _handle(self):
        for workspace_poetry in self.context.root_poetry.workspaces_poetries:
            project_root = workspace_poetry.pyproject.path.parent

            self.line(f' <question>{project_root.name}</question> {project_root.as_posix()}')

        return 0
