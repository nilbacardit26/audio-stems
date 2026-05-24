from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from audio_stems.web import (
    browse_payload,
    command_line,
    frontend_url,
    health_payload,
    payload_to_namespace,
    presets_payload,
    validate_run_inputs,
)


class WebApiTests(unittest.TestCase):
    def test_presets_payload_exposes_cli_presets(self) -> None:
        payload = presets_payload()
        names = [preset["name"] for preset in payload["presets"]]

        self.assertIn("demucs", names)
        self.assertIn("separator", names)
        self.assertIn("inst-hq", [model["alias"] for model in payload["separatorModels"]])

    def test_payload_to_namespace_builds_demucs_namespace(self) -> None:
        namespace = payload_to_namespace(
            {
                "inputs": ["~/song.wav"],
                "preset": "fast",
                "out": "separated",
                "device": "cpu",
                "format": "WAV",
            },
            dry_run=True,
        )

        self.assertEqual(namespace.preset, "fast")
        self.assertEqual(namespace.device, "cpu")
        self.assertEqual(namespace.inputs, [Path("~/song.wav").expanduser().resolve()])
        self.assertTrue(namespace.dry_run)

    def test_payload_to_namespace_resolves_separator_alias(self) -> None:
        namespace = payload_to_namespace(
            {
                "inputs": ["/tmp/song.wav"],
                "preset": "separator",
                "out": "separated",
                "device": "auto",
                "separatorModel": "inst-hq",
                "format": "FLAC",
            },
            dry_run=False,
        )

        self.assertEqual(namespace.separator_model, "UVR-MDX-NET-Inst_HQ_3.onnx")
        self.assertEqual(namespace.format, "FLAC")
        self.assertFalse(namespace.dry_run)

    def test_validate_run_inputs_rejects_missing_files(self) -> None:
        namespace = payload_to_namespace(
            {
                "inputs": ["/tmp/audio-stems-missing-file.wav"],
                "preset": "demucs",
                "out": "separated",
                "device": "auto",
            },
            dry_run=False,
        )

        self.assertEqual(
            validate_run_inputs(namespace),
            ["Input file not found: /tmp/audio-stems-missing-file.wav"],
        )

    def test_command_line_quotes_spaces(self) -> None:
        self.assertEqual(command_line(["demucs", "two words.wav"]), "+ demucs 'two words.wav'")

    def test_health_payload_identifies_app(self) -> None:
        self.assertEqual(health_payload(), {"app": "audio-stems", "status": "ok"})

    def test_frontend_url_uses_loopback_for_wildcard_host(self) -> None:
        self.assertEqual(frontend_url("0.0.0.0", 8765), "http://127.0.0.1:8765")

    def test_browse_payload_lists_folders_and_audio_files(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "album").mkdir()
            (root / "song.wav").touch()
            (root / "notes.txt").touch()

            payload = browse_payload(str(root))
            entries = {entry["name"]: entry for entry in payload["entries"]}

            self.assertEqual(payload["path"], str(root.resolve()))
            self.assertEqual(entries["album"]["kind"], "directory")
            self.assertEqual(entries["song.wav"]["kind"], "file")
            self.assertNotIn("notes.txt", entries)


if __name__ == "__main__":
    unittest.main()
