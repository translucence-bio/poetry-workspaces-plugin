from typing import cast

from cleo.helpers import argument
from poetry.console.commands.command import Command
from poetry.poetry import Poetry

from poetry_workspaces_plugin.commands.base import BaseCommand


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

        workspace_poetries = self.context.root_poetry.workspaces_poetries

        workspace_poetry = next(
            filter(lambda wp: wp.pyproject.path.parent.name == workspace_name, workspace_poetries),
            None,
        )
        workspace_poetry = cast(Poetry | None, workspace_poetry)

        if not workspace_poetry:
            raise ValueError(f'Could not find a project with the name: {workspace_name}')

        name = command_name[0]
        args = ' '.join(command_name)

        self.line(
            f'Running <info>{name}</info> in workspace <question>{workspace_name}</question>\n'
        )

        self.context.target_poetry = workspace_poetry

        self.call(name, args)

        return 0
