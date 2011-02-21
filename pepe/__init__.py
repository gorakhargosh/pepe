#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2002-2008 ActiveState Software Inc.
# Copyright (C) 2011 Yesudeep Mangalapilly <yesudeep@gmail.com>
# License: MIT License (http://www.opensource.org/licenses/mit-license.php)

"""\
Pepe: Portable multi-language preprocessor.

Module Usage:
    from pepe import preprocess
    preprocess(infile, outfile=sys.stdout, defines={}, force=0,
               keepLines=0, includePath=[], substitute=0,
               contentType=None)

The <infile> can be marked up with special preprocessor statement lines
of the form:
    <comment-prefix> <preprocessor-statement> <comment-suffix>
where the <comment-prefix/suffix> are the native comment delimiters for
that file type.


Examples
--------

HTML (*.htm, *.html) or XML (*.xml, *.kpf, *.xul) files:

    <!-- #if FOO -->
    ...
    <!-- #endif -->

Python (*.py), Perl (*.pl), Tcl (*.tcl), Ruby (*.rb), Bash (*.sh),
or make ([Mm]akefile*) files:

    # #if defined('FAV_COLOR') and FAV_COLOR == "blue"
    ...
    # #elif FAV_COLOR == "red"
    ...
    # #else
    ...
    # #endif

C (*.c, *.h), C++ (*.cpp, *.cxx, *.cc, *.h, *.hpp, *.hxx, *.hh),
Java (*.java), PHP (*.php) or C# (*.cs) files:

    // #define FAV_COLOR 'blue'
    ...
    /* #ifndef FAV_COLOR */
    ...
    // #endif

Fortran 77 (*.f) or 90/95 (*.f90) files:

    C     #if COEFF == 'var'
          ...
    C     #endif

And other languages.


Preprocessor Syntax
-------------------

- Valid statements:
    #define <var> [<value>]
    #undef <var>
    #ifdef <var>
    #ifndef <var>
    #if <expr>
    #elif <expr>
    #else
    #endif
    #error <error string>
    #include "<file>"
    #include <var>
  where <expr> is any valid Python expression.
- The expression after #if/elif may be a Python statement. It is an
  error to refer to a variable that has not been defined by a -D
  option or by an in-content #define.
- Special built-in methods for expressions:
    defined(varName)    Return true if given variable is defined.

"""
import logging

__version_info__ = (1, 1, 0)
__version__ = '.'.join(map(str, __version_info__))

import os
import sys
import types
import re
# We don't use cStringIO because it may have issues with writing UTF-8 encoded files.
# http://mail.python.org/pipermail/python-list/2007-June/1097078.html
from StringIO import StringIO
from pkg_resources import resource_filename
from pathtools.path import absolute_path

try:
    from pepe.content_types import ContentTypesDatabase
# TODO: Remove this later.
except ImportError:
    from content_types import ContentTypesDatabase


DEFAULT_CONTENT_TYPES_FILE = resource_filename(__name__, "content-types.yaml")

logger = logging.getLogger("pepe")

# TODO: Why is only one regexp prefixed with r''?
PREPROCESSOR_STATEMENT_REGEXP_PATTERNS = [
    '#\s*(?P<op>if|elif|ifdef|ifndef)\s+(?P<expr>.*?)',
    '#\s*(?P<op>else|endif)',
    '#\s*(?P<op>error)\s+(?P<error>.*?)',
    '#\s*(?P<op>define)\s+(?P<var>[^\s]*?)(\s+(?P<val>.+?))?',
    '#\s*(?P<op>undef)\s+(?P<var>[^\s]*?)',
    '#\s*(?P<op>include)\s+"(?P<fname>.*?)"',
    r'#\s*(?P<op>include)\s+(?P<var>[^\s]+?)',
]


