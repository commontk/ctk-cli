# see https://github.com/commontk/CTK/blob/master/Libs/CommandLineModules/Core/Resources/ctkCmdLineModule.xsd
# for what we aim to be able to parse

import os, logging
import xml.etree.ElementTree as ET
from .execution import isCLIExecutable, getXMLDescription

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------

def _tagToIdentifier(tagName):
    return tagName.replace('-', '_')

def _parseBool(x):
    if x in ('true', 'True', '1'):
        return True
    if x in ('false', 'False', '0'):
        return False
    raise ValueError("cannot convert %r to boolean" % (x, ))

def _tag(element):
    """Return element.tag with xmlns stripped away."""
    tag = element.tag
    if tag[0] == "{":
        uri, tag = tag[1:].split("}")
    return tag

def _uriPrefix(element):
    """Return xmlns prefix of the given element."""
    i = element.tag.find('}')
    if i < 0:
        return ""
    return element.tag[:i+1]


def _parseElements(self, elementTree, expectedTag = None):
    """Read REQUIRED_ELEMENTS and OPTIONAL_ELEMENTS and returns
    the rest of the children.  Every read child element's text
    value will be filled into an attribute of the same name,
    i.e. <description>Test</description> will lead to 'Test' being
    assigned to self.description.  Missing REQUIRED_ELEMENTS
    result in warnings."""

    xmlns = _uriPrefix(elementTree)

    if expectedTag is not None:
        assert _tag(elementTree) == expectedTag, 'expected <%s>, got <%s>' % (expectedTag, _tag(elementTree))

    parsed = []

    for tagName in self.REQUIRED_ELEMENTS + self.OPTIONAL_ELEMENTS:
        tags = elementTree.findall(xmlns + tagName)
        if tags:
            parsed.extend(tags)
            tagValue = tags[0].text
            tagValue = tagValue.strip() if tagValue else ""
            if len(tags) > 1:
                logger.warning("More than one <%s> found within %r (using only first)" % (tagName, _tag(elementTree)))
        else:
            tagValue = None
            if tagName in self.REQUIRED_ELEMENTS:
                logger.warning("Required element %r not found within %r" % (tagName, _tag(elementTree)))
        setattr(self, _tagToIdentifier(tagName), tagValue)

    return [tag for tag in elementTree if tag not in parsed]


class CLIModule(list):
    REQUIRED_ELEMENTS = ('title', 'description')

    OPTIONAL_ELEMENTS = ('category', 'index', 'version', 'documentation-url',
                         'license', 'contributor', 'acknowledgements')

    __slots__ = ('path', ) + tuple(map(_tagToIdentifier, REQUIRED_ELEMENTS + OPTIONAL_ELEMENTS))

    def __init__(self, path = None, env = None, stream = None):
        """
        Parse a CLI specification from an XML document. This class can be
        instantiated in three different modes:

        1. Pass the ``path`` parameter that points to a CLI executable. This
           mode will run the executable in a subprocess, passing "--xml"
           and parsing the output.
        2. Pass the ``path`` parameter representing the path to an XML
           file on disk that contains the CLI description.
        3. Pass a file-like object in the ``stream`` kwarg that contains
           the XML document to be parsed.

        :param path: The path on the filesystem of either the CLI to
            be interrogated, or a CLI XML description document.
        :param env: If using mode 1 described above, setting this parameter
            causes "env=<value>" to be passed as an additional command line argument
            when invoking the subprocess to describe the CLI.
        :param stream: An open file-like object that will stream the CLI
            XML description document.
        """
        self.path = path

        if path and isCLIExecutable(path):
            elementTree = getXMLDescription(path, env = env)
        elif path:
            with file(path) as f:
                elementTree = ET.parse(f)
        elif stream is not None:
            elementTree = ET.parse(stream)
        else:
            raise RuntimeError('You must pass either a path or stream when instantiating CLIModule.')

        self._parse(elementTree.getroot())

    def __repr__(self):
        return '<CLIModule %r>' % (self.name, )

    @property
    def name(self):
        if self.path is None:
            return None

        result = os.path.basename(self.path)
        base, ext = os.path.splitext(result)
        if ext in ('.exe', '.xml', '.py'):
            result = base
        return result

    def parameters(self):
        """Generator that recursively enumerates all parameters from
        all parameter groups"""
        for parameters in self:
            for parameter in parameters:
                yield parameter

    def classifyParameters(self):
        """Return (arguments, options, outputs) tuple.  Together, the
        three lists contain all parameters (recursively fetched from
        all parameter groups), classified into optional parameters,
        required ones (with an index), and simple output parameters
        (that would get written to a file using
        --returnparameterfile).  `arguments` contains the required
        arguments, already sorted by index."""

        arguments = []
        options = []
        outputs = []
        for parameter in self.parameters():
            if parameter.channel == 'output' and not parameter.isExternalType():
                outputs.append(parameter)
            elif parameter.index is not None:
                arguments.append(parameter)
                if parameter.flag is not None or parameter.longflag is not None:
                    logger.warning("Parameter '%s' has both index=%d and flag set." % (
                        parameter.identifier(), parameter.index))
            elif parameter.flag or parameter.longflag:
                options.append(parameter)
            else:
                logger.warning("Parameter '%s' cannot be passed (missing flag, longflag, or index)!" % parameter.name)
        arguments.sort(key = lambda parameter: parameter.index)
        return (arguments, options, outputs)

    # this is called _parse, not parse (like in the classes below),
    # because it is not a classmethod that is supposed to be used as a
    # factory method from the outside, even if the signature and
    # content is really similar:
    def _parse(self, elementTree):
        childNodes = _parseElements(self, elementTree, 'executable')

        for pnode in childNodes:
            if _tag(pnode) == 'parameters':
                self.append(CLIParameters.parse(pnode))
            else:
                logger.warning("Element %r within %r not parsed" % (_tag(pnode), _tag(elementTree)))


