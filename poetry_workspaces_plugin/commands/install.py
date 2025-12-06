from poetry.console.commands.install import InstallCommand as BaseInstallCommand

from poetry_workspaces_plugin.constants import LOG_PREFIX
from poetry_workspaces_plugin.context import Context
from poetry_workspaces_plugin.factory import Factory


class InstallCommand(BaseInstallCommand):

    def __init__(self, context: Context | None) -> None:
        super().__init__()

        self.context = context

    def handle(self) -> int:
        if not self.context or not self.context.should_manage:
            return super().handle()

        self.line(f'{LOG_PREFIX} Installing dependencies for all workspaces')

        # opt_with = self.option('with')
        opt_only = self.option('only')
        # opt_without = self.option('without')
        # opt_all_groups = self.option('all-groups')

        opt_no_root = self.option('no-root')
        opt_only_root = self.option('only-root')

        self.io.input.set_option('no-root', True)

        # Run initial install
        if not opt_only_root:
            self.line('')

            res = super().handle()

            if opt_only:
                self.line('')
                self.line(f'{LOG_PREFIX} Skipping root installation as "only" was passed')

                return res

            if opt_no_root:
                self.line('')
                self.line(f'{LOG_PREFIX} Skipping root installation as "no-root" was passed')

                return res

        self.io.input.set_option('with', False)
        self.io.input.set_option('only', False)
        self.io.input.set_option('without', False)
        self.io.input.set_option('all-groups', False)
        self.io.input.set_option('no-root', False)
        self.io.input.set_option('only-root', True)

        self.line('')
        self.line(f'{LOG_PREFIX} Running root install for project root')
        self.line('')

        self.set_poetry(
            Factory().create_poetry(
                Context(self.context.root_pyproject, self.context.root_pyproject, [])
            )
        )

        if (res := super().handle()) != 0:
            return res

        for wp in self.context.workspaces_pyprojects:
            self.line('')
            self.line(f'{LOG_PREFIX} Running root install for workspace <c1>{wp.path.parent.name}</c1>')
            self.line('')

            self.set_poetry(
                Factory().create_poetry(
                    Context(self.context.root_pyproject, wp, [])
                )
            )

            if (res := super().handle()) != 0:
                return res

        return 0