class PreprocessorError(Exception):
    def __init__(self, error_message, filename=None, line_number=None,
                 line=None):
        self.error_message = error_message
        self.filename = filename
        self.line_number = line_number
        self.line = line
        Exception.__init__(self, error_message, filename, line_number, line)

    def __str__(self):
        """
        Usage:

            >>> assert str(PreprocessorError("whatever", filename="somefile.py", line_number=20, line="blahblah")) == "somefile.py:20: whatever"
            >>> assert str(PreprocessorError("whatever", line_number=20, line="blahblah")) == "20: whatever"
            >>> assert str(PreprocessorError("whatever", filename="somefile.py", line="blahblah")) == "somefile.py: whatever"
            >>> assert str(PreprocessorError("whatever", line="blahblah")) == "whatever"
        """
        s = ":".join([str(f) for f in [self.filename, self.line_number] if f])
        if s:
            s += ": "
        s += self.error_message
        return s


def _evaluate(expression, defines):
    """Evaluate the given expression string with the given context.

    .. WARNING:
        This runs eval() on a user string. This is unsafe.
    """
    #interpolated = _interpolate(s, defines)
    try:
        defined = {'defined': (lambda v: v in defines)}
        return_value = eval(expression, defined, defines)
    except Exception, ex:
        message = str(ex)
        if message.startswith("name '") and message.endswith("' is not defined"):
            # A common error (at least this is presumed:) is to have
            #   defined(FOO)   instead of   defined('FOO')
            # We should give a little insight into what might be wrong.
            # message == "name 'FOO' is not defined"
            #    -->  variable_name == "FOO"
            variable_name = message[len("name '"):-len("' is not defined")]
            if expression.find("defined(%s)" % variable_name) > -1:
                # "defined(FOO)" in expr instead of "defined('FOO')"
                message += ''' (perhaps you want `defined('%s')` instead of `defined(%s)`)''' % (variable_name, variable_name)
        elif message.startswith("invalid syntax"):
            message = "invalid syntax: `%s`" % expression
        raise PreprocessorError(message, defines['__FILE__'], defines['__LINE__'])

    logger.debug("evaluate %r -> %s (defines=%r)", expression, return_value, defines)
    return return_value


def get_statement_regexps(comment_groups):
    # Generate statement parsing regexes. Basic format:
    #       <comment-prefix> <preprocessor-stmt> <comment-suffix>
    #  Examples:
    #       <!-- #if foo -->
    #       ...
    #       <!-- #endif -->
    #
    #       # #if BAR
    #       ...
    #       # #else
    #       ...
    #       # #endif
    patterns = []
    for preprocessor_statement_regexp in PREPROCESSOR_STATEMENT_REGEXP_PATTERNS:
        # The comment group prefix and suffix can either be just a
        # string or a compiled regex.
        for cprefix, csuffix in comment_groups:
            if hasattr(cprefix, "pattern"):
                pattern = cprefix.pattern
            else:
                pattern = r"^\s*%s\s*" % re.escape(cprefix)
            pattern += preprocessor_statement_regexp
            if hasattr(csuffix, "pattern"):
                pattern += csuffix.pattern
            else:
                pattern += r"\s*%s\s*$" % re.escape(csuffix)
            patterns.append(pattern)
    statement_regexps = [re.compile(p) for p in patterns]
    return statement_regexps


