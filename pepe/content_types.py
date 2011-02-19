

class ContentTypesDatabase(object):
    """A class that handles determining the file type of a given path.

    Usage:
        >>> registry = ContentTypesRegistry()
        >>> assert registry.get_content_type("__init__.py") == "Python"
    """

    def __init__(self, content_types_config_files=None):
        self.content_types_config_files = content_types_config_files or []
        self._load()

    def _load(self):
        from os.path import dirname, join, exists

        self.suffixMap = {}
        self.regexMap = {}
        self.filenameMap = {}

        self._loadContentType(DEFAULT_CONTENT_TYPES)
        localContentTypesPath = join(dirname(__file__), "content.types")
        if exists(localContentTypesPath):
            logger.debug("load content types file: `%r'" % localContentTypesPath)
            self._loadContentType(open(localContentTypesPath, 'r').read())
        for path in self.content_types_config_files:
            logger.debug("load content types file: `%r'" % path)
            self._loadContentType(open(path, 'r').read())

    def _loadContentType(self, content, path=None):
        """Return the registry for the given content.types file.

        The registry is three mappings:
            <suffix> -> <content type>
            <regex> -> <content type>
            <filename> -> <content type>
        """
        for line in content.splitlines(0):
            words = line.strip().split()
            for i in range(len(words)):
                if words[i][0] == '#':
                    del words[i:]
                    break
            if not words: continue
            contentType, patterns = words[0], words[1:]
            if not patterns:
                if line[-1] == '\n': line = line[:-1]
                raise PreprocessorError("bogus content.types line, there must "\
                                        "be one or more patterns: '%s'" % line)
            for pattern in patterns:
                if pattern.startswith('.'):
                    if sys.platform.startswith("win"):
                        # Suffix patterns are case-insensitive on Windows.
                        pattern = pattern.lower()
                    self.suffixMap[pattern] = contentType
                elif pattern.startswith('/') and pattern.endswith('/'):
                    self.regexMap[re.compile(pattern[1:-1])] = contentType
                else:
                    self.filenameMap[pattern] = contentType

    def get_content_type(self, path):
        """Return a content type for the given path.

        @param path {str} The path of file for which to guess the
            content type.
        @returns {str|None} Returns None if could not determine the
            content type.
        """
        basename = os.path.basename(path)
        contentType = None
        # Try to determine from the path.
        if not contentType and self.filenameMap.has_key(basename):
            contentType = self.filenameMap[basename]
            logger.debug("Content type of '%s' is '%s' (determined from full "\
                      "path).", path, contentType)
            # Try to determine from the suffix.
        if not contentType and '.' in basename:
            suffix = "." + basename.split(".")[-1]
            if sys.platform.startswith("win"):
                # Suffix patterns are case-insensitive on Windows.
                suffix = suffix.lower()
            if self.suffixMap.has_key(suffix):
                contentType = self.suffixMap[suffix]
                logger.debug("Content type of '%s' is '%s' (determined from "\
                          "suffix '%s').", path, contentType, suffix)
                # Try to determine from the registered set of regex patterns.
        if not contentType:
            for regex, ctype in self.regexMap.items():
                if regex.search(basename):
                    contentType = ctype
                    logger.debug(
                        "Content type of '%s' is '%s' (matches regex '%s')",
                        path, contentType, regex.pattern)
                    break
                    # Try to determine from the file contents.
        content = open(path, 'rb').read()
        if content.startswith("<?xml"):  # cheap XML sniffing
            contentType = "XML"
        return contentType
