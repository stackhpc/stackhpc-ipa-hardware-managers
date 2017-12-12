stackhpc-hardware-managers
==========================

.. image:: https://travis-ci.org/stackhpc/stackhpc-ipa-hardware-managers.svg?branch=master
   :target: https://travis-ci.org/stackhpc/stackhpc-ipa-hardware-managers

A collection of hardware managers for the Ironic Python Agent.

system_bios
-----------

A simple hardware manager for checking the system BIOS version against
a version specified in the Ironic node info. The following node info
is expected to be set:

'extra': {
    'system_vendor': {
        'product_name': 'PowerEdge R630',
        'bios_version': '2.3.4'
    }
}

The hardware manager should be supported by any system which supports
returning the product name and BIOS version via dmidecode.

Credits
-------

Based on the example hardware manager project by Jay Faulkner:

https://github.com/openstack/ipa-example-hardware-managers
