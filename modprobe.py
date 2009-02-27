#
# $Id$
#

"""Modprobe is a utility to read/modify/write /etc/modprobe.conf"""

import os
import tempfile

class Modprobe:
    def __init__(self,filename="/etc/modprobe.conf"):
        self.conffile = {}
        for keyword in ("include","alias","options","install","remove","blacklist","MODULES"):
            self.conffile[keyword]={}
        self.filename = filename

    def input(self,filename=None):
        if filename==None: filename=self.filename

        # list of file names; loop itself might add filenames
        filenames = [filename]

        for filename in filenames:
            if not os.path.exists(filename):
                continue

            fb = file(filename,"r")
            for line in fb.readlines():
                def __default():
                    modulename=parts[1]
                    rest=" ".join(parts[2:])
                    self._set(command,modulename,rest)

                def __alias():
                    wildcard=parts[1]
                    modulename=parts[2]
                    self.aliasset(wildcard,modulename)
                    options=''
                    if len(parts)>3:
                        options=" ".join(parts[3:])
                        self.optionsset(modulename,options)
                    self.conffile['MODULES'][modulename]=options

                def __options():
                    modulename=parts[1]
                    rest=" ".join(parts[2:])
                    self.conffile['MODULES'][modulename]=rest
                    __default()

                def __blacklist():
                    modulename=parts[1]
                    self.blacklistset(modulename,'')

                def __include():
                    newfilename = parts[1]
                    if os.path.exists(newfilename):
                        if os.path.isdir(newfilename):
                            for e in os.listdir(newfilename):
                                filenames.append("%s/%s"%(newfilename,e))
                        else:
                            filenames.append(newfilename)

                funcs = {"alias":__alias,
                         "options":__options,
                         "blacklis":__blacklist,
                         "include":__include}

                parts = line.split()

                # skip empty lines or those that are comments
                if len(parts) == 0 or parts[0] == "#":
                    continue

                # lower case first word
                command = parts[0].lower()

                # check if its a command we support
                if not self.conffile.has_key(command):
                    print "WARNING: command %s not recognized." % command
                    continue

                func = funcs.get(command,__default)
                func()
            
            fb.close()

    def _get(self,command,key):
        return self.conffile[command].get(key,None)

    def _set(self,command,key,value):
        self.conffile[command][key]=value

    def aliasget(self,key):
        return self._get('alias',key)

    def optionsget(self,key):
        return self._get('options',key)

    def blacklistget(self,key):
        return self._get('blacklist',key)

    def aliasset(self,key,value):
        self._set("alias",key,value)

    def optionsset(self,key,value):
        self._set("options",key,value)

    def blacklistset(self,key,value):
        self._set("blacklist",key,value)
        
    def _comparefiles(self,a,b):
        try:
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

    def output(self,filename="/etc/modprobe.conf",program="NodeManager"):
        (fd, tmpnam) = tempfile.mkstemp(dir=os.path.dirname(filename))
        fb = os.fdopen(fd, "w")
        fb.write("# Written out by %s\n" % program)

        for command in ("alias","options","install","remove","blacklist"):
            table = self.conffile[command]
            keys = table.keys()
            keys.sort()
            for k in keys:
                v = table[k]
                fb.write("%s %s %s\n" % (command,k,v))

        fb.close()
        if not self._comparefiles(tmpnam,filename):
            os.rename(tmpnam,filename)
            os.chmod(filename,0644)
            return True
        else:
            os.unlink(tmpnam)
            return False

    def probe(self,name):
        o = os.popen("/sbin/modprobe %s" % name)
        o.close()

    def checkmodules(self):
        syspath="/sys/module"
        modules = os.listdir(syspath)
        for module in modules:
            path="%/%s/parameters"%(syspath,module)
            if os.path.exists(path):
                ps=os.listdir(path)
                parameters={}
                for p in ps:
                    fb = file("%s/%s"%(path,p),"r")
                    parameters[p]=fb.readline()
                    fb.close()
         
if __name__ == '__main__':
    import sys
    if len(sys.argv)>1:
        m = Modprobe(sys.argv[1])
    else:
        m = Modprobe()

    m.input()
    m.aliasset("bond0","bonding")
    m.optionsset("bond0","miimon=100")
    m.output("/tmp/x")