class CLIParameters(list):
    REQUIRED_ELEMENTS = ('label', 'description')
    OPTIONAL_ELEMENTS = ()

    __slots__ = ("advanced", ) + REQUIRED_ELEMENTS

    @classmethod
    def parse(cls, elementTree):
        self = cls()

        childNodes = _parseElements(self, elementTree, 'parameters')

        self.advanced = _parseBool(elementTree.get('advanced', 'false'))

        for pnode in childNodes:
            self.append(CLIParameter.parse(pnode))

        return self

    def __repr__(self):
        return '<CLIParameters %r%s>' % (self.label, ' (advanced)' if self.advanced else '')


class CLIParameter(object):
    VALUE_TYPES = (
        'boolean',
        'integer', 'float', 'double',
        'string', 'directory',
        'integer-vector', 'float-vector', 'double-vector',
        'string-vector',
        'integer-enumeration', 'float-enumeration', 'double-enumeration',
        'string-enumeration',
        'point', 'region',
        'file',
    )

    # parameter types which are passed through temporary files (with default extensions)
    EXTERNAL_TYPES = {
        'image'       : '.nrrd',
        'geometry'    : '.vtp',
        'pointfile'   : '.fcsv',
        'transform'   : '.mrml',
        'table'       : '.ctbl', # (CSV format)
        'measurement' : '.csv',
    }

    TYPES = VALUE_TYPES + tuple(EXTERNAL_TYPES)

    PYTHON_TYPE_MAPPING = {
        'boolean' : bool,
        'integer' : int,
        'float' : float,
        'double' : float,
        'string' : str
    }

    REQUIRED_ELEMENTS = ('name', 'description', 'label')

    OPTIONAL_ELEMENTS = (# either 'index' or at least one of 'flag' or 'longflag' is required
                         'flag', 'longflag', 'index',
                         'default', 'channel')

    __slots__ = ("typ", "hidden", "_pythonType") + REQUIRED_ELEMENTS + OPTIONAL_ELEMENTS + (
                 "constraints", # scalarVectorType, scalarType
                 "multiple", # multipleType
                 "elements", # enumerationType
                 "coordinateSystem", # pointType, pointFileType
                 "fileExtensions", # fileType
                 "reference", # imageType, transformType, geometryType, tableType
                 "subtype", # 'type' of imageType / geometryType
        )

    def __str__(self):
        return "%s parameter '%s'" % (self.typ, self.identifier())

    def __repr__(self):
        return '<CLIParameter %r of type %s>' % (self.identifier(), self.typ)

    def identifier(self):
        result = self.name if self.name else self.longflag.lstrip('-')
        if not result:
            raise RuntimeError("Cannot identify parameter either by name or by longflag (both missing)")
        return result

    def parseValue(self, value):
        """Parse the given value and return result."""
        if self.isVector():
            return map(self._pythonType, value.split(','))
        if self.typ == 'boolean':
            return _parseBool(value)
        return self._pythonType(value)

    def isOptional(self):
        return self.index is None

    def isVector(self):
        """Return whether this is a vector-like type with multiple
        elements of a numeric or string type.  This includes the
        xxx-vector types as well as point (fixed 3D) and region (fixed
        6D).  For these, the value will be a sequence of the
        corresponding python type."""
        return self.isNumericVector() or self.typ == 'string-vector'

    def isNumericVector(self):
        """Return whether this is a vector-like type with multiple
        elements of a numeric type.  This includes the numeric
        xxx-vector types as well as point (fixed 3D) and region (fixed
        6D).  For these, the value will be a sequence of the
        corresponding python type."""
        return (self.typ.endswith('-vector') and self.typ != 'string-vector') or self.typ in ('point', 'region')

    def isExternalType(self):
        """Return True iff values of this type are file paths"""
        return (self.typ in self.EXTERNAL_TYPES or
                self.typ in ['file', 'directory'])

    def defaultExtension(self):
        """Return default extension for this parameter type, checked
        against supported fileExtensions.  If the default extension is
        not within `fileExtensions`, return the first supported
        extension."""
        result = self.EXTERNAL_TYPES[self.typ]
        if not self.fileExtensions:
            return result
        if result in self.fileExtensions:
            return result
        return self.fileExtensions[0]

    @classmethod
    def parse(cls, elementTree):
        assert _tag(elementTree) in cls.TYPES, "%s not in CLIParameter.TYPES" % _tag(elementTree)

        self = cls()
        self.typ = _tag(elementTree)

        if self.typ in ('point', 'region'):
            self._pythonType = float
        else:
            elementType = self.typ
            if elementType.endswith('-vector'):
                elementType = elementType[:-7]
            elif elementType.endswith('-enumeration'):
                elementType = elementType[:-12]
            self._pythonType = self.PYTHON_TYPE_MAPPING.get(elementType, str)

        self.hidden = _parseBool(elementTree.get('hidden', 'false'))

        self.constraints = None
        self.multiple = None
        self.elements = None
        self.coordinateSystem = None
        self.fileExtensions = None
        self.reference = None
        self.subtype = None

        for key, value in elementTree.items():
            if key == 'multiple':
                self.multiple = _parseBool(value)
            elif key == 'coordinateSystem' and self.typ in ('point', 'pointfile'):
                self.coordinateSystem = value
            elif key == 'fileExtensions':
                self.fileExtensions = [ext.strip() for ext in value.split(",")]
            elif key == 'reference' and self.typ in ('image', 'transform', 'geometry', 'table'):
                self.reference = value
                logger.warning("'reference' attribute of %r is not part of the spec yet (CTK issue #623)" % (_tag(elementTree), ))
            elif key == 'type':
                self.subtype = value
            elif key != 'hidden':
                logger.warning('attribute of %r ignored: %s=%r' % (_tag(elementTree), key, value))

        elements = []

        childNodes = _parseElements(self, elementTree)
        for n in childNodes:
            if _tag(n) == 'constraints':
                self.constraints = CLIConstraints.parse(n)
            elif _tag(n) == 'element':
                if not n.text:
                    logger.warning("Ignoring empty <element> within <%s>" % (_tag(elementTree), ))
                else:
                    elements.append(n.text)
            else:
                logger.warning("Element %r within %r not parsed" % (_tag(n), _tag(elementTree)))

        if not self.flag and not self.longflag and self.index is None:
            logger.warning("Parameter %s cannot be passed (missing one of flag, longflag, or index)!" % (
                self.identifier(), ))

        if self.flag and not self.flag.startswith('-'):
            self.flag = '-' + self.flag
        if self.longflag and not self.longflag.startswith('-'):
            self.longflag = '--' + self.longflag

        if self.index is not None:
            self.index = int(self.index)

        if self.default:
            try:
                self.default = self.parseValue(self.default)
            except ValueError as e:
                logger.warning('Could not parse default value of <%s> (%s): %s' % (
                    _tag(elementTree), self.name, e))

        if self.typ.endswith('-enumeration'):
            try:
                self.elements = map(self.parseValue, elements)
            except ValueError as e:
                logger.warning('Problem parsing enumeration element values of <%s> (%s): %s' % (
                    _tag(elementTree), self.name, e))
            if not elements:
                logger.warning("No <element>s found within <%s>" % (_tag(elementTree), ))
        else:
            self.elements = None
            if elements:
                logger.warning("Ignoring <element>s within <%s>" % (_tag(elementTree), ))

        return self


class CLIConstraints(object):
    REQUIRED_ELEMENTS = ('step', )

    OPTIONAL_ELEMENTS = ('minimum', 'maximum')

    __slots__ = REQUIRED_ELEMENTS + OPTIONAL_ELEMENTS

    @classmethod
    def parse(cls, elementTree):
        self = cls()
        childNodes = _parseElements(self, elementTree, 'constraints')
        for n in childNodes:
            logger.warning("Element %r within %r not parsed" % (_tag(n), _tag(elementTree)))

        return self
