**ng-upnp2mrtg** - (c) 2009-2017 by Michael Strecke

_released under GPL v3.0_

# Overview
_ng-upnp2mrtg3_ is a small python script to retrieve data from UPNP enabled routers and hand it over to MRTG.

* The current version is _ng-upnp2mrtg3.py_ running under Python3.
* The old Python2 version _ng-upnp2mrtg.py_ is still available but not recommended.

## Supported devices
 * NetCologne Premium (a re-branded Sphairon Turbolink 7211)
 * Fritzbox 7490
 * Tp-Link Archer C7

# PREREQUISITES

* Python 3.1 or 2.5 resp.
* standard libraries only

# INSTALLATION

* Copy the script `ng-upnp2mrtg3.py` to a directory of your choice.
* Modify the MRTG configuration file accordingly.

# USAGE

_ng-upnp2mrtg.py_ is usually called via _mrtg_.  An example mrtg configuration file 
is included. Compare with `/etc/mrtg.cfg` on your system.

# CONFIGURATION

_ng-upnp2mrtg3.py_ itself is configured using command line options:


**--host, -h** - IP address or host name of the UPNP device (default: 192.168.0.1)

**--port, -p** - UPNP port of the device (default: 49300)

**--type, -t** - type of router (mandatory) (see `--list` option below)

**--nowrap filename** - activates the anti-wrap option.  Modems tend to reset their byte counts after a disconnect 
 which shows up as a huge spike in the MRTG graph.  To counter this, _ng-upnp2mrtg3.py_ keeps track of the byte count
 and adds the last byte count before the reset as an offset to all subsequent results.  This information is stored 
 in `filename`

**--rawlog filename** - the raw byte counts can be logged in `filename` for debugging purposes.

**--debug** - outputs even more debugging information (to stdout).  This option must not be used if the script is 
 called via MRTG.

**--help** - short help

**--list** - displays a list of supported routers.  The values in the first column are used in the `-t` option.

# OTHER UPNP DEVICES

_ng-upnp2mrtg3.py_ can be easily extended.  See [Wiki](https://github.com/MStrecke/ng-upnp2mrtg/wiki) or 
http://tuxpool.blogspot.com/search/label/UPnP for further information.