def preprocess(input_file,
               output_file,
               defines=None,
               options=None,
               content_types_db=None,
               _preprocessed_files=None,
               _depth=0):
    """
    Preprocesses the specified file.

    :param input_filename:
        The input path.
    :param output_filename:
        The output file (NOT path).
    :param defines:
        a dictionary of defined variables that will be
        understood in preprocessor statements. Keys must be strings and,
        currently, only the truth value of any key's value matters.
    :param options:
        A ``Namespace`` of command-line options.
    :param content_types_db:
        is an instance of ``ContentTypesDatabase``.
    :param _preprocessed_files:
        (for internal use only) is used to ensure files
        are not recursively preprocessed.
    :param _depth:
        When the call reaches _depth == 0, the output file is actually
        written. For all internal recursive calls _depth == 1.
    :return:
        Modified dictionary of defines or raises ``PreprocessorError`` if
        an error occurred.
    """

    # Options that can later be turned into function parameters.
    include_paths = options.include_paths
    should_keep_lines = options.should_keep_lines
    should_substitute = options.should_substitute
    default_content_type = options.default_content_type
    input_filename = input_file.name

    defines = defines or {}

    # Ensure preprocessing isn't cyclic(?).
    _preprocessed_files = _preprocessed_files or []
    input_file_absolute_path = absolute_path(input_filename)
    if input_file_absolute_path in _preprocessed_files:
        raise PreprocessorError("detected recursive #include of '%s'"\
                                % input_filename)
    _preprocessed_files.append(input_file_absolute_path)

    # Determine the content type and comment info for the input file.
    comment_groups = content_types_db.get_comment_group_for_path(input_filename, default_content_type)
    statement_regexps = get_statement_regexps(comment_groups)

    # Process the input file.
    # (Would be helpful if I knew anything about lexing and parsing
    # simple grammars.)
    input_lines = input_file.readlines()
    if _depth == 0:
        # Only at recursion depth 0 is the temporary buffer created.
        temp_output_buffer = StringIO()
    else:
        # At deeper levels, the temporary buffer is the output file.
        temp_output_buffer = output_file

    defines['__FILE__'] = input_filename
    SKIP, EMIT = range(2) # states
    states = [(EMIT, # a state is (<emit-or-skip-lines-in-this-section>,
               0, #             <have-emitted-in-this-if-block>,
               0)]     #             <have-seen-'else'-in-this-if-block>)
    line_number = 0
    for line in input_lines:
        line_number += 1
        logger.debug("line %d: %r", line_number, line)
        defines['__LINE__'] = line_number

        # Is this line a preprocessor stmt line?
        #XXX Could probably speed this up by optimizing common case of
        #    line NOT being a preprocessor stmt line.
        for statement_regexp in statement_regexps:
            match = statement_regexp.match(line)
            if match:
                break
        else:
            match = None

        if match:
            op = match.group("op")
            logger.debug("%r stmt (states: %r)", op, states)
            if op == "define":
                if not (states and states[-1][0] == SKIP):
                    var, val = match.group("var", "val")
                    if val is None:
                        val = None
                    else:
                        try:
                            val = eval(val, {}, {})
                        except:
                            pass
                    defines[var] = val
            elif op == "undef":
                if not (states and states[-1][0] == SKIP):
                    var = match.group("var")
                    try:
                        del defines[var]
                    except KeyError:
                        pass
            elif op == "include":
                if not (states and states[-1][0] == SKIP):
                    if "var" in match.groupdict():
                        # This is the second include form: #include VAR
                        var = match.group("var")
                        f = defines[var]
                    else:
                        # This is the first include form: #include "path"
                        f = match.group("fname")

                    for d in [os.path.dirname(input_filename)] + include_paths:
                        fname = os.path.normpath(os.path.join(d, f))
                        if os.path.exists(fname):
                            break
                    else:
                        raise PreprocessorError(
                            "could not find #include'd file "\
                            "\"%s\" on include path: %r"\
                            % (f, include_paths))
                    with open(fname, 'rb') as f:
                        defines = preprocess(f,
                                             temp_output_buffer,
                                             defines=defines,
                                             options=options,
                                             content_types_db=content_types_db,
                                             _preprocessed_files=_preprocessed_files,
                                             _depth=1)
            elif op in ("if", "ifdef", "ifndef"):
                if op == "if":
                    expr = match.group("expr")
                elif op == "ifdef":
                    expr = "defined('%s')" % match.group("expr")
                elif op == "ifndef":
                    expr = "not defined('%s')" % match.group("expr")
                try:
                    if states and states[-1][0] == SKIP:
                        # Were are nested in a SKIP-portion of an if-block.
                        states.append((SKIP, 0, 0))
                    elif _evaluate(expr, defines):
                        states.append((EMIT, 1, 0))
                    else:
                        states.append((SKIP, 0, 0))
                except KeyError:
                    raise PreprocessorError("use of undefined variable in "\
                                            "#%s stmt" % op, defines['__FILE__']
                                            ,
                                            defines['__LINE__'], line)
            elif op == "elif":
                expr = match.group("expr")
                try:
                    if states[-1][2]: # already had #else in this if-block
                        raise PreprocessorError("illegal #elif after #else in "\
                                                "same #if block",
                                                defines['__FILE__'],
                                                defines['__LINE__'], line)
                    elif states[-1][1]: # if have emitted in this if-block
                        states[-1] = (SKIP, 1, 0)
                    elif states[:-1] and states[-2][0] == SKIP:
                        # Were are nested in a SKIP-portion of an if-block.
                        states[-1] = (SKIP, 0, 0)
                    elif _evaluate(expr, defines):
                        states[-1] = (EMIT, 1, 0)
                    else:
                        states[-1] = (SKIP, 0, 0)
                except IndexError:
                    raise PreprocessorError("#elif stmt without leading #if "\
                                            "stmt", defines['__FILE__'],
                                            defines['__LINE__'], line)
            elif op == "else":
                try:
                    if states[-1][2]: # already had #else in this if-block
                        raise PreprocessorError("illegal #else after #else in "\
                                                "same #if block",
                                                defines['__FILE__'],
                                                defines['__LINE__'], line)
                    elif states[-1][1]: # if have emitted in this if-block
                        states[-1] = (SKIP, 1, 1)
                    elif states[:-1] and states[-2][0] == SKIP:
                        # Were are nested in a SKIP-portion of an if-block.
                        states[-1] = (SKIP, 0, 1)
                    else:
                        states[-1] = (EMIT, 1, 1)
                except IndexError:
                    raise PreprocessorError("#else stmt without leading #if "\
                                            "stmt", defines['__FILE__'],
                                            defines['__LINE__'], line)
            elif op == "endif":
                try:
                    states.pop()
                except IndexError:
                    raise PreprocessorError("#endif stmt without leading #if"\
                                            "stmt", defines['__FILE__'],
                                            defines['__LINE__'], line)
            elif op == "error":
                if not (states and states[-1][0] == SKIP):
                    error = match.group("error")
                    raise PreprocessorError("#error: " + error,
                                            defines['__FILE__'],
                                            defines['__LINE__'], line)
            logger.debug("states: %r", states)
            if should_keep_lines:
                temp_output_buffer.write("\n")
        else:
            try:
                if states[-1][0] == EMIT:
                    logger.debug("emit line (%s)" % states[-1][1])
                    # Substitute all defines into line.
                    # XXX Should avoid recursive substitutions. But that
                    #     would be a pain right now.
                    sline = line
                    if should_substitute:
                        for name in reversed(sorted(defines, key=len)):
                            value = defines[name]
                            sline = sline.replace(name, str(value))
                    temp_output_buffer.write(sline)
                elif should_keep_lines:
                    logger.debug("keep blank line (%s)" % states[-1][1])
                    temp_output_buffer.write("\n")
                else:
                    logger.debug("skip line (%s)" % states[-1][1])
            except IndexError:
                raise PreprocessorError("superfluous #endif before this line",
                                        defines['__FILE__'],
                                        defines['__LINE__'])
    if len(states) > 1:
        raise PreprocessorError("unterminated #if block", defines['__FILE__'],
                                defines['__LINE__'])
    elif len(states) < 1:
        raise PreprocessorError("superfluous #endif on or before this line",
                                defines['__FILE__'], defines['__LINE__'])

    #if temp_output_buffer != output_file:
    #    temp_output_buffer.close()
    if _depth == 0:
        output_file.write(temp_output_buffer.getvalue())
        temp_output_buffer.close()

    return defines


