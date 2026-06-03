from mic_tester_raspberry_pi import classify_signal, compute_audio_levels


def pcm16(samples):
    return b"".join(int(sample).to_bytes(2, "little", signed=True) for sample in samples)


def test_silence_levels():
    rms, peak = compute_audio_levels(pcm16([0] * 400))
    assert rms == 0.0
    assert peak == 0.0
    assert classify_signal(rms, peak) == "Mostly silence"


def test_clear_voice_like_signal():
    rms, peak = compute_audio_levels(pcm16([0, 2000, -2000, 6000, -6000] * 100))
    assert rms > 5.0
    assert peak > 10.0
    assert classify_signal(rms, peak) == "Clear signal detected"


def test_weak_signal():
    rms, peak = compute_audio_levels(pcm16([0, 700, -700, 1000, -1000] * 100))
    assert rms > 0.0
    assert peak > 0.0
    assert classify_signal(rms, peak) == "Weak signal detected"


if __name__ == "__main__":
    test_silence_levels()
    test_clear_voice_like_signal()
    test_weak_signal()
    print("mic tester logic tests passed")
