==============================
stackhpc-ipa-hardware-managers
==============================

.. image:: https://travis-ci.org/stackhpc/stackhpc-ipa-hardware-managers.svg?branch=master
    :target: https://travis-ci.org/stackhpc/stackhpc-ipa-hardware-managers

A collection of hardware managers for the Ironic Python Agent.

system_bios
-----------

A simple hardware manager for checking the system BIOS version against
a version specified in the Ironic node info. The following node info
is expected to be set:

.. code-block::

    'extra': {
        'system_vendor': {
            'product_name': 'PowerEdge R630',
            'bios_version': '2.3.4'
        }
    }

The following examples may be used to set the node info.

* To set multiple fields at once:

    .. code-block::

        openstack baremetal node set $NODE_ID --extra system_vendor='{"product_name": "PowerEdge R630", "bios_version": "2.6.0"}'

* To set a single field:

    .. code-block::

        openstack baremetal node set $NODE_ID --extra system_vendor/bios_version=1.0

The hardware manager should be supported by any system which supports
returning the product name and BIOS version via dmidecode.

In the case that you wish to disable the hardware manager for specific nodes,
you can set the following property in the nodes extra info:

.. code-block::

    openstack baremetal node set $NODE_ID --extra disable_bios_version_check=True

If you wish to re-enable the hardware manager, you can either unset the property, or
set it to `False`. For example:

.. code-block::

    openstack baremetal node set $NODE_ID --extra disable_bios_version_check=False

or:

.. code-block::

    openstack baremetal node unset $NODE_ID --extra disable_bios_version_check

system_nic
-----------

Provides a hardware manager to verify the firmware version of network interface
cards against a list of expected versions in the Ironic node info. The following
node info is expected to be set:

.. code-block::

  "extra": {
    "nic_firmware": [
      {
        "vendor_id": "<vendor_id>",
        "device_id": "<device_id>",
        "firmware_version": "<firmware_version>"
      }
    ]
  }

You may discover <vendor_id>, <device_id> and <firmware_version> by running:

.. code-block::

    lshw -class network -numeric

on a given node in the cluster. The following is an example output:

.. code-block::

  *-network
       description: Ethernet interface
       product: RTL8111/8168/8411 PCI Express Gigabit Ethernet Controller [10EC:8168]
       vendor: Realtek Semiconductor Co., Ltd. [10EC]
       physical id: 0
       bus info: pci@0000:03:00.0
       logical name: enp3s0
       version: 06
       serial: 90:2b:34:19:a8:7c
       size: 1Gbit/s
       capacity: 1Gbit/s
       width: 64 bits
       clock: 33MHz
       capabilities: bus_master cap_list ethernet physical tp mii 10bt 10bt-fd 100bt 100bt-fd 1000bt 1000bt-fd autonegotiation
       configuration: autonegotiation=on broadcast=yes driver=r8169 driverversion=2.3LK-NAPI duplex=full firmware=rtl8168e-3_0.0.4 03/27/12 ip=192.168.1.3 latency=0 link=yes multicast=yes port=MII speed=1Gbit/s
       resources: irq:31 ioport:1000(size=256) memory:f0404000-f0404fff memory:f0400000-f0403fff

The vendor and device ids are shown in the product line; in this example: `[10EC:8168]`,
where *10ec* and *8168* are the vendor and device ids respectively. The firmware version
is shown in the configuration line; in this example the firmware version is:
`rtl8168e-3_0.0.4 03/27/12`.

Below is an example of how to set the node info:

.. code-block::

   openstack baremetal node set $NODE_ID --extra nic_firmware='[{"vendor_id": "15B3", "device_id": "1013", "firmware_version": "12.20.1010"}]'

The hardware manager should work with any network card that supports returning
the firmware-version with `ethtool`.

In the case that you wish to disable the hardware manager for specific nodes,
you can set the following property in the nodes extra info:

.. code-block::

    openstack baremetal node set $NODE_ID --extra disable_nic_firmware_check=True

If you wish to re-enable the hardware manager, you can either unset the property, or
set it to `False`. For example:

.. code-block::

    openstack baremetal node unset $NODE_ID --extra disable_nic_firmware_check

known limitations:
^^^^^^^^^^^^^^^^^^^

* If a network card presents itself as multiple different interfaces, multiple
  failures will be reported for the same card. An example is an Mellanox ConnectX-4
  dual-port device:

    .. code-block::

        Bus info          Device     Class          Description
        =======================================================
        pci@0000:03:00.0  ib0        network        MT27700 Family [ConnectX-4]
        pci@0000:03:00.1  p3p2       network        MT27700 Family [ConnectX-4]

  The error will shown as:

    .. code-block::

        Clean step failed: Error performing clean_step verify_nic_firmware: Clean step failed: Found 2 firmware version mismatches when verifying NIC firmware. The errors were:
        Firmware version mismatch for card: ib0. The expected version was: 12.20.1019, but the actual version was 12.20.1010. The matcher that failed was {u'firmware_version': u'12.20.1019', u'vendor_id': u'15B3', u'device_id': u'1013'}
        Firmware version mismatch for card: p3p2. The expected version was: 12.20.1019, but the actual version was 12.20.1010. The matcher that failed was {u'firmware_version': u'12.20.1019', u'vendor_id': u'15B3', u'device_id': u'1013'}

* We don't currently discriminate based on the version of the card. There may be
  issues when cards have differing versions and do not use the same firmware.

Credits
-------

Based on the example hardware manager project by Jay Faulkner:

https://github.com/openstack/ipa-example-hardware-managers
