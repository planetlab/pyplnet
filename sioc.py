# $Id$
# vim:set ts=4 sw=4 expandtab:
# (c) Copyright 2008 The Trustees of Princeton University

import os
import socket
import fcntl
import struct

SIOCGIFADDR = 0x8915
SIOCGIFADDR_struct = "16xH2xI8x"
SIOCGIFHWADDR = 0x8927
SIOCGIFHWADDR_struct = "16x2x6B8x"

def _format_ip(nip):
    ip = socket.ntohl(nip)
    return "%d.%d.%d.%d" % ((ip & 0xff000000) >> 24,
                            (ip & 0x00ff0000) >> 16,
                            (ip & 0x0000ff00) >> 8,
                            (ip & 0x000000ff))

def gifaddr(interface):
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        ifreq = fcntl.ioctl(s.fileno(), SIOCGIFADDR, struct.pack("16s16x", interface))
        (family, ip) = struct.unpack(SIOCGIFADDR_struct, ifreq)
        if family == socket.AF_INET:
            return _format_ip(ip)
    finally:
        if s is not None:
            s.close()
    return None

def gifconf():
    try:
        interfaces = os.listdir("/sys/class/net")
    except:
        interfaces = []
    s = None
    ret = {}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        for interface in interfaces:
            try:
                ifreq = fcntl.ioctl(s.fileno(), SIOCGIFADDR,
                                    struct.pack("16sH14x", interface, socket.AF_INET))
                (family, ip) = struct.unpack(SIOCGIFADDR_struct, ifreq)
                if family == socket.AF_INET:
                    ret[interface] = _format_ip(ip)
                else:
                    raise Exception
            except:
                ret[interface] = "0.0.0.0"
    finally:
        if s is not None:
            s.close()
    return ret

def gifhwaddr(interface):
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        ifreq = fcntl.ioctl(s.fileno(), SIOCGIFHWADDR, struct.pack("16s16x", interface))
        mac = struct.unpack(SIOCGIFHWADDR_struct, ifreq)
        return "%02x:%02x:%02x:%02x:%02x:%02x" % mac
    finally:
        s.close()
    return None
