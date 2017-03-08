#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from threading import Thread, Lock
import socket
import struct
import argparse

MCAST_GRP = "239.255.255.250"
MCAST_PORT = 1900

result_list = []
result_list_lock = Lock()

request_end = False

def split2dict(lines):
    """ split to lines and serach for "key: value"s and store in dict

    :param lines: single string containing multiple lines
    :return: dict result
    """
    res = {}
    for s in lines.splitlines():
        ma = re.match('^(.+?):\s*(.+)$', s)
        if ma is not None:
            res[ ma.group(1).lower() ] = ma.group(2)
    return res

class Scan_for_ssdp(Thread):
    def __init__(self, mcast_grp, mcast_port, timeout=3, verbose=False):
        """
        :param mcast_grp: '': all mcast on port, or specific: e.g. '239.255.255.250'
        :param mcast_port: multicast port
        :param timeout: delay between tries
        :param verbose: more info
        :return:
        """
        Thread.__init__(self)
        self.verbose = verbose

        # define listening socket
        # s.a. http://stackoverflow.com/questions/603852/multicast-in-python
        socket.setdefaulttimeout(timeout)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((mcast_grp, mcast_port))
        mreq = struct.pack("4sl", socket.inet_aton(mcast_grp), socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    def run(self):
        global result_list, result_list_lock
        global request_end

        count_timeouts = 0
        count_errors = 0
        count_locations = 0

        while not request_end:
            dt = None
            try:
                dt = self.sock.recv(1024)
                dtlen = len(dt)
                eline = dt.find(b'\r\n\r\n')
                if eline == -1:
                    if self.verbose:
                        count_errors += 1
                        print('*** malformed packet')
                    continue
                eline += 4
                if dtlen > eline:
                    if self.verbose:
                        print('*** excess data in ssdp packet', eline, dtlen)
                    dt = dt[:eline]

                s = dt.decode('utf8')
                if self.verbose:
                    print(s)
                else:
                    print(s.splitlines()[0])
                if s.startswith('NOTIFY * HTTP') or s.startswith('HTTP/1.1 200 '):
                    r = split2dict(s)
                    if 'location' in r:
                        with result_list_lock:
                            loc = r['location']
                            server = r.get('server')
                            if not loc in result_list:
                                result_list.append(loc)
                                count_locations += 1
                        print('>> location:', loc)
                        if server is not None:
                            print(' > server:', server)

            except socket.timeout:
                count_timeouts += 1
            except UnicodeDecodeError:
                count_errors += 1
                if self.verbose:
                    print("decode error")

            print('unique loc. %s, errors %s, timeouts %s' % (count_locations, count_errors, count_timeouts))

        self.sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='wait and parse ssdp packets')
    parser.add_argument('--verbose',
                        action='store_true',
                        help='include input variables')

    args = parser.parse_args()

    # start listen thread
    th = Scan_for_ssdp(MCAST_GRP, MCAST_PORT, timeout=3, verbose=args.verbose)
    th.start()

    # wait for the user to end the scan
    c = input("Press [Enter] to stop!\n\n")

    # signal the thread
    request_end = True
    # wait for its completion
    th.join()

    # show the result
    if len(result_list)==0:
        print('*** No locations found')
    else:
        result_list.sort()
        print("Locations found:")
        print("================")
        for ele in result_list:
            print(ele)