def parse_int_token(token):
    """
    Parses a string to convert it to an integer based on the format used:

    :param token:
        The string to convert to an integer.
    :type token:
        ``str``
    :return:
        ``int`` or raises ``ValueError`` exception.

    Usage::

        >>> parse_int_token("0x40")
        64
        >>> parse_int_token("040")
        32
        >>> parse_int_token("40")
        40
        >>> parse_int_token("foobar")
        Traceback (most recent call last):
            ...
        ValueError: invalid literal for int() with base 10: 'foobar'
    """
    if token.startswith("0x") or token.startswith("0X"):
        return int(token, 16)
    elif token.startswith("0"):
        return int(token, 8)
    else:
        return int(token)


def parse_bool_token(token):
    """
    Parses a string token to convert it to its equivalent boolean value ignoring
    the case of the string token or leaves the token intact if it cannot.

    :param token:
        String to convert to ``True`` or ``False``.
    :type token:
        ``str``
    :return:
        ``True`` or ``False`` or the token itself if not converted.

    Usage::

        >>> parse_bool_token('FAlse')
        False
        >>> parse_bool_token('FalS')
        'FalS'
        >>> parse_bool_token('true')
        True
        >>> parse_bool_token('TRUE')
        True
    """
    return {'true': True, 'false': False}.get(token.lower(), token)


