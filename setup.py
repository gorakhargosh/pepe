#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2002-2005 ActiveState Software Ltd.
# Copyright (C) 2011 Yesudeep Mangalapilly <yesudeep@gmail.com>

"""pepe: a multi-language preprocessor"""

import os
import sys
import imp
from setuptools import setup

pepe = imp.load_source('pepe', 'pepe.py')

def read_file(filename):
    """
    Reads the contents of a given file relative to the directory
    containing this file and returns it.

    :param filename:
        The file to open and read contents from.
    """
    return open(os.path.join(os.path.dirname(__file__), filename)).read()


if sys.version_info < (3,):
    extra = {}
else:
    extra = dict(use_2to3=True)

install_requires = []
if sys.version_info < (2, 7, 0):
# argparse is merged into Python 2.7 in the Python 2x series
# and Python 3.2 in the Python 3x series.
    install_requires.append('argparse >=1.1')

setup(
    name="pepe",
    version=pepe.__version__,
    description="Portable multi-language file preprocessor",
    long_description=read_file('README'),
    author="Trent Mick",
    author_email="trentm@gmail.com",
    maintainer="Yesudeep Mangalapilly",
    maintainer_email="yesudeep@gmail.com",
    url="http://github.com/gorakhargosh/pepe",
    license="MIT License",
    platforms=["any"],
    classifiers="""Development Status :: 5 - Production/Stable
Intended Audience :: Developers
License :: OSI Approved :: MIT License
Programming Language :: Python
Operating System :: OS Independent
Topic :: Software Development :: Libraries :: Python Modules
Topic :: Text Processing :: Filters""".split("\n"),
    keywords=' '.join(["python",
                       "preprocessor",
                       "pepe",
                       "preprocess",
                       "portable",
                       ]),
    packages=["pepe"],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'pepe = pepe:main',
            ]
        },
    zip_safe=False,
    install_requires=install_requires,
    **extra
    )
