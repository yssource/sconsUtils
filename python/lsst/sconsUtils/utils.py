##
#  @file utils.py
#
#  Internal utilities for sconsUtils.
##

import os
import sys
import warnings
import subprocess
import platform
import SCons.Script


##
#  @brief A dead-simple logger for all messages.
#
#  This simply centralizes decisions about whether to throw exceptions or print user-friendly messages
#  (the traceback variable) and whether to print extra debug info (the verbose variable).
#  These are set from command-line options in state.py.
##
class Log:

    def __init__(self):
        self.traceback = False
        self.verbose = True

    def info(self, message):
        if self.verbose:
            print(message)

    def warn(self, message):
        if self.traceback:
            warnings.warn(message, stacklevel=2)
        else:
            print(message, file=sys.stderr)

    def fail(self, message):
        if self.traceback:
            raise RuntimeError(message)
        else:
            if message:
                print(message, file=sys.stderr)
            SCons.Script.Exit(1)

    def flush(self):
        sys.stderr.flush()


##
#  @brief Internal function indicating that the OS has System
#  Integrity Protection.
##
def _has_OSX_SIP():
    hasSIP = False
    os_platform = SCons.Platform.platform_default()
    # SIP is enabled on OS X >=10.11 equivalent to darwin >= 15
    if os_platform == 'darwin':
        release_str = platform.release()
        release_major = int(release_str.split('.')[0])
        if release_major >= 15:
            hasSIP = True
    return hasSIP


##
#  @brief Returns name of library path environment variable to be passed through
#  or else returns None if no pass through is required on this platform.
##
def libraryPathPassThrough():
    if _has_OSX_SIP():
        return "DYLD_LIBRARY_PATH"
    return None


# Cache variable for whichPython() function
_pythonPath = None


##
#  @brief Returns the full path to the Python executable as determined
#  from the PATH. Does not return the full path of the Python running
#  SCons. Caches result and assumes the PATH does not change between
#  calls. Runs the "python" command and asks where it is rather than
#  scanning the PATH.
##
def whichPython():
    global _pythonPath
    if _pythonPath is None:
        _pythonPath = runExternal(["python", "-c", "import sys; print(sys.executable)"],
                                  fatal=True, msg="Error getting python path")
    return _pythonPath


##
#  @brief Returns True if the shebang lines of executables should be rewritten
##
def needShebangRewrite():
    return _has_OSX_SIP()


##
#  @brief Returns library loader path environment string to be prepended to external commands
#         Will be "" if nothing is required.
#
# If we have an OS X with System Integrity Protection enabled or similar
# we need to pass through both DYLD_LIBRARY_PATH and LSST_LIBRARY_PATH
# to the external command.
# DYLD_LIBRARY_PATH for Python code
# LSST_LIBRARY_PATH for shell scripts
#
# If both are already defined then pass them each through
# If only one is defined, then set both to the defined env variable
# If neither is defined then pass through nothing.
##
def libraryLoaderEnvironment():
    libpathstr = ""
    lib_pass_through_var = libraryPathPassThrough()
    aux_pass_through_var = "LSST_LIBRARY_PATH"
    if lib_pass_through_var is not None:
        for varname in (lib_pass_through_var, aux_pass_through_var):
            if varname in os.environ:
                libpathstr += '{}="{}" '.format(varname, os.environ[varname])

        if aux_pass_through_var in os.environ and \
           lib_pass_through_var not in os.environ:
                libpathstr += '{}="{}" '.format(lib_pass_through_var, os.environ[aux_pass_through_var])

        if lib_pass_through_var in os.environ and \
           aux_pass_through_var not in os.environ:
                libpathstr += '{}="{}" '.format(aux_pass_through_var, os.environ[lib_pass_through_var])

    return libpathstr


##
#  @brief Safe wrapper for running external programs, reading stdout, and sanitizing error messages.
#
#  Command can be given as a list/tuple of command with separate options.
#
#  Note that the entire program output is returned, not just a single line.
#  @returns Strings not bytes.
##
def runExternal(cmd, fatal=False, msg=None):
    if msg is None:
        try:
            msg = "Error running %s" % cmd.split()[0]
        except Exception:
            msg = "Error running external command"

    # Run with shell unless given a list of options
    shell = True
    if isinstance(cmd, (list, tuple)):
        shell = False

    try:
        retval = subprocess.run(cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=True)
    except subprocess.CalledProcessError as e:
        if fatal:
            raise RuntimeError(f"{msg}: {e.stderr.decode()}") from e
        else:
            from . import state  # can't import at module scope due to circular dependency
            state.log.warn(f"{msg}: {e.stderr}")
    return retval.stdout.decode().strip()


##
#  @brief A Python decorator that injects functions into a class.
#
#  For example:
#  @code
#  class test_class:
#      pass
#
#  @memberOf(test_class):
#  def test_method(self):
#      print "test_method!"
#  @endcode
#  ...will cause test_method to appear as as if it were defined within test_class.
#
#  The function or method will still be added to the module scope as well, replacing any
#  existing module-scope function with that name; this appears to be unavoidable.
##
def memberOf(cls, name=None):
    if isinstance(cls, type):
        classes = (cls,)
    else:
        classes = tuple(cls)
    kw = {"name": name}

    def nested(member):
        if kw["name"] is None:
            kw["name"] = member.__name__
        for scope in classes:
            setattr(scope, kw["name"], member)
        return member
    return nested
