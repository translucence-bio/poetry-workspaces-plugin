from cleo.io.null_io import NullIO
from poetry.__version__ import __version__ as poetry_version
from poetry.config.config import Config
from poetry.core.constraints.version.parser import parse_constraint
from poetry.core.constraints.version.version import Version
from poetry.core.factory import Factory as BaseFactory
from poetry.core.packages.project_package import ProjectPackage
from poetry.exceptions import PoetryError
from poetry.config.config import Config
from poetry.factory import Factory as BaseFactory
from poetry.packages import Locker
from poetry.poetry import Poetry

from poetry_workspaces_plugin.context import Context
from poetry_workspaces_plugin.merge import PyProjectMerged
from poetry_workspaces_plugin.utils import set_path


class Factory(BaseFactory):

    def create_poetry(self, context: Context):  # type: ignore[reportIncompatibleMethodOverride]
        """Modified version of Factory().create_poetry()

        Lock: Shared venv
        Install: Shared venv install + root install for all workspaces
        Add: Shared venv to ensure conflicting version is not being added
        Remove: No shared venv but want to ensure that target is not removed if another
            workspace depends on it
        Build: No shared venv but need to substitute "workspace:" protocol dependencies
        """
        with_groups = True
        disable_cache = False
        io = NullIO()

        merged_pyproject = PyProjectMerged(context)

        # Root project is never in package mode
        if context.target_is_root:
            set_path(merged_pyproject.data, 'tool.poetry.package-mode', False)

        def validate(pyproject):
            check_result = BaseFactory.validate(pyproject.data)

            if check_result["errors"]:
                message = ""
                for error in check_result["errors"]:
                    message += f"  - {error}\n"

                raise RuntimeError("The Poetry configuration is invalid:\n" + message)

        validate(context.root_pyproject)
        validate(merged_pyproject)

        project = merged_pyproject.data.get('project', {})
        name = project.get('name') or merged_pyproject.poetry_config.get('name', 'non-package-mode')
        version = project.get('version') or merged_pyproject.poetry_config.get('version', '0')

        package = ProjectPackage(name, version)

        BaseFactory.configure_package(
            package,
            merged_pyproject,
            context.target_pyproject.path.parent,
            with_groups=with_groups,
        )

        if version_str := context.root_pyproject.poetry_config.get('requires-poetry'):
            version_constraint = parse_constraint(version_str)
            version = Version.parse(poetry_version)

            if not version_constraint.allows(version):
                raise PoetryError(
                    f'This project requires Poetry {version_constraint},'
                    f' but you are using Poetry {version}'
                )

        # locker = LockerMerged(
        #     root_path.parent / 'poetry.lock',
        #     pyproject_merged.data,
        #     target_path,
        #     workspaces_paths,
        # )
        locker = Locker(context.root_pyproject.path.parent / 'poetry.lock', merged_pyproject.data)

        # Loading global configuration
        config = Config.create()

        # Loading local configuration
        config.merge(context.root_pyproject.data)

        # Load local sources
        repositories = {}
        existing_repositories = config.get('repositories', {})

        for source in context.root_pyproject.poetry_config.get('source', []):
            name = source.get('name')
            url = source.get('url')
            if name and url and name not in existing_repositories:
                repositories[name] = {'url': url}

        config.merge({'repositories': repositories})

        # toml_file = TOMLFileMerged(root_path, target_path, workspaces_paths)
        # toml_file = TOMLFileMerged(root_path, target_path, [])

        # poetry = PoetryWorkspaces(
        #     context,
        #     merged_pyproject.poetry_config,
        #     package,
        #     locker,
        #     config,
        #     disable_cache=disable_cache,
        # )

        poetry = Poetry(
            context.target_pyproject.path,
            merged_pyproject.poetry_config,
            package,
            locker,
            config,
            disable_cache=disable_cache,
        )

        poetry.set_pool(
            Factory.create_pool(
                config,
                poetry.local_config.get('source', []),
                io,
                disable_cache=disable_cache,
            )
        )

        return poetry
