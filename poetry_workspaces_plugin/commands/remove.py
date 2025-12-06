from collections import defaultdict
from pathlib import Path
from poetry.console.commands.remove import RemoveCommand as BaseRemoveCommand
from poetry.toml import TOMLFile

from poetry_workspaces_plugin.constants import LOG_PREFIX
from poetry_workspaces_plugin.context import Context
from poetry_workspaces_plugin.utils import (
    ResolvedDependency,
    get_dependency_from_pyproject,
    remove_package,
)


class RemoveCommand(BaseRemoveCommand):
    def __init__(self, context: Context):
        super().__init__()

        self.context = context

    def handle(self) -> int:
        if not self.context.should_manage:
            return super().handle()

        self.line(f'{LOG_PREFIX} Checking existing configuration.')
        self.line('')

        packages = self.argument('packages')

        if self.option('dev'):
            group = 'dev'
        else:
            group = self.option('group', self.default_group)

        excluded: set[ResolvedDependency] = set()
        excluded_workspace_map: dict[ResolvedDependency, set[Path]] = defaultdict(set)

        workspaces_pyprojects = self.context.workspaces_pyprojects
        target_pyproject = self.context.target_pyproject

        non_targets = [wp for wp in workspaces_pyprojects if wp != target_pyproject]

        for package in packages.copy():
            res = get_dependency_from_pyproject(target_pyproject.path, package, group)

            if res is None:
                continue

            for non_target in non_targets:
                if get_dependency_from_pyproject(non_target.path, package):
                    excluded.add(res)
                    excluded_workspace_map[res].add(non_target.path)

                    if package in packages:
                        packages.remove(package)

        if excluded:
            file = TOMLFile(target_pyproject.path)

            content = file.read()

            for res in excluded:
                remove_package(content, res)

                name = res.dependency.name

                msg = (
                    f'After removal from workspace <c1>{target_pyproject.path.parent.name}</c1>,'
                    f' the following workspaces still depend on <c1>{name}</c1>:\n\n'
                )

                for wp in excluded_workspace_map[res]:
                    msg += (f'  - <c1>{wp.parent.name}</c1>\n')

                self.line(msg)

            file.write(content)

        if not packages:
            self.line('Lock file and environment unchanged.')

            return 0

        return super().handle()
