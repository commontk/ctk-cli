# see https://github.com/commontk/CTK/blob/master/Libs/CommandLineModules/Core/Resources/ctkCmdLineModule.xsd
# for what we aim to be able to parse

import os, sys, glob, subprocess, logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

def isCLIExecutable(filePath):
    # see qSlicerUtils::isCLIExecutable
    # e.g. https://github.com/Slicer/Slicer/blob/master/Base/QTCore/qSlicerUtils.cxx
    if not os.path.isfile(filePath):
        return False
    if sys.platform.startswith('win'):
        filePath = filePath.lower() # be case insensitive
        return filePath.endswith(".exe") or filePath.endswith(".bat")
    else:
        return not '.' in os.path.basename(filePath)

def listCLIExecutables(baseDir):
    return [path for path in glob.glob(os.path.join(baseDir, '*'))
            if isCLIExecutable(path)]

def getXMLDescription(cliExecutable):
    p = subprocess.Popen([cliExecutable, '--xml'], stdout = subprocess.PIPE)
    return ET.parse(p.stdout)

# --------------------------------------------------------------------

def _tagToIdentifier(tagName):
    return tagName.replace('-', '_')

def _parseBool(x):
    if x in ('true', 'True', '1'):
        return True
    if x in ('false', 'False', '0'):
        return False
    raise ValueError, "cannot convert %r to boolean" % (x, )


def _parseElements(self, elementTree, expectedTag = None):
    """Read REQUIRED_ELEMENTS and OPTIONAL_ELEMENTS and returns
    the rest of the children.  Every read child element's text
    value will be filled into an attribute of the same name,
    i.e. <description>Test</description> will lead to 'Test' being
    assigned to self.description.  Missing REQUIRED_ELEMENTS
    result in warnings."""

    if expectedTag is not None:
        assert elementTree.tag == expectedTag, 'expected <%s>, got <%s>' % (expectedTag, elementTree.tag)

    parsed = []

    for tagName in self.REQUIRED_ELEMENTS + self.OPTIONAL_ELEMENTS:
        tagValue = elementTree.find(tagName)
        if tagValue is not None:
            parsed.append(tagValue)
            tagValue = tagValue.text.strip() if tagValue.text else ""
        elif tagName in self.REQUIRED_ELEMENTS:
            logger.warning("Required element %r not found within %r" % (tagName, elementTree.tag))
        setattr(self, _tagToIdentifier(tagName), tagValue)

    return [tag for tag in elementTree if tag not in parsed]


class CLIModule(list):
    REQUIRED_ELEMENTS = ('title', 'description')

    OPTIONAL_ELEMENTS = ('category', 'version', 'documentation-url',
                         'license', 'contributor', 'acknowledgements')

    __slots__ = ('name', ) + tuple(map(_tagToIdentifier, REQUIRED_ELEMENTS + OPTIONAL_ELEMENTS))

    def __init__(self, name):
        self.name = name

    def parse(self, elementTree):
        childNodes = _parseElements(self, elementTree, 'executable')

        for pnode in childNodes:
            if pnode.tag == 'parameters':
                p = CLIParameters()
                p.parse(pnode)
                self.append(p)
            else:
                logger.warning("Element %r within %r not parsed" % (pnode.tag, elementTree.tag))


class CLIParameters(list):
    REQUIRED_ELEMENTS = ('label', 'description')
    OPTIONAL_ELEMENTS = ()

    __slots__ = ("advanced", ) + REQUIRED_ELEMENTS

    def parse(self, elementTree):
        childNodes = _parseElements(self, elementTree, 'parameters')
        
        self.advanced = _parseBool(elementTree.get('advanced', 'false'))

        for pnode in childNodes:
            p = CLIParameter()
            p.parse(pnode)
            self.append(p)


class CLIParameter(object):
    TYPES = (
        'boolean',
        'integer', 'float', 'double',
        'string', 'directory',
        'integer-vector', 'float-vector', 'double-vector',
        'string-vector',
        'integer-enumeration', 'float-enumeration', 'double-enumeration', 'string-enumeration',
        'point', 'region',
        'file', 'image', 'geometry',
        'transform', 'table', 'measurement',
    )

    REQUIRED_ELEMENTS = ('name', 'description', 'label')

    OPTIONAL_ELEMENTS = (# either 'flag' or 'longflag' (or both) or 'index' are required
                         'flag', 'longflag', 'index',
                         'default', 'channel')
    
    __slots__ = ("typ", "hidden") + REQUIRED_ELEMENTS + OPTIONAL_ELEMENTS + (
                 "constraints", # scalarVectorType, scalarType
                 "multiple", # multipleType
                 "elements", # enumerationType
                 "coordinateSystem", # pointType
        )

    def parse(self, elementTree):
        assert elementTree.tag in self.TYPES, elementTree.tag

        childNodes = _parseElements(self, elementTree)
        for n in childNodes:
            logger.warning("Element %r within %r not parsed" % (n.tag, elementTree.tag))

        self.hidden = _parseBool(elementTree.get('hidden', 'false'))


