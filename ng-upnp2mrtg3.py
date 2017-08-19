#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
######################################################################
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
######################################################################

# prints lots of stuff
global_debug = None         # will be set by command line parameter

import socket
import re
import argparse
import collections
import datetime

def dhms(s):
    """ convert integer uptime to human readable form

    :param s: integer
    :return: "x days, xx:xx:xx h"
    .note: conversion routine for uptime values measured in seconds
    """
    try:
        sec = int(s)
    except:
        # oops, not an integer? display as is
        return s

    min = sec // 60
    sec %= 60
    ho = min // 60
    min %= 60
    day = ho // 24
    ho %= 24

    return "%s days, %02d:%02d:%02d h" % (day, ho, min, sec)

def archer_uptime_conv(s):
    """ convert uptime answer to human readable form
    """
    # string returned by archer modem: "103 Days, 12:49:51"
    # not much to do here
    return s.lower() + ' h'

def none2unknown(val):
    """ return value or "UNKNOWN" if value is None

    :param val: value to check
    :return: value or "UNKNOWN"
    .note: rrdtools/mrtg wants UNKNOWN if the value is None
    """
    if val is None:
        return "UNKNOWN"
    return val

def my_int(s, default=None):
    """ get integer from string

    :param s: string to convert
    :param default: value in case of a conversion error
    :return: integer value
    """
    try:
        v = int(s)
    except:
        v = default
    return v

def get_response_code(msg):
    """ extract response status code from HTTP response

    :param msg: HTTP response, e.g. "HTTP/1.1 200 OK"
    :return: code or None on error
    """
    if msg is None:
        return None

    match = re.match('^HTTP/1\.[0|1]\s+(\d+)',msg)
    if match is None:
        return None
    return int(match.group(1))

def gettag(answer, tag):
    """ get contents of result tag in answer

    :param answer: SOAP answer
    :param tag: tag around the desired value
    :return: content or None
    """

    if (answer is None) or (tag is None):
        return None

    # <tag>result</tag>
    # extract part between <tag> and </tag>
    tag1 = "<%s>" % (tag,)
    tag2 = "</%s>" % (tag,)
    po1 = answer.find(tag1) + len(tag1)
    if po1<0 :
        return None      # opening tag not found

    po2 = answer.find(tag2,po1)
    if po2<0 :
        return None      # closing tag not found

    return answer[po1:po2]

class Upnpclient:
    """ Class to build a SOAP request
        send it to tht server
        read the answer
        and extract the desired information
    """

    def __init__(self, host, port):
        """ initialize

        :param host: host name of UPNP server
        :param port: port of UPNP server
        """
        self.host = host
        self.port = port

    def create_message(self, serviceurl, schema, action):
        # create the SOAP request
        body="""<?xml version="1.0"?>
    <s:Envelope
        xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
        s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
    <s:Body>
       <u:%s xmlns:u="urn:schemas-upnp-org:service:%s" />
    </s:Body>
</s:Envelope>""" % (action, schema)

        # create the HTTP POST request header
        pream = """POST %s HTTP/1.0
HOST: %s:%s
CONTENT-LENGTH: %s
CONTENT-TYPE: text/xml; charset="utf-8"
SOAPACTION: "urn:schemas-upnp-org:service:%s#%s"

""".replace("\n","\r\n") % (serviceurl, self.host, self.port, len(body), schema, action)

        return "%s%s" % (pream, body)

    def send(self, cmd):
        """ send command to host:port and wait for the answer

        :param cmd: HTTP POST with SOAP payload
        :return: answer from the UPNP server
        """

        # create TCP socket and connect to host:port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, self.port))

        # send text
        s.send(cmd.encode('utf-8'))

        # receive answer
        resp = ""
        while True:
            data = s.recv(1024)                 # receive up to 1K bytes
            if len(data) == 0:
                break
            resp += data.decode('utf-8')
        s.close()

        return resp

    def send_command(self, serviceurl, schema, action, tag):
        """ send command to router and analyse the result
            returns the value between <tag> and </tag>
            or None on error

            tag can be a single string (in this case the function returns a string)
            or a tuple of strings (in this case a tuple of results is returned)
        """
        global global_debug

        cmd = self.create_message(serviceurl,schema,action)
        if global_debug:
            print(cmd)
        try:
            res = self.send(cmd)
        except socket.error as msg:
            print('Socket error:', msg)
            return None
        if global_debug:
            print(res)

        # check return code
        ret_code = get_response_code(res)
        if global_debug:
            print('repsonse code:', ret_code)
        if ret_code != 200:
            return None

        if tag is None:
            return res  # debug

        if type(tag) is tuple:
            answer = []
            for t in tag:
                answer.append( gettag(res,t) )
            if global_debug:
                return answer
            return tuple(answer)
        else:
            if global_debug:
                return gettag(res,tag)
            return gettag(res,tag)

