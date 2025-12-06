from pathlib import Path

import pytest

from poetry_workspaces_plugin.constants import SECTION_KEY
from testing.utils import run


@pytest.mark.parametrize(
    ('location'),
    (
        '',
        'packages',
        'packages/project-a',
    ),
    ids=('root', 'subdir', 'workspace'),
)
def test_behaves_correctly_from_any_location(test_package, location):
    root_file, workspace_files = test_package

    working_dir = root_file.path.parent / location

    result = run(working_dir, ['poetry', 'workspaces', 'list'])

    assert result.output

    lines = list(map(lambda l: l.strip(), result.output.strip().split('\n')))

    assert len(lines) == len(workspace_files)

    for line in lines:
        name, strpath = line.split(' ')

        path = Path(strpath)

        assert name == path.name
        assert any([wf.path.parent == path for wf in workspace_files])


def test_raises_in_non_workspaces_project(test_package):
    root_file, _ = test_package

    content = root_file.read()

    content['tool'].pop(SECTION_KEY)

    root_file.write(content)

    result = run(root_file.path.parent, ['poetry', 'workspaces', 'list'])

    assert result.output == ''
    assert result.error_output.startswith('Could not find')
