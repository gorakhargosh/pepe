# -*- coding: utf-8 -*-

import sys
import re
import os
import yaml


# * Ensure structure-text has NO comment-groups within this
#   test config.
# * Ensure foobar.f37993ajdha73 does not exist anywhere in this
#   test config.
test_content_types_yaml = """
version: 1.0

comment-groups:
  python:
  - ['#', '']
  xml:
  - ['<!--', '-->']
  - ['/*', '*/']
  - ['//', '']
  html:
  - ['<!--', '-->']
  - ['/*', '*/']
  - ['//', '']
  Makefile:
  - ['#', '']
  javascript:
  - ['/*', '*/']
  - ['//', '']
  text:
  - ['#', '']

content-types:
  javascript:
  - .js
  coffee-script:
  - .coffee
  - Cakefile
  xml:
  - .xhtml
  - .xml
  - .xsl
  - .xslt
  - .xul
  - .rdf
  - .wxi
  - .wxs
  - .kpf
  text:
  - .txt
  - .kkf
  structured-text:
  - .rst
  - .md
  - .markdown
  ruby:
  - .rb
  - Rakefile
  python:
  - .py
  - .pyw
  - .ksf
  - SConscript
  - SConstruct
  - wscript
  - wscript_build
  Makefile:
  - /^[Mm]akefile.*$/
"""

test_config = yaml.load(test_content_types_yaml)

extension_case_transform_func = (lambda w: w)
if sys.platform.startswith('win'):
    # We lower the pattern case on Windows to keep stuff case insensitive.
    def extension_case_transform_func(extension):
        return extension.lower()

