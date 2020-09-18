import subprocess
import time
import sys


flag = "UpdateVirtualBoxMachinesFinalSignalOperationIsComplete"
binary = '"C:/Program Files/Oracle/VirtualBox/VBoxManage.exe"'
newline = "\r\n"


def parseArguments(argv):
    """Parse given command line arguments"""

    if 3 > len(argv):
        return False

    argv.pop() # Remove script name
    arguments = {
        "username": argv.pop(),
        "password": argv.pop(),
        "remove": False
    }

    while len(argv):
        arg = argv.pop()

        if "-r" == arg:
            arguments["remove"] = True
        else:
            print("Unknown argument:", arg, newline)
            return False

    return arguments

def printHelp():
    """Print help instructions"""

    print("""Usage:
python update.py $username $password [arguments]

Arguments
-r  remove  Autoremove packages
""")
    exit()

def getUpdateCommand(args):
    """Create update command based on options"""

    command = ('echo {0} | sudo -S apt update && '
        'echo {0} | sudo -S apt upgrade -y && '
        '{1} echo {2}')

    autoremove = ""
    if args["remove"]:
        autoremove = ("echo {0} | sudo -S apt autoremove -y &&").format(args["password"])

    return command.format(args["password"], autoremove, flag)

def findPropertyValue(vminfo, property):
    """Retrieve value from VBoxManage showvminfo"""

    for line in vminfo.split(newline):
        if line.startswith(property):
            return line[line.index("\"") + 1:-1]
    raise Exception("findPropertyValue() - Property '{0}' not found".format(property))

def vboxmanage(command):
    """Run VBoxManage command"""

    p = subprocess.Popen(binary + " " + command, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    stdout, stderr = p.communicate()
    stdout = stdout.decode("utf-8")
    stderr = stderr.decode("utf-8")
    return stdout + stderr

def parseMachines(list):
    """Parse response from 'VBoxManage list vms'"""

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

def update(vm, args):
    """Update virtual machine"""

    vmInfo = vboxmanage("showvminfo {0} --machinereadable".format(vm["uuid"]))

    # Skip VMs in saved or running state
    if "poweroff" != findPropertyValue(vmInfo, "VMState"):
        return False

    operatingSystem = findPropertyValue(vmInfo, "ostype")
    if "Windows" == operatingSystem:
        return False

    vboxmanage("startvm {0}".format(vm["uuid"]))
    time.sleep(60) # Wait for VM to start
    response = ""

    # Loop until VM is running and command succeeds
    while True:
        response = vboxmanage(('guestcontrol {0} --username {1} --password {2} '
        'run --exe "/bin/sh" -- "/bin/sh" "-c" "{3}"'
        ''.format(vm["uuid"], args["username"], args["password"], getUpdateCommand(args))))

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
    args = parseArguments(sys.argv)
    if not args:
        printHelp()
        return False

    machines = parseMachines(vboxmanage("list vms"))
    print(len(machines), "found")
    for i in range(len(machines)):
        print("Updating", i, machines[i]["name"])
        success = update(machines[i], args)

main()
