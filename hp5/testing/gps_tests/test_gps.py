import unittest
import time
from hp5.utils.gps_utils import GPSReader

class TestGPSReader(unittest.TestCase):
    def setUp(self):
        self.reader = GPSReader()
        self.reader.start()
        time.sleep(2)  # дать время на запуск потока

    def tearDown(self):
        self.reader.stop()

    def test_gps_data_received(self):
        gps_data = self.reader.get_data()
        print("GPS DATA:", gps_data)
        self.assertIsNotNone(gps_data, "GPS data should not be None")
        self.assertIn('lat', gps_data, "GPS data should include latitude")
        self.assertIn('lon', gps_data, "GPS data should include longitude")

if __name__ == '__main__':
    unittest.main()
