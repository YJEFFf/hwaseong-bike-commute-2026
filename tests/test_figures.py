import pandas as pd
from shapely.geometry import LineString, box

from analysis.figures import fig1_disagreement, fig3_priority_links


def _tiny_frame():
    rows = [
        {"seg_id": 0, "origin": "official", "district": "동탄", "in_official_line": True,
         "in_official_poly": True, "in_osm": True, "stratum": "합의", "length_m": 20.0,
         "geometry": LineString([(0, 0), (20, 0)])},
        {"seg_id": 1, "origin": "official", "district": "만세", "in_official_line": True,
         "in_official_poly": False, "in_osm": False, "stratum": "공식단일", "length_m": 15.0,
         "geometry": LineString([(0, 100), (15, 100)])},
        {"seg_id": 2, "origin": "osm", "district": "동탄", "in_official_line": False,
         "in_official_poly": False, "in_osm": True, "stratum": "OSM단일", "length_m": 10.0,
         "geometry": LineString([(50, 50), (60, 50)])},
        {"seg_id": 3, "origin": "official", "district": "기타", "in_official_line": True,
         "in_official_poly": True, "in_osm": False, "stratum": "공식단일", "length_m": 5.0,
         "geometry": LineString([(200, 0), (205, 0)])},
    ]
    return pd.DataFrame(rows)


def test_fig1_disagreement_smoke(tmp_path):
    df = _tiny_frame()
    out_path = tmp_path / "fig1_map_disagreement.png"

    result = fig1_disagreement(df, out_path)

    assert out_path.exists()
    assert out_path.stat().st_size > 0
    assert str(result) == str(out_path)


def test_fig1_disagreement_handles_empty_stratum(tmp_path):
    # No "합의" rows at all -- must not crash on an empty stratum slice.
    df = _tiny_frame()
    df = df[df.stratum != "합의"].reset_index(drop=True)
    out_path = tmp_path / "fig1_no_agree.png"

    fig1_disagreement(df, out_path)

    assert out_path.exists() and out_path.stat().st_size > 0


def test_fig1_disagreement_with_admin_boundaries_and_dongtan_inset(tmp_path):
    # Exercises the admin-boundary overlay, scale bar, and 동탄 inset code path.
    df = _tiny_frame()
    admin_polys = [box(-5, -5, 65, 65), box(-5, 95, 20, 105)]
    admin_labels = ["동탄", "만세"]
    out_path = tmp_path / "fig1_with_admin.png"

    result = fig1_disagreement(df, out_path, admin_polys=admin_polys, admin_labels=admin_labels)

    assert out_path.exists() and out_path.stat().st_size > 0
    assert str(result) == str(out_path)


def test_fig1_disagreement_without_dongtan_in_admin_labels(tmp_path):
    # No "동탄" among admin_labels -- inset must be skipped, not crash.
    df = _tiny_frame()
    admin_polys = [box(-5, 95, 20, 105)]
    admin_labels = ["만세"]
    out_path = tmp_path / "fig1_no_dongtan.png"

    fig1_disagreement(df, out_path, admin_polys=admin_polys, admin_labels=admin_labels)

    assert out_path.exists() and out_path.stat().st_size > 0


def test_fig3_priority_links_smoke(tmp_path):
    network_lines = [LineString([(0, 0), (100, 0)]), LineString([(0, 0), (0, 100)])]
    region_polys = {1: box(-10, -10, 110, 110)}
    priority_df = pd.DataFrame({
        "cand_id": [0, 1],
        "region": [1, 1],
        "x1": [10.0, 20.0], "y1": [10.0, 20.0],
        "x2": [50.0, 60.0], "y2": [50.0, 60.0],
        "inclusion_reach": [0.6, 1.0],
    })
    out_path = tmp_path / "fig3.png"

    result = fig3_priority_links(network_lines, region_polys, priority_df, out_path)

    assert out_path.exists() and out_path.stat().st_size > 0
    assert str(result) == str(out_path)


def test_fig3_priority_links_handles_empty_priority_df(tmp_path):
    network_lines = [LineString([(0, 0), (100, 0)])]
    region_polys = {1: box(-10, -10, 110, 110)}
    priority_df = pd.DataFrame(columns=["cand_id", "region", "x1", "y1", "x2", "y2", "inclusion_reach"])
    out_path = tmp_path / "fig3_empty.png"

    fig3_priority_links(network_lines, region_polys, priority_df, out_path)

    assert out_path.exists() and out_path.stat().st_size > 0
