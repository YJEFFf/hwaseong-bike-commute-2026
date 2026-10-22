import json

from analysis.osm_roads import load_low_stress_lines

WAYS = {
    "elements": [
        {
            "type": "way",
            "id": 1,
            "tags": {"highway": "residential"},
            "geometry": [
                {"lat": 37.20, "lon": 126.83},
                {"lat": 37.201, "lon": 126.831},
            ],
        },
        {
            "type": "way",
            "id": 2,
            "tags": {"highway": "primary"},
            "geometry": [
                {"lat": 37.21, "lon": 126.84},
                {"lat": 37.211, "lon": 126.841},
            ],
        },
        {
            "type": "way",
            "id": 3,
            "tags": {"highway": "footway", "bicycle": "designated"},
            "geometry": [
                {"lat": 37.22, "lon": 126.85},
                {"lat": 37.221, "lon": 126.851},
            ],
        },
    ]
}


def test_load_low_stress_lines(tmp_path):
    p = tmp_path / "roads.json"
    p.write_text(json.dumps(WAYS), encoding="utf-8")

    lines = load_low_stress_lines(p)

    # residential + footway(bicycle=designated) pass; primary without a
    # bike facility does not.
    assert len(lines) == 2

    for line in lines:
        for x, y in line.coords:
            assert 150000 <= x <= 250000
            assert 450000 <= y <= 550000
