import numpy as np
import pandas as pd
from shapely import STRtree
from shapely.geometry import LineString, Polygon, box

from analysis.sample_frames import cluster_points, cluster_representatives, island_gaps, midpoint


def test_cluster_points_transitive_chain_and_outlier():
    # three points 20m apart in a row -> one cluster under transitive closure
    # even though the two end points are 40m apart (> radius).
    xy = np.array([[0, 0], [20, 0], [40, 0], [140, 0]])
    labels = cluster_points(xy, radius=30)
    assert labels[0] == labels[1] == labels[2]
    assert labels[3] != labels[0]
    assert len(set(labels.tolist())) == 2


def test_midpoint_linestring():
    p = midpoint(LineString([(0, 0), (100, 0)]))
    assert abs(p.x - 50) < 1e-9
    assert abs(p.y - 0) < 1e-9


def test_midpoint_polygon_inside():
    square = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    p = midpoint(square)
    assert square.contains(p)


def test_island_gaps_sorted_ascending_with_k():
    # three 1.5km collinear lines separated by 50m then 200m gaps.
    a = LineString([(0, 0), (1500, 0)])
    b = LineString([(1550, 0), (3050, 0)])   # 50m gap from a
    c = LineString([(3250, 0), (4750, 0)])   # 200m gap from b (1750m from a)
    gaps = island_gaps([a, b, c], tol=1.0, min_component_len=1000, k=2)
    assert [round(g[3]) for g in gaps] == [50, 200]


def test_island_gaps_returns_all_when_fewer_than_k():
    a = LineString([(0, 0), (1500, 0)])
    b = LineString([(1550, 0), (3050, 0)])
    gaps = island_gaps([a, b], tol=1.0, min_component_len=1000, k=20)
    assert len(gaps) == 1
    assert round(gaps[0][3]) == 50


def test_cluster_representatives_picks_shortest_distance_m_per_cluster():
    # three candidates within 30m of each other -> one cluster -> one representative
    # (the row with the smallest distance_m), plus one far-away outlier -> its own rep.
    df = pd.DataFrame({
        "candidate_id": ["C1", "C2", "C3", "C4"],
        "x": [0.0, 10.0, 20.0, 500.0],
        "y": [0.0, 0.0, 0.0, 0.0],
        "distance_m": [12.0, 5.0, 9.0, 3.0],
    })
    reps = cluster_representatives(df, "x", "y", radius=30.0, rank_col="distance_m")
    assert len(reps) == 2
    assert set(reps.candidate_id) == {"C2", "C4"}
    assert reps.district.isna().all()  # no admin_tree given -> district stays None


def test_cluster_representatives_assigns_district_via_admin_tree():
    admin_polys = [box(0, 0, 100, 100)]
    admin_labels = ["A"]
    tree = STRtree(admin_polys)
    df = pd.DataFrame({
        "candidate_id": ["C1"],
        "x": [50.0],
        "y": [50.0],
        "distance_m": [1.0],
    })
    reps = cluster_representatives(df, "x", "y", radius=30.0, rank_col="distance_m",
                                    admin_tree=tree, admin_polys=admin_polys,
                                    admin_labels=admin_labels)
    assert reps.district.tolist() == ["A"]