def parse_number_token(token):
    """
    Parses a number token to convert it to a float or int.
    Caveat: Float values like 2e-23 will not be parsed as numbers.

    :param token:
        String token to be converted.
    :type token:
        ``str``
    :return:
        ``float`` or ``int`` or raises a ``ValueError`` if a parse error
        occurred.

    Usage::

        >>> parse_number_token("0x40")
        64
        >>> parse_number_token("040")
        32
        >>> parse_number_token("40")
        40
        >>> parse_number_token("4.0")
        4.0
        >>> parse_number_token("2e-23")
        Traceback (most recent call last):
            ...
        ValueError: invalid literal for int() with base 10: '2e-23'
        >>> parse_number_token("foobar")
        Traceback (most recent call last):
            ...
        ValueError: invalid literal for int() with base 10: 'foobar'
    """
    return float(token) if '.' in token else parse_int_token(token)


def parse_definition_expr(expr, default_value=None):
    """
    Parses a definition expression and returns a key-value pair
    as a tuple.

    Each definition expression should be in one of these two formats:

        * <variable>=<value>
        * <variable>

    :param expr:
        String expression to be parsed.
    :param default_value:
        (Default None) When a definition is encountered that has no value, this
        will be used as its value.
    :return:
        A (define, value) tuple

        or raises a ``ValueError`` if an invalid
        definition expression is provided.

        or raises ``AttributeError`` if None is provided for ``expr``.

    Usage:

        >>> parse_definition_expr('DEBUG=1')
        ('DEBUG', 1)
        >>> parse_definition_expr('FOOBAR=0x40')
        ('FOOBAR', 64)
        >>> parse_definition_expr('FOOBAR=whatever')
        ('FOOBAR', 'whatever')
        >>> parse_definition_expr('FOOBAR=false')
        ('FOOBAR', False)
        >>> parse_definition_expr('FOOBAR=TRUE')
        ('FOOBAR', True)
        >>> parse_definition_expr('FOOBAR', default_value=None)
        ('FOOBAR', None)
        >>> parse_definition_expr('FOOBAR', default_value=1)
        ('FOOBAR', 1)
        >>> parse_definition_expr('FOOBAR=ah=3')
        ('FOOBAR', 'ah=3')
        >>> parse_definition_expr(' FOOBAR=ah=3 ')
        ('FOOBAR', 'ah=3 ')
        >>> parse_definition_expr(' FOOBAR =ah=3 ')
        ('FOOBAR', 'ah=3 ')
        >>> parse_definition_expr(' FOOBAR = ah=3 ')
        ('FOOBAR', ' ah=3 ')
        >>> parse_definition_expr(" ")
        Traceback (most recent call last):
            ...
        ValueError: Invalid definition symbol ` `
        >>> parse_definition_expr(None)
        Traceback (most recent call last):
            ...
        AttributeError: 'NoneType' object has no attribute 'split'
    """
    try:
        define, value = expr.split('=', 1)
        try:
            value = parse_number_token(value)
        except ValueError:
            value = parse_bool_token(value)
    except ValueError:
        if expr:
            define, value = expr, default_value
        else:
            raise ValueError("Invalid definition expression `%s`" % str(expr))
    d = define.strip()
    if d:
        return d, value
    else:
        raise ValueError("Invalid definition symbol `%s`" % str(define))


