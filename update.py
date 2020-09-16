import os

binary = '"C:/Program Files/Oracle/VirtualBox/VBoxManage.exe"'
newline = '\n'

def vboxmanage(command):
    return os.popen(binary + " " + command).read()

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

def main():
    machines = parseMachines(vboxmanage("list vms"))
    for i in range(len(machines)):
        print(machines[i])

main()
