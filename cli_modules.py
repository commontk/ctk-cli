# see https://github.com/commontk/CTK/blob/master/Libs/CommandLineModules/Core/Resources/ctkCmdLineModule.xsd
# for what we aim to be able to parse

import os, sys, glob, subprocess
import xml.etree.ElementTree as ET

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

ParameterNames = (
    'boolean',

    'integer',
    'float',
    'double',

    'string',
    'directory',

    'integer-vector',
    'float-vector',
    'double-vector',

    'string-vector',

    'integer-enumeration',
    'float-enumeration',
    'double-enumeration',
    'string-enumeration',

    'point',
    'region',

    'file',
    'image',
    'geometry',
              
    #'transform', 'table', 'measurement'
)

def _tagToIdentifier(tagName):
    return tagName.replace('-', '_')


class CLIModule(list):
    REQUIRED_ELEMENTS = ('title', 'description')

    OPTIONAL_ELEMENTS = ('category', 'version', 'documentation-url',
                         'license', 'contributor', 'acknowledgements')

    __slots__ = tuple(map(_tagToIdentifier, REQUIRED_ELEMENTS + OPTIONAL_ELEMENTS))

    def parse(self, elementTree):
        assert elementTree.tag == 'executable'

        for tagName in self.REQUIRED_ELEMENTS:
            tagValue = element.find(tagName).text.strip()
            setattr(self, _tagToIdentifier(tagName), tagValue)

        for tagName in self.REQUIRED_ELEMENTS:
            tagValue = element.find(tagName)
            if tagValue is not None:
                tagValue = tagValue.text.strip()
            setattr(self, _tagToIdentifier(tagName), tagValue)

        for pnode in elementTree.findall('parameters'):
            p = CLIParameters()
            p.parse(pnode)
            self.append(p)


class CLIParameters(list):
    REQUIRED_ELEMENTS = ('label', 'description')

    __slots__ = ("advanced", ) + REQUIRED_ELEMENTS

    def parse(self, elementTree):
        assert elementTree.tag == 'parameters'

        self.advanced = _parseBool(element.get('advanced', 'false'))

        for tagName in self.REQUIRED_ELEMENTS:
            tagValue = element.find(tagName).text.strip()
            setattr(self, _tagToIdentifier(tagName), tagValue)


class CLIParameter(object):
    __slots__ = ("name", "flag", "longflag",
                 "description", "label", "default",
                 "channel", "hidden",
                 "constraints", # scalarVectorType, scalarType
                 "multiple", # multipleType
                 "elements", # enumerationType
                 "coordinateSystem", # pointType
        )

