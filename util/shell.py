import shlex
from subprocess import Popen, PIPE, CalledProcessError
import sys


def run_command(command):
    """Run 'command' (shell command string) as a subprocess. Return stdin of
    the subprocess (file), stdout of the subprocess (file), and function that
    raises a CalledProcessError if the process exited with non-0 status.
    stderr of the subprocess is redirected to this script's stderr.
    :param command: shell command string
    """
    process = Popen(shlex.split(command), stdin=PIPE, stdout=PIPE,
                    stderr=sys.stderr)
    def check_exit_status():
        status = process.wait()
        if status != 0:
            raise CalledProcessError(status, command)
    return process.stdin, process.stdout, check_exit_status

def run_command_in_shell(command):
    # launch bash as a subprocess in "login shell" mode so it reads
    # ~/.bash_profile etc. in order to include any modifications to the PATH
    # in those files. then write the command into its stdin.
    process = Popen(['/bin/bash', '--login'], stdin=PIPE, stdout=PIPE,
                    stderr=sys.stderr)
    process.communicate(input=command)

    # TODO duplicate code
    def check_exit_status():
        status = process.wait()
        if status != 0:
            raise CalledProcessError(status, command)
    return process.stdin, process.stdout, check_exit_status

def shell_quote(s):
    return "'" + s.replace("'", "'\\''") + "'"