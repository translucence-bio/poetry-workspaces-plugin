import os
from typing import cast

from cleo.helpers import argument

from poetry_workspaces_plugin.commands.base import BaseCommand
from poetry_workspaces_plugin.constants import LOG_PREFIX
from poetry_workspaces_plugin.utils import seq_to_cmdline
from poetry_workspaces_plugin.pyproject import PyProjectTOML


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

        workspaces_pyprojects = self.context.workspaces_pyprojects

        workspace_pyproject = next(
            filter(lambda wp: wp.name == workspace_name, workspaces_pyprojects),
            None,
        )
        workspace_pyproject = cast(PyProjectTOML | None, workspace_pyproject)

        if not workspace_pyproject:
            raise ValueError(f'Could not find a project with the name: {workspace_name}')

        self.context.target_pyproject = workspace_pyproject

        name = command_name[0]
        args = seq_to_cmdline(command_name)

        self.line(
            f'{LOG_PREFIX} Running <info>{args}</info> in workspace <c1>{workspace_name}</c1>'
        )

        cwd = os.getcwd()

        os.chdir(workspace_pyproject.path.parent)

        self.call(name, args)

        os.chdir(cwd)

        return 0
