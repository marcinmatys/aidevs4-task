from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from common.HttpUtil import HttpUtil
from tasks.base_task import BaseTask


class S01E01(BaseTask):
    def __init__(self) -> None:
        super().__init__(base_url="{HUB_BASE_URL}", task_name="people")
        self.http_util = HttpUtil(self.base_url)

    def run(self) -> Dict[str, Any]:
        """Run stage 1 and stage 2 of task S01E01."""
        self.logger.info("Starting S01E01 task execution (stage 1-2).")

        api_key = self._ensure_api_key()
        people_csv_path = self._get_people(api_key)

        self.logger.info("Stage 1 and 2 completed successfully.")
        return {
            "status": "success",
            "task": self.task_name,
            "people_csv_path": str(people_csv_path),
        }

    def _ensure_api_key(self) -> str:
        """Validate API_KEY availability in environment variables."""
        api_key = os.getenv("API_KEY")
        if not api_key:
            raise ValueError("Missing API_KEY environment variable.")

        return api_key

    def _get_people(self, api_key: str) -> Path:
        """Use cached people.csv or download it when missing using HttpUtil."""
        people_csv_path = self._get_people_csv_path()

        if people_csv_path.exists():
            self.logger.info(f"Using cached input file: {people_csv_path}")
            self._validate_non_empty_file(people_csv_path)
            return people_csv_path

        endpoint = f"/data/{api_key}/people.csv"
        self.logger.info(f"Downloading input file from endpoint: {endpoint}")

        try:
            csv_content = self.http_util.getData(endpoint)
        except Exception as error:
            raise RuntimeError(f"Failed to download people.csv: {error}") from error

        if not csv_content:
            raise ValueError("Downloaded people.csv is empty.")

        people_csv_path.parent.mkdir(parents=True, exist_ok=True)
        people_csv_path.write_text(csv_content + "\n", encoding="utf-8")
        self.logger.info(f"Saved input file to cache: {people_csv_path}")

        return people_csv_path

    def _get_people_csv_path(self) -> Path:
        """Build absolute path to tasks/S01E01/resources/people.csv."""
        return Path(__file__).resolve().parent / "resources" / "people.csv"

    @staticmethod
    def _validate_non_empty_file(file_path: Path) -> None:
        """Validate that the file exists and is not empty."""
        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        if file_path.stat().st_size == 0:
            raise ValueError(f"File is empty: {file_path}")
