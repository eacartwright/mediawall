import unittest

from core.media_cost import (
    HW_SOFTWARE,
    classify_log_line,
    estimate_bytes,
    format_bytes,
    hw_choices,
    hw_env_value,
    hw_mode_from_env,
    parse_gpu_memory,
    parse_process_memory,
)


class EstimateTests(unittest.TestCase):

    def test_image_with_mipmaps(self):
        self.assertEqual(estimate_bytes("image", 1000, 1000, mipmap=False), 4_000_000)
        self.assertEqual(estimate_bytes("image", 1000, 1000), 5_333_333)

    def test_hardware_video_costs_far_more_than_software(self):
        hw = estimate_bytes("video", 1920, 1080, hardware=True)
        sw = estimate_bytes("video", 1920, 1080, hardware=False)
        self.assertEqual(sw, 1920 * 1080 * 4)
        self.assertGreater(hw, 5 * sw)

    def test_nothing_for_audio_or_unknown_size(self):
        self.assertEqual(estimate_bytes("audio", 1920, 1080), 0)
        self.assertEqual(estimate_bytes("none", 1920, 1080), 0)
        self.assertEqual(estimate_bytes("image", 0, 1080), 0)

    def test_format(self):
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(1536), "1.5 KB")
        self.assertEqual(format_bytes(128 * 1024 * 1024), "128.0 MB")
        self.assertEqual(format_bytes(3 * 1024 ** 3), "3.00 GB")


class HardwareDecodingTests(unittest.TestCase):

    def test_choices_per_platform(self):
        linux = [v for v, _ in hw_choices("linux")]
        self.assertIn("vaapi", linux)
        self.assertIn(HW_SOFTWARE, linux)
        self.assertIn("d3d11va", [v for v, _ in hw_choices("win32")])

    def test_env_value(self):
        self.assertIsNone(hw_env_value("auto"))
        self.assertIsNone(hw_env_value(""))
        self.assertEqual(hw_env_value(HW_SOFTWARE), ",")
        self.assertEqual(hw_env_value("cuda"), "cuda")

    def test_mode_from_env(self):
        self.assertIsNone(hw_mode_from_env(None))
        self.assertEqual(hw_mode_from_env(","), HW_SOFTWARE)
        self.assertEqual(hw_mode_from_env(""), HW_SOFTWARE)
        self.assertEqual(hw_mode_from_env(" vaapi "), "vaapi")


class LogLineTests(unittest.TestCase):

    def test_the_reported_lines(self):
        self.assertEqual(classify_log_line(
            "[AVHWDeviceContext @ 0x25587040] cu->cuMemAlloc(&data, size) failed "
            "-> CUDA_ERROR_OUT_OF_MEMORY: out of memory"), "oom")
        self.assertEqual(classify_log_line(
            "[h264 @ 0x28517300] Failed setup for format cuda: hwaccel "
            "initialisation returned error."), "fallback")
        self.assertIsNone(classify_log_line("[info] Using Qt multimedia with FFmpeg"))


class NvidiaSmiTests(unittest.TestCase):

    def test_gpu_memory(self):
        self.assertEqual(parse_gpu_memory("7900, 8192\n"),
                         (7900 * 1024 ** 2, 8192 * 1024 ** 2))
        self.assertIsNone(parse_gpu_memory(""))
        self.assertIsNone(parse_gpu_memory("[N/A], [N/A]"))

    def test_process_memory(self):
        text = "1234, 300\n555, 1000\n1234, 200\n"
        self.assertEqual(parse_process_memory(text, 1234), 500 * 1024 ** 2)
        self.assertIsNone(parse_process_memory(text, 42))
        self.assertIsNone(parse_process_memory("1234, [N/A]", 1234))


if __name__ == "__main__":
    unittest.main()
