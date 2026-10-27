import numpy as np
from netra.eval import metrics as m

def test_brier_perfect():
    y = np.array([0, 1, 1, 0]); assert m.brier(y, y.astype(float)) == 0.0

def test_wilson_bounds():
    lo, hi = m.wilson_interval(8, 10); assert 0 <= lo < 0.8 < hi <= 1
