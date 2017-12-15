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

Credits
-------

Based on the example hardware manager project by Jay Faulkner:

https://github.com/openstack/ipa-example-hardware-managers
