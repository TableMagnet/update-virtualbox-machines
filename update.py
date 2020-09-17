import subprocess
import time
import sys


username = sys.argv[1]
password = sys.argv[2]

binary = '"C:/Program Files/Oracle/VirtualBox/VBoxManage.exe"'
newline = "\r\n"

def vboxmanage(command):
    p = subprocess.Popen(binary + " " + command, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    stdout, stderr = p.communicate()
    stdout = stdout.decode("utf-8")
    stderr = stderr.decode("utf-8")
    return stdout + stderr

def parseMachines(list):
    vms = []
    for line in list.split(newline):

        # validate line format
        if "" == line:
            return vms
        elif not (
            2 == line.count("\"") and
            4 == line.count("-") and
            1 == line.count("{") and
            1 == line.count("}")
        ):
            raise Exception("Command 'list vms' returned unknown format")

        vm = {}
        line = line[1:] # remove first quote
        vm["name"] = line[:line.index("\"")]
        vm["uuid"] = line[line.index("\"") + 3:-1] # skip quote, space & braces
        vms.append(vm)

def update(vm):
    vboxmanage("startvm {0}".format(vm["uuid"]))
    time.sleep(60) # Wait for VM to start
    flag = "UpdateVirtualBoxMachinesFinalSignalOperationIsComplete"
    response = ""

    # Loop until VM is running and command succeeds
    while True:
        response = vboxmanage(('guestcontrol {0} --username {1} --password {2} '
        'run --exe "/bin/sh" -- "/bin/sh" "-c" "'
        'echo {2} | sudo -S apt update && '
        'echo {2} | sudo -S apt upgrade -y && '
        'echo {3}"'
        ''.format(vm["uuid"], username, password, flag)))

        if "error:" in response:
            time.sleep(30)
        else:
            break

    # Loop until update is complete
    while True:
        if flag in response:
            break
        else:
            time.sleep(30)

    vboxmanage("controlvm {0} acpipowerbutton".format(vm["uuid"]))
    return True

def main():
    machines = parseMachines(vboxmanage("list vms"))
    update(machines[0])

main()
