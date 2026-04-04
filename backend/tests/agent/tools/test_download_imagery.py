from app.agent.tools.download_imagery import validate_scene_count, MAX_SCENES


class TestValidateSceneCount:
    def test_within_limit(self) -> None:
        result = validate_scene_count(["scene_a", "scene_b"])
        assert result is None

    def test_single_scene(self) -> None:
        result = validate_scene_count(["scene_a"])
        assert result is None

    def test_exceeds_limit(self) -> None:
        result = validate_scene_count(["a", "b", "c"])
        assert result is not None
        assert "2" in result
        assert "3" in str(result)

    def test_max_scenes_is_two(self) -> None:
        assert MAX_SCENES == 2
