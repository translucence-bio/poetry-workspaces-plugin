import pytest
from pytest import FixtureRequest
from pathlib import Path
from poetry.toml import TOMLFile
from tomlkit import table

from poetry_workspaces_plugin.constants import SECTION_KEY

from testing.utils import create_project_pyproject, create_poetry_pyproject


@pytest.fixture(params=('project', 'poetry'))
def test_package(tmp_path: Path, request: FixtureRequest):
    if request.param == 'project':
        create = create_project_pyproject
    else:
        create = create_poetry_pyproject

    workspace_specs = [
        {
            'name': 'project-a',
            'dependencies': {'pydantic': '>=2.0'},
            'group_dependencies': {
                'test': {
                    'pytest': '>=1.0',
                    'pytest-mock': '>=1.0',
                },
            },
        },
        {
            'name': 'project-b',
            'dependencies': {'numpy': '>=1.0'},
            'group_dependencies': {
                'dev': {
                    'ipython': '>=1.0',
                    'ipdb': '>=1.0',
                },
            },
        },
    ]

    root = tmp_path / 'project-root'
    root.mkdir()

    root_pyproject = create('project-root')
    root_pyproject.setdefault('tool', table())[SECTION_KEY] = {
        'workspaces': ['packages/*'],
    }

    root_file = TOMLFile(root / 'pyproject.toml')
    root_file.write(root_pyproject)

    packages_dir = root / 'packages'
    packages_dir.mkdir()

    workspace_files = []

    for spec in workspace_specs:
        workspace_name = spec['name']

        workspace_dir = packages_dir / workspace_name
        workspace_dir.mkdir()

        src_dir = workspace_dir / workspace_name.replace('-', '_')
        src_dir.mkdir()

        (src_dir / '__init__.py').write_text('')

        workspace_pyproject = create(**spec)

        workspace_file = TOMLFile(workspace_dir / 'pyproject.toml')
        workspace_file.write(workspace_pyproject)

        workspace_files.append(workspace_file)

    return root_file, workspace_files