def parse_definitions(definitions):
    """
    Parses a list of macro definitions and returns a "symbol table"
    as a dictionary.

    :params definitions:
        A list of command line macro definitions.
        Each item in the list should be in one of these two formats:

            * <variable>=<value>
            * <variable>
    :return:
        ``dict`` as symbol table or raises an exception thrown by
        :func:``parse_definition_expr``.

    Usage::

        >>> parse_definitions(['DEBUG=1'])
        {'DEBUG': 1}
        >>> parse_definitions(['FOOBAR=0x40', 'DEBUG=false'])
        {'DEBUG': False, 'FOOBAR': 64}
        >>> parse_definitions(['FOOBAR=whatever'])
        {'FOOBAR': 'whatever'}
        >>> parse_definitions(['FOOBAR'])
        {'FOOBAR': None}
        >>> parse_definitions(['FOOBAR=ah=3'])
        {'FOOBAR': 'ah=3'}
        >>> parse_definitions(None)
        {}
        >>> parse_definitions([])
        {}
    """
    defines = {}
    if definitions:
        for definition in definitions:
            define, value = parse_definition_expr(definition,
                                                  default_value=None)
            defines[define] = value
    return defines


def parse_command_line():
    """
    Parses the command line and returns a ``Namespace`` object
    containing options and their values.

    :return:
        A ``Namespace`` object containing options and their values.
    """

    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument('-v',
                        '--version',
                        action='version',
                        version='%(prog)s ' + __version__,
                        help="Show version number and exit.")
    parser.add_argument('input_filename',
                        metavar='INPUT_FILE',
                        type=str,
                        help='Path of the input file to be preprocessed')
    parser.add_argument('-q',
                        '--quiet',
                        dest='should_be_quiet',
                        action='store_true',
                        default=False,
                        help="Disables verbose logging")
    parser.add_argument('-L',
                        '--log-level',
                        '--logging-level',
                        dest='logging_level',
                        choices=[
                            'DEBUG',
                            'INFO',
                            'WARNING',
                            'ERROR',
                            'CRITICAL',
                            'NONE',
                            ],
                        default='INFO',
                        help="Logging level.")
    parser.add_argument('-o',
                        '--output',
                        metavar="OUTPUT_FILE",
                        dest='output_filename',
                        default=None,
                        help='Output file name (default STDOUT)')
    parser.add_argument('-f',
                        '--force',
                        dest='should_force_overwrite',
                        action='store_true',
                        default=False,
                        help='Force overwrite existing output file.')
    parser.add_argument('-D',
                        '--define',
                        metavar="EXPR",
                        dest='definitions',
                        action='append',
                        help="""\
Define a variable for preprocessing. <define>
can simply be a variable name (in which case it
will be true) or it can be of the form
<var>=<val>. An attempt will be made to convert
<val> to an integer so -D 'FOO=0' will create a
false value.""")
    parser.add_argument('-I',
                        '--include',
                        metavar="DIR_PATH",
                        dest='include_paths',
                        action='append',
                        default=['.'],
                        help='Add a directory to the include path for #include directives.')
    parser.add_argument('-k',
                        '--keep-lines',
                        dest='should_keep_lines',
                        action='store_true',
                        default=False,
                        help='''\
Emit empty lines for preprocessor statement
lines and skipped output lines. This allows line
numbers to stay constant.''')
    parser.add_argument('-s',
                        '--substitute',
                        dest='should_substitute',
                        action='store_true',
                        default=False,
                        help='''\
Substitute #defines into emitted lines.
(Disabled by default to avoid polluting strings)''')
    parser.add_argument('--default-content-type',
                        metavar="CONTENT_TYPE",
                        dest='default_content_type',
                        default=None,
                        help='If the content type of the file cannot be determined this will be used. (Default: an error is raised)')
    parser.add_argument('-c',
                        '--content-types-path',
                        '--content-types-config',
                        metavar="PATH",
                        dest='content_types_config_files',
                        default=[],
                        action='append',
                        help="""\
Specify a path to a content.types file to assist
with file type determination. Use the -p or -P flags
to display content types as read by pepe.""")
    parser.add_argument('-p',
                        '--print-content-types',
                        dest='should_print_content_types',
                        action='store_true',
                        default=False,
                        help='Display content types and exit.')
    parser.add_argument('-P',
                        '--print-content-types-config',
                        dest='should_print_content_types_config',
                        action='store_true',
                        default=False,
                        help='Display content types configuration and exit.')
    return parser.parse_args()


