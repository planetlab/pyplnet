#!/usr/bin/python /usr/bin/plcsh

import os
import socket
import time
import tempfile
import errno
import struct

import sioc
import modprobe

global version
version = 4.3

def InitInterfaces(logger, plc, data, root="", files_only=False, program="NodeManager"):
    global version

    sysconfig = "%s/etc/sysconfig/network-scripts" % root
    try:
        os.makedirs(sysconfig)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise e

    # query running network interfaces
    devs = sioc.gifconf()
    ips = dict(zip(devs.values(), devs.keys()))
    macs = {}
    for dev in devs:
        macs[sioc.gifhwaddr(dev).lower()] = dev

    devices_map = {}
    device_id = 1
    hostname = data.get('hostname',socket.gethostname())
    gateway = None
    # assume data['interfaces'] contains this node's Interfaces
    # can cope with 4.3 ('networks') or 5.0 ('interfaces')
    try:
        interfaces = data['interfaces']
    except:
        interfaces = data['networks']
    failedToGetSettings = False

    # NOTE: GetInterfaces/NodeNetworks does not necessarily order the interfaces
    # returned.  Because 'interface' is decremented as each interface is processed,
    # by the time is_primary=True (primary) interface is reached, the device
    # "eth%s" % interface, is not eth0.  But, something like eth-4, or eth-12.
    # This code sorts the interfaces, placing is_primary=True interfaces first.  
    # There is a lot of room for improvement to how this
    # script handles interfaces and how it chooses the primary interface.
    def compare_by (fieldname):
        def compare_two_dicts (a, b):
            return cmp(a[fieldname], b[fieldname])
        return compare_two_dicts

    # NOTE: by sorting on 'is_primary' and then reversing (since False is sorted
    # before True) all 'is_primary' interfaces are at the beginning of the list.
    interfaces.sort( compare_by('is_primary') )
    interfaces.reverse()

    for interface in interfaces:
        logger.verbose('net:InitInterfaces interface %d: %r'%(device_id,interface))
        logger.verbose('net:InitInterfaces macs = %r' % macs)
        logger.verbose('net:InitInterfaces ips = %r' % ips)
        # Get interface name preferably from MAC address, falling back
        # on IP address.
        hwaddr=interface['mac']
        if hwaddr <> None: hwaddr=hwaddr.lower()
        if hwaddr in macs:
            orig_ifname = macs[hwaddr]
        elif interface['ip'] in ips:
            orig_ifname = ips[interface['ip']]
        else:
            orig_ifname = None

        if orig_ifname:
            logger.verbose('net:InitInterfaces orig_ifname = %s' % orig_ifname)

        details = {}
        details['ONBOOT']='yes'
        details['USERCTL']='no'
        if interface['mac']:
            details['HWADDR'] = interface['mac']
        if interface['is_primary']:
            details['PRIMARY']='yes'

        if interface['method'] == "static":
            details['BOOTPROTO'] = "static"
            details['IPADDR'] = interface['ip']
            details['NETMASK'] = interface['netmask']
            details['GATEWAY'] = interface['gateway']
            if interface['is_primary']:
                gateway = interface['gateway']
                if interface['dns1']:
                    details['DNS1'] = interface['dns1']
                if interface['dns2']:
                    details['DNS2'] = interface['dns2']

        elif interface['method'] == "dhcp":
            details['BOOTPROTO'] = "dhcp"
            details['PERSISTENT_DHCLIENT'] = "yes"
            if interface['hostname']:
                details['DHCP_HOSTNAME'] = interface['hostname']
            else:
                details['DHCP_HOSTNAME'] = hostname 
            if not interface['is_primary']:
                details['DHCLIENTARGS'] = "-R subnet-mask"

        if 'interface_tag_ids' in interface:
            version = 4.3
            interface_tag_ids = "interface_tag_ids"
            interface_tag_id = "interface_tag_id"
            name_key = "tagname"
        else:
            version = 4.2
            interface_tag_ids = "nodenetwork_setting_ids"
            interface_tag_id = "nodenetwork_setting_id"
            name_key = "name"

        if len(interface[interface_tag_ids]) > 0:
            try:
                if version == 4.3:
                    settings = plc.GetInterfaceTags({interface_tag_id:interface[interface_tag_ids]})
                else:
                    settings = plc.GetNodeNetworkSettings({interface_tag_id:interface[interface_tag_ids]})
            except:
                logger.log("net:InitInterfaces FATAL: failed call GetInterfaceTags({'interface_tag_id':{%s})"% \
                           interface[interface_tag_ids])
                failedToGetSettings = True
                continue # on to the next interface

            for setting in settings:
                settingname = setting[name_key].upper()
                if settingname in ('IFNAME','ALIAS','CFGOPTIONS','DRIVER'):
                    details[settingname]=setting['value']
                # wireless settings
                elif settingname in \
                        [  "MODE", "ESSID", "NW", "FREQ", "CHANNEL", "SENS", "RATE",
                           "KEY", "KEY1", "KEY2", "KEY3", "KEY4", "SECURITYMODE", 
                           "IWCONFIG", "IWPRIV" ] :
                    details [settingname] = setting['value']
                    details ['TYPE']='Wireless'
                else:
                    logger.log("net:InitInterfaces WARNING: ignored setting named %s"%setting[name_key])

        # support aliases to interfaces either by name or HWADDR
        if 'ALIAS' in details:
            if 'HWADDR' in details:
                hwaddr = details['HWADDR'].lower()
                del details['HWADDR']
                if hwaddr in macs:
                    hwifname = macs[hwaddr]
                    if ('IFNAME' in details) and details['IFNAME'] <> hwifname:
                        logger.log("net:InitInterfaces WARNING: alias ifname (%s) and hwaddr ifname (%s) do not match"%\
                                       (details['IFNAME'],hwifname))
                        details['IFNAME'] = hwifname
                else:
                    logger.log('net:InitInterfaces WARNING: mac addr %s for alias not found' %(hwaddr))

            if 'IFNAME' in details:
                # stupid RH /etc/sysconfig/network-scripts/ifup-aliases:new_interface()
                # checks if the "$DEVNUM" only consists of '^[0-9A-Za-z_]*$'. Need to make
                # our aliases compliant.
                parts = details['ALIAS'].split('_')
                isValid=True
                for part in parts:
                    isValid=isValid and part.isalnum()

                if isValid:
                    devices_map["%s:%s" % (details['IFNAME'],details['ALIAS'])] = details 
                else:
                    logger.log("net:InitInterfaces WARNING: interface alias (%s) not a valid string for RH ifup-aliases"% details['ALIAS'])
            else:
                logger.log("net:InitInterfaces WARNING: interface alias (%s) not matched to an interface"% details['ALIAS'])
            device_id -= 1
        else:
            if 'IFNAME' in details:
                ifname = details['IFNAME']
                device_id -= 1
            elif orig_ifname:
                ifname = orig_ifname
                device_id -= 1
            else:
                while True:
                    ifname="eth%d" % (device_id-1)
                    if ifname not in devices_map:
                        break
                    device_id += 1
                if os.path.exists("%s/ifcfg-%s"%(sysconfig,ifname)):
                    logger.log("net:InitInterfaces WARNING: possibly blowing away %s configuration"%ifname)
            devices_map[ifname] = details
        device_id += 1 
    m = modprobe.Modprobe()
    try:
        m.input("%s/etc/modprobe.conf" % root)
    except:
        pass
    for (dev, details) in devices_map.iteritems():
        # get the driver string "moduleName option1=a option2=b"
        driver=details.get('DRIVER','')
        if driver <> '':
            driver=driver.split()
            kernelmodule=driver[0]
            m.aliasset(dev,kernelmodule)
            options=" ".join(driver[1:])
            if options <> '':
                m.optionsset(dev,options)
    m.output("%s/etc/modprobe.conf" % root, program)

    # clean up after any ifcfg-$dev script that's no longer listed as
    # part of the Interfaces associated with this node

    # list all network-scripts
    files = os.listdir(sysconfig)

    # filter out the ifcfg-* files
    ifcfgs=[]
    for f in files:
        if f.find("ifcfg-") == 0:
            ifcfgs.append(f)

    # remove loopback (lo) from ifcfgs list
    lo = "ifcfg-lo"
    if lo in ifcfgs: ifcfgs.remove(lo)

    # remove known devices from icfgs list
    for (dev, details) in devices_map.iteritems():
        ifcfg = 'ifcfg-'+dev
        if ifcfg in ifcfgs: ifcfgs.remove(ifcfg)

    # delete the remaining ifcfgs from 
    deletedSomething = False

    if not failedToGetSettings:
        for ifcfg in ifcfgs:
            dev = ifcfg[len('ifcfg-'):]
            path = "%s/ifcfg-%s" % (sysconfig,dev)
            if not files_only:
                logger.verbose("net:InitInterfaces removing %s %s"%(dev,path))
                os.system("/sbin/ifdown %s" % dev)
            deletedSomething=True
            os.unlink(path)

    # wait a bit for the one or more ifdowns to have taken effect
    if deletedSomething:
        time.sleep(2)

    # Write network configuration file
    networkconf = file("%s/etc/sysconfig/network" % root, "w")
    networkconf.write("NETWORKING=yes\nHOSTNAME=%s\n" % hostname)
    if gateway is not None:
        networkconf.write("GATEWAY=%s\n" % gateway)
    networkconf.close()

    # Process ifcfg-$dev changes / additions
    newdevs = []
    for (dev, details) in devices_map.iteritems():
        (fd, tmpnam) = tempfile.mkstemp(dir=sysconfig)
        f = os.fdopen(fd, "w")
        f.write("# Autogenerated by pyplnet... do not edit!\n")
        if 'DRIVER' in details:
            f.write("# using %s driver for device %s\n" % (details['DRIVER'],dev))
        f.write('DEVICE=%s\n' % dev)
        
        # print the configuration values
        for (key, val) in details.iteritems():
            if key not in ('IFNAME','ALIAS','CFGOPTIONS','DRIVER','GATEWAY'):
                f.write('%s="%s"\n' % (key, val))

        # print the configuration specific option values (if any)
        if 'CFGOPTIONS' in details:
            cfgoptions = details['CFGOPTIONS']
            f.write('#CFGOPTIONS are %s\n' % cfgoptions)
            for cfgoption in cfgoptions.split():
                key,val = cfgoption.split('=')
                key=key.strip()
                key=key.upper()
                val=val.strip()
                f.write('%s="%s"\n' % (key,val))
        f.close()

        # compare whether two files are the same
        def comparefiles(a,b):
            try:
                logger.verbose("net:InitInterfaces comparing %s with %s" % (a,b))
                if not os.path.exists(a): return False
                fb = open(a)
                buf_a = fb.read()
                fb.close()

                if not os.path.exists(b): return False
                fb = open(b)
                buf_b = fb.read()
                fb.close()

                return buf_a == buf_b
            except IOError, e:
                return False

        src_route_changed = False
        if ('PRIMARY' not in details and 'GATEWAY' in details and
            details['GATEWAY'] != ''):
            i = len(dev) - 1
            while dev[i - 1].isdigit():
                i -= 1
            table = 10 + int(dev[i:])
            (fd, rule_tmpnam) = tempfile.mkstemp(dir=sysconfig)
            os.write(fd, "from %s lookup %d\n" % (details['IPADDR'], table))
            os.close(fd)
            rule_dest = "%s/rule-%s" % (sysconfig, dev)
            if not comparefiles(rule_tmpnam, rule_dest):
                os.rename(rule_tmpnam, rule_dest)
                os.chmod(rule_dest, 0644)
                src_route_changed = True
            else:
                os.unlink(rule_tmpnam)
            (fd, route_tmpnam) = tempfile.mkstemp(dir=sysconfig)
            netmask = struct.unpack("I", socket.inet_aton(details['NETMASK']))[0]
            ip = struct.unpack("I", socket.inet_aton(details['IPADDR']))[0]
            network = socket.inet_ntoa(struct.pack("I", (ip & netmask)))
            netmask = socket.ntohl(netmask)
            i = 0
            while (netmask & (1 << i)) == 0:
                i += 1
            prefix = 32 - i
            os.write(fd, "%s/%d dev %s table %d\n" % (network, prefix, dev, table))
            os.write(fd, "default via %s dev %s table %d\n" % (details['GATEWAY'], dev, table))
            os.close(fd)
            route_dest = "%s/route-%s" % (sysconfig, dev)
            if not comparefiles(route_tmpnam, route_dest):
                os.rename(route_tmpnam, route_dest)
                os.chmod(route_dest, 0644)
                src_route_changed = True
            else:
                os.unlink(route_tmpnam)

        path = "%s/ifcfg-%s" % (sysconfig,dev)
        if not os.path.exists(path):
            logger.verbose('net:InitInterfaces adding configuration for %s' % dev)
            # add ifcfg-$dev configuration file
            os.rename(tmpnam,path)
            os.chmod(path,0644)
            newdevs.append(dev)
            
        elif not comparefiles(tmpnam,path) or src_route_changed:
            logger.verbose('net:InitInterfaces Configuration change for %s' % dev)
            if not files_only:
                logger.verbose('net:InitInterfaces ifdown %s' % dev)
                # invoke ifdown for the old configuration
                os.system("/sbin/ifdown %s" % dev)
                # wait a few secs for ifdown to complete
                time.sleep(2)

            logger.log('replacing configuration for %s' % dev)
            # replace ifcfg-$dev configuration file
            os.rename(tmpnam,path)
            os.chmod(path,0644)
            newdevs.append(dev)
        else:
            # tmpnam & path are identical
            os.unlink(tmpnam)

    for dev in newdevs:
        cfgvariables = {}
        fb = file("%s/ifcfg-%s"%(sysconfig,dev),"r")
        for line in fb.readlines():
            parts = line.split()
            if parts[0][0]=="#":continue
            if parts[0].find('='):
                name,value = parts[0].split('=')
                # clean up name & value
                name = name.strip()
                value = value.strip()
                value = value.strip("'")
                value = value.strip('"')
                cfgvariables[name]=value
        fb.close()

        def getvar(name):
            if name in cfgvariables:
                value=cfgvariables[name]
                value = value.lower()
                return value
            return ''

        # skip over device configs with ONBOOT=no
        if getvar("ONBOOT") == 'no': continue

        # don't bring up slave devices, the network scripts will
        # handle those correctly
        if getvar("SLAVE") == 'yes': continue

        if not files_only:
            logger.verbose('net:InitInterfaces bringing up %s' % dev)
            os.system("/sbin/ifup %s" % dev)

