from __future__ import absolute_import

from pip.req import InstallRequirement

# -----------------------------------------------------------------------------


def ireqs_from_package_strs(package_strs):
    return tuple(
        ireq_from_package_str(package_str)
        for package_str in package_strs,
    )


def ireq_from_package_str(package_str):
    return InstallRequirement.from_line(package_str)


# -----------------------------------------------------------------------------


def ireqs_from_packages(packages):
    return tuple(
        ireq_from_package(package_tuple)
        for package_tuple in packages.items(),
    )


def ireq_from_package(package_tuple):
    package_key, package_info = package_tuple

    if not isinstance(package_info, dict):
        package_info = {'version': package_info}

    requirement_parts = [package_key]

    if package_info['version'] != '*':
        requirement_parts.append(package_info['version'])

    markers = []

    if 'markers' in package_info:
        markers.append(package_info['markers'])

    # TODO: Handle individual markers.

    if markers:
        requirement_parts.append('; ')
        requirement_parts.append(markers[0])

        for marker in markers[1:]:
            requirement_parts.append(' and ')
            requirement_parts.append(marker)

    options = {}
    if 'hashes' in package_info:
        options['hashes'] = package_info['hashes']

    return InstallRequirement.from_line(
        ''.join(requirement_parts), options=options,
    )
