from app.agent.tools.search_imagery import pick_best_scenes


class TestPickBestScenes:
    def test_returns_max_n_scenes(self) -> None:
        scenes = [
            {"scene_id": "a", "cloud_cover": 5.0, "datetime": "2025-01-01"},
            {"scene_id": "b", "cloud_cover": 10.0, "datetime": "2025-01-06"},
            {"scene_id": "c", "cloud_cover": 3.0, "datetime": "2025-01-12"},
            {"scene_id": "d", "cloud_cover": 8.0, "datetime": "2025-01-18"},
        ]
        result = pick_best_scenes(scenes, max_scenes=2)
        assert len(result) == 2

    def test_prefers_low_cloud_cover(self) -> None:
        scenes = [
            {"scene_id": "cloudy", "cloud_cover": 50.0, "datetime": "2025-01-01"},
            {"scene_id": "clear", "cloud_cover": 2.0, "datetime": "2025-01-06"},
            {"scene_id": "medium", "cloud_cover": 20.0, "datetime": "2025-01-12"},
        ]
        result = pick_best_scenes(scenes, max_scenes=2)
        ids = [s["scene_id"] for s in result]
        assert "clear" in ids
        assert "cloudy" not in ids

    def test_single_scene_when_max_is_one(self) -> None:
        scenes = [
            {"scene_id": "a", "cloud_cover": 5.0, "datetime": "2025-01-01"},
            {"scene_id": "b", "cloud_cover": 3.0, "datetime": "2025-01-06"},
        ]
        result = pick_best_scenes(scenes, max_scenes=1)
        assert len(result) == 1
        assert result[0]["scene_id"] == "b"

    def test_empty_input(self) -> None:
        result = pick_best_scenes([], max_scenes=2)
        assert result == []

    def test_fewer_scenes_than_max(self) -> None:
        scenes = [{"scene_id": "a", "cloud_cover": 5.0, "datetime": "2025-01-01"}]
        result = pick_best_scenes(scenes, max_scenes=2)
        assert len(result) == 1

    def test_preserves_temporal_spread(self) -> None:
        scenes = [
            {"scene_id": "jan1", "cloud_cover": 5.0, "datetime": "2025-01-01"},
            {"scene_id": "jan3", "cloud_cover": 4.0, "datetime": "2025-01-03"},
            {"scene_id": "mar1", "cloud_cover": 6.0, "datetime": "2025-03-01"},
        ]
        result = pick_best_scenes(scenes, max_scenes=2)
        ids = [s["scene_id"] for s in result]
        assert "mar1" in ids
