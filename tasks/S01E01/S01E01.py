from __future__ import annotations

import csv
import os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from common.HttpUtil import HttpUtil
from llmService.responses_service import LLMProvider, ResponsesService
from tasks.base_task import BaseTask


class S01E01(BaseTask):
    ALLOWED_TAGS = [
        "IT",
        "transport",
        "edukacja",
        "medycyna",
        "praca z ludźmi",
        "praca z pojazdami",
        "praca fizyczna",
    ]

    def __init__(self) -> None:
        super().__init__(base_url="{HUB_BASE_URL}", task_name="people")
        self.http_util = HttpUtil(self.base_url)

    def run(self) -> Dict[str, Any]:
        """Run stage 1 to 7 of task S01E01."""
        self.logger.info("Starting S01E01 task execution (stage 1-7).")

        api_key = self._ensure_api_key()
        people_csv_path = self._get_people(api_key)
        filtered_csv_path = self._filter_people(people_csv_path)
        filtered_people = self._read_csv_rows(filtered_csv_path)
        job_to_tags = self._classify_jobs(filtered_people)
        filtered_people = self._filter_people_by_tag(filtered_people, job_to_tags, "transport")

        answer_payload = self._build_answer_payload(filtered_people, job_to_tags)
        verification_result = self.verify(answer_payload)

        self.logger.info("Stage 1 to 7 completed successfully.")
        return verification_result

    def _build_answer_payload(
        self,
        filtered_people: list[Dict[str, str]],
        job_to_tags: Dict[str, list[str]],
    ) -> list[Dict[str, Any]]:
        """Build final answer payload for the hub."""
        answer = []

        for person in filtered_people:
            job_description = person.get("job", "").strip()
            tags = job_to_tags.get(job_description, [])

            if not tags:
                self.logger.warning(
                    f"No tags found for job: {job_description} "
                    f"(person: {person.get('name')} {person.get('surname')})"
                )

            # Format: name, surname, gender, born (year), city (birthPlace), tags
            birth_date_str = person.get("birthDate", "")
            try:
                birth_year = datetime.strptime(birth_date_str, "%Y-%m-%d").year
            except ValueError:
                self.logger.error(f"Invalid birthDate for payload: {birth_date_str}")
                birth_year = 0

            answer.append(
                {
                    "name": person.get("name"),
                    "surname": person.get("surname"),
                    "gender": person.get("gender"),
                    "born": birth_year,
                    "city": person.get("birthPlace"),
                    "tags": tags,
                }
            )

        self.logger.info(f"Built answer payload with {len(answer)} records.")
        return answer

    def _filter_people_by_tag(
        self,
        people: list[Dict[str, str]],
        job_to_tags: Dict[str, list[str]],
        required_tag: str,
    ) -> list[Dict[str, str]]:
        """Keep only people whose job classification contains the required tag."""
        filtered_people = [
            person
            for person in people
            if required_tag in job_to_tags.get(person.get("job", "").strip(), [])
        ]
        self.logger.info(
            "Filtered people by tag '%s': %s -> %s",
            required_tag,
            len(people),
            len(filtered_people),
        )
        return filtered_people

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

    def _filter_people(self, input_path: Path) -> Path:
        """Filter people based on criteria and cache the result."""
        output_path = self._get_filtered_csv_path()

        if output_path.exists():
            self.logger.info(f"Using cached filtered file: {output_path}")
            self._validate_non_empty_file(output_path)
            return output_path

        self.logger.info(f"Filtering records from {input_path}")
        filtered_records: list[Dict[str, str]] = []
        fieldnames: list[str] = []

        # Load and filter
        with open(input_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                fieldnames = reader.fieldnames

            for row in reader:
                if self._matches_criteria(row):
                    filtered_records.append(row)

        self.logger.info(f"Found {len(filtered_records)} matching records.")

        # Save to cache
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if filtered_records:
            with open(output_path, mode="w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(filtered_records)
            self.logger.info(f"Saved filtered records to: {output_path}")
        else:
            self.logger.warning("No records matched the criteria. Saving header-only filtered file.")
            with open(output_path, mode="w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

        return output_path

    def _read_csv_rows(self, input_path: Path) -> list[Dict[str, str]]:
        """Load CSV rows from disk into a list of dictionaries."""
        self._validate_non_empty_file(input_path)

        with open(input_path, mode="r", encoding="utf-8") as file_obj:
            reader = csv.DictReader(file_obj)
            if not reader.fieldnames:
                raise ValueError(f"Missing CSV headers in file: {input_path}")

            return [row for row in reader]

    def _classify_jobs(self, filtered_people: list[Dict[str, str]]) -> Dict[str, list[str]]:
        """Classify unique job descriptions using Responses API and structured output."""
        unique_jobs = sorted(
            {
                person.get("job", "").strip()
                for person in filtered_people
                if person.get("job", "").strip()
            }
        )
        if not unique_jobs:
            self.logger.warning("No job descriptions found in filtered records.")
            return {}

        service = self._build_responses_service()
        self.logger.info(f"Classifying {len(unique_jobs)} unique jobs using model: {service.model}")

        job_id_to_description = {
            str(index): job_description for index, job_description in enumerate(unique_jobs, start=1)
        }
        batch_size = int(os.getenv("JOB_CLASSIFICATION_BATCH_SIZE", "25"))
        if batch_size <= 0:
            raise ValueError("JOB_CLASSIFICATION_BATCH_SIZE must be a positive integer.")

        all_classifications: Dict[str, list[str]] = {}
        for batch in self._chunk_job_map(job_id_to_description, batch_size):
            response = service.classify_with_schema(
                system_prompt=self._build_classification_prompt(),
                input_payload={
                    "jobs": [
                        {"job_id": job_id, "job_description": description}
                        for job_id, description in batch.items()
                    ],
                    "allowed_tags": self.ALLOWED_TAGS,
                },
                output_schema=self._build_jobs_classification_schema(),
            )

            batch_result = self._validate_classification_result(response, batch)
            all_classifications.update(batch_result)

        missing_ids = set(job_id_to_description.keys()) - set(all_classifications.keys())
        if missing_ids:
            raise ValueError(f"Missing job classifications for ids: {sorted(missing_ids)}")

        return {
            job_id_to_description[job_id]: all_classifications[job_id]
            for job_id in sorted(job_id_to_description.keys(), key=int)
        }

    def _build_responses_service(self) -> ResponsesService:
        """Build provider-aware Responses API service with OpenRouter as default."""
        provider_name = os.getenv("LLM_PROVIDER", LLMProvider.OPENROUTER.value).strip().lower()

        try:
            provider = LLMProvider(provider_name)
        except ValueError as error:
            allowed_values = ", ".join([item.value for item in LLMProvider])
            raise ValueError(
                f"Unsupported LLM_PROVIDER '{provider_name}'. Allowed: {allowed_values}."
            ) from error

        return ResponsesService(provider=provider)

    def _build_classification_prompt(self) -> str:
        """Build system prompt for job classification task."""
        tags_csv = ", ".join(self.ALLOWED_TAGS)

        return (
            "You classify Polish job descriptions into tags. "
            "Return only valid JSON matching the provided JSON schema. "
            "Use only tags from this list: "
            f"{tags_csv}. "
            "Each job must have at least one tag and short reasoning in Polish."
        )

    def _build_jobs_classification_schema(self) -> Dict[str, Any]:
        """Build strict JSON schema for Responses API output."""
        return {
            "type": "object",
            "description": "Jobs classification result.",
            "properties": {
                "classifications": {
                    "type": "array",
                    "description": "List of classifications for each requested job.",
                    "items": {
                        "type": "object",
                        "description": "Classification of a single job.",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "Job identifier from the input payload.",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Short explanation why these tags were selected.",
                                "minLength": 1,
                            },
                            "tags": {
                                "type": "array",
                                "description": "Selected tags from allowed set.",
                                "minItems": 1,
                                "items": {
                                    "type": "string",
                                    "enum": self.ALLOWED_TAGS,
                                    "description": "Single tag from allowed set.",
                                },
                            },
                        },
                        "required": ["job_id", "reasoning", "tags"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["classifications"],
            "additionalProperties": False,
        }

    def _validate_classification_result(
        self,
        response_data: Dict[str, Any],
        expected_batch: Dict[str, str],
    ) -> Dict[str, list[str]]:
        """Validate model response and return mapping from job_id to tags."""
        classifications = response_data.get("classifications")
        if not isinstance(classifications, list):
            raise ValueError("Invalid model response: 'classifications' must be a list.")

        expected_ids = set(expected_batch.keys())
        result: Dict[str, list[str]] = {}

        for item in classifications:
            if not isinstance(item, dict):
                raise ValueError("Invalid model response item: expected an object.")

            job_id = item.get("job_id")
            reasoning = item.get("reasoning")
            tags = item.get("tags")

            if not isinstance(job_id, str) or job_id not in expected_ids:
                raise ValueError(f"Invalid or unexpected job_id in model response: {job_id}")
            if job_id in result:
                raise ValueError(f"Duplicate job_id in model response: {job_id}")
            if not isinstance(reasoning, str) or not reasoning.strip():
                raise ValueError(f"Missing reasoning for job_id: {job_id}")
            if not isinstance(tags, list) or not tags:
                raise ValueError(f"Missing tags for job_id: {job_id}")

            validated_tags = [tag for tag in tags if isinstance(tag, str) and tag in self.ALLOWED_TAGS]
            if len(validated_tags) != len(tags):
                raise ValueError(f"Invalid tag set for job_id {job_id}: {tags}")

            result[job_id] = sorted(set(validated_tags))

        missing_ids = expected_ids - set(result.keys())
        if missing_ids:
            raise ValueError(f"Missing classifications in batch for ids: {sorted(missing_ids)}")

        return result

    def _chunk_job_map(
        self,
        job_map: Dict[str, str],
        batch_size: int,
    ) -> Iterable[Dict[str, str]]:
        """Yield chunks of job map preserving insertion order."""
        current_chunk: Dict[str, str] = {}

        for job_id, description in job_map.items():
            current_chunk[job_id] = description
            if len(current_chunk) >= batch_size:
                yield current_chunk
                current_chunk = {}

        if current_chunk:
            yield current_chunk

    def _matches_criteria(self, person: Dict[str, str]) -> bool:
        """
        Check if person matches:
        - gender == 'M'
        - birthPlace == 'Grudziądz' or 'Grudziadz'
        - age between 20-40 (relative to 2026)
        """
        # Gender check
        if person.get("gender") != "M":
            return False

        # Birthplace check (case-insensitive and diacritic-agnostic for 'Grudziądz')
        city = person.get("birthPlace", "").strip().lower()
        if city not in ["grudziądz", "grudziadz"]:
            return False

        # Age check (relative to current date)
        birth_date_str = person.get("birthDate", "")
        try:
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d")
            today = datetime.now()
            age = today.year - birth_date.year #- ((today.month, today.day) < (birth_date.month, birth_date.day))
            
            if not (20 <= age <= 40):
                return False
        except ValueError:
            self.logger.error(f"Invalid birthDate format for record: {person}")
            return False

        return True

    def _get_people_csv_path(self) -> Path:
        """Build absolute path to tasks/S01E01/resources/people.csv."""
        return Path(__file__).resolve().parent / "resources" / "people.csv"

    def _get_filtered_csv_path(self) -> Path:
        """Build absolute path to tasks/S01E01/resources/people_filtered.csv."""
        return Path(__file__).resolve().parent / "resources" / "people_filtered.csv"

    @staticmethod
    def _validate_non_empty_file(file_path: Path) -> None:
        """Validate that the file exists and is not empty."""
        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        if file_path.stat().st_size == 0:
            raise ValueError(f"File is empty: {file_path}")
