import json
from dataclasses import dataclass
from packaging.utils import canonicalize_name
from pathlib import Path
from typing import Any, TypeVar, cast

from poetry.core.packages.dependency import Dependency
from poetry.core.packages.dependency_group import MAIN_GROUP
from poetry.core.packages.utils.utils import convert_markers
from poetry.factory import Factory
from poetry.core.packages.dependency import Dependency
from poetry.toml import TOMLFile
from tomlkit import TOMLDocument, inline_table, table
from tomlkit.api import array
from tomlkit.items import Table


T = TypeVar('T')


@dataclass
class ResolvedDependency:
    dependency: Dependency
    location: str
    source_location: str | None = None

    def __hash__(self) -> int:
        return hash(self.dependency.name)


def seq_to_cmdline(args):
    "Convert a sequence of arguments to a command line string with proper quoting."""
    parsed_args = []

    for arg in args:
        if ' ' in arg:
            arg = f'"{arg}"'

        parsed_args.append(arg)

    cmd = ' '.join(parsed_args)

    return cmd


def dedupe(o: Any):
    """Recursively de-duplicate all arrays in a TOMLDocument."""
    if isinstance(o, Table):
        t = table()
        t.update({k: dedupe(v) for k, v in o.items()})

        return t

    elif isinstance(o, list):
        a = array()
        a.extend([
            json.loads(i)
            for i in sorted(set(json.dumps(dedupe(item), sort_keys=True) for item in o))
        ])

        return a

    else:
        return o


def update_from_diff(old_dict, new_dict, target_dict):
    """Update target_dict by applying differences between old_dict and new_dict."""
    # Handle added or modified keys
    for key in new_dict:
        new_val = new_dict[key]
        old_val = old_dict.get(key)

        if key not in old_dict:
            # Key was added - add to target
            target_dict[key] = new_val

        elif old_val != new_val:
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                # Recursively handle nested dictionaries
                if key not in target_dict:
                    target_dict[key] = {}

                update_from_diff(old_val, new_val, target_dict[key])

            elif isinstance(old_val, list) and isinstance(new_val, list):
                # Handle list differences - add new items, remove missing ones
                if key not in target_dict:
                    target_dict[key] = []

                # Remove items that are in old but not in new
                target_dict[key] = [item for item in target_dict[key] if item in new_val]

                # Add items that are in new but not in target
                for item in new_val:
                    if item not in target_dict[key]:
                        target_dict[key].append(item)
            else:
                # Simple value change
                target_dict[key] = new_val

    # Handle removed keys
    for key in old_dict:
        if key not in new_dict:
            target_dict.pop(key, None)


def get_path(o: dict[str, Any], path: str):
    keys = path.split('.')

    for key in keys[:-1]:
        o = o.get(key, {})

    res = o.get(keys[-1])

    return res


def set_path(o: dict[str, Any], path: str, value: Any, replace=True):
    keys = path.split('.')

    for key in keys[:-1]:
        o = o.setdefault(key, {})

    if keys[-1] not in o or replace:
        o[keys[-1]] = value

    return value


def delete_path(o: dict[str, Any], path: str):
    if '.' in path:
        path, key = path.rsplit('.', 1)
        keys = path.split('.')
    else:
        key = path
        keys = []

    for key in keys:
        o = o.get(key, dict)

    if key in o:
        del o[key]


def resolve_path(spec: dict | str, pyproject_path: Path):
    if isinstance(spec, str):
        return spec

    spec = spec.copy()

    path = spec.get('path')

    if path is None:
        return spec

    path = pyproject_path.parent / path

    spec['path'] = path.resolve()

    return spec


def get_dependency(
    package: str,
    content: dict[str, Any],
    location: str,
) -> ResolvedDependency | None:
    """Get dependency spec if it exists in a set of dependencies."""
    dependencies = cast(list[str] | dict[str, str | dict] | None, get_path(content, location))

    if dependencies is None:
        return

    if not isinstance(dependencies, (list, dict)):
        return

    normalized_package = canonicalize_name(package)

    res = None

    if isinstance(dependencies, list):
        for req in dependencies:
            dep = Dependency.create_from_pep_508(req)

            if dep.name == normalized_package:
                if location.startswith('dependency-groups'):
                    group_name = location.replace('dependency-groups.', '')

                    src_location = f'tool.poetry.group.{group_name}.dependencies.{package}'
                else:
                    src_location = f'tool.poetry.dependencies.{package}'

                dep.source_name = cast(str | None, get_path(content, f'{src_location}.source'))

                res = ResolvedDependency(dep, location, src_location)
    else:
        for name, value in dependencies.items():
            if canonicalize_name(name) == normalized_package:
                dep = Factory().create_dependency(name, value)
                res = ResolvedDependency(dep, location)

    return res


