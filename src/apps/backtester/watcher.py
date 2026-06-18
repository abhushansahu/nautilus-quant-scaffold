"""Continuous backtest watcher daemon."""

from __future__ import annotations

import logging
import signal
import time
from pathlib import Path

from analysis.compare import select_best_profile
from core.active_strategy import DEFAULT_STATE_PATH, ActiveStrategyState
from core.config import DEFAULT_CONFIG_DIR, load_config
from core.orchestrator import RunOrchestrator
from core.run_profile import RunSuite, load_run_suite
from data_pipeline.catalog import MarketDataCatalog
from data_pipeline.loader import DataWindow
from data_pipeline.watermarks import WatermarkStore
from models.promotion import should_promote

logger = logging.getLogger(__name__)


class BacktestWatcher:
    """Poll catalog watermarks and re-run suite evaluation when new bars arrive."""

    def __init__(
        self,
        suite: RunSuite,
        config_dir: Path = DEFAULT_CONFIG_DIR,
        watermark_store: WatermarkStore | None = None,
        state_path: Path | None = None,
    ) -> None:
        self.suite = suite
        self.config_dir = config_dir
        self.watermarks = watermark_store or WatermarkStore()
        self._state_path = state_path
        self._running = True
        self._app_cfg = load_config("backtest", config_dir=config_dir)

    def stop(self) -> None:
        self._running = False

    def run_once(self) -> bool:
        """Run a single evaluation cycle if any watched bar type has new data."""
        catalog = MarketDataCatalog(self._app_cfg.catalog_path)
        if not any(self.watermarks.has_new_data(bt, catalog) for bt in self.suite.bar_types):
            return False

        logger.info("New catalog data detected; running suite '%s'", self.suite.name)
        data_window = DataWindow(mode="rolling", lookback_bars=500)
        orchestrator = RunOrchestrator(self.suite, config_dir=self.config_dir)
        results = orchestrator.run_all(data_window=data_window)

        for bar_type in self.suite.bar_types:
            latest = catalog.latest_ts(bar_type)
            if latest is not None:
                self.watermarks.set(bar_type, latest)

        self._update_active_strategy(results)
        self._maybe_promote_model(results)
        return True

    def _update_active_strategy(self, results: list) -> None:
        try:
            profile, entry = select_best_profile(self.suite, self._app_cfg.results_dir)
        except ValueError:
            logger.warning("No indexed runs to select active strategy")
            return
        metric_value = entry.get("metrics", {}).get(self.suite.selection_metric, 0.0)
        ActiveStrategyState.write(
            suite=self.suite.name,
            active_profile=profile.name,
            metric=self.suite.selection_metric,
            metric_value=float(metric_value),
            run_id=entry["run_id"],
            path=self._state_path or DEFAULT_STATE_PATH,
        )

    def _maybe_promote_model(self, results: list) -> None:
        feedback = self.suite.ml_feedback
        if feedback is None or not feedback.enabled:
            return

        state = ActiveStrategyState.load()
        if state is None:
            return

        incumbent = next(
            (r for r in results if r.profile_name == state.active_profile),
            None,
        )
        challenger = max(
            results,
            key=lambda r: r.artifacts.summary.get("metrics", {}).get(
                self.suite.selection_metric, float("-inf")
            ),
        )
        if incumbent is None:
            return

        inc_metrics = incumbent.artifacts.summary.get("metrics", {})
        chal_metrics = challenger.artifacts.summary.get("metrics", {})
        if not should_promote(inc_metrics, chal_metrics, self.suite.selection_metric):
            return

        if feedback.train_command == "mlp":
            from models.training.train_mlp import train

            artifact_dir = self._app_cfg.artifacts_dir / f"mlp_{challenger.profile_name}"
            train(artifact_dir=artifact_dir, num_steps=50, num_bars=1000)
            logger.info("Promoted model artifact to %s", artifact_dir)

    def serve(self) -> None:
        """Long-running poll loop with graceful shutdown on SIGINT/SIGTERM."""

        def _handle_signal(signum: int, _frame: object) -> None:
            logger.info("Received signal %s; shutting down watcher", signum)
            self.stop()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        logger.info(
            "Watcher started for suite '%s' (poll=%ss)",
            self.suite.name,
            self.suite.poll_interval_secs,
        )
        while self._running:
            try:
                ran = self.run_once()
                if ran:
                    logger.info("Evaluation cycle complete")
                else:
                    logger.debug("No new data; sleeping")
            except Exception:
                logger.exception("Watcher cycle failed")
            time.sleep(self.suite.poll_interval_secs)

        logger.info("Watcher stopped")


def run_watcher(suite_path: Path, config_dir: Path = DEFAULT_CONFIG_DIR) -> None:
    suite = load_run_suite(suite_path)
    watcher = BacktestWatcher(suite, config_dir=config_dir)
    watcher.serve()
