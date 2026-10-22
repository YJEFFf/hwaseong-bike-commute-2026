import json

from analysis.destinations import load_osm_pois, load_schools


def test_load_schools_filters_hwaseong_operating(tmp_path):
    page = [
        {
            "SCHOOL_NM": "화성초등학교",
            "SCHOOL_SE": "초등학교",
            "OPER_STTUS": "운영",
            "RDNMADR": "경기도 화성시 만세구 장안면 화곡로 166",
            "LNMADR": "경기도 화성시 만세구 장안면 노진리 506-6",
            "LATITUDE": "37.0514252332",
            "LONGITUDE": "126.8089486922",
        },
        {
            "SCHOOL_NM": "폐교초등학교",
            "SCHOOL_SE": "초등학교",
            "OPER_STTUS": "폐교",
            "RDNMADR": "경기도 화성시 봉담읍 어딘가로 1",
            "LNMADR": "",
            "LATITUDE": "37.20",
            "LONGITUDE": "126.95",
        },
        {
            "SCHOOL_NM": "서울초등학교",
            "SCHOOL_SE": "초등학교",
            "OPER_STTUS": "운영",
            "RDNMADR": "서울특별시 종로구 어딘가로 1",
            "LNMADR": "",
            "LATITUDE": "37.57",
            "LONGITUDE": "126.98",
        },
    ]
    page_path = tmp_path / "page_1.json"
    page_path.write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")

    df = load_schools([page_path], address_token="화성시")

    assert list(df.columns) == ["name", "kind", "x", "y"]
    assert len(df) == 1
    row = df.iloc[0]
    assert row["name"] == "화성초등학교"
    assert row["kind"] == "초등학교"
    assert 150000 <= row["x"] <= 250000
    assert 450000 <= row["y"] <= 550000


def test_load_schools_concatenates_multiple_pages(tmp_path):
    p1 = [
        {
            "SCHOOL_NM": "가초등학교", "SCHOOL_SE": "초등학교", "OPER_STTUS": "운영",
            "RDNMADR": "경기도 화성시 봉담읍 1", "LNMADR": "",
            "LATITUDE": "37.20", "LONGITUDE": "126.95",
        }
    ]
    p2 = [
        {
            "SCHOOL_NM": "나중학교", "SCHOOL_SE": "중학교", "OPER_STTUS": "운영",
            "RDNMADR": "경기도 화성시 향남읍 1", "LNMADR": "",
            "LATITUDE": "37.15", "LONGITUDE": "126.90",
        }
    ]
    path1, path2 = tmp_path / "page_1.json", tmp_path / "page_2.json"
    path1.write_text(json.dumps(p1, ensure_ascii=False), encoding="utf-8")
    path2.write_text(json.dumps(p2, ensure_ascii=False), encoding="utf-8")

    df = load_schools([path1, path2], address_token="화성시")

    assert len(df) == 2
    assert set(df["kind"]) == {"초등학교", "중학교"}


def test_load_osm_pois_counts_bus_stops_and_stations(tmp_path):
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 37.20, "lon": 126.95, "tags": {"highway": "bus_stop", "name": "정류장1"}},
            {"type": "node", "id": 2, "lat": 37.21, "lon": 126.96, "tags": {"railway": "station", "name": "역1"}},
            {"type": "node", "id": 3, "lat": 37.22, "lon": 126.97, "tags": {"public_transport": "station", "name": "역2"}},
            # both bus_stop and station tags -> counted once as station
            {"type": "node", "id": 4, "lat": 37.23, "lon": 126.98, "tags": {"highway": "bus_stop", "railway": "station", "name": "복합"}},
            # irrelevant node, should be skipped
            {"type": "node", "id": 5, "lat": 37.24, "lon": 126.99, "tags": {"amenity": "cafe", "name": "카페"}},
        ]
    }
    json_path = tmp_path / "stops.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    df = load_osm_pois(json_path)

    assert list(df.columns) == ["name", "kind", "x", "y"]
    counts = df["kind"].value_counts().to_dict()
    assert counts == {"station": 3, "bus_stop": 1}
