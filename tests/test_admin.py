import json

from shapely.geometry import Polygon

from analysis.admin import polygons_from_geojson, polygons_from_overpass


def _way(coords, role="outer"):
    """coords: list of (lon, lat) forming a closed ring."""
    return {
        "type": "way",
        "role": role,
        "geometry": [{"lat": lat, "lon": lon} for lon, lat in coords],
    }


def _square_relation(name, admin_level, lon0, lat0, side=0.01):
    """Two ways forming a closed square ring, split so polygonize must merge them."""
    lon1, lat1 = lon0 + side, lat0 + side
    ring = [
        (lon0, lat0),
        (lon1, lat0),
        (lon1, lat1),
        (lon0, lat1),
        (lon0, lat0),
    ]
    mid = len(ring) // 2
    way_a = _way(ring[: mid + 1])
    way_b = _way(ring[mid:])
    return {
        "type": "relation",
        "tags": {"boundary": "administrative", "admin_level": str(admin_level), "name": name},
        "members": [way_a, way_b],
    }


def test_two_adjacent_squares_become_named_polygons():
    rel_a = _square_relation("가상동A", 8, 127.00, 37.20)
    rel_b = _square_relation("가상동B", 8, 127.01, 37.20)

    result = polygons_from_overpass([rel_a, rel_b], admin_level="8")

    assert set(result.keys()) == {"가상동A", "가상동B"}
    for name, geom in result.items():
        assert geom.area > 0
        assert not geom.is_empty


def test_admin_level_7_ignored_when_requesting_8():
    rel_7 = _square_relation("상위구", 7, 127.00, 37.20)
    rel_8 = _square_relation("하위동", 8, 127.01, 37.20)

    result = polygons_from_overpass([rel_7, rel_8], admin_level="8")

    assert set(result.keys()) == {"하위동"}


def test_non_administrative_relation_ignored():
    rel = _square_relation("무관계", 8, 127.00, 37.20)
    rel["tags"]["boundary"] = "not_administrative"

    result = polygons_from_overpass([rel], admin_level="8")

    assert result == {}


def _square_feature(adm_nm, lon0, lat0, side=0.01):
    lon1, lat1 = lon0 + side, lat0 + side
    ring = [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]
    return {
        "type": "Feature",
        "properties": {"adm_nm": adm_nm},
        "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]},
    }


def test_polygons_from_geojson_keys_by_last_token(tmp_path):
    features = [
        _square_feature("경기도 화성시효행구 봉담읍", 127.00, 37.20),
        _square_feature("경기도 화성시만세구 우정읍", 127.02, 37.20),
    ]
    fc = {"type": "FeatureCollection", "features": features}
    path = tmp_path / "hwaseong_hjd.geojson"
    path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")

    result = polygons_from_geojson(path, name_field="adm_nm")

    assert set(result.keys()) == {"봉담읍", "우정읍"}
    for name, geom in result.items():
        assert geom.area > 0
        assert not geom.is_empty
        # reprojected to a Korea-scale EPSG:5186 extent, not left in WGS84 degrees
        minx, miny, maxx, maxy = geom.bounds
        assert minx > 1000
        assert miny > 1000


def test_polygons_from_geojson_skips_features_without_name(tmp_path):
    features = [
        _square_feature("경기도 화성시효행구 봉담읍", 127.00, 37.20),
        {"type": "Feature", "properties": {}, "geometry": {
            "type": "MultiPolygon",
            "coordinates": [[[[127.02, 37.20], [127.03, 37.20], [127.03, 37.21], [127.02, 37.21], [127.02, 37.20]]]],
        }},
    ]
    fc = {"type": "FeatureCollection", "features": features}
    path = tmp_path / "hwaseong_hjd.geojson"
    path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")

    result = polygons_from_geojson(path, name_field="adm_nm")

    assert set(result.keys()) == {"봉담읍"}
