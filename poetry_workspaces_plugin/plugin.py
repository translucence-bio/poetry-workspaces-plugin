from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.console_events import COMMAND
from poetry.console.application import Application
from poetry.console.commands.command import Command
from poetry.console.commands.self.self_command import SelfCommand
from poetry.plugins.application_plugin import ApplicationPlugin

# from poetry_workspaces_plugin.commands.add import AddCommand
from poetry_workspaces_plugin.commands.install import InstallCommand
from poetry_workspaces_plugin.commands.build import BuildCommand
# from poetry_workspaces_plugin.commands.remove import RemoveCommand
from poetry_workspaces_plugin.commands.workspace import WorkspaceCommand
from poetry_workspaces_plugin.commands.workspaces_list import WorkspacesListCommand
from poetry_workspaces_plugin.config import Config
from poetry_workspaces_plugin.context import Context
from poetry_workspaces_plugin.factory import Factory
from poetry_workspaces_plugin.pyproject import (
    get_root_pyproject,
    get_workspaces_pyprojects,
    locate_poetry_pyproject,
)


if TYPE_CHECKING:
    from cleo.events.event import Event


class WorkspacesPlugin(ApplicationPlugin):

    def __init__(self) -> None:
        super().__init__()

        self.config = Config()
        self.context: Context | None = None

    def activate(self, application: Application):
        root_pyproject = get_root_pyproject()

        if root_pyproject is not None:
            assert root_pyproject.plugin_section

            self.config.load(root_pyproject.plugin_section)

            self.context = Context(
                root_pyproject=root_pyproject,
                target_pyproject=locate_poetry_pyproject(Path.cwd()) or root_pyproject,
                workspaces_pyprojects=get_workspaces_pyprojects(self.config, root_pyproject.path),
            )

            # Ensure that virtual environment is always relative to root directory
            application._poetry = Factory().create_poetry(
                Context(root_pyproject, root_pyproject, [])
            )

        install_command = InstallCommand(self.context)
        install_command.set_application(application)

        build_command = BuildCommand(self.context)
        build_command.set_application(application)

        application._commands['install'] = install_command
        application._commands['build'] = build_command

        application.command_loader.register_factory(
            WorkspaceCommand.name,
            lambda: WorkspaceCommand(self.context),
        )
        application.command_loader.register_factory(
            WorkspacesListCommand.name,
            lambda: WorkspacesListCommand(self.context),
        )

        if application.event_dispatcher is not None:
            application.event_dispatcher.add_listener(COMMAND, self.prepare)

    def prepare(self, event: Event, *args):
        if not isinstance(event, ConsoleCommandEvent):
            return

        command = event.command

        if not isinstance(command, Command):
            return

        if isinstance(command, SelfCommand):
            return

        if not self.context or not self.context.should_manage:
            return

        poetry = Factory().create_poetry(self.context)

        command.set_poetry(poetry)
