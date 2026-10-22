import numpy as np
from shapely.geometry import LineString
from analysis.topo import dangling_endpoints, parallel_pairs, dedupe, components, knee_distance

A = LineString([(0, 0), (100, 0)])
B = LineString([(100, 0), (200, 0)])          # A와 끝점 공유
C = LineString([(0, 20), (100, 20)])          # A와 20m 평행
D = LineString([(215, 0), (300, 0)])          # B와 15m 간격 끊김
A2 = LineString([(0, 0.5), (100, 0.5)])       # A 중복

def test_dangling():
    ends = dangling_endpoints([A, B, D])
    xs = sorted(round(p.x) for p in ends)
    assert xs == [0, 200, 215, 300]

def test_parallel_and_dedupe():
    assert (0, 1) in parallel_pairs([A, C])
    assert dedupe([A, A2, B]) == [0, 2]

def test_components_tolerance():
    assert len(components([A, B, D], [], tol=1.0)) == 2
    assert len(components([A, B, D], [], tol=20.0)) == 1

def test_knee_distance_picks_steepest_jump():
    # 대부분 거리가 3 근처에 몰려 있고 grid의 5->10 구간에서 급증
    dists = np.array([1, 2, 3, 3, 3, 9, 9, 9, 9, 9, 9, 9, 9, 9, 40])
    grid = [1, 2, 5, 10, 15, 20, 30, 50, 100]
    assert knee_distance(dists, grid) == 10
