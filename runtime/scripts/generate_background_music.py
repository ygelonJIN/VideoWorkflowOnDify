#!/usr/bin/env python3
import argparse
import math
import random
import struct
import wave
from pathlib import Path


SAMPLE_RATE = 44100


def envelope(t, attack, release, duration):
    if t < attack:
        return t / attack
    if t > duration - release:
        return max(0.0, (duration - t) / release)
    return 1.0


def synth_tone(t, frequencies, amplitude, detune=0.0):
    value = 0.0
    for index, frequency in enumerate(frequencies):
        phase = 2 * math.pi * frequency * (1 + detune * (index - 1)) * t
        value += math.sin(phase) * (0.72 ** index)
    return amplitude * value / max(1, len(frequencies))


def generate(destination: Path):
    duration = 30.0
    total = int(SAMPLE_RATE * duration)
    left = [0.0] * total
    right = [0.0] * total
    rng = random.Random(20261023)

    chords = [
        [220.00, 261.63, 329.63],
        [174.61, 220.00, 261.63],
        [196.00, 261.63, 329.63],
        [196.00, 246.94, 293.66],
        [220.00, 261.63, 329.63],
        [174.61, 220.00, 261.63],
        [196.00, 261.63, 329.63],
        [196.00, 246.94, 293.66],
        [220.00, 261.63, 329.63],
        [174.61, 220.00, 261.63],
    ]
    bpm = 80
    beat = 60 / bpm
    bar = beat * 4

    for bar_index, chord in enumerate(chords):
        start = int(bar_index * bar * SAMPLE_RATE)
        bar_samples = int(bar * SAMPLE_RATE)
        bass_frequency = chord[0] / 2
        for offset in range(bar_samples):
            index = start + offset
            if index >= total:
                break
            t = offset / SAMPLE_RATE
            pad = synth_tone(t, chord, 0.105, detune=0.0015) * envelope(t, 0.35, 0.55, bar)
            bass = math.sin(2 * math.pi * bass_frequency * t) * 0.12 * envelope(t, 0.035, 0.25, bar)
            shimmer = math.sin(2 * math.pi * chord[-1] * 2 * t) * 0.012
            value = pad + bass + shimmer
            left[index] += value * (1.0 + 0.035 * math.sin(2 * math.pi * 0.11 * t))
            right[index] += value * (1.0 - 0.035 * math.sin(2 * math.pi * 0.11 * t))

        for step in range(8):
            note_time = bar_index * bar + step * beat / 2
            start_index = int(note_time * SAMPLE_RATE)
            frequency = chord[step % len(chord)] * (2 if step in {2, 6} else 1)
            note_duration = 0.42
            note_samples = int(note_duration * SAMPLE_RATE)
            for offset in range(note_samples):
                index = start_index + offset
                if index >= total:
                    break
                t = offset / SAMPLE_RATE
                decay = math.exp(-7.0 * t)
                note = math.sin(2 * math.pi * frequency * t) * 0.042 * decay
                left[index] += note * 0.92
                right[index] += note * 1.08

        for beat_index in range(4):
            kick_time = bar_index * bar + beat_index * beat
            kick_start = int(kick_time * SAMPLE_RATE)
            kick_samples = int(0.19 * SAMPLE_RATE)
            for offset in range(kick_samples):
                index = kick_start + offset
                if index >= total:
                    break
                t = offset / SAMPLE_RATE
                frequency = 78 - 36 * min(1.0, t / 0.12)
                kick = math.sin(2 * math.pi * frequency * t) * 0.11 * math.exp(-13 * t)
                left[index] += kick
                right[index] += kick

            for half in (0, 1):
                hat_time = kick_time + half * beat / 2
                hat_start = int(hat_time * SAMPLE_RATE)
                hat_samples = int(0.045 * SAMPLE_RATE)
                for offset in range(hat_samples):
                    index = hat_start + offset
                    if index >= total:
                        break
                    t = offset / SAMPLE_RATE
                    noise = rng.uniform(-1, 1) * 0.018 * math.exp(-45 * t)
                    left[index] += noise
                    right[index] += noise * 0.82

    fade_samples = int(1.2 * SAMPLE_RATE)
    peak = max(max(abs(v) for v in left), max(abs(v) for v in right), 1e-9)
    scale = 0.72 / peak
    frames = bytearray()
    for index in range(total):
        fade = 1.0
        if index < fade_samples:
            fade = index / fade_samples
        elif index > total - fade_samples:
            fade = (total - index) / fade_samples
        sample_left = max(-1.0, min(1.0, left[index] * scale * fade))
        sample_right = max(-1.0, min(1.0, right[index] * scale * fade))
        frames.extend(struct.pack("<hh", int(sample_left * 32767), int(sample_right * 32767)))

    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(frames)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("媒体/背景音乐.wav"))
    args = parser.parse_args()
    generate(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
