from __future__ import absolute_import

from piptools.repositories import LocalRequirementsRepository, PyPIRepository
from piptools.resolver import Resolver
from piptools.scripts.compile import get_pip_command
from piptools.utils import key_from_ireq

# -----------------------------------------------------------------------------


def pins_from_ireqs(ireqs, update_ireqs=()):
    pins = {
        key_from_ireq(ireq): ireq
        for ireq in ireqs
    }

    for update_ireq in update_ireqs:
        update_key = key_from_ireq(update_ireq)
        pins.pop(update_key, None)

    return pins


def resolve_ireqs(requirements, prev_pins=None):
    pip_command = get_pip_command()
    pip_options, _ = pip_command.parse_args([])
    session = pip_command._build_session(pip_options)
    repository = PyPIRepository(pip_options, session)

    if prev_pins:
        repository = LocalRequirementsRepository(prev_pins, repository)

    resolver = Resolver(requirements, repository)
    ireqs = resolver.resolve()

    for ireq, hashes in resolver.resolve_hashes(ireqs).items():
        ireq.options['hashes'] = list(hashes)

    return ireqs
