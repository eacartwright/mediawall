"""
A stand-in for Piper, for check_speech.py: takes Piper's arguments and
words (stdin), writes a short tone as the WAV, and logs the call (one
JSON line) to $FAKE_PIPER_LOG. Words containing FAIL fail; SLOW takes
five seconds (for Stop).
"""

import argparse
import json
import math
import os
import struct
import sys
import time
import wave

parser = argparse.ArgumentParser()
parser.add_argument("--model")
parser.add_argument("--output_file")
parser.add_argument("--length_scale", type=float, default=1.0)
parser.add_argument("--sentence_silence", type=float, default=0.0)
args = parser.parse_args()

text = sys.stdin.buffer.read().decode("utf-8").strip()

with open(os.environ["FAKE_PIPER_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({"text": text, "model": args.model, "out": args.output_file,
                          "length_scale": args.length_scale,
                          "sentence_silence": args.sentence_silence}) + "\n")

if "FAIL" in text:
    print("ERROR: the voice couldn't be loaded", file=sys.stderr)
    sys.exit(1)
if "SLOW" in text:
    time.sleep(5)

rate = 22050
frames = int(rate * max(0.3, 0.5 * len(text.split()) * args.length_scale))
with wave.open(args.output_file, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i * 0.06)))
                           for i in range(frames)))
