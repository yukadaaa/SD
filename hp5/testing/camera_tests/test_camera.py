import unittest
from hp5.utils.camera import CameraHandler

class TestCameraHandler(unittest.TestCase):
    def setUp(self):
        self.camera = CameraHandler()

    def test_camera_capture(self):
        frame = self.camera.capture()
        print("Captured Frame:", type(frame))
        self.assertIsNotNone(frame, "Frame should not be None")
        self.assertGreater(len(frame), 0, "Frame should contain data")

if __name__ == '__main__':
    unittest.main()