def get_dependency_from_pyproject(
    pyproject_path: Path,
    package: str,
    group_name: str | None = None,
) -> ResolvedDependency | None:
    """Get the spec and dot notation path of a package (if it exists) in a pyproject file."""
    group_name = group_name if group_name != MAIN_GROUP else None

    content = TOMLFile(pyproject_path).read()

    groups_content = content.get('dependency-groups', {})
    poetry_content = content.get('tool', {}).get('poetry', {})
    poetry_groups_content = poetry_content.get('group', {})

    if group_name:
        if group_name == 'dev' and 'dev-dependencies' in content:
            location = 'dev-dependencies'

            return get_dependency(package, content, location)
        else:
            location = f'dependency-groups.{group_name}'

            if res := get_dependency(package, content, location):
                return res

            location = f'tool.poetry.group.{group_name}.dependencies'

            return get_dependency(package, content, location)
    else:
        location = 'project.dependencies'

        if res := get_dependency(package, content, location):
            return res

        for group_name in groups_content:
            location = f'dependency-groups.{group_name}'

            if res := get_dependency(package, content, location):
               return res

        location = 'tool.poetry.dependencies'

        if res := get_dependency(package, content, location):
            return res

        for group_name in poetry_groups_content:
            location = f'tool.poetry.group.{group_name}.dependencies'

            if res := get_dependency(package, content, location):
                return res


def determine_location(content: dict[str, Any], group: str | None = None, is_source=False):
    project_dependencies = content.get('project', {}).get('dependencies', None)
    project_group_deps = content.get('dependency-groups', None)

    if group:
        if group == 'dev' and 'dev-dependencies' in content:
            location = 'dev-dependencies'
        else:
            if project_dependencies is None or is_source:
                location = f'tool.poetry.group.{group}.dependencies'
            else:
                location = f'dependency-groups.{group}'
    else:
        if project_group_deps is None or is_source:
            location = 'tool.poetry.dependencies'
        else:
            location = 'project.dependencies'

    return location


def dependency_to_constraint(dependency: Dependency):
    constraint = inline_table()

    constraint['version'] = str(dependency.constraint)

    if dependency.is_optional():
        constraint['optional'] = True

    if dependency.allows_prereleases():
        constraint['allow-prereleases'] = True

    if dependency.extras:
        constraint['extras'] = list(dependency.extras)

    if dependency._develop:
        constraint['develop'] = True

    if not dependency.python_constraint.is_any():
        constraint['python'] = str(dependency.python_constraint)

    if str(dependency.marker):
        markers = convert_markers(dependency.marker)

        if 'python_version' in markers:
            constraint['python'] = ','.join([''.join(m) for m in markers['python_version'][0]])

        if 'sys_platform' in markers:
            constraint['platform'] = ','.join([''.join(m) for m in markers['sys_platform'][0]])

        remaining = dependency.marker.exclude('sys_platform').exclude('python_version')

        if str(remaining):
            constraint['markers'] = str(remaining)

    if dependency.source_name:
        constraint['source'] = dependency.source_name

    if len(constraint) == 1 and 'version' in constraint:
        constraint = constraint['version']

    return constraint


def add_package(
    content: TOMLDocument,
    res: ResolvedDependency,
    group: str | None = None,
):
    """Add a package entry to a pyproject dict."""
    group = group if group != MAIN_GROUP else None

    location = determine_location(content, group)

    if location.startswith('project') or location.startswith('dependency-groups'):
        default = array().multiline(True)
    else:
        default = inline_table()

    container = set_path(content, location, default, replace=False)

    name = res.dependency.name

    # If list, use pep_508 format. Otherwise, use dict
    if isinstance(container, list):
        container.append(res.dependency.to_pep_508())

        if res.dependency.source_name:
            location = determine_location(content, group, True)

            set_path(content, f'{location}.{name}.source', res.dependency.source_name)

    elif isinstance(container, dict):
        container[name] = dependency_to_constraint(res.dependency)


def remove_package(content: dict[str, Any], res: ResolvedDependency):
    """Remove a package entry from a pyproject dict."""
    container = get_path(content, res.location)

    if not isinstance(container, (list, dict)):
        return

    if isinstance(container, list):
        for req in container:
            if Dependency.create_from_pep_508(req).name == res.dependency.name:
                container.remove(req)

                if res.source_location:
                    location, key = res.source_location.rsplit('.', 1)

                    src_container = get_path(content, location)

                    if src_container and key in src_container:
                        del src_container[key]

                break

    elif isinstance(container, dict):
        for name in container:
            if canonicalize_name(name) == res.dependency.name:
                del content[name]

                break

    # Delete any empty containers
    if not container:
        location = res.location

        while not container:
            location = location.rsplit('.', 1)[0]
            container = get_path(content, location)

        delete_path(content, location)
