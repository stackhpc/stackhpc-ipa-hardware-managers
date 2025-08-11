2. Edit the ``/etc/example_hardware_manager/example_hardware_manager.conf`` file and complete the following
   actions:

   * In the ``[database]`` section, configure database access:

     .. code-block:: ini

        [database]
        ...
        connection = mysql+pymysql://example_hardware_manager:EXAMPLE_HARDWARE_MANAGER_DBPASS@controller/example_hardware_manager
