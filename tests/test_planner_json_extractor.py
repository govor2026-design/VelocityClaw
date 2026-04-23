import unittest

from velocity_claw.planner.planner import extract_json_payload


class PlannerJsonExtractorTests(unittest.TestCase):
    def test_plain_json(self):
        data = extract_json_payload('{"task":"x","steps":[]}')
        self.assertEqual(data["task"], "x")

    def test_markdown_fenced_json(self):
        raw = """
        ```json
        {"task":"x","steps":[]}
        ```
        """
        data = extract_json_payload(raw)
        self.assertEqual(data["task"], "x")

    def test_json_with_leading_text(self):
        raw = 'Here is the plan:\n{"task":"x","steps":[]}\nDone.'
        data = extract_json_payload(raw)
        self.assertEqual(data["task"], "x")


if __name__ == "__main__":
    unittest.main()
