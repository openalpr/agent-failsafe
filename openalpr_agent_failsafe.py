#!/usr/bin/python3
import time
import logging
import os
import json
from argparse import ArgumentParser
from logging.handlers import RotatingFileHandler
import pytz
from datetime import datetime

logger = logging.getLogger('OpenALPR Agent Failsafe Log')

class OutageChecker():
    def __init__(self):
        self.tracked_cameras = {}
        self.INFO_FILE = '/var/lib/openalpr/openalpr_system_status.json'

    def get_now_epoch(self):
        epoch = datetime.utcfromtimestamp(0).replace(tzinfo=pytz.utc)
        return (datetime.now(tz=pytz.utc) - epoch).total_seconds()

    def reset(self):
        self.tracked_cameras = {}

    def tracked_camera_count(self):
        # Used by unit tests
        return len(self.tracked_cameras.items())

    def print_tracked_cameras(self):
        # Used for debugging
        logger.info(json.dumps(self.tracked_cameras,indent=2))

    def get_outage_seconds(self):
        try:

            if not os.path.isfile(self.INFO_FILE):
                logger.warning(f"Unable to find OpenALPR status file: {self.INFO_FILE} -- Skipping")
                return 0.0

            now_epoch = self.get_now_epoch()

            with open(self.INFO_FILE, 'r') as info_file:
                info_data = json.load(info_file)

                alpr_cameras = []
                for video_stream in info_data['video_streams']:
                    video_id = video_stream['camera_id']
                    fps = video_stream['fps']

                    # Consider the camera failed if the FPS is very low
                    currently_failed = fps < 1.0

                    alpr_cameras.append(video_id)
                    if video_id not in self.tracked_cameras:
                        self.tracked_cameras[video_id] = {'last_update': 0, 'is_failed': False, 'cumulative_outage': 0.0}

                    if currently_failed:
                        if self.tracked_cameras[video_id]['is_failed']:
                            # The camera was failed before and it's still failed.
                            # Add the delta time between now and last check to the cumulative outage time
                            self.tracked_cameras[video_id]['cumulative_outage'] += now_epoch - self.tracked_cameras[video_id]['last_update']
                            if self.tracked_cameras[video_id]['cumulative_outage'] < 0:
                                self.tracked_cameras[video_id]['cumulative_outage'] = 0
                        else:
                            # The camera is newly failed.  Set the flag to true and cumulative outage to 0
                            self.tracked_cameras[video_id]['is_failed'] = True
                            self.tracked_cameras[video_id]['cumulative_outage'] = 0.0
                    else:
                        # The camera is not failed now.  If it was failed before, it does not matter
                        self.tracked_cameras[video_id]['is_failed'] = False
                        self.tracked_cameras[video_id]['cumulative_outage'] = 0.0

                    self.tracked_cameras[video_id]['last_update'] = now_epoch

                # First delete any cameras that we are tracking that is NOT in the alpr list
                # We do not want to trigger a restart if, for example, the config was updated and a camera was removed
                for camera_id in list(self.tracked_cameras.keys()):
                    if camera_id not in alpr_cameras:
                        del self.tracked_cameras[camera_id]

                # Now iterate through the actively tracked cameras.  Return the highest outage value
                max_outage = 0.0
                for camera_id, tracked_cam in self.tracked_cameras.items():
                    if tracked_cam['is_failed']:
                        if tracked_cam['cumulative_outage'] > max_outage:
                            max_outage = tracked_cam['cumulative_outage']

                        if tracked_cam['cumulative_outage'] > 1.0:
                            logger.info(f"Tracking camera {camera_id} with {tracked_cam['cumulative_outage']:.2f}s outage")
                return max_outage

        except json.decoder.JSONDecodeError:
            logger.warning(f"Invalid JSON content.  Could not parse {self.INFO_FILE}")
            return 0.0

        except:
            logger.exception("Unable to check OpenALPR status.  Skipping")
            return 0.0

def restart_agent():
    logger.warning("Restarting OpenALPR Agent")
    os.system("service openalpr-daemon restart")


if __name__ == "__main__":

    parser = ArgumentParser(description='OpenALPR Agent Failsafe Daemon')


    parser.add_argument('-f', '--foreground', action='store_true', default=False,
                        help="Run the daemon program in the foreground.  Default=false")

    parser.add_argument('-l', '--log', action='store', default='/var/log/openalpr_agent_failsafe.log',
                        help="log file for daemon process")

    parser.add_argument('-m', '--max_time_restart_seconds', type=int, action='store', default=10,
                        help="The maximum amount of time to allow 0 FPS connections before restarting the agent")

    options = parser.parse_args()


    logger.setLevel(logging.DEBUG)

    if options.foreground:
        handler = logging.StreamHandler()
        logger.addHandler(handler)
    else:
        # Setup the logging

        # add a rotating file handler
        handler = RotatingFileHandler(options.log, maxBytes=20 * 1024 * 1024,
                                      backupCount=3)

        fmt = logging.Formatter("%(asctime)-15s %(thread)d: %(message)s", datefmt='%Y-%m-%dT%H:%M:%S')
        handler.setFormatter(fmt)

        logger.addHandler(handler)


    logger.info("Script initialized")

    oc = OutageChecker()

    while True:
        try:
            outage_seconds = oc.get_outage_seconds()

            if outage_seconds > options.max_time_restart_seconds:
                logger.warning(f"Restarting agent due to outage of {outage_seconds}")
                restart_agent()

                # Wait longer for agent to initialize
                logger.info("Waiting 20 seconds after agent restart")
                time.sleep(20.0)
                oc.reset()


            time.sleep(1.0)

        except KeyboardInterrupt:
            raise
        except:
            time.sleep(1.0)
            logger.error("Exception in failsafe check loop")


    logger.info("Script complete.  Shutting down")

