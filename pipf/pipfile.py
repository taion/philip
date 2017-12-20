from contextlib import contextmanager
import copy
import json
from pathlib import Path

import click
import toml

# -----------------------------------------------------------------------------


class Pipfile(object):
    NAME = 'Pipfile'

    REQUIRES_KEY = 'requires'
    PROD_KEY = 'packages'
    DEV_KEY = 'dev-packages'

    LOCKFILE_PROD_KEY = 'default'
    LOCKFILE_DEV_KEY = 'develop'

    def __init__(self, filename=None):
        if filename is None:
            filename = self.find_filename()

        self.filename = filename
        self.lockfile_filename = filename.parent / 'Pipfile.lock'

        self.data = self.get_default_data()

        self.lockfile_data = self.get_default_lockfile_data()
        self.lockfile_file_data = None

        if filename.is_file():
            with filename.open() as file:
                try:
                    file_data = toml.load(file)
                except toml.TomlDecodeError:
                    pass
                else:
                    self.data.update(file_data)

        if self.lockfile_filename.is_file():
            with self.lockfile_filename.open() as lockfile_file:
                try:
                    lockfile_file_data = json.load(lockfile_file)
                except ValueError:
                    pass
                else:
                    self.lockfile_data.update(
                        # Ensure that we don't mutate the original used below.
                        copy.deepcopy(lockfile_file_data),
                    )
                    self.lockfile_file_data = lockfile_file_data

    @classmethod
    def find_filename(cls):
        current_dir = Path().absolute()

        for project_dir in (current_dir,) + tuple(current_dir.parents):
            pipfile_filename = project_dir / cls.NAME
            if pipfile_filename.is_file():
                return pipfile_filename

        raise click.ClickException("no Pipfile found")

    @classmethod
    def get_default_data(cls):
        return {
            'source': [{}],
            cls.REQUIRES_KEY: {},
            cls.PROD_KEY: {},
            cls.DEV_KEY: {},
        }

    @classmethod
    def get_default_lockfile_data(cls):
        return {
            '_meta': {},
            cls.LOCKFILE_PROD_KEY: {},
            cls.LOCKFILE_DEV_KEY: {},
        }

    def get_group_key(self, dev):
        return self.PROD_KEY if not dev else self.DEV_KEY

    def get_lockfile_group_key(self, dev):
        return self.LOCKFILE_DEV_KEY if not dev else self.LOCKFILE_PROD_KEY

    @property
    def python_version(self):
        return self.data[self.REQUIRES_KEY]['python_version']

    @python_version.setter
    def python_version(self, python_version):
        self.data[self.REQUIRES_KEY]['python_version'] = python_version

    def get_lockfile_packages(self, prod_only=False):
        packages = {}

        if not prod_only:
            packages.update(self.lockfile_data[self.LOCKFILE_DEV_KEY])

        packages.update(self.lockfile_data[self.LOCKFILE_PROD_KEY])

        return packages

    def add(self, ireqs, dev=False):
        self.data[self.get_group_key(dev)].update(
            self.make_packages(ireqs),
        )

    def remove(self, ireqs, dev=False):
        group = self.data[self.get_group_key(dev)]
        for package_key in self.make_packages(ireqs):
            group.pop(package_key, None)

    @contextmanager
    def package_diff(self):
        prev_packages = self.get_lockfile_packages()

        package_diff = PackageDiff()
        yield package_diff

        packages = self.get_lockfile_packages()

        updated = {
            package_key: package_info
            for package_key, package_info in packages.items()
            if prev_packages.get(package_key) != package_info
        }

        removed = {
            package_key: package_info
            for package_key, package_info in prev_packages.items()
            if package_key not in packages
        }

        package_diff.set(updated, removed)

    def update_lockfile(self, upgrade=False, update_ireqs=()):
        from .pip import ireqs_from_packages
        from .piptools import pins_from_ireqs, resolve_ireqs

        click.echo("resolving packages...")

        if upgrade:
            prev_prod_pins = None
        else:
            prev_prod_pins = pins_from_ireqs(
                ireqs_from_packages(
                    self.lockfile_data[self.LOCKFILE_PROD_KEY],
                ),
                update_ireqs=update_ireqs,
            )

        prod_ireqs = resolve_ireqs(
            ireqs_from_packages(self.data[self.PROD_KEY]),
            prev_pins=prev_prod_pins,
        )
        self.lockfile_data[self.LOCKFILE_PROD_KEY] = self.make_packages(
            prod_ireqs, lockfile=True,
        )

        if upgrade:
            prev_dev_pins = {}
        else:
            prev_dev_pins = pins_from_ireqs(
                ireqs_from_packages(
                    self.lockfile_data[self.LOCKFILE_DEV_KEY],
                ),
                update_ireqs=update_ireqs,
            )

        prev_dev_pins.update(pins_from_ireqs(prod_ireqs))

        dev_ireqs = resolve_ireqs(
            ireqs_from_packages(self.data[self.DEV_KEY]),
            prev_pins=prev_dev_pins,
        )
        self.lockfile_data[self.LOCKFILE_DEV_KEY] = self.make_packages(
            dev_ireqs, lockfile=True,
        )

        # TODO: Fail if any dev pins don't match corresponding prod ones.

    def make_packages(self, ireqs, lockfile=False):
        return dict(
            self.make_package_tuple(ireq, lockfile=lockfile)
            for ireq in ireqs,
        )

    def make_package_tuple(self, ireq, lockfile=False):
        package_info = {
            'version': str(ireq.req.specifier) or '*',
        }

        if 'hashes' in ireq.options:
            package_info['hashes'] = ireq.options['hashes']

        if not lockfile and tuple(package_info.keys()) == ('version',):
            package_info = package_info['version']

        return self.get_key(ireq), package_info

    @classmethod
    def get_key(cls, ireq):
        return ireq.req.name.lower().replace('_', '-')

    def write(self):
        # Use native open() to work around Unicode handling with pathlib on
        # Python 2.
        with open(str(self.filename), 'w') as file:
            toml.dump(self.data, file)

    def write_lockfile(self):
        if self.lockfile_data == self.lockfile_file_data:
            return

        # Use native open() to work around Unicode handling with pathlib on
        # Python 2.
        with open(str(self.lockfile_filename), 'w') as lockfile_file:
            json.dump(
                self.lockfile_data,
                lockfile_file,
                indent=2,
                separators=(',', ': '),
            )

        click.echo("saved lockfile")


class PackageDiff(object):
    def __init__(self):
        self.updated = None
        self.removed = None

    def set(self, updated, removed):
        self.updated = updated
        self.removed = removed
