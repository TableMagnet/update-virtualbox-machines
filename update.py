import subprocess
import time
import sys


flag = "UpdateVirtualBoxMachinesFinalSignalOperationIsComplete"
binary = '"C:/Program Files/Oracle/VirtualBox/VBoxManage.exe"'
newline = "\r\n"


def parseArguments(argv):
    if 3 > len(argv):
        return False

    arguments = {
        "username": argv[1],
        "password": argv[2],
        "remove": False
    }

    argv = argv[3:]

    while len(argv):
        arg = argv.pop()

        if "-r" == arg:
            arguments["remove"] = True
        else:
            print("Unknown argument:", arg, newline)
            return False

    return arguments

def printHelp():
    print("""Usage:
python update.py $username $password [arguments]

Arguments
-r  remove  Autoremove packages
""")
    exit()

def getUpdateCommand(args):
    command = ('echo {0} | sudo -S apt update && '
        'echo {0} | sudo -S apt upgrade -y && '
        '{1} echo {2}')

    autoremove = ""
    if args["remove"]:
        autoremove = ("echo {0} | sudo -S apt autoremove -y &&").format(args["password"])

    return command.format(args["password"], autoremove, flag)

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

def update(vm, args):
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
    update(machines[0], args)

main()
