#!/usr/bin/python3
import unittest
from openalpr_agent_failsafe import OutageChecker
import logging
import os
import json
import time
import copy

TEMP_FOLDER = '/tmp/'
TEMP_JSON = os.path.join(TEMP_FOLDER, 'failsafe_test.json')

JSON_TEMPLATE = {
   "agent_hostname" : "mhill-gpulap",
   "agent_type" : "alprd",
   "openalpr_version" : "2.8.101",
   "system_uptime_seconds" : 514018,
    "daemon_uptime_seconds" : 600,
   "timestamp" : 1611078298405,
   "video_streams" : [
      {
         "camera_id" : 1234,
         "camera_name" : "cameraA",
         "fps" : 29.6666660308838,
         "is_streaming" : True,
         "last_plate_read" : 1611078296652,
         "last_update" : 1611078298380,
         "total_plate_reads" : 1,
         "url" : "camera1url"
      },
       {
           "camera_id": 5678,
           "camera_name": "cameraB",
           "fps": 29.6666660308838,
           "is_streaming": True,
           "last_plate_read": 1611078296652,
           "last_update": 1611078298380,
           "total_plate_reads": 1,
           "url": "camera2url"
       },
   ]
}

SLEEP_STEP_TIME = 0.05
MIN_AGENT_UPTIME = 300

logger = logging.getLogger('OpenALPR Agent Failsafe Log')

def write_file(json_content, output_file):
    with open(output_file, 'w') as outf:
        json.dump(json_content, outf)

def set_fps(camera_1_fps, camera_2_fps, json_content, write_to_file=True):
    json_content['video_streams'][0]['fps'] = camera_1_fps
    json_content['video_streams'][1]['fps'] = camera_2_fps

    if write_to_file:
        write_file(json_content, TEMP_JSON)

    return json_content


def backwards_time_epoch_func():
    # Jumps time backwards by 500 seconds
    from datetime import datetime
    import pytz
    epoch = datetime.utcfromtimestamp(0).replace(tzinfo=pytz.utc)
    return (datetime.now(tz=pytz.utc) - epoch).total_seconds() - 500

def forwards_time_epoch_func():
    # Jumps time backwards by 500 seconds
    from datetime import datetime
    import pytz
    epoch = datetime.utcfromtimestamp(0).replace(tzinfo=pytz.utc)
    return (datetime.now(tz=pytz.utc) - epoch).total_seconds() + 500

