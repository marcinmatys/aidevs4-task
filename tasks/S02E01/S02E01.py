from __future__ import annotations

import csv
import io
import os
from typing import Any, Dict

from dotenv import load_dotenv, find_dotenv

from common.HttpUtil import HttpUtil
from tasks.base_task import BaseTask


class S02E01(BaseTask):
    def __init__(self) -> None:
        _ = load_dotenv(find_dotenv())
        base_url = os.getenv("HUB_BASE_URL")
        super().__init__(base_url=base_url, task_name="categorize")
        self.http_util = HttpUtil(self.base_url)

    def run(self) -> Dict[str, Any]:
        """Execute task S02E01 by processing memory CSV."""
        self.logger.info("Starting S02E01 task execution.")

        api_key = self._ensure_api_key()
        
        # Etap 1: Pobranie CSV wprost do pamięci
        items_data = self._download_csv_content(api_key)
        items = self._parse_csv(items_data)
        
        self.logger.info("Resetting balance.")
        self.verify({"prompt": "reset"})

        # Etap 2: Weryfikacja każdego towaru 
        results = []
        for index, item in enumerate(items, start=1):
            code = item.get("code", "").strip()
            description = item.get("description", "").strip()
            
            if not code or not description:
                self.logger.warning(f"Item #{index} missing required fields, skipping: {item}")
                continue
                
            prompt = (
                f"Weapons/knives/batons/guns=DNG. Reactor parts/tools/hardware/other=NEU. OUTPUT ONLY DNG or NEU! "
                f"code={code} desc={description}"
            )
            answer_payload = {"prompt": prompt}
            
            self.logger.info(f"Classifying item #{index}: code={code}")
            verification_result = self.verify(answer_payload)
            results.append({
                "code": code,
                "result": verification_result
            })
            
            # log results for visibility, self.verify already logs payload
            self.logger.debug(f"Item #{index} response: {verification_result}")
            

        self.logger.info("S02E01 task completed. Processed %s items.", len(results))
        # Zwracamy podsumowanie akcji do wrappera
        return {"processed_items": len(results), "results": results}

    def _ensure_api_key(self) -> str:
        """Validate API_KEY availability in environment variables."""
        api_key = os.getenv("API_KEY")
        if not api_key:
            raise ValueError("Missing API_KEY environment variable.")
        return api_key

    def _download_csv_content(self, api_key: str) -> str:
        """Download categorize.csv from HUB and return content as string."""
        endpoint = f"/data/{api_key}/categorize.csv"
        self.logger.info(f"Downloading input file from endpoint: {endpoint}")

        try:
            # http_util returns raw response.text
            csv_content = self.http_util.getData(endpoint)
        except Exception as error:
            raise RuntimeError(f"Failed to download categorize.csv: {error}") from error

        if not csv_content:
            raise ValueError("Downloaded categorize.csv is empty.")

        return csv_content

    def _parse_csv(self, csv_content: str) -> list[Dict[str, str]]:
        """Parse CSV string data to list of dicts directly in memory."""
        self.logger.info("Parsing CSV content in memory.")
        
        # io.StringIO expects a string, HttpUtil.getData() returns string according to S01E01 behavior
        file_obj = io.StringIO(csv_content)
        reader = csv.DictReader(file_obj)
        
        if not reader.fieldnames:
            raise ValueError("Missing CSV headers in downloaded data.")
            
        items = [row for row in reader]
        self.logger.info("Successfully parsed %s items from CSV.", len(items))
        return items
