#!/usr/bin/env python
# Copyright (c) 2002-2005 ActiveState Software Ltd.
# Copyright (C) 2011 Yesudeep Mangalapilly <yesudeep@gmail.com>

"""pepe: a multi-language preprocessor

There are millions of templating systems out there (most of them
developed for the web). This isn't one of those, though it does share
some basics: a markup syntax for templates that are processed to give
resultant text output.  The main difference with `pepe.py` is
that its syntax is hidden in comments (whatever the syntax for comments
maybe in the target filetype) so that the file can still have valid
syntax. A comparison with the C preprocessor is more apt.

`pepe.py` is targetted at build systems that deal with many
types of files. Languages for which it works include: C++, Python,
Perl, Tcl, XML, JavaScript, CSS, IDL, TeX, Fortran, PHP, Java, Shell
scripts (Bash, CSH, etc.) and C#. Pepe is usable both as a
command line app and as a Python module.
"""

import imp
from setuptools import setup

pepe = imp.load_source('pepe', 'pepe.py')

classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python",
    "Operating System :: OS Independent",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: Text Processing :: Filters",    
]

doclines = __doc__.split("\n")

setup(
    name="pepe",
    version=pepe.__version__,
    maintainer="Yesudeep Mangalapilly",
    maintainer_email="yesudeep@gmail.com",
    url="http://github.com/gorakhargosh/pepe",
    license="MIT License",
    platforms=["any"],
    py_modules=["pepe"],
    entry_points={
        'console_scripts': [
            'pepe = pepe:main',
        ]
    },
    zip_safe=False,
    description=doclines[0],
    classifiers=classifiers,
    long_description="\n".join(doclines[2:]),
)
