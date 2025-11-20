from pathlib import Path
from typing import cast

from cleo.helpers import argument

from poetry_workspaces_plugin.commands.base import BaseCommand
from poetry_workspaces_plugin.utils import get_default_poetry


class WorkspaceCommand(BaseCommand):
    name: str = 'workspace'
    description: str = 'Run a Poetry command within the specified workspace.'

    arguments = [
        argument(
            'workspace_name',
            'The workspace to run the command in.',
        ),
        argument(
            'command_name',
            'The Poetry command to run along with any arguments.',
            multiple=True,
        ),
    ]


    def _handle(self):
        workspace_name = self.argument('workspace_name')
        command_name = self.argument('command_name')

        workspaces_paths = self.context.root_poetry.workspaces_paths

        workspace_path = next(
            filter(lambda wp: wp.parent.name == workspace_name, workspaces_paths),
            None,
        )
        workspace_path = cast(Path | None, workspace_path)

        if not workspace_path:
            raise ValueError(f'Could not find a project with the name: {workspace_name}')

        name = command_name[0]
        args = ' '.join(command_name)

        self.line(
            f'Running <info>{name}</info> in workspace <question>{workspace_name}</question>\n'
        )

        target_poetry = get_default_poetry(workspace_path.parent)

        if not target_poetry:
            self.line_error(
                f'Pyproject file for workspace "{workspace_name}" is invalid or does not exist.',
                'error',
            )

            return 1

        self.context.target_poetry = target_poetry

        self.call(name, args)

        return 0
