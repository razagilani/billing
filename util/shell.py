"""Shell- and subprocess-related utilities."""
import shlex
import sys
from subprocess import Popen, PIPE, CalledProcessError


def _get_check_exit_status(command, process):
    """
    Helper function used by run_command and run_command_in_shell below.
    :param command: shell command string
    :param process: Popen object representing a subprocess
    :return: a function that raises a CalledProcessError if the process
    exited with non-0 status.
    """
    def check_exit_status():
        status = process.wait()
        if status != 0:
            raise CalledProcessError(status, command)
    return check_exit_status

def run_command(command):
    """Run 'command' (shell command string) as a subprocess.
    stderr of the subprocess is redirected to this script's stderr.
    :param command: shell command string
    :return: stdin of the subprocess (file), stdout of the subprocess (file),
    and a function that raises a CalledProcessError if the process exited with
    non-0 status.
    """
    process = Popen(shlex.split(command), stdin=PIPE, stdout=PIPE,
                    stderr=sys.stderr)
    return process.stdin, process.stdout, _get_check_exit_status(
            command, process)

def run_command_in_shell(command):
    """Run 'command' (shell command string) in a login shell using bash,
    so commands on the PATH as set by ~/.bash_profile etc. can be used.
    stderr of the subprocess is redirected to this script's stderr.
    :param command: shell command string
    :return: stdin of the subprocess (file), stdout of the subprocess (file),
    and a function that raises a CalledProcessError if the process exited with
    non-0 status.
    """
    # note command does not need to be quoted even if it contains quotes,
    # because Popen knows each element of the list is a separate token
    process = Popen(['/bin/bash', '--login', '-c', command],
                    stdin=PIPE, stdout=PIPE, stderr=sys.stderr)
    return process.stdin, process.stdout, _get_check_exit_status(
            command, process)

def shell_quote(s):
    return "'" + s.replace("'", "'\\''") + "'"