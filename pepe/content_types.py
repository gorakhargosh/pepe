
import sys
import re
import os
import yaml


extension_case_transform_func = (lambda w: w)
if sys.platform.startswith('win'):
    # We lower the pattern case on Windows to keep stuff case insensitive.
    def extension_case_transform_func(extension):
        return extension.lower()


class ContentTypesDatabase(object):
    """A class that handles determining the file type of a given path.

    Usage:
        >>> db = ContentTypesDatabase()
        >>> assert db.guess_content_type("__init__.py") == "Python"
    """

    def __init__(self):
        self._extension_map = {}
        self._regexp_map = {}
        self._filename_map = {}
        self._content_types = {}
        self._comment_groups = {}


    def get_comment_group(self, content_type):
        """
        Returns a comment group for the specified content type.

        :param content_type:
            The content type for which the comment group will be determined.
        :return:
            Comment group for the specified content type.
        """
        return self._comment_groups[content_type]


    def add_config_file(self, config_filename):
        """
        Parses the content.types file and updates the content types database.

        :param config_filename:
            The path to the configuration file.
        """
        with open(config_filename, 'rb') as f:
            content = f.read()
            config = yaml.load(content)
            self._update_config(config, config_filename)


    def _update_config(self, config, config_filename):
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
        """
        file_basename = os.path.basename(pathname)
        content_type = None

        # Try to determine from the path.
        if not content_type and self._filename_map.has_key(file_basename):
            content_type = self._filename_map[file_basename]
            logger.debug("Content type of '%s' is '%s' (determined from full "\
                         "path).", pathname, content_type)

        # Try to determine from the suffix.
        if not content_type and '.' in file_basename:
            extension = "." + file_basename.split(".")[-1]
            extension = extension_case_transform_func(extension)
            try:
                content_type = self._extension_map[extension]
                logger.debug("Content type of '%s' is '%s' (determined from "\
                             "suffix '%s').", pathname, content_type, extension)
            except KeyError:
                pass

        # Try to determine from the registered set of regular expression patterns.
        if not content_type:
            for regexp, _content_type in self._regexp_map.iteritems():
                if regexp.search(file_basename):
                    content_type = _content_type
                    logger.debug(
                        "Content type of '%s' is '%s' (matches regexp '%s')",
                        pathname, content_type, regexp.pattern)
                    break

        # Try to determine from the file contents.
        with open(pathname, 'rb') as f:
            content = f.read()
            if content.startswith("<?xml"):  # cheap XML sniffing
                content_type = "XML"

        # TODO: Try to determine from mime-type.

        return content_type
