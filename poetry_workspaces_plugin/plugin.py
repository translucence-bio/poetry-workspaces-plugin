from __future__ import annotations

from typing import TYPE_CHECKING

from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.console_events import COMMAND
from poetry.console.application import Application
from poetry.console.commands.command import Command
from poetry.console.commands.self.self_command import SelfCommand
from poetry.plugins.application_plugin import ApplicationPlugin

from poetry_workspaces_plugin.commands.add import AddCommand
from poetry_workspaces_plugin.commands.remove import RemoveCommand
from poetry_workspaces_plugin.commands.workspace import WorkspaceCommand
from poetry_workspaces_plugin.commands.workspaces_list import WorkspacesListCommand
from poetry_workspaces_plugin.context import Context
from poetry_workspaces_plugin.poetry import create_poetry_workspaces
from poetry_workspaces_plugin.utils import get_workspaces_paths, get_workspaces_root_path


if TYPE_CHECKING:
    from cleo.events.event import Event


class WorkspacesPlugin(ApplicationPlugin):

    def __init__(self) -> None:
        super().__init__()

        self.context = Context()

    def activate(self, application: Application):
        """The entry point of the plugin. This is called by Poetry when the plugin is activated.

        Args:
            application: The Poetry application instance.
        """
        self.context.target_path = application.poetry.pyproject_path

        add_command = AddCommand(self.context)
        add_command.set_application(application)

        remove_command = RemoveCommand(self.context)
        remove_command.set_application(application)

        application._commands['add'] = add_command
        application._commands['remove'] = remove_command

        application.command_loader.register_factory(
            WorkspaceCommand.name,
            lambda: WorkspaceCommand(self.context),
        )
        application.command_loader.register_factory(
            WorkspacesListCommand.name,
            lambda: WorkspacesListCommand(self.context),
        )

        if application.event_dispatcher is not None:
            application.event_dispatcher.add_listener(
                COMMAND, self.setup_context, 10
            )

    def setup_context(self, event: Event, *args):
        if not isinstance(event, ConsoleCommandEvent):
            return

        command = event.command

        if not isinstance(command, Command):
            return

        if isinstance(command, SelfCommand):
            return

        target_path = self.context.target_path

        root_path = get_workspaces_root_path(target_path.parent)

        if not root_path:
            return

        workspaces_paths = get_workspaces_paths(root_path)

        self.context.root_path = root_path
        self.context.workspaces_paths = workspaces_paths

        if not self.context.should_manage:
            return

        poetry = create_poetry_workspaces(root_path, target_path, workspaces_paths)

        command.set_poetry(poetry)
