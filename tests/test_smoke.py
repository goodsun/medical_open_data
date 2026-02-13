"""Smoke tests — 全エンドポイントが200を返すことを確認"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


class TestHealthAndMeta:
    def test_health(self):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_stats(self):
        r = client.get("/api/v1/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_facilities"] > 0
        assert data["total_specialities"] > 0

    def test_prefectures(self):
        r = client.get("/api/v1/prefectures")
        assert r.status_code == 200
        assert len(r.json()) == 47

    def test_specialities(self):
        r = client.get("/api/v1/specialities")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_catalog(self):
        r = client.get("/api/v1/catalog")
        assert r.status_code == 200
        data = r.json()
        assert data["@type"] == "dcat:Catalog"
        assert len(data["dcat:dataset"]) > 0

    def test_openapi(self):
        r = client.get("/openapi.json")
        assert r.status_code == 200


class TestFacilitySearch:
    def test_basic_search(self):
        r = client.get("/api/v1/facilities?per_page=5")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "pagination" in data
        assert data["pagination"]["total"] > 0

    def test_keyword_search(self):
        r = client.get("/api/v1/facilities?q=渋谷&per_page=3")
        assert r.status_code == 200
        assert len(r.json()["data"]) > 0

    def test_specialty_search(self):
        r = client.get("/api/v1/facilities?specialty=内科&per_page=3")
        assert r.status_code == 200
        assert r.json()["pagination"]["total"] > 0

    def test_type_filter(self):
        r = client.get("/api/v1/facilities?type=1&per_page=3")
        assert r.status_code == 200
        for fac in r.json()["data"]:
            assert fac["facility_type"] == 1

    def test_prefecture_filter(self):
        r = client.get("/api/v1/facilities?prefecture=13&per_page=3")
        assert r.status_code == 200
        for fac in r.json()["data"]:
            assert fac["prefecture_code"] == "13"

    def test_open_now(self):
        r = client.get("/api/v1/facilities?q=渋谷&open_now=true&per_page=3")
        assert r.status_code == 200
        # 件数は時間帯による。200が返ればOK

    def test_pagination(self):
        r = client.get("/api/v1/facilities?per_page=5&page=2")
        assert r.status_code == 200
        data = r.json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["per_page"] == 5


class TestNearbySearch:
    def test_nearby(self):
        r = client.get("/api/v1/facilities/nearby?lat=35.658&lng=139.702&radius=1")
        assert r.status_code == 200
        results = r.json()
        assert len(results) > 0
        # 距離順ソート確認
        dists = [f["distance_km"] for f in results if f["distance_km"] is not None]
        assert dists == sorted(dists)

    def test_nearby_with_open_now(self):
        r = client.get("/api/v1/facilities/nearby?lat=35.658&lng=139.702&radius=1&open_now=true")
        assert r.status_code == 200

    def test_nearby_with_specialty(self):
        r = client.get("/api/v1/facilities/nearby?lat=35.658&lng=139.702&radius=1&specialty=内科")
        assert r.status_code == 200


class TestFacilityDetail:
    def test_detail(self):
        # まず1件取得
        r = client.get("/api/v1/facilities?per_page=1")
        fac_id = r.json()["data"][0]["id"]

        r = client.get(f"/api/v1/facilities/{fac_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == fac_id
        assert "specialities" in data
        assert "name" in data

    def test_detail_not_found(self):
        r = client.get("/api/v1/facilities/0000000000000")
        assert r.status_code == 404
