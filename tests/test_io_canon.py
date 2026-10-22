import copy
from analysis.io_canon import canonical_hash

FC = {"type": "FeatureCollection", "timeStamp": "2026-09-14T16:40:58.582Z",
      "features": [{"type": "Feature", "id": "b", "properties": {"k": 1},
                    "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [1.00049, 2.0]]}},
                   {"type": "Feature", "id": "a", "properties": {"k": 2},
                    "geometry": {"type": "LineString", "coordinates": [[3.0, 3.0], [4.0, 4.0]]}}]}

def test_timestamp_and_order_do_not_change_hash():
    other = copy.deepcopy(FC)
    other["timeStamp"] = "2030-01-01T00:00:00Z"
    other["features"].reverse()
    assert canonical_hash(FC) == canonical_hash(other)

def test_sub_millimetre_noise_ignored_but_centimetre_change_detected():
    noisy = copy.deepcopy(FC); noisy["features"][0]["geometry"]["coordinates"][1][0] = 1.0004
    moved = copy.deepcopy(FC); moved["features"][0]["geometry"]["coordinates"][1][0] = 1.01
    assert canonical_hash(FC) == canonical_hash(noisy)
    assert canonical_hash(FC) != canonical_hash(moved)