class NullLoggingHandler(logging.Handler):
    """
    Attach this handler to your logger to disable all logging.
    """
    def emit(self, record):
        pass


def set_up_logging(logger, level, should_be_quiet):
    """
    Sets up logging for pepe.

    :param logger:
        The logger object to update.
    :param level:
        Logging level specified at command line.
    :param should_be_quiet:
        Boolean value for the -q option.
    :return:
        logging level ``int`` or None
    """
    LOGGING_LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
        'NONE': None,
    }

    logging_level = LOGGING_LEVELS.get(level)
    if should_be_quiet or logging_level is None:
        logging_handler = NullLoggingHandler()
    else:
        logger.setLevel(logging_level)
        logging_handler = logging.StreamHandler()
        logging_handler.setLevel(logging_level)
        logging_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s:%(name)s:%(levelname)s: %(message)s"
                )
            )

    logger.addHandler(logging_handler)
    return logging_level


def main():
    """
    Entry-point function.
    """
    args = parse_command_line()

    logging_level = set_up_logging(logger, args.logging_level, args.should_be_quiet)
    defines = parse_definitions(args.definitions)

    try:
        content_types_db = ContentTypesDatabase(DEFAULT_CONTENT_TYPES_FILE)
        for config_file in args.content_types_config_files:
            content_types_db.add_config_file(config_file)

        output_filename = args.output_filename

        with open(args.input_filename, 'rb') as input_file:
            if output_filename is None:
                # No output file specified. Will output to stdout.
                preprocess(input_file=input_file,
                           output_file=sys.stdout,
                           defines=defines,
                           options=args,
                           content_types_db=content_types_db)
            else:
                if os.path.exists(output_filename):
                    if args.should_force_overwrite:
                        # Overwrite existing file.
                        with open(output_filename, 'wb') as output_file:
                            preprocess(input_file=input_file,
                                       output_file=output_file,
                                       defines=defines,
                                       options=args,
                                       content_types_db=content_types_db)
                    else:
                        raise IOError("File `%s` exists - cannot overwrite. (Use -f to force overwrite.)" % args.output_filename)
                else:
                    # File doesn't exist and output file is provided, so write.
                    with open(output_filename, 'wb') as output_file:
                        preprocess(input_file=input_file,
                                   output_file=output_file,
                                   defines=defines,
                                   options=args,
                                   content_types_db=content_types_db)
    except PreprocessorError, ex:
        if logging_level == logging.DEBUG:
            import traceback
            traceback.print_exc(file=sys.stderr)
        else:
            sys.stderr.write("pepe: error: %s\n" % str(ex))
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
