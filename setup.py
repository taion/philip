import subprocess

from setuptools import Command, setup

# -----------------------------------------------------------------------------


def system(command):
    class SystemCommand(Command):
        user_options = []

        def initialize_options(self):
            pass

        def finalize_options(self):
            pass

        def run(self):
            subprocess.check_call(command, shell=True)

    return SystemCommand


# -----------------------------------------------------------------------------

setup(
    name="philip",
    version='0.0.0',
    description="Predictable Python package management",
    url='https://github.com/taion/philip',
    author="Jimmy Jia",
    author_email='tesrin@gmail.com',
    license='MIT',
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ),
    keywords='pip pipfile',
    packages=('philip',),
    install_requires=(
        'backports.tempfile; python_version < "3.2"',
        'click',
        'pathlib; python_version < "3.4"',
        'pip-tools',
        'pew',
        'toml',
    ),
    entry_points='''
        [console_scripts]
        philip = philip:cli
    ''',
    cmdclass={
        'clean': system('rm -rf build dist *.egg-info'),
        'package': system('python setup.py pandoc sdist bdist_wheel'),
        'pandoc': system('pandoc README.md -o README.rst'),
        'publish': system('twine upload dist/*'),
        'release': system('python setup.py clean package publish'),
        'test': system('tox'),
    },
)
