from models.promotion import should_promote


class TestShouldPromote:
    def test_challenger_beats_incumbent(self):
        assert should_promote(
            {"sharpe_ratio": 0.5},
            {"sharpe_ratio": 1.0},
            "sharpe_ratio",
        )

    def test_challenger_does_not_beat_incumbent(self):
        assert not should_promote(
            {"sharpe_ratio": 1.5},
            {"sharpe_ratio": 1.0},
            "sharpe_ratio",
        )

    def test_no_incumbent_promotes_challenger(self):
        assert should_promote({}, {"sharpe_ratio": 0.1}, "sharpe_ratio")
