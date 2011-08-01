# #ifdef FOO

def foo(message, filename=None, line_number=None):
    s = ""
    if filename is not None:
        s += filename + ":"
    if line_number is not None:
        s += str(line_number) + ":"
    if filename is not None or line_number is not None:
        s += " "
    s += message
    return s

# #endif

# #include "foo.txt"

def bar(message, filename=None, line_number=None):
    s = ":".join([str(f) for f in [filename, line_number] if f])
    if s:
        s += ": "
    s += message
    return s



names = """\
filename.py
filename.pyw
filename.pl
filename.rb
filename.tcl
filename.xml
filename.kpf
filename.xul
filename.rdf
filename.xslt
filename.xsl
filename.wxs
filename.wxi
filename.htm
filename.html
filename.xhtml
filename.php
filename.js
filename.css
filename.c
filename.cpp
filename.cxx
filename.cc
filename.h
filename.hpp
filename.hxx
filename.hh
filename.idl
filename.txt
filename.f
filename.f90
filename.sh
filename.csh
filename.ksh
filename.zsh
filename.java
filename.cs
filename.tex
filename.ksf
filename.kkf
"""

import mimetypes
import yaml

d = {}

for name in names.splitlines():
    type = mimetypes.guess_type(name)[0]
    try:
        extension = "\"." + str(name.split('.')[1]) + "\""
    except Exception:
        continue
    if type in d:
        d[type].append(extension)
    else:
        d[type] = [extension]

print(yaml.dump(d))
