#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import urllib.request
from urllib.parse import urljoin, urlparse
import os.path
import argparse
import re

DUMPDIR = '/tmp'

def dump_file(url, binary_content):
    pa = os.path.basename(urlparse(url).path)
    if pa == '':
        pa = 'untitled.txt'
    bn = os.path.join(DUMPDIR, pa)

    open(bn, 'wb').write(binary_content)
    print('** Dumped '+ url)

def split_ns(tag):
    ma = re.match("^({.*?}){0,1}(.+)$", tag.tag)
    if ma is None:
        raise ValueError('Malformed tag')
    return ma.group(1)[1:-1], ma.group(2)

def parse_service(service, ns):
    serviceType = service.find('./upnp:serviceType', ns)
    urlbase = service.find('./upnp:URLBase', ns)
    controlUrl = service.find('./upnp:controlURL', ns)
    scpdUrl = service.find('./upnp:SCPDURL', ns)

    assert serviceType is not None, 'serviceType not found'
    assert controlUrl is not None, 'controlURL not found'
    assert scpdUrl is not None, 'scpdURL not found'

    if urlbase is None:
        urlbase = starturl
    surl = urljoin(urlbase, scpdUrl.text)

    curl = controlUrl.text
    print(controlUrl.text)
    print('    ' + serviceType.text)

    try:
        scpdCont = urllib.request.urlopen(surl).read()
        if args.dump:
            dump_file(surl, scpdCont)
        scpdroot = ET.fromstring(scpdCont.decode('utf-8'))
    except Exception:
        print('*** Error reading SCPD url:', surl)
        print('*** Skipping')
        return

    scpd_ns, scpd_localname = split_ns(scpdroot)
    if not scpd_ns in [
        'urn:schemas-upnp-org:service-1-0',
        'urn:dslforum-org:service-1-0'
    ]:
        print('** Warning: unexptected namespace in scpd file, continuing anyway: %s' % scpd_ns)

    assert scpd_localname == 'scpd', 'wrong root element in scpd file: ' + scpd_localname

    scns = {'ns1': scpd_ns}

    for action in scpdroot.findall('./ns1:actionList/ns1:action', scns):
        name = action.find('./ns1:name', scns)
        argsList = action.find('./ns1:argumentList', scns)

        assert name is not None, 'name not found'
        print('        ' + name.text)
        if argsList is None:
            print('            (no arguments)')
        else:
            for argument in argsList.findall('./ns1:argument', scns):
                argname = None
                direction = None
                for desc in argument.findall('./', ns):
                    if desc.tag == '{%s}name' % scpd_ns:
                        argname = desc.text
                    if desc.tag == '{%s}direction' % scpd_ns:
                        direction = desc.text
                print('            %s (%s)' % (argname, direction))


def parse_device(root, ns):
    fnt = root.find('./upnp:friendlyName', ns)
    friendlyName = None
    if fnt is not None:
        friendlyName = fnt.text
        print()
        print(friendlyName)
        print('='*len(friendlyName))
        print()

    serviceList = root.find('./upnp:serviceList', ns)
    assert serviceList is not None, 'no serviceList found'

    for service in serviceList.findall('./upnp:service', ns):
        parse_service(service, ns)

    subdev = root.find('./upnp:deviceList', ns)
    if subdev is not None:
        for device in subdev.findall('./upnp:device', ns):
            parse_device(device, ns)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='discover SOAP parameters')
    parser.add_argument('baseurl',
                        help='URL of description XML')
    parser.add_argument('--dump',
                        action='store_true',
                        help='store downloaded XML files in %s' % DUMPDIR)

    args = parser.parse_args()

    starturl = args.baseurl

    try:
        data = urllib.request.urlopen(starturl).read()
        if args.dump:
            dump_file(starturl, data)
        root = ET.fromstring(data.decode('utf-8'))
    except Exception as msg:
        print('Error: '+ msg)
        parser.exit(1)


    root_ns, root_tagname = split_ns(root)
    if not root_ns in ['urn:schemas-upnp-org:device-1-0']:
        print('** Warning: unexpected namespace in root file, continuing anyway: %s' % root_ns)
    assert root_tagname == 'root', 'unexpected root XML file'
    ns = {'upnp': root_ns}

    # Try to get top level device
    tld = root.find('./upnp:device', ns)
    assert tld is not None, 'no top level device'
    parse_device(tld, ns)


