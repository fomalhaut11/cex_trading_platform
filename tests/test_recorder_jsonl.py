import json
import tempfile
import unittest
from pathlib import Path

from cex_quant.recorder import (
    JsonLinesReader,
    JsonLinesRecorder,
    RecorderError,
    RecorderErrorCode,
    ReplayResult,
    encode_event,
    replay,
)
from tests.test_recorder_codec import canonical_events


class CollectingSink:
    def __init__(self) -> None:
        self.events: list[object] = []

    def on_event(self, event: object) -> None:
        self.events.append(event)


class FailingReader:
    def read(self):  # type: ignore[no-untyped-def]
        raise AssertionError("reader must not be advanced")
        yield


class JsonLinesRecorderTests(unittest.TestCase):
    def test_append_reopen_read_and_replay_preserve_order(self) -> None:
        events = canonical_events()[:3]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            with JsonLinesRecorder(path) as recorder:
                results = [
                    recorder.append(event)  # type: ignore[arg-type]
                    for event in events
                ]
            with JsonLinesRecorder(path) as recorder:
                recorder.append(events[0])  # type: ignore[arg-type]

            expected = (*events, events[0])
            self.assertEqual(tuple(JsonLinesReader(path).read()), expected)
            self.assertEqual(results[0].offset, 0)
            self.assertEqual(
                results[1].offset,
                results[0].offset + results[0].byte_length,
            )

            sink = CollectingSink()
            result = replay(JsonLinesReader(path), sink)
            self.assertEqual(result, ReplayResult(event_count=4))
            self.assertEqual(tuple(sink.events), expected)

    def test_record_size_is_bounded_before_append(self) -> None:
        event = canonical_events()[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            with (
                JsonLinesRecorder(path, max_record_bytes=16) as recorder,
                self.assertRaises(RecorderError) as caught,
            ):
                recorder.append(event)  # type: ignore[arg-type]
            self.assertEqual(caught.exception.code, RecorderErrorCode.RECORD_TOO_LARGE)
            self.assertEqual(path.read_bytes(), b"")

    def test_truncated_last_record_fails_explicitly(self) -> None:
        event = canonical_events()[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_bytes(encode_event(event))  # type: ignore[arg-type]
            with self.assertRaises(RecorderError) as caught:
                tuple(JsonLinesReader(path).read())
            self.assertEqual(caught.exception.code, RecorderErrorCode.TRUNCATED_RECORD)
            self.assertEqual(caught.exception.line_number, 1)

    def test_checksum_failure_is_typed_and_stops_at_corrupt_line(self) -> None:
        first, second = canonical_events()[:2]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            first_record = encode_event(first)  # type: ignore[arg-type]
            raw = json.loads(encode_event(second))  # type: ignore[arg-type]
            raw["payload"]["metadata"]["event_time_ns"] += 1
            corrupt = json.dumps(raw, separators=(",", ":"), sort_keys=True).encode()
            path.write_bytes(first_record + b"\n" + corrupt + b"\n")

            reader = iter(JsonLinesReader(path).read())
            self.assertEqual(next(reader), first)
            with self.assertRaises(RecorderError) as caught:
                next(reader)
            self.assertEqual(
                caught.exception.code,
                RecorderErrorCode.CHECKSUM_MISMATCH,
            )
            self.assertEqual(caught.exception.line_number, 2)

    def test_reader_rejects_overlong_line_with_bounded_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_bytes(b"x" * 33 + b"\n")
            with self.assertRaises(RecorderError) as caught:
                tuple(JsonLinesReader(path, max_record_bytes=32).read())
            self.assertEqual(caught.exception.code, RecorderErrorCode.RECORD_TOO_LARGE)

    def test_replay_limit_and_invalid_limit(self) -> None:
        events = canonical_events()[:3]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            with JsonLinesRecorder(path) as recorder:
                for event in events:
                    recorder.append(event)  # type: ignore[arg-type]
            sink = CollectingSink()
            self.assertEqual(
                replay(JsonLinesReader(path), sink, max_events=2),
                ReplayResult(event_count=2),
            )
            self.assertEqual(tuple(sink.events), events[:2])
        with self.assertRaises(ValueError):
            replay(JsonLinesReader(Path("unused")), CollectingSink(), max_events=-1)
        self.assertEqual(
            replay(FailingReader(), CollectingSink(), max_events=0),
            ReplayResult(event_count=0),
        )

    def test_missing_parent_is_rejected_without_creating_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing" / "events.jsonl"
            with self.assertRaises(ValueError):
                JsonLinesRecorder(path)
            self.assertFalse(path.parent.exists())


if __name__ == "__main__":
    unittest.main()
