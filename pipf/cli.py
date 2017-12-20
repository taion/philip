from pathlib import Path
from subprocess import CalledProcessError
import sys

try:
    from tempfile import TemporaryDirectory
except ImportError:
    from backports.tempfile import TemporaryDirectory

import click
from pew import pew

from .pipfile import Pipfile

# -----------------------------------------------------------------------------

VENV_NAME = 'venv'

# -----------------------------------------------------------------------------


def configure_venv():
    pipfile_filename = Pipfile.find_filename()

    project_dir = pipfile_filename.parent
    pew.workon_home = project_dir

    if not (project_dir / VENV_NAME).is_dir():
        click.echo("creating environment")

        pipfile = Pipfile(pipfile_filename)
        try:
            python_version = pipfile.python_version
        except KeyError:
            raise click.ClickException(
                "could not get Python version from Pipfile",
            )

        pew.mkvirtualenv(VENV_NAME, 'python{}'.format(python_version))

    pew.workon_home = Path().absolute()


def venv_call(*args, **kwargs):
    try:
        pew.inve(VENV_NAME, *args, **kwargs)
    except CalledProcessError as e:
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------


def sync_packages(package_diff):
    remove_packages(package_diff.removed)
    update_packages(package_diff.updated)


def update_packages(updated_packages):
    from .pip import ireqs_from_packages

    if not updated_packages:
        return

    with TemporaryDirectory() as requirements_dir:
        requirements_dir = Path(requirements_dir)
        requirements_filename = requirements_dir / 'requirements.txt'

        with open(str(requirements_filename), 'w') as requirements_file:
            for ireq in ireqs_from_packages(updated_packages):
                requirements_file.write(str(ireq))

                for hash in ireq.options.get('hashes', ()):
                    requirements_file.write(' --hash=')
                    requirements_file.write(hash)

                requirements_file.write('\n')

        venv_call(
            'pip',
            'install',
            '--require-hashes',
            '-r',
            str(requirements_filename),
        )


def remove_packages(removed_packages):
    from .pip import ireq_from_package_str, ireqs_from_packages

    if not removed_packages:
        return

    pip_freeze_result = pew.invoke(
        str(pew.workon_home / VENV_NAME / pew.env_bin_dir / 'pip'),
        'freeze',
    )
    installed_package_keys = frozenset(
        Pipfile.get_key(ireq_from_package_str(package_str))
        for package_str in pip_freeze_result.out.splitlines(),
    )
    to_remove_ireqs = tuple(
        ireq for ireq in ireqs_from_packages(removed_packages)
        if Pipfile.get_key(ireq) in installed_package_keys,
    )

    if to_remove_ireqs:
        venv_call(
            'pip',
            'uninstall',
            '-y',
            *(str(ireq) for ireq in to_remove_ireqs)
        )


# -----------------------------------------------------------------------------


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    '-p', '--python-version',
    default='{0.major}.{0.minor}'.format(sys.version_info),
    show_default=True,
    help="Python version number",
)
def init(python_version):
    pipfile_filename = Path(Pipfile.NAME)
    if pipfile_filename.exists():
        raise click.ClickException("Pipfile already exists")

    click.echo("creating Pipfile")
    pipfile = Pipfile(pipfile_filename)
    pipfile.python_version = python_version
    pipfile.write()


@cli.command()
@click.option('--prod', '--production', is_flag=True)
def install(production):
    prod_only = production

    pipfile = Pipfile()
    pipfile.update_lockfile()
    lockfile_packages = pipfile.get_lockfile_packages(prod_only=prod_only)

    configure_venv()
    update_packages(lockfile_packages)

    pipfile.write_lockfile()


@cli.command(context_settings={
    'ignore_unknown_options': True,
})
@click.argument('packages', nargs=-1)
@click.option('-D', '--dev', is_flag=True)
def add(packages, dev):
    from .pip import ireqs_from_package_strs

    package_strs = packages
    ireqs = ireqs_from_package_strs(package_strs)

    pipfile = Pipfile()
    pipfile.add(ireqs, dev=dev)
    pipfile.write()

    with pipfile.package_diff() as package_diff:
        pipfile.update_lockfile(update_ireqs=ireqs)

    configure_venv()
    sync_packages(package_diff)

    pipfile.write_lockfile()


@cli.command()
@click.argument('packages', nargs=-1)
@click.option('-D', '--dev', is_flag=True)
def remove(packages, dev):
    from .pip import ireqs_from_package_strs

    package_strs = packages
    ireqs = ireqs_from_package_strs(package_strs)

    pipfile = Pipfile()
    pipfile.remove(ireqs, dev=dev)
    pipfile.write()

    with pipfile.package_diff() as package_diff:
        pipfile.update_lockfile()

    configure_venv()
    sync_packages(package_diff)

    pipfile.write_lockfile()


@cli.command('list')
def ls():
    configure_venv()
    venv_call('pip', 'list', '--format=columns')


@cli.command(context_settings={
    'ignore_unknown_options': True,
})
@click.argument('command')
@click.argument('args', nargs=-1)
def run(command, args):
    configure_venv()
    venv_call(command, *args)


@cli.command()
def shell():
    configure_venv()
    pew.shell(VENV_NAME)
