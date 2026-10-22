from shapely import STRtree
from shapely.geometry import LineString, Point, box
from analysis.agreement import split_line, label_segments, district_for_point


def test_split_line_lengths():
    parts = split_line(LineString([(0, 0), (100, 0)]), 20.0)
    assert len(parts) == 5 and abs(sum(p.length for p in parts) - 100) < 1e-6


def test_split_line_last_piece_shorter_and_no_zero_length_pieces():
    parts = split_line(LineString([(0, 0), (105, 0)]), 20.0)
    assert len(parts) == 6
    assert abs(parts[-1].length - 5.0) < 1e-6
    assert all(p.length > 0 for p in parts)
    assert abs(sum(p.length for p in parts) - 105) < 1e-6


def test_labels():
    off = [LineString([(0, 0), (100, 0)])]
    osm = [LineString([(0, 3), (60, 3)]), LineString([(0, 500), (40, 500)])]
    polys = [box(0, -2, 100, 2)]
    df = label_segments(off, polys, osm)
    off_rows = df[df.origin == "official"]
    assert set(off_rows[off_rows.geometry.apply(lambda g: g.centroid.x) < 60].stratum) == {"합의"}
    assert set(off_rows[off_rows.geometry.apply(lambda g: g.centroid.x) > 70].stratum) == {"공식단일"}
    assert set(df[(df.origin == "osm") & ~df.in_official_line & ~df.in_official_poly].stratum) == {"OSM단일"}
    assert len(df[(df.origin == "osm") & (df.stratum == "합의")]) == 0   # 합의 구간은 공식 쪽에서만 센다


def test_label_segments_columns_exact():
    off = [LineString([(0, 0), (100, 0)])]
    osm = [LineString([(0, 3), (60, 3)])]
    df = label_segments(off, [], osm)
    assert list(df.columns) == [
        "seg_id", "origin", "district", "in_official_line", "in_official_poly",
        "in_osm", "stratum", "length_m", "geometry",
    ]


def test_district_containment_and_outside_fallback():
    # Two adjacent district squares: A = [0,100]x[0,100], B = [100,200]x[0,100].
    admin_polys = [box(0, 0, 100, 100), box(100, 0, 200, 100)]
    admin_labels = ["A", "B"]

    seg_in_a = LineString([(10, 50), (30, 50)])          # midpoint (20,50) -- inside A
    seg_100m_out = LineString([(298, 50), (302, 50)])    # midpoint (300,50) -- 100m past B's edge (200)
    seg_500m_out = LineString([(698, 50), (702, 50)])    # midpoint (700,50) -- 500m past B's edge (200)

    df = label_segments([seg_in_a, seg_100m_out, seg_500m_out], [], [],
                         admin_polys=admin_polys, admin_labels=admin_labels,
                         outside_threshold=200.0)

    by_seg = dict(zip(df.seg_id, df.district))
    assert by_seg[0] == "A"
    assert by_seg[1] == "B"       # within outside_threshold of nearest (B) -> assigned
    assert by_seg[2] == "화성외"  # beyond outside_threshold -> outside


def test_district_for_point_containment_and_outside_fallback():
    # Same two adjacent district squares as test_district_containment_and_outside_fallback,
    # but exercised directly with points (no segment/midpoint indirection) -- this is the
    # point-based wrapper Task 5b (sample_frames.cluster_representatives, island_gap/
    # placeholder rows) uses directly instead of duplicating district assignment logic.
    admin_polys = [box(0, 0, 100, 100), box(100, 0, 200, 100)]
    admin_labels = ["A", "B"]
    tree = STRtree(admin_polys)

    assert district_for_point(Point(20, 50), tree, admin_polys, admin_labels) == "A"
    assert district_for_point(Point(300, 50), tree, admin_polys, admin_labels,
                               outside_threshold=200.0) == "B"
    assert district_for_point(Point(700, 50), tree, admin_polys, admin_labels,
                               outside_threshold=200.0) == "화성외"
    assert district_for_point(Point(20, 50), None, admin_polys, admin_labels) is None


def test_district_none_when_admin_polys_not_given():
    off = [LineString([(0, 0), (20, 0)])]
    polys = [box(-5, -5, 25, 5)]
    df = label_segments(off, polys, [])
    assert df.district.isna().all()


def test_osm_dropped_when_near_official_polygon_even_if_far_from_official_line():
    # OSM line sits near an official polygon (byc poly) but far from the official
    # linework itself -- ruling #1 says buf_poly on the polygon side still drops it.
    off = [LineString([(0, 0), (100, 0)])]
    polys = [box(0, 500, 100, 502)]   # far from the official line, near the OSM line below
    osm = [LineString([(0, 501), (40, 501)])]
    df = label_segments(off, polys, osm, buf_line=10.0, buf_poly=3.0)
    assert len(df[df.origin == "osm"]) == 0
