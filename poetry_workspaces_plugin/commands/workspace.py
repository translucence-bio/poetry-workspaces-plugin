from pathlib import Path
from typing import cast

from cleo.helpers import argument

from poetry_workspaces_plugin.commands.base import BaseCommand
from poetry_workspaces_plugin.constants import LOG_PREFIX
from poetry_workspaces_plugin.utils import seq_to_cmdline


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

        workspaces_paths = self.context.workspaces_paths

        workspace_path = next(
            filter(lambda wp: wp.parent.name == workspace_name, workspaces_paths),
            None,
        )
        workspace_path = cast(Path | None, workspace_path)

        if not workspace_path:
            raise ValueError(f'Could not find a project with the name: {workspace_name}')

        self.context.target_path = workspace_path

        name = command_name[0]
        args = seq_to_cmdline(command_name)

        self.line(
            f'{LOG_PREFIX} Running <info>{name}</info> in workspace <c1>{workspace_name}</c1>'
        )
        self.line('')

        self.call(name, args)

        return 0