if __name__ == "__main__":
    import optparse
    import sys

    parser = optparse.OptionParser(usage="plnet [-v] [-f] [-p <program>] -r root node_id")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose")
    parser.add_option("-r", "--root", action="store", type="string",
                      dest="root", default=None)
    parser.add_option("-f", "--files-only", action="store_true",
                      dest="files_only")
    parser.add_option("-p", "--program", action="store", type="string",
                      dest="program", default="plnet")
    (options, args) = parser.parse_args()
    if len(args) != 1 or options.root is None:
        print sys.argv
        print >>sys.stderr, "Missing root or node_id"
        parser.print_help()
        sys.exit(1)

    node = shell.GetNodes({'node_id': [int(args[0])]})
    try:
        interfaces = shell.GetInterfaces({'interface_id': node[0]['interface_ids']})
    except AttributeError:
        interfaces = shell.GetNodeNetworks({'nodenetwork_id':node[0]['nodenetwork_ids']})
        version = 4.2


    data = {'hostname': node[0]['hostname'], 'interfaces': interfaces}
    class logger:
        def __init__(self, verbose):
            self.verbosity = verbose
        def log(self, msg, loglevel=2):
            if self.verbosity:
                print msg
        def verbose(self, msg):
            self.log(msg, 1)
    l = logger(options.verbose)
    InitInterfaces(l, shell, data, options.root, options.files_only)
