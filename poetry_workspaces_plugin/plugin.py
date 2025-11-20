"""Copyright (C) 2024 GlaxoSmithKline plc"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.console_events import COMMAND
from poetry.console.commands.env_command import EnvCommand
from poetry.console.commands.self.self_command import SelfCommand
from poetry.plugins.application_plugin import ApplicationPlugin

from poetry_workspaces_plugin.commands.remove import RemoveCommand
from poetry_workspaces_plugin.context import Context
from poetry_workspaces_plugin.poetry import PoetryWorkspaces
from poetry_workspaces_plugin.commands.add import AddCommand
from poetry_workspaces_plugin.commands.workspace import WorkspaceCommand
from poetry_workspaces_plugin.commands.workspaces_list import WorkspacesListCommand
from poetry_workspaces_plugin.utils import get_root_poetry


if TYPE_CHECKING:
    from cleo.events.event import Event
    from poetry.console.application import Application


class WorkspacesPlugin(ApplicationPlugin):

    def __init__(self) -> None:
        super().__init__()

        self.context = None

    def activate(self, application: Application):
        """The entry point of the plugin. This is called by Poetry when the plugin is activated.

        Args:
            application: The Poetry application instance.
        """
        root_poetry = get_root_poetry(application.poetry.pyproject_path.parent)

        if root_poetry:
            root_poetry = PoetryWorkspaces.from_poetry(root_poetry)

            self.context = Context(
                root_poetry=root_poetry,
                target_poetry=application.poetry,
            )

            # If target project is not a managed workspace, don't register commands.
            # This could happen if for whatever reason there are non-workspace projects
            # alongside workspace projects.
            if self.context.target_is_managed:
                add_command = AddCommand(self.context)
                add_command.set_application(application)

                remove_command = RemoveCommand(self.context)
                remove_command.set_application(application)

                application._commands['add'] = add_command
                application._commands['remove'] = remove_command

        if application.event_dispatcher is not None:
            application.event_dispatcher.add_listener(
                COMMAND, self.console_command_event_listener, 1
            )
            # application.event_dispatcher.add_listener(
            #     TERMINATE, self.post_console_command_event_listener
            # )

        application.command_loader.register_factory(
            WorkspaceCommand.name,
            lambda: WorkspaceCommand(self.context),
        )
        application.command_loader.register_factory(
            WorkspacesListCommand.name,
            lambda: WorkspacesListCommand(self.context),
        )

    def console_command_event_listener(self, event: Event, *args):
        """The event listener for console commands. This is executed before the command is run.

        Args:
            event: The event object.
        """
        if not isinstance(event, ConsoleCommandEvent):
            return

        if self.context and not self.context.target_is_managed:
            return

        command = event.command

        if isinstance(command, EnvCommand) and not isinstance(command, SelfCommand):
            if self.context:
                command.set_poetry(self.context.root_poetry)

        # if isinstance(command, (LockCommand, InstallCommand, UpdateCommand)):
        #     from poetry_workspaces_plugin.lock_modifier import LockModifier

        #     # NOTE: consider moving this to a separate UpdateModifier class
        #     if isinstance(command, UpdateCommand) and not event.io.input._arguments.get('packages', None):
        #         event.io.input._arguments["packages"] = [command.poetry.package.name]

        #     LockModifier(self.plugin_conf).execute(event)

        # if isinstance(command, BuildCommand):
        #     from poetry_workspaces_plugin.path_dep_pinner import PathDepPinner

        #     PathDepPinner(self.plugin_conf).execute(event)

        # if ExportCommand is not None and isinstance(command, ExportCommand):
        #     from poetry_workspaces_plugin.export_modifier import ExportModifier

        #     ExportModifier(self.plugin_conf).execute(event)

    # def post_console_command_event_listener(self, event: Event, *args):
    #     """The event listener for console commands. This is executed after the command is run.

    #     Args:
    #         event: The event object.
    #         event_name: The name of the event.
    #         dispatcher: The event dispatcher.
    #     """
    #     if not isinstance(event, ConsoleTerminateEvent):
    #         return

        # command = event.command

        # if isinstance(command, EnvCommand) and not isinstance(command, SelfCommand):
        #     command.set_poetry(command.get_application().poetry)

        # if isinstance(command, (AddCommand, RemoveCommand)):
        #     from poetry_workspaces_plugin.monorepo_adder import MonorepoAdderRemover

        #     adder_remover = self.ctx.pop(AddCommand, MonorepoAdderRemover(self.plugin_conf))
        #     adder_remover.post_execute(event)
