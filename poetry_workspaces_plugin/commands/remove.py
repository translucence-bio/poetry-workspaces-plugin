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

        packages = self.argument('packages')

        if self.option('dev'):
            group = 'dev'
        else:
            group = self.option('group', self.default_group)

        excluded: set[ResolvedDependency] = set()
        excluded_workspace_map: dict[ResolvedDependency, set[Path]] = defaultdict(set)

        workspaces_paths = self.context.workspaces_paths
        target_path = self.context.target_path

        non_target_paths = [wp for wp in workspaces_paths if wp != target_path]

        for package in packages.copy():
            res = get_dependency_from_pyproject(target_path, package, group)

            if res is None:
                continue

            for workspace_path in non_target_paths:
                if get_dependency_from_pyproject(workspace_path, package):
                    excluded.add(res)
                    excluded_workspace_map[res].add(workspace_path)

                    if package in packages:
                        packages.remove(package)

        if excluded:
            file = TOMLFile(target_path)

            content = file.read()

            for res in excluded:
                remove_package(content, res)

                name = res.dependency.name

                msg = (
                    f'After removal from workspace <c1>{target_path.parent.name}</c1>,'
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
