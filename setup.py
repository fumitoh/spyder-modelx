# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Fumito Hamamura
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""Setup script for spyder_modelx."""

# Standard library imports
import ast
import os

# Third party imports
from setuptools import find_packages, setup


HERE = os.path.abspath(os.path.dirname(__file__))
def get_version(module='spyder_modelx'):
    """Get version."""
    with open(os.path.join(HERE, module, '_version.py'), 'r') as f:
        data = f.read()
    lines = data.split('\n')
    for line in lines:
        if line.startswith('version_info'):
            version_tuple = ast.literal_eval(line.split('=')[-1].strip())
            version = '.'.join(map(str, version_tuple))
            break
    return version

def get_description():
    """Get long description."""
    with open(os.path.join(HERE, 'README.rst'), 'r') as f:
        data = f.read()
    return data


REQUIREMENTS = ['spyder']


setup(
    name='spyder-modelx',
    version=get_version(),
    keywords=['Spyder', 'Plugin'],
    url='https://github.com/fumitoh/spyder-modelx',
    license='MIT',
    author='Fumito Hamamura',
    author_email='fumito.ham@gmail.com',
    description='Spyder plugin for modelx',
    long_description=get_description(),
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),
    install_requires=REQUIREMENTS,
    include_package_data=True,
    package_data={'assets':['*']},
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ])
