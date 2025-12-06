from collections import defaultdict
from pathlib import Path

from poetry.console.commands.add import AddCommand as BaseAddCommand
from poetry.core.packages.dependency_group import MAIN_GROUP
from poetry.toml import TOMLFile

from poetry_workspaces_plugin.constants import LOG_PREFIX
from poetry_workspaces_plugin.context import Context
from poetry_workspaces_plugin.utils import (
    ResolvedDependency,
    add_package,
    get_dependency_from_pyproject,
)


class AddCommand(BaseAddCommand):
    def __init__(self, context: Context) -> None:
        super().__init__()

        self.context = context

    def handle(self) -> int:
        if not self.context.should_manage:
            return super().handle()

        self.line(f'{LOG_PREFIX} Checking existing configuration.')
        self.line('')

        packages = self.argument('name')

        if self.option('dev'):
            group = 'dev'
        else:
            group = self.option('group', self.default_group or MAIN_GROUP)

        if self.option('extras') and len(packages) > 1:
            raise ValueError(
                'You can only specify one package when using the --extras option'
            )

        optional = self.option('optional')
        if optional and group != MAIN_GROUP:
            raise ValueError('You can only add optional dependencies to the main group')

        excluded: set[ResolvedDependency] = set()
        excluded_workspace_map: dict[ResolvedDependency, set[Path]] = defaultdict(set)

        workspaces_pyprojects = self.context.workspaces_pyprojects
        target_pyproject = self.context.target_pyproject

        non_targets = [wp for wp in workspaces_pyprojects if wp != target_pyproject]

        for package in packages.copy():
            res = get_dependency_from_pyproject(target_pyproject.path, package)

            if res:
                continue

            for non_target in non_targets:
                res = get_dependency_from_pyproject(non_target.path, package)

                if res:
                    excluded.add(res)
                    excluded_workspace_map[res].add(non_target.path)

                    if package in packages:
                        packages.remove(package)

        if excluded:
            file = TOMLFile(target_pyproject.path)

            content = file.read()

            for res in excluded:
                add_package(content, res, group)

                name = res.dependency.name

                msg = (
                    f'Package <c1>{name}</c1> already exists in the following '
                    'workspaces:\n\n'
                )

                for wp in excluded_workspace_map[res]:
                    msg += (f'  - <c1>{wp.parent.name}</c1>\n')

                self.line(msg)
                self.line(
                    f'Adding to workspace <c1>{target_pyproject.path.parent.name}</c1> with '
                    'matching constraint.'
                )
                self.line('')

            file.write(content)

        if not packages:
            self.line('Lock file and environment unchanged.')

            return 0

        return super().handle()
