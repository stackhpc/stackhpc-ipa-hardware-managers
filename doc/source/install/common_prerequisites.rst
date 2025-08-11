Prerequisites
-------------

Before you install and configure the TestService service,
you must create a database, service credentials, and API endpoints.

#. To create the database, complete these steps:

   * Use the database access client to connect to the database
     server as the ``root`` user:

     .. code-block:: console

        $ mysql -u root -p

   * Create the ``example_hardware_manager`` database:

     .. code-block:: none

        CREATE DATABASE example_hardware_manager;

   * Grant proper access to the ``example_hardware_manager`` database:

     .. code-block:: none

        GRANT ALL PRIVILEGES ON example_hardware_manager.* TO 'example_hardware_manager'@'localhost' \
          IDENTIFIED BY 'EXAMPLE_HARDWARE_MANAGER_DBPASS';
        GRANT ALL PRIVILEGES ON example_hardware_manager.* TO 'example_hardware_manager'@'%' \
          IDENTIFIED BY 'EXAMPLE_HARDWARE_MANAGER_DBPASS';

     Replace ``EXAMPLE_HARDWARE_MANAGER_DBPASS`` with a suitable password.

   * Exit the database access client.

     .. code-block:: none

        exit;

#. Source the ``admin`` credentials to gain access to
   admin-only CLI commands:

   .. code-block:: console

      $ . admin-openrc

#. To create the service credentials, complete these steps:

   * Create the ``example_hardware_manager`` user:

     .. code-block:: console

        $ openstack user create --domain default --password-prompt example_hardware_manager

   * Add the ``admin`` role to the ``example_hardware_manager`` user:

     .. code-block:: console

        $ openstack role add --project service --user example_hardware_manager admin

   * Create the example_hardware_manager service entities:

     .. code-block:: console

        $ openstack service create --name example_hardware_manager --description "TestService" testservice

#. Create the TestService service API endpoints:

   .. code-block:: console

      $ openstack endpoint create --region RegionOne \
        testservice public http://controller:XXXX/vY/%\(tenant_id\)s
      $ openstack endpoint create --region RegionOne \
        testservice internal http://controller:XXXX/vY/%\(tenant_id\)s
      $ openstack endpoint create --region RegionOne \
        testservice admin http://controller:XXXX/vY/%\(tenant_id\)s
