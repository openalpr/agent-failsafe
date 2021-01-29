openalpr-agent-failsafe
============================

This Python process watches the alprd process "Video FPS" to see if it drops to 0 for a long period.  If this occurs and the agent does not auto-restart, this service will restart the agent process.

Install Notes
---------------

    sudo apt-get update
    sudo dpkg -i openalpr-agent-failsafe.deb
    sudo apt-get install -f -y

The default timeout before restarting OpenALPR is 15 seconds.  You can modify this by editing /etc/init.d/openalpr-agent-failsafe

The service can be restarted with: 

    sudo /etc/init.d/openalpr-agent-failsafe restart

Logs are stored in /var/log/openalpr_agent_failsafe.log

To run manually (to test), run:

    sudo /usr/share/openalpr-agent-failsafe/openalpr_agent_failsafe.py -f --max_time_restart_seconds 15


Unit tests are in the tests.py file