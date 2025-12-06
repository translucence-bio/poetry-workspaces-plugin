from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from cleo.io.inputs.argv_input import ArgvInput
from cleo.io.outputs.stream_output import StreamOutput
from poetry.console.application import Application
from poetry.core.packages.dependency import Dependency
from tomlkit import TOMLDocument


def create_project_pyproject(
    name: str,
    version='0.1.0',
    requires_python='>=3.11,<4.0',
    dependencies: dict[str, str] = {},
    group_dependencies: dict[str, dict[str, str]] = {},
):
    content = {
        'project': {
            'name': name,
            'version': version,
            'description': f'Test project {name}.',
            'authors': [],
            'requires-python': requires_python,
        },

        'build-system': {
            'requires': ['poetry-core'],
            'build-backend': ['poetry.core.masonry.api'],
        },
    }

    if dependencies:
        content['project']['dependencies'] = [Dependency(n, c).to_pep_508()
                                                for n, c in dependencies.items()]

    if group_dependencies:
        content['dependency-groups'] = {}

        for group, dependencies in group_dependencies.items():
            content['dependency-groups'][group] = [Dependency(n, c).to_pep_508()
                                                     for n, c in dependencies.items()]

    pyproject = TOMLDocument()
    pyproject.update(content)

    return pyproject


def create_poetry_pyproject(
    name: str,
    version='0.1.0',
    requires_python='>=3.11,<4.0',
    dependencies: dict[str, str] = {},
    group_dependencies: dict[str, dict[str, str]] = {},
):
    dependencies['python'] = requires_python

    content = {
        'tool': {
            'poetry': {
                'name': name,
                'version': version,
                'description': f'Test project {name}.',
                'authors': [],
                'dependencies': dependencies,
            },
        },

        'build-system': {
            'requires': ['poetry-core'],
            'build-backend': ['poetry.core.masonry.api'],
        },
    }

    if group_dependencies:
        group_section = {}

        content['tool']['poetry']['group'] = group_section

        for group, dependencies in group_dependencies.items():
            group_section.setdefault(group, {})['dependencies'] = dependencies

    pyproject = TOMLDocument()
    pyproject.update(content)

    return pyproject


@dataclass
class RunResult:
    app: Application
    output: str
    error_output: str


def run(working_dir: Path, args: list[str]):
    app = Application()
    app._auto_exit = False

    input = ArgvInput([*args, '--directory', working_dir.as_posix()])

    output = StreamOutput(StringIO())
    error_output = StreamOutput(StringIO())

    app.run(input=input, output=output, error_output=error_output)

    output.stream.seek(0)
    error_output.stream.seek(0)

    result = RunResult(app, output.stream.read(), error_output.stream.read())

    return result