#############################################################
# Router definition
#
# A list of Router definitions.
#
#    short id, used in list_model and as parameter --type
#    long id, something more descriptive, will be on the output for MRTG
#    default router IP address
#    default router port number
#    SoapAction for incoming byte count
#    SoapAction for outgoing byee count
#    SoapAction for uptime request
#    function pointer to convert uptime into a human readable form
#
#  SoapAction:
#    control path (with leading slash)
#    service type
#    service action
#    tag in answer containing the result
#
Router = collections.namedtuple('Router',
        ['short_id', 'long_id', 'host', 'port', 'incoming', 'outgoing', 'uptime', 'uptime_conv'])
SoapAction = collections.namedtuple('SoapAction',
        ['path', 'schema', 'action', 'tag'])
ROUTERS = [
    Router(
        # short_id, long_id
        "nc_premium", "NetCologne Premium",
        # host, port
        "192.168.0.1", 49300,
        # incoming bytes
        SoapAction(
            "/WANCommonInterfaceConfigService/control",    # control url
           "WANCommonInterfaceConfig:1",              # schema
           "GetTotalBytesReceived",                   # action
           "NewTotalBytesReceived"),                   # tag
        # outgoing bytes
        SoapAction(
           "/WANCommonInterfaceConfigService/control",
           "WANCommonInterfaceConfig:1",
           "GetTotalBytesSent",
           "NewTotalBytesSent"),
        # uptime
        SoapAction(
           "/WANIPConnectionService/control",
           "WANIPConnection:1",
           "GetStatusInfo",
           "NewUptime"),
        # function pointer: uptime -> human readable format
        dhms
    ),
    Router(
        # short_id, long_id
        "fritzbox_7490", "Fritzbox 7490",
        # host, port
        "192.168.178.1", 49000,
        # incoming bytes
        SoapAction(
           "/igdupnp/control/WANCommonIFC1",
           "WANCommonInterfaceConfig:1",
           "GetTotalBytesReceived",
           "NewTotalBytesReceived"),
        # outgoing bytes
        SoapAction(
           "/igdupnp/control/WANCommonIFC1",
           "WANCommonInterfaceConfig:1",
           "GetTotalBytesSent",
           "NewTotalBytesSent"),
        # uptime
        SoapAction(
           "/igdupnp/control/WANIPConn1",   # controlurl
           "WANIPConnection:1",  # servicetype
           "GetStatusInfo",
           "NewUptime"),
        # function pointer: uptime -> human readable format
        dhms
    ),
    Router(
        # info contributed by https://github.com/ddiepo
        # short_id, long_id
        "archer_c7", "Tp-Link Archer C7",
        # host, port
        "192.168.0.1", 49300,
        # incoming bytes
        SoapAction(
           "/ifc",
           "WANCommonInterfaceConfig:1",
           "GetTotalBytesReceived",
           "NewTotalBytesReceived"),
        # outgoing bytes
        SoapAction(
           "/ifc",
           "WANCommonInterfaceConfig:1",
           "GetTotalBytesSent",
           "NewTotalBytesSent"),
        # uptime
        SoapAction(
           "/ipc",                  # controlurl
           "WANIPConnection:1",  # servicetype
           "GetStatusInfo",
           "NewUptime"),
        archer_uptime_conv
    )
]

class Nowrap_handler:
    """ Handle wrap-around of counter

    The last raw values from the device and the last offsets are stored in a file.
    """

    def __init__(self,filename):
        self.filename = filename
        self.lastinraw = None
        self.lastoutraw = None
        self.inoffset = 0
        self.outoffset = 0

        try:
            lines = open(filename,'r').readlines()
            if len(lines) != 2:
                raise ValueError("format mismatch")

            comp = re.compile("^(\d+)\t(\d+)\n$")
            m1 = comp.match(lines[0])
            m2 = comp.match(lines[1])
            if (m1 is None) or (m2 is None):
                raise ValueError("format mismatch")

            self.lastinraw = int(m1.group(1))
            self.lastoutraw = int(m1.group(2))
            self.inoffset = int(m2.group(1))
            self.outoffset = int(m2.group(2))
        except (IOError, ValueError):
            pass

    def __str__(self):
        return "%s\t%s\n%s\t%s\n" % (self.lastinraw, self  .lastoutraw, \
            self.inoffset, self.outoffset)

    def get_corr_values(self,newinraw,newoutraw):
        # - get corrected values
        # - store last values (if not None)
        # - calc new offset

        newinraw = my_int(newinraw, None)
        newoutraw = my_int(newoutraw, None)

        if self.lastinraw is None:
            self.lastinraw = newinraw
        else:
            if not (newinraw is None):
                if newinraw < self.lastinraw:
                    self.inoffset += self.lastinraw
                self.lastinraw = newinraw

                newinraw += self.inoffset

        if self.lastoutraw is None:
            self.lastoutraw = newoutraw
        else:
            if not (newoutraw is None):
                if newoutraw < self.lastoutraw:
                    self.outoffset += self.lastoutraw
                self.lastoutraw = newoutraw

                newoutraw += self.outoffset

        return newinraw, newoutraw

    def store_info(self):
        f = open(self.filename,'w')
        f.write(str(self))
        f.close()

    def get_offsets(self):
        return self.inoffset, self.outoffset

