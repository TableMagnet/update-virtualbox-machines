import subprocess
import time
import sys


flag = "UpdateVirtualBoxMachinesFinalSignalOperationIsComplete"
newline = "\r\n"


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

        if "-r" == arg:
            arguments["remove"] = True
        elif "-s" == arg:
            arguments["shutdown"] = True
        elif "-v" == arg:
            arguments["verbose"] = True
        else:
            print("Unknown argument:", arg, newline)
            return False

    return arguments

def printHelp():
    """Print help instructions"""

    print("""Usage:
python update.py $username $password [arguments]

Arguments
-r  remove      Autoremove packages
-s  shutdown    Shutdown host once finished
-v  verbose     Print in depth information
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

def getHostOS():
    """Check the host OS type"""

    if "win32" == sys.platform:
        return "Windows"
    return "Linux"

def vboxmanage(command):
    """Run VBoxManage command"""

    binary = '"C:/Program Files/Oracle/VirtualBox/VBoxManage.exe"'

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

    if args["verbose"]:
        print("Starting machine")

    response = vboxmanage("startvm {0}".format(vm["uuid"]))
    time.sleep(60) # Wait for VM to start

    # Check that machine started
    if "successfully started" not in response:
        return False

    if args["verbose"]:
        print("Machine started successfully")

    attemptCount = 0
    errorDetected = False

    # Loop until VM is running and command succeeds
    while not errorDetected:

        if args["verbose"]:
            print("Attempt {0}: run update command".format(attemptCount))

        attemptCount += 1
        if 5 < attemptCount:
            errorDetected = True
            break

        response = vboxmanage(('guestcontrol {0} --username {1} --password {2} '
        'run --exe "/bin/sh" -- "/bin/sh" "-c" "{3}"'
        ''.format(vm["uuid"], args["username"], args["password"], getUpdateCommand(args))))

        if "error:" in response:
            time.sleep(30)
        else:
            break

    attemptCount = 0
    if args["verbose"]:
        if errorDetected:
            print("Update command failed")
        else:
            print("Update command run successfully")

    # Loop until update is complete
    while not errorDetected:

        if args["verbose"]:
            print("Check {0}: has update completed?".format(attemptCount))

        attemptCount += 1
        if 20 < attemptCount: # 10 minutes (20 * 30 seconds)
            errorDetected = True
            break

        if flag in response:
            break
        else:
            time.sleep(30)

    if args["verbose"]:
        if errorDetected:
            print("Update command timed out")
        else:
            print("Update command completed successfully")

        print("Shutting down machine")

    vboxmanage("controlvm {0} acpipowerbutton".format(vm["uuid"]))

    # Wait for machine to shutdown
    time.sleep(30)
    while True:
        vmInfo = vboxmanage("showvminfo {0} --machinereadable".format(vm["uuid"]))
        if "poweroff" == findPropertyValue(vmInfo, "VMState"):
            break;
        time.sleep(15)

    if args["verbose"]:
        print("Shutdown complete")

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

        if args["verbose"]:
            if success:
                print("Update successful")
            else:
                print("Update failed")
            print()

    if args["shutdown"]:
        if "Windows" == getHostOS():
            subprocess.Popen("shutdown /s /t 60")
        else:
            subprocess.Popen("shutdown")

main()
