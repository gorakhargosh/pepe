# -*- coding: utf-8 -*-

import re

# Comment delimiter info.
#   A mapping of content type to a list of 2-tuples defining the line
#   prefix and suffix for a comment. Each prefix or suffix can either
#   be a string (in which case it is transformed into a pattern allowing
#   whitespace on either side) or a compiled regex.
COMMENT_GROUPS = {
    "Python": [('#', '')],
    "Perl": [('#', '')],
    "PHP": [('/*', '*/'), ('//', ''), ('#', '')],
    "Ruby": [('#', '')],
    "Tcl": [('#', '')],
    "Shell": [('#', '')],
    # Allowing for CSS and JavaScript comments in XML/HTML.
    "XML": [('<!--', '-->'), ('/*', '*/'), ('//', '')],
    "HTML": [('<!--', '-->'), ('/*', '*/'), ('//', '')],
    "Makefile": [('#', '')],
    "JavaScript": [('/*', '*/'), ('//', '')],
    "CSS": [('/*', '*/')],
    "C": [('/*', '*/')],
    "C++": [('/*', '*/'), ('//', '')],
    "Java": [('/*', '*/'), ('//', '')],
    "C#": [('/*', '*/'), ('//', '')],
    "IDL": [('/*', '*/'), ('//', '')],
    "Text": [('#', '')],
    "Fortran": [(re.compile(r'^[a-zA-Z*$]\s*'), ''), ('!', '')],
    "TeX": [('%', '')],
}