class ContentTypesDatabase(object):
    """
    A class that handles determining the content type of a file path.
    """

    def __init__(self, config_file=None):
        self._extension_map = {}
        self._regexp_map = {}
        self._filename_map = {}
        self._content_types = {}
        self._comment_groups = {}
        self._test_config = test_config

        if config_file:
            self.add_config_file(config_file)

    def get_comment_group_for_path(self, pathname, default_content_type=None):
        """
        Obtains the comment group for a specified pathname.

        :param pathname:
            The path for which the comment group will be obtained.
        :return:
            Returns the comment group for the specified pathname
            or raises a ``ValueError`` if a content type is not found
            or raises a ``KeyError`` if a comment group is not found.

        Usage:
            >>> db = ContentTypesDatabase()
            >>> db.add_config(db._test_config, 'test_config.yaml')
            >>> g = db.get_comment_group_for_path
            >>> g("foobar.py")
            [['#', '']]
            >>> g("foobar.js")
            [['/*', '*/'], ['//', '']]

            >>> g('foobar.rst')
            Traceback (most recent call last):
                ...
            KeyError: 'No comment groups for content type `structured-text` for file `foobar.rst` found'

            # If the content type cannot be determined, we assume the content
            # type to be ``python`` in this case.
            >>> g('foobar.f37993ajdha73', default_content_type='python')
            [['#', '']]

            >>> g("foobar.f37993ajdha73")
            Traceback (most recent call last):
                ...
            ValueError: No content type defined for file path: foobar.f37993ajdha73
            >>> g("foobar.f37993ajdha73", default_content_type=None)
            Traceback (most recent call last):
                ...
            ValueError: No content type defined for file path: foobar.f37993ajdha73
            """
        content_type = self.guess_content_type(pathname)
        if not content_type:
            # Content type is not found.
            if default_content_type:
                content_type = default_content_type
                return self.get_comment_group(content_type)
            else:
                raise ValueError(
                    "No content type defined for file path: %s" % pathname)
        else:
            try:
                return self.get_comment_group(content_type)
            except KeyError:
                raise KeyError(
                    "No comment groups for content type `%s` for file `%s` found" % (
                    content_type, pathname))


    def get_comment_group(self, content_type):
        """
        Returns a comment group for the specified content type.

        :param content_type:
            The content type for which the comment group will be determined.
        :return:
            Comment group for the specified content type. Raises a ``KeyError``
            exception if a comment group for the specified content type
            is not found.

        Usage:
            >>> db = ContentTypesDatabase()
            >>> db.add_config(db._test_config, 'test_config.yaml')
            >>> g = db.get_comment_group
            >>> g("python")
            [['#', '']]
            >>> g("javascript")
            [['/*', '*/'], ['//', '']]
            >>> g("structured-text")
            Traceback (most recent call last):
            ...
            KeyError: 'No comment groups for content type `structured-text` found.'
        """
        try:
            return self._comment_groups[content_type]
        except KeyError:
            raise KeyError(
                "No comment groups for content type `%s` found." % content_type)


    def add_config_file(self, config_filename):
        """
        Parses the content.types file and updates the content types database.

        :param config_filename:
            The path to the configuration file.
        """
        with open(config_filename, 'rb') as f:
            content = f.read()
            config = yaml.load(content)
            self.add_config(config, config_filename)


    def add_config(self, config, config_filename):
        """
        Updates the content types database with the given configuration.

        :param config:
            The configuration dictionary.
        :param config_filename:
            The path of the configuration file.
        """
        content_types = config['content-types']
        comment_groups = config['comment-groups']

        self._comment_groups.update(comment_groups)
        self._content_types.update(content_types)

        for content_type, patterns in content_types.iteritems():
            if not patterns:
                raise ValueError('''error: config parse error: \
%s: Missing pattern for content type - `%s`"''' % (config_file, content_type))
            for pattern in patterns:
                first_character = pattern[0]
                last_character = pattern[-1]
                if first_character == '.':
                    # Extension map.
                    pattern = extension_case_transform_func(pattern)
                    self._extension_map[pattern] = content_type
                elif first_character == '/' and last_character == '/':
                    # Regular expression map.
                    self._regexp_map[re.compile(pattern[1:-1])] = content_type
                else:
                    # Filename map.
                    self._filename_map[pattern] = content_type


    def guess_content_type(self, pathname):
        """Guess the content type for the given path.

        :param path:
            The path of file for which to guess the content type.
        :return:
            Returns the content type or ``None`` if the content type
            could not be determined.

        Usage:
            >>> db = ContentTypesDatabase()
            >>> db.add_config_file('content-types.yaml')
            >>> g = db.guess_content_type
            >>> assert g("__init__.py") == "python"
            >>> assert g("Makefile") == "Makefile"
            >>> assert g("Makefile.gmake") == "Makefile"
            >>> assert g("Makefile.py") == "python"
            >>> assert g("foobar.rb") == "ruby"
            >>> assert g("wscript") == "python"
            >>> assert g("foo.coffee") == "coffee-script"
            >>> assert g("Rakefile") == "ruby"
            >>> assert g("foobar.xml") == "xml"
            >>> assert g("foobar.html") == "html"
            >>> assert g("foo7a738fg") == None
            >>> assert g("foo.rst") == "structured-text"
            >>> assert g("foo.md") == "structured-text"
            >>> assert g("foo.markdown") == "structured-text"
        """
        file_basename = os.path.basename(pathname)
        content_type = None

        # Try to determine from the path.
        if not content_type and self._filename_map.has_key(file_basename):
            content_type = self._filename_map[file_basename]
            #logger.debug("Content type of '%s' is '%s' (determined from full "\
            #             "path).", pathname, content_type)

        # Try to determine from the suffix.
        if not content_type and '.' in file_basename:
            extension = "." + file_basename.split(".")[-1]
            extension = extension_case_transform_func(extension)
            try:
                content_type = self._extension_map[extension]
                #logger.debug("Content type of '%s' is '%s' (determined from "\
                #             "suffix '%s').", pathname, content_type, extension)
            except KeyError:
                pass

        # Try to determine from the registered set of regular expression patterns.
        if not content_type:
            for regexp, _content_type in self._regexp_map.iteritems():
                if regexp.search(file_basename):
                    content_type = _content_type
                    #logger.debug(
                    #    "Content type of '%s' is '%s' (matches regexp '%s')",
                    #    pathname, content_type, regexp.pattern)
                    break

        # Try to determine from the file contents.
        if os.path.exists(pathname):
            with open(pathname, 'rb') as f:
                content = f.read()
                if content.startswith("<?xml"):  # cheap XML sniffing
                    content_type = "XML"

        # TODO: Try to determine from mime-type.

        return content_type


if __name__ == "__main__":
    import doctest

    doctest.testmod()
