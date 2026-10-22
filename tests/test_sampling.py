import pandas as pd
from analysis.sampling import stratified_sample, cohen_kappa, wilson_ci

def test_stratified_sample_caps_and_is_reproducible():
    df = pd.DataFrame({"d": ["a"] * 30 + ["b"] * 5, "s": ["x"] * 35, "v": range(35)})
    s1 = stratified_sample(df, ["d", "s"], 10); s2 = stratified_sample(df, ["d", "s"], 10)
    assert s1.groupby("d").size().to_dict() == {"a": 10, "b": 5}
    assert list(s1.v) == list(s2.v)

def test_kappa_known_value():
    a = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    b = ["y"] * 20 + ["y"] * 5 + ["n"] * 10 + ["n"] * 15
    assert abs(cohen_kappa(a, b) - 0.4) < 1e-9

def test_wilson():
    lo, hi = wilson_ci(8, 10)
    assert 0.49 < lo < 0.50 and 0.94 < hi < 0.95
