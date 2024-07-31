#!/usr/bin/env python3

from setuptools import setup, find_packages
import alot


setup(
    license=alot.__copyright__,
    packages=find_packages(exclude=['tests*']),
    package_data={
        'alot': [
            'defaults/alot.rc.spec',
            'defaults/abook_contacts.spec',
            'defaults/default.theme',
            'defaults/default.bindings',
            'defaults/config.stub',
            'defaults/theme.spec',
        ]
    },
)