class TestOutageChecker(unittest.TestCase):

    def test_missing_file(self):
        test_checker = OutageChecker(MIN_AGENT_UPTIME)
        test_checker.INFO_FILE = '/bogus/file/doesnot/exist'

        # if the file doesn't exist, don't report an outage
        self.assertEqual(test_checker.get_outage_seconds(), 0)


    def test_bad_file_content(self):
        test_checker = OutageChecker(MIN_AGENT_UPTIME)
        test_checker.INFO_FILE = TEMP_JSON

        with open(TEMP_JSON, 'w') as outf:
            outf.write("{badjson,data}")

        self.assertEqual(test_checker.get_outage_seconds(), 0)


    def test_timeout_good_to_bad(self):
        # Cameras start connected then fail

        test_checker = OutageChecker(MIN_AGENT_UPTIME)
        test_checker.INFO_FILE = TEMP_JSON

        json_data = copy.deepcopy(JSON_TEMPLATE)
        json_data = set_fps(25.0, 25.0, json_data)

        self.assertEqual(test_checker.get_outage_seconds(), 0)

        json_data = set_fps(0.5, 25.0, json_data)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME)

        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME*2)

        json_data = set_fps(25.0, 25.0, json_data)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)

        time.sleep(SLEEP_STEP_TIME)

        json_data = set_fps(25.0, 0.0, json_data)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)

        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME)

    def test_timeout_bad_to_good(self):
        test_checker = OutageChecker(MIN_AGENT_UPTIME)
        test_checker.INFO_FILE = TEMP_JSON

        json_data = copy.deepcopy(JSON_TEMPLATE)
        json_data = set_fps(0.0, 0.0, json_data)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)

        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME)

        json_data = set_fps(0.0, 25.0, json_data)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME*2)

        json_data = set_fps(0.0, 0.0, json_data)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME*2)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME*3)

        # One camera recovers and the other is still failing
        json_data = set_fps(25.0, 0.0, json_data)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME*2)
        self.assertLess(test_checker.get_outage_seconds(), SLEEP_STEP_TIME*3)

        json_data = set_fps(5.0, 5.0, json_data)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)


    def test_reset(self):
        test_checker = OutageChecker(MIN_AGENT_UPTIME)
        test_checker.INFO_FILE = TEMP_JSON

        json_data = copy.deepcopy(JSON_TEMPLATE)
        json_data = set_fps(0.0, 0.0, json_data)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)

        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME)

        json_data = set_fps(0.0, 25.0, json_data)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME*2)

        test_checker.reset()
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)

        time.sleep(SLEEP_STEP_TIME)
        json_data = set_fps(0.0, 0.0, json_data)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME)
        self.assertLess(test_checker.get_outage_seconds(), SLEEP_STEP_TIME*2)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME*2)
        self.assertLess(test_checker.get_outage_seconds(), SLEEP_STEP_TIME*3)


    def test_removing_and_adding_camera(self):
        test_checker = OutageChecker(MIN_AGENT_UPTIME)
        test_checker.INFO_FILE = TEMP_JSON

        json_data = copy.deepcopy(JSON_TEMPLATE)
        json_data = set_fps(25.0, 0.0, json_data)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)
        self.assertEqual(test_checker.tracked_camera_count(), 2)

        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME)
        self.assertEqual(test_checker.tracked_camera_count(), 2)

        single_camera = copy.deepcopy(json_data)
        single_camera['video_streams'].pop()
        write_file(single_camera, TEMP_JSON)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)
        self.assertEqual(test_checker.tracked_camera_count(), 1)

        single_camera['video_streams'][0]['fps'] = 0.0
        write_file(single_camera, TEMP_JSON)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME)
        self.assertEqual(test_checker.tracked_camera_count(), 1)


        json_data = set_fps(25.0, 25.0, json_data)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)
        self.assertEqual(test_checker.tracked_camera_count(), 2)

        json_data = set_fps(25.0, 0.0, json_data)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)
        self.assertEqual(test_checker.tracked_camera_count(), 2)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME)
        self.assertEqual(test_checker.tracked_camera_count(), 2)


    def test_backwards_time_jump(self):

        test_checker = OutageChecker(MIN_AGENT_UPTIME)
        test_checker.INFO_FILE = TEMP_JSON

        json_data = copy.deepcopy(JSON_TEMPLATE)
        json_data = set_fps(0.0, 25.0, json_data)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)
        self.assertEqual(test_checker.tracked_camera_count(), 2)

        test_checker.get_now_epoch = backwards_time_epoch_func

        json_data = set_fps(0.0, 25.0, json_data)
        time.sleep(SLEEP_STEP_TIME)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)
        self.assertEqual(test_checker.tracked_camera_count(), 2)

        json_data = set_fps(0.0, 25.0, json_data)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME)
        self.assertEqual(test_checker.tracked_camera_count(), 2)

        json_data = set_fps(0.0, 25.0, json_data)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME*2)
        self.assertEqual(test_checker.tracked_camera_count(), 2)

        json_data = set_fps(25.0, 25.0, json_data)
        time.sleep(SLEEP_STEP_TIME)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)
        self.assertEqual(test_checker.tracked_camera_count(), 2)


    def test_forward_time_jump(self):

        test_checker = OutageChecker(MIN_AGENT_UPTIME)
        test_checker.INFO_FILE = TEMP_JSON

        json_data = copy.deepcopy(JSON_TEMPLATE)
        json_data = set_fps(0.0, 25.0, json_data)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)
        self.assertEqual(test_checker.tracked_camera_count(), 2)

        test_checker.get_now_epoch = forwards_time_epoch_func

        json_data = set_fps(0.0, 25.0, json_data)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME)
        self.assertEqual(test_checker.tracked_camera_count(), 2)

        json_data = set_fps(25.0, 25.0, json_data)
        time.sleep(SLEEP_STEP_TIME)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)
        self.assertEqual(test_checker.tracked_camera_count(), 2)

    def test_daemon_uptime(self):
        # Cameras start connected then fail

        test_checker = OutageChecker(MIN_AGENT_UPTIME)
        test_checker.INFO_FILE = TEMP_JSON

        json_data = copy.deepcopy(JSON_TEMPLATE)
        json_data = set_fps(25.0, 25.0, json_data)

        self.assertEqual(test_checker.get_outage_seconds(), 0)

        json_data = set_fps(0.0, 25.0, json_data)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME)

        low_uptime = copy.deepcopy(json_data)
        low_uptime['daemon_uptime_seconds'] = 250
        write_file(low_uptime, TEMP_JSON)
        self.assertAlmostEqual(test_checker.get_outage_seconds(), 0.0, 3)

        json_data = set_fps(0.0, 25.0, json_data)
        time.sleep(SLEEP_STEP_TIME)
        self.assertGreaterEqual(test_checker.get_outage_seconds(), SLEEP_STEP_TIME)

if __name__ == '__main__':
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    unittest.main()