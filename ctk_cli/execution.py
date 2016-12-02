import os, sys, glob, logging, subprocess, tempfile, re
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


def isCLIExecutable(filePath):
    """Test whether given `filePath` is an executable.  Does not really
    check whether the executable is a CLI (e.g. whether it supports
    --xml), but can be used to filter out non-executables within a
    directory with CLI modules.
    """
    # see qSlicerUtils::isCLIExecutable
    # e.g. https://github.com/Slicer/Slicer/blob/master/Base/QTCore/qSlicerUtils.cxx
    if not os.path.isfile(filePath):
        return False
    if sys.platform.startswith('win'):
        filePath = filePath.lower() # be case insensitive
        return filePath.endswith(".exe") or filePath.endswith(".bat")
    else:
        # differing from qSlicerUtils here, which does not check for executable bits
        # (this way we can differentiate between XML files saved with the same name
        # as the executables and the executables themselves)
        if not os.access(filePath, os.X_OK):
            return False
        return not '.' in os.path.basename(filePath)


def listCLIExecutables(baseDir):
    """Return list of paths to valid CLI executables within baseDir (non-recursively).
    This calls `isCLIExecutable()` on all files within `baseDir`."""
    return [path for path in glob.glob(os.path.join(os.path.normpath(baseDir), '*'))
            if isCLIExecutable(path)]


re_slicerSubPath = '(/Extensions-[0-9]*/.*)?/lib/Slicer-[0-9.]*/cli-modules/.*'
if sys.platform.startswith('win'):
    re_slicerSubPath = re_slicerSubPath.replace('/', r'[/\\]')
re_slicerSubPath = re.compile(re_slicerSubPath)

def popenCLIExecutable(command, **kwargs):
    """Wrapper around subprocess.Popen constructor that tries to
    detect Slicer CLI modules and launches them through the Slicer
    launcher in order to prevent potential DLL dependency issues.

    Any kwargs are passed on to subprocess.Popen().

    If you ever try to use this function to run a CLI, you might want to
    take a look at
    https://github.com/hmeine/MeVisLab-CLI/blob/master/Modules/Macros/CTK_CLI/CLIModuleBackend.py
    (in particular, the CLIExecution class.)
    Ideally, more of that code would be extracted and moved here, but
    I have not gotten around to doing that yet.
    """

    cliExecutable = command[0]

    # hack (at least, this does not scale to other module sources):
    # detect Slicer modules and run through wrapper script setting up
    # appropriate runtime environment
    ma = re_slicerSubPath.search(cliExecutable)
    if ma:
        wrapper = os.path.join(cliExecutable[:ma.start()], 'Slicer')
        if sys.platform.startswith('win'):
            wrapper += '.exe'
        if os.path.exists(wrapper):
            command = [wrapper, '--launcher-no-splash', '--launch'] + command

    return subprocess.Popen(command, **kwargs)


def getXMLDescription(cliExecutable, **kwargs):
    """Call given cliExecutable with --xml and return xml ElementTree
    representation of standard output.

    Any kwargs are passed on to subprocess.Popen() (via popenCLIExecutable())."""

    command = [cliExecutable, '--xml']
    
    stdout, stdoutFilename = tempfile.mkstemp('.stdout')
    stderr, stderrFilename = tempfile.mkstemp('.stderr')
    try:
        p = popenCLIExecutable(command, stdout = stdout, stderr = stderr, **kwargs)
        ec = p.wait()
        with file(stderrFilename) as f:
            for line in f:
                logger.warning('%s: %s' % (os.path.basename(cliExecutable), line[:-1]))
        if ec:
            raise RuntimeError("Calling %s failed (exit code %d)" % (cliExecutable, ec))
        with file(stdoutFilename) as f:
            return ET.parse(f)
    finally:
        os.close(stdout)
        os.close(stderr)
        os.unlink(stdoutFilename)
        os.unlink(stderrFilename)
