import io
import unittest

from PIL import Image

from parking_analysis import (
    AnalysisError, build_request, parse_response, prepare_image, render_result, validate_result,
)


def space(status="free", confidence=0.95, polygon=None):
    return {
        "status": status,
        "confidence": confidence,
        "polygon": polygon or [
            {"x": 100, "y": 100}, {"x": 300, "y": 100},
            {"x": 300, "y": 300}, {"x": 100, "y": 300},
        ],
    }


class ParkingAnalysisTests(unittest.TestCase):
    def test_uncertain_space_is_not_reported_free(self):
        result = validate_result({
            "scene_usable": True, "note": "", "spaces": [space(confidence=0.79)],
        })
        self.assertEqual(result.count("free"), 0)
        self.assertEqual(result.count("unknown"), 1)

    def test_unusable_scene_and_invalid_geometry_fail_closed(self):
        with self.assertRaises(AnalysisError):
            validate_result({"scene_usable": False, "note": "темно", "spaces": []})
        crossed = [{"x": 100, "y": 100}, {"x": 300, "y": 300},
                   {"x": 100, "y": 300}, {"x": 300, "y": 100}]
        with self.assertRaises(AnalysisError):
            validate_result({"scene_usable": True, "note": "", "spaces": [space(polygon=crossed)]})

    def test_prepared_frame_is_sent_without_response_storage_and_rendered(self):
        raw = io.BytesIO()
        Image.new("RGB", (2400, 1200), "white").save(raw, "JPEG")
        image = prepare_image(raw.getvalue())
        self.assertEqual(image.size, (1920, 960))

        request = build_request(image, "gpt-4.1-mini")
        self.assertIs(request["store"], False)
        self.assertEqual(request["input"][0]["content"][1]["detail"], "high")
        self.assertTrue(request["input"][0]["content"][1]["image_url"].startswith("data:image/jpeg;base64,"))

        analysis = validate_result({"scene_usable": True, "note": "", "spaces": [space()]})
        with Image.open(io.BytesIO(render_result(image, analysis))) as output:
            self.assertEqual(output.size, image.size)
            self.assertNotEqual(output.getpixel((192, 96)), (255, 255, 255))

    def test_incomplete_response_cannot_be_mistaken_for_zero_free_spaces(self):
        with self.assertRaises(AnalysisError):
            parse_response({"status": "incomplete", "output": []})


if __name__ == "__main__":
    unittest.main()
