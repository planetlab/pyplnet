#!/usr/bin/python /usr/bin/plcsh
# $Id$

import os
import socket
import time
import tempfile
import errno

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

    # assume data['networks'] contains this node's NodeNetworks
    interfaces = {}
    interface = 1
    hostname = data.get('hostname',socket.gethostname())
    gateway = None
    networks = data['networks']
    failedToGetSettings = False

    # NOTE: GetInterfaces/NodeNetworks does not necessarily order the interfaces
    # returned.  Because 'interface'is decremented as each interface is processed,
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
    networks.sort( compare_by('is_primary') )
    networks.reverse()

    for network in networks:
    	logger.verbose('net:InitInterfaces interface %d: %s'%(interface,network))
    	logger.verbose('net:InitInterfaces macs = %s' % macs)
        logger.verbose('net:InitInterfaces ips = %s' % ips)
        # Get interface name preferably from MAC address, falling back
        # on IP address.
        hwaddr=network['mac']
        if hwaddr <> None: hwaddr=hwaddr.lower()
        if hwaddr in macs:
            orig_ifname = macs[hwaddr]
        elif network['ip'] in ips:
            orig_ifname = ips[network['ip']]
        else:
            orig_ifname = None

	if orig_ifname:
       		logger.verbose('net:InitInterfaces orig_ifname = %s' % orig_ifname)
	
        inter = {}
        inter['ONBOOT']='yes'
        inter['USERCTL']='no'
        if network['mac']:
            inter['HWADDR'] = network['mac']
        if network['is_primary']:
            inter['PRIMARY']='yes'

        if network['method'] == "static":
            inter['BOOTPROTO'] = "static"
            inter['IPADDR'] = network['ip']
            inter['NETMASK'] = network['netmask']
            if network['is_primary']:
                gateway = network['gateway']
                if network['dns1']:
                    inter['DNS1'] = network['dns1']
                if network['dns2']:
                    inter['DNS2'] = network['dns2']

        elif network['method'] == "dhcp":
            inter['BOOTPROTO'] = "dhcp"
            inter['PERSISTENT_DHCLIENT'] = "yes"
            if network['hostname']:
                inter['DHCP_HOSTNAME'] = network['hostname']
            else:
                inter['DHCP_HOSTNAME'] = hostname 
            if not network['is_primary']:
                inter['DHCLIENTARGS'] = "-R subnet-mask"

        try:
            plc.GetInterfaceTags()
            version = 4.3
        except AttributeError:
            version = 4.2

        if version == 4.3:
            interface_tag_ids = "interface_tag_ids"
            interface_tag_id = "interface_tag_id"
        else:
            interface_tag_ids = "nodenetwork_setting_ids"
            interface_tag_id = "nodenetwork_setting_id"

        if len(network[interface_tag_ids]) > 0:
            try:
                if version == 4.3:
                    settings = plc.GetInterfaceTags({interface_tag_id:network[interface_tag_ids]})
                else:
                    settings = plc.GetNodeNetworkSettings({interface_tag_id:network[interface_tag_ids]})
            except:
                logger.log("net:InitInterfaces FATAL: failed call GetInterfaceTags({'interface_tag_id':{%s})"% \
                           network['interface_tag_ids'])
                failedToGetSettings = True
                continue # on to the next network

            for setting in settings:
                # to explicitly set interface name
                name_key = "name"
                if version == 4.3:
                    name_key = "tagname"
                    
                settingname = setting[name_key].upper()
                if settingname in ('IFNAME','ALIAS','CFGOPTIONS','DRIVER'):
                    inter[settingname]=setting['value']
                # wireless settings
                elif settingname in \
                        [  "MODE", "ESSID", "NW", "FREQ", "CHANNEL", "SENS", "RATE",
                           "KEY", "KEY1", "KEY2", "KEY3", "KEY4", "SECURITYMODE", 
                           "IWCONFIG", "IWPRIV" ] :
                    inter [settingname] = setting['value']
                    inter ['TYPE']='Wireless'
                else:
                    logger.log("net:InitInterfaces WARNING: ignored setting named %s"%setting[name_key])

        # support aliases to interfaces either by name or HWADDR
        if 'ALIAS' in inter:
            if 'HWADDR' in inter:
                hwaddr = inter['HWADDR'].lower()
                del inter['HWADDR']
                if hwaddr in macs:
                    hwifname = macs[hwaddr]
                    if ('IFNAME' in inter) and inter['IFNAME'] <> hwifname:
                        logger.log("net:InitInterfaces WARNING: alias ifname (%s) and hwaddr ifname (%s) do not match"%\
                                       (inter['IFNAME'],hwifname))
                        inter['IFNAME'] = hwifname
                else:
                    logger.log('net:InitInterfaces WARNING: mac addr %s for alias not found' %(hwaddr))

            if 'IFNAME' in inter:
                # stupid RH /etc/sysconfig/network-scripts/ifup-aliases:new_interface()
                # checks if the "$DEVNUM" only consists of '^[0-9A-Za-z_]*$'. Need to make
                # our aliases compliant.
                parts = inter['ALIAS'].split('_')
                isValid=True
                for part in parts:
                    isValid=isValid and part.isalnum()

                if isValid:
                    interfaces["%s:%s" % (inter['IFNAME'],inter['ALIAS'])] = inter 
                else:
                    logger.log("net:InitInterfaces WARNING: interface alias (%s) not a valid string for RH ifup-aliases"% inter['ALIAS'])
            else:
                logger.log("net:InitInterfaces WARNING: interface alias (%s) not matched to an interface"% inter['ALIAS'])
            interface -= 1
        else:
            if ('IFNAME' not in inter) and not orig_ifname:
                ifname="eth%d" % (interface-1)
                # should check if $ifname is an eth already defines
                if os.path.exists("%s/ifcfg-%s"%(sysconfig,ifname)):
                    logger.log("net:InitInterfaces WARNING: possibly blowing away %s configuration"%ifname)
            else:
		if ('IFNAME' not in inter) and orig_ifname:
                    ifname = orig_ifname
                else:
                    ifname = inter['IFNAME']
                interface -= 1
            interfaces[ifname] = inter
                
    m = modprobe.Modprobe()
    try:
        m.input("%s/etc/modprobe.conf" % root)
    except:
        pass
    for (dev, inter) in interfaces.iteritems():
        # get the driver string "moduleName option1=a option2=b"
        driver=inter.get('DRIVER','')
        if driver <> '':
            driver=driver.split()
            kernelmodule=driver[0]
            m.aliasset(dev,kernelmodule)
            options=" ".join(driver[1:])
            if options <> '':
                m.optionsset(dev,options)
    m.output("%s/etc/modprobe.conf" % root, program)

    # clean up after any ifcfg-$dev script that's no longer listed as
    # part of the NodeNetworks associated with this node

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
    for (dev, inter) in interfaces.iteritems():
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
    for (dev, inter) in interfaces.iteritems():
        (fd, tmpnam) = tempfile.mkstemp(dir=sysconfig)
        f = os.fdopen(fd, "w")
        f.write("# Autogenerated by pyplnet... do not edit!\n")
        if 'DRIVER' in inter:
            f.write("# using %s driver for device %s\n" % (inter['DRIVER'],dev))
        f.write('DEVICE=%s\n' % dev)
        
        # print the configuration values
        for (key, val) in inter.iteritems():
            if key not in ('IFNAME','ALIAS','CFGOPTIONS','DRIVER'):
                f.write('%s=%s\n' % (key, val))

        # print the configuration specific option values (if any)
        if 'CFGOPTIONS' in inter:
            cfgoptions = inter['CFGOPTIONS']
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

        path = "%s/ifcfg-%s" % (sysconfig,dev)
        if not os.path.exists(path):
            logger.verbose('net:InitInterfaces adding configuration for %s' % dev)
            # add ifcfg-$dev configuration file
            os.rename(tmpnam,path)
            os.chmod(path,0644)
            newdevs.append(dev)
            
        elif not comparefiles(tmpnam,path):
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
        print >>sys.stderr, "Missing root or node_id"
        parser.print_help()
        sys.exit(1)

    node = shell.GetNodes({'node_id': [int(args[0])]})
    try:
        networks = shell.GetInterfaces({'interface_id': node[0]['interface_ids']})
    except AttributeError:
        networks = shell.GetNodeNetworks({'nodenetwork_id':node[0]['nodenetwork_ids']})
        version = 4.2


    data = {'hostname': node[0]['hostname'], 'networks': networks}
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