def list_models(args):
    """ output nicely formatted list

    :param args: dummy parameter (expected by argparse)
    :return:
    """
    global ROUTERS

    if len(ROUTERS) == 0:
        print("No models available")
        return

    print("Model id        Description")
    print("--------        -----------")

    for m in ROUTERS:
        print("%-15s %s" % (m.short_id, m.long_id))

def main():
    global global_debug

    all_short_ids = [d.short_id for d in ROUTERS]

    parser = argparse.ArgumentParser(description='query UPNP router', add_help=False)
    parser.add_argument('--host', '-h',
                        help='host ip')
    parser.add_argument('--port', '-p',
                        type=int,
                        help='port number')
    parser.add_argument('--type', '-t',
                        choices=all_short_ids,
                        help='type of router')
    parser.add_argument('--list', '-l',
                        action='store_true',
                        help='list available routers')
    parser.add_argument('--rawlog',
                        help='save raw values in this file')
    parser.add_argument('--nowrap',
                        help='activate anti-wrap, store status in this file')
    parser.add_argument('--debug',
                        action='store_true',
                        help='display communication')
    parser.add_argument('--help',                   # as we have disabled it with "add_help=False"
                        action='help',              # we need to add it manually for "--help"
                        help='show this help message and exit')

    args = parser.parse_args()

    if args.list is True:
        parser.print_help()
        print()
        list_models(None)
        parser.exit(0)                   # = sys.exit(0)

    if args.type is None:
        print("*** Error: router type not given\n")
        list_models(args)
        parser.exit(1)

    global_debug = args.debug

    selected_model = None
    for dt in ROUTERS:
        if dt.short_id == args.type:
            selected_model = dt
            break

    host = args.host
    if not host:
        host = selected_model.host

    port = args.port
    if not port:
        port = selected_model.port

    # query the box
    uc = Upnpclient(host, port)
    inbytes  = uc.send_command(selected_model.incoming.path, selected_model.incoming.schema,
            selected_model.incoming.action, selected_model.incoming.tag)
    outbytes = uc.send_command(selected_model.outgoing.path, selected_model.outgoing.schema,
            selected_model.outgoing.action, selected_model.outgoing.tag)
    uptime   = uc.send_command(selected_model.uptime.path, selected_model.uptime.schema,
            selected_model.uptime.action, selected_model.uptime.tag)

    uptime_str = selected_model.uptime_conv(uptime)

    nowrap = None
    if not(args.nowrap is None):
        nowrap = Nowrap_handler(args.nowrap)
        inbytes, outbytes = nowrap.get_corr_values(inbytes,outbytes)
        nowrap.store_info()

    # store raw data in a file (if requested)
    # give a hint in the output that will displayed in the HTML page

    # "logindicator" is being appended to the "long_id" string and being displayed in the HTML page created by MRTG.
    # It has no other function other than to send some feedback from this routine to the user

    if args.rawlog is None:
        logindicator = ''
    else:
        try:
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if nowrap is None:
                add_info = ''
            else:
                di, do = nowrap.get_offsets()
                add_info = '\t%s\t%s' % (di,do)

            f = open(args.rawlog,'a')
            f.write('%s\t%s\t%s\t%s%s\n' % (now,inbytes,outbytes,uptime,add_info))
            f.close()
            logindicator = ' (logged)'
        except IOError:
            logindicator = ' (error during logging)'

    # output for MRTG
    print(none2unknown(inbytes))
    print(none2unknown(outbytes))
    print(uptime_str)
    print(selected_model.long_id + logindicator)

if __name__ == "__main__":
    main()
