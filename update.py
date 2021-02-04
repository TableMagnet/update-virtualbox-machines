#!/usr/bin/env python3

import subprocess
import time
import sys


flag = "UpdateVirtualBoxMachinesFinalSignalOperationIsComplete"
newline = "\r\n"
verbose = False


def parseArguments(argv):
    """Parse given command line arguments"""

    if 3 > len(argv):
        return False

    argv.reverse()

    argv.pop() # Remove script name
    arguments = {
        "username": argv.pop(),
        "password": argv.pop(),
        "remove": False,
        "shutdown": False,
        "verbose": False
    }

    while len(argv):
        arg = argv.pop()

        if "-h" == arg:
            return False
        elif "-r" == arg:
            arguments["remove"] = True
        elif "-s" == arg:
            arguments["shutdown"] = True
        elif "-v" == arg:
            arguments["verbose"] = True
            verbose = True
        else:
            print("Unknown argument:", arg, newline)
            return False

    return arguments

def printHelp():
    """Print help instructions"""

    print("""Usage:
python3 update.py $username $password [arguments]

Arguments
-h  help        Display help
-r  remove      Autoremove packages
-s  shutdown    Shutdown host once finished
-v  verbose     Print detailed information""")
    exit()

def findPropertyValue(vminfo, property):
    """Retrieve value from VBoxManage showvminfo"""

    for line in vminfo.split(newline):
        if line.startswith(property):
            return line[line.index("\"") + 1:-1]

    raise Exception("findPropertyValue() - Property '{0}' not found".format(property))

def getHostOS():
    """Check the host OS type"""

    if "win32" == sys.platform:
        return "Windows"
    return "Linux"

def vboxmanage(command):
    """Run VBoxManage command"""

    binary = ""

    if "Windows" == getHostOS():
        binary = '"C:/Program Files/Oracle/VirtualBox/VBoxManage.exe"'
    else:
        binary = "VBoxManage"

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

def printIfVerbose(message):
    """Message to print if verbose option set"""

    if verbose:
        print(message)

def runUpdateCommand(vm, args):
    """Run update command on the guest OS"""

    managers = discoverPackageManagers(vm, args)
    command = getUpdateCommand(managers, args)

    return runCommand(vm, args, command)

def discoverPackageManagers(vm, args):
    """Identify which package managers to guest is using"""

    managers = {
        "apt": False
    }

    for manager in managers:
        response = runCommand(vm, args, "which {0}".format(manager))

        if response:
            managers[manager] = True

    return managers

def getUpdateCommand(managers, args):
    """Construct update command based on options"""

    command = ""

    if managers["apt"]:
        command += '{0} apt update && {0} apt upgrade -y && '
        if args["remove"]:
            command += "{0} apt autoremove -y && "

    command += "echo {0}".format(flag)

    return command.format("echo {0} | sudo -S".format(args["password"]))

def runCommand(vm, args, command):
    """Run given command on the guest"""

    vboxCommand = ('guestcontrol {0} --username {1} --password {2}'
        'run --exe "/bin/sh" -- "/bin/sh" "-c" "{3}"'
        '').format(vm["uuid"], args["username"], args["password"], command)

    return vboxmanage(vboxCommand)

def update(vm, args):
    """Update virtual machine"""

    vmInfo = vboxmanage("showvminfo {0} --machinereadable".format(vm["uuid"]))

    # Skip VMs in saved or running state
    if "poweroff" != findPropertyValue(vmInfo, "VMState"):
        return False

    operatingSystem = findPropertyValue(vmInfo, "ostype")
    if "Windows" == operatingSystem:
        return False

    printIfVerbose("Starting machine")

    response = vboxmanage("startvm {0}".format(vm["uuid"]))
    time.sleep(60) # Wait for VM to start

    # Check that machine started
    if "successfully started" not in response:
        return False

    printIfVerbose("Machine started successfully")

    attemptCount = 0
    errorDetected = False
    printIfVerbose("Waiting to run update command")

    # Loop until VM is running and command succeeds
    while not errorDetected:
        attemptCount += 1
        if 5 < attemptCount:
            errorDetected = True
            break

        response = runUpdateCommand(vm, args)

        if "error:" in response:
            time.sleep(30)
        else:
            break

    attemptCount = 0
    printIfVerbose("Update command {0}".format("failed" if errorDetected else "run"))
    printIfVerbose("Waiting for update to finish")

    # Loop until update is complete
    while not errorDetected:
        attemptCount += 1
        if 20 < attemptCount: # 10 minutes (20 * 30 seconds)
            errorDetected = True
            break

        if flag in response:
            break
        else:
            time.sleep(30)

    printIfVerbose("Update {0}".format("timed out" if errorDetected else "completed"))
    printIfVerbose("Shutting down machine")

    vboxmanage("controlvm {0} acpipowerbutton".format(vm["uuid"]))

    # Wait for machine to shutdown
    time.sleep(30)
    while True:
        vmInfo = vboxmanage("showvminfo {0} --machinereadable".format(vm["uuid"]))
        if "poweroff" == findPropertyValue(vmInfo, "VMState"):
            break;
        time.sleep(15)

    printIfVerbose("Shutdown complete")

    return True

def main():
    args = parseArguments(sys.argv)
    if not args:
        printHelp()
        return False

    machines = parseMachines(vboxmanage("list vms"))

    print(len(machines), "found")
    for i in range(len(machines)):
        print()
        print("Updating", i, machines[i]["name"])
        success = update(machines[i], args)

        printIfVerbose("Update successful" if success else "Update failed")

    if args["shutdown"]:
        if "Windows" == getHostOS():
            subprocess.Popen("shutdown /s /t 60")
        else:
            subprocess.Popen("shutdown")

main()
