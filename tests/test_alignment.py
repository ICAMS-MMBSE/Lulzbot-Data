"""Time alignment for OctoPrint-vs-sensor comparison."""
from sensor_service.validation.alignment import AlignedPair, Sample, SampleBuffer, align


def make_buffer(samples, horizon=15.0):
    buf = SampleBuffer(horizon_s=horizon)
    for t, v in samples:
        buf.append(Sample(t=t, value=v))
    return buf


def test_nearest_picks_closest():
    buf = make_buffer([(1.0, 10.0), (2.0, 20.0), (3.0, 30.0)])
    sample, gap = buf.nearest(2.2)
    assert sample.value == 20.0
    assert abs(gap - 0.2) < 1e-9


def test_nearest_on_empty():
    assert SampleBuffer().nearest(1.0) is None


def test_align_within_gap():
    buf = make_buffer([(100.0, 5.1)])
    pair = align(buf, ref_t=100.3, ref_value=5.0, max_gap_s=0.5)
    assert isinstance(pair, AlignedPair)
    assert abs(pair.residual - 0.1) < 1e-9  # measured 5.1 - commanded 5.0


def test_align_rejects_large_gap():
    buf = make_buffer([(100.0, 5.1)])
    assert align(buf, ref_t=101.0, ref_value=5.0, max_gap_s=0.5) is None


def test_residual_sign_convention():
    buf = make_buffer([(10.0, 4.0)])
    pair = align(buf, 10.0, 5.0, 0.5)
    assert pair.residual == -1.0  # sensor reads low => negative


def test_buffer_prunes_old_samples():
    buf = make_buffer([(0.0, 1.0), (1.0, 2.0), (100.0, 3.0)], horizon=15.0)
    assert len(buf) == 1  # first two fell off the horizon
    sample, _ = buf.nearest(0.0)
    assert sample.value == 3.0


def test_out_of_order_insertion():
    buf = make_buffer([(1.0, 10.0), (3.0, 30.0), (2.0, 20.0)])
    sample, gap = buf.nearest(2.1)
    assert sample.value == 20.0
