"""
WeatherVault - AWS S3 Manager Module
======================================
Class that handles all S3 operations: reading config files,
saving weather search logs, listing files, and getting bucket stats.

Uses in-memory caching with 10-minute TTL for S3 reads.
Bucket name is always read from Secrets Manager, never hardcoded.
Works with both local AWS CLI credentials and EC2 IAM roles.
"""

import json
import time
import logging
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Manager:
    """Manages all S3 operations with in-memory caching."""

    _CACHE_TTL = 600  # 10 minutes in seconds

    def __init__(self, bucket_name, region="us-east-1"):
        """
        Initialize S3Manager.

        Args:
            bucket_name (str): The S3 bucket name (from Secrets Manager).
            region (str): AWS region for the bucket.
        """
        self._bucket_name = bucket_name
        self._region = region
        self._cache = {}
        self._cache_timestamps = {}
        self._client = None
        logger.info(
            f"[S3Manager] Initialized with bucket: {bucket_name}, region: {region}"
        )

    def _get_client(self):
        """Lazily create the S3 boto3 client."""
        if self._client is None:
            try:
                self._client = boto3.client("s3", region_name=self._region)
                logger.info("[S3Manager] boto3 S3 client created successfully")
            except Exception as e:
                logger.error(f"[S3Manager] Failed to create S3 client: {e}")
                raise
        return self._client

    def _is_cache_valid(self, cache_key):
        """Check if cached data is still within TTL."""
        if cache_key not in self._cache:
            return False
        if cache_key not in self._cache_timestamps:
            return False
        elapsed = time.time() - self._cache_timestamps[cache_key]
        return elapsed < self._CACHE_TTL

    def _set_cache(self, cache_key, data):
        """Store data in cache with current timestamp."""
        self._cache[cache_key] = data
        self._cache_timestamps[cache_key] = time.time()

    def get_json(self, s3_key):
        """
        Read and parse a JSON file from S3.

        Args:
            s3_key (str): The S3 object key (path in bucket).

        Returns:
            dict: Parsed JSON data.
        """
        cache_key = f"get_json:{s3_key}"

        if self._is_cache_valid(cache_key):
            logger.info(f"[S3Manager] Cache HIT for key: {s3_key}")
            return self._cache[cache_key]

        logger.info(f"[S3Manager] Cache MISS - Reading from S3: {s3_key}")

        try:
            client = self._get_client()
            response = client.get_object(Bucket=self._bucket_name, Key=s3_key)
            body = response["Body"].read().decode("utf-8")
            data = json.loads(body)

            self._set_cache(cache_key, data)
            logger.info(f"[S3Manager] Successfully read and cached: {s3_key}")
            return data

        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            if error_code == "NoSuchKey":
                logger.error(
                    f"[S3Manager] File not found in S3: {s3_key}. "
                    "Run s3_setup/setup_s3.py to upload config files."
                )
                raise Exception(
                    f"S3 file not found: '{s3_key}'. "
                    "Please run s3_setup/setup_s3.py to upload configuration files."
                )
            elif error_code == "NoSuchBucket":
                logger.error(
                    f"[S3Manager] Bucket not found: {self._bucket_name}. "
                    "Create the bucket first or check the name in Secrets Manager."
                )
                raise Exception(
                    f"S3 bucket '{self._bucket_name}' does not exist. "
                    "Create it first or verify the bucket name in Secrets Manager."
                )
            elif error_code == "AccessDenied":
                logger.error(
                    f"[S3Manager] Access denied to {s3_key} in {self._bucket_name}. "
                    "Check IAM permissions for AmazonS3FullAccess."
                )
                raise Exception(
                    f"Access denied to S3 object '{s3_key}'. "
                    "Ensure your IAM role/user has AmazonS3FullAccess permissions."
                )
            else:
                logger.error(
                    f"[S3Manager] Unexpected S3 error for {s3_key}: "
                    f"{error_code} - {e.response['Error']['Message']}"
                )
                raise Exception(
                    f"S3 error ({error_code}): {e.response['Error']['Message']}"
                )
        except json.JSONDecodeError as e:
            logger.error(f"[S3Manager] Invalid JSON in S3 file {s3_key}: {e}")
            raise Exception(f"S3 file '{s3_key}' contains invalid JSON: {e}")
        except Exception as e:
            logger.error(f"[S3Manager] Unexpected error reading {s3_key}: {e}")
            raise

    def save_json(self, s3_key, data):
        """
        Save a JSON object to S3.

        Args:
            s3_key (str): The S3 object key (path in bucket).
            data (dict): The data to serialize and upload.
        """
        logger.info(f"[S3Manager] Saving JSON to S3: {s3_key}")

        try:
            client = self._get_client()
            json_body = json.dumps(data, indent=2, default=str)
            client.put_object(
                Bucket=self._bucket_name,
                Key=s3_key,
                Body=json_body.encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(f"[S3Manager] Successfully saved to S3: {s3_key}")

            # Invalidate any cached version of this key
            cache_key = f"get_json:{s3_key}"
            if cache_key in self._cache:
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]
                logger.info(f"[S3Manager] Invalidated cache for: {s3_key}")

        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            if error_code == "NoSuchBucket":
                logger.error(f"[S3Manager] Bucket not found: {self._bucket_name}")
                raise Exception(
                    f"S3 bucket '{self._bucket_name}' does not exist. "
                    "Create it first or verify the bucket name."
                )
            elif error_code == "AccessDenied":
                logger.error(
                    f"[S3Manager] Access denied writing to {s3_key}. "
                    "Check IAM permissions."
                )
                raise Exception(
                    f"Access denied writing to S3 '{s3_key}'. "
                    "Check IAM permissions for S3 write access."
                )
            else:
                logger.error(
                    f"[S3Manager] Error saving to S3 {s3_key}: "
                    f"{error_code} - {e.response['Error']['Message']}"
                )
                raise Exception(
                    f"S3 write error ({error_code}): {e.response['Error']['Message']}"
                )
        except Exception as e:
            logger.error(f"[S3Manager] Unexpected error saving {s3_key}: {e}")
            raise

    def save_weather_log(self, city, weather_data):
        """
        Save a weather search log to S3.

        Saves two copies:
        - weather-data/{city-slug}/latest.json (overwritten each search)
        - weather-data/{city-slug}/{timestamp}.json (historical record)

        Args:
            city (str): The city name.
            weather_data (dict): The weather data to log.
        """
        city_slug = city.lower().replace(" ", "-").replace(",", "")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        log_entry = {
            "city": city,
            "city_slug": city_slug,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "weather_data": weather_data,
            "logged_by": "WeatherVault",
            "source": "OpenWeatherMap API",
        }

        # Save latest
        latest_key = f"weather-data/{city_slug}/latest.json"
        self.save_json(latest_key, log_entry)
        logger.info(f"[S3Manager] Saved latest weather log for {city}: {latest_key}")

        # Save timestamped copy
        history_key = f"weather-data/{city_slug}/{timestamp}.json"
        self.save_json(history_key, log_entry)
        logger.info(f"[S3Manager] Saved historical weather log for {city}: {history_key}")

    def list_files(self, prefix=""):
        """
        List files in the S3 bucket with an optional prefix filter.

        Args:
            prefix (str): Optional prefix to filter results.

        Returns:
            list: List of dicts with key, size, and last_modified.
        """
        logger.info(f"[S3Manager] Listing files with prefix: '{prefix}'")

        try:
            client = self._get_client()
            files = []
            paginator = client.get_paginator("list_objects_v2")
            page_params = {"Bucket": self._bucket_name}
            if prefix:
                page_params["Prefix"] = prefix

            for page in paginator.paginate(**page_params):
                for obj in page.get("Contents", []):
                    files.append(
                        {
                            "key": obj["Key"],
                            "size_bytes": obj["Size"],
                            "last_modified": obj["LastModified"].isoformat(),
                        }
                    )

            logger.info(f"[S3Manager] Found {len(files)} files with prefix '{prefix}'")
            return files

        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            if error_code == "NoSuchBucket":
                logger.error(f"[S3Manager] Bucket not found: {self._bucket_name}")
                raise Exception(
                    f"S3 bucket '{self._bucket_name}' does not exist."
                )
            elif error_code == "AccessDenied":
                logger.error(
                    f"[S3Manager] Access denied listing bucket {self._bucket_name}"
                )
                raise Exception(
                    f"Access denied listing S3 bucket '{self._bucket_name}'. "
                    "Check IAM permissions."
                )
            else:
                logger.error(
                    f"[S3Manager] Error listing files: "
                    f"{error_code} - {e.response['Error']['Message']}"
                )
                raise Exception(
                    f"S3 list error ({error_code}): {e.response['Error']['Message']}"
                )
        except Exception as e:
            logger.error(f"[S3Manager] Unexpected error listing files: {e}")
            raise

    def get_bucket_stats(self):
        """
        Get statistics about the S3 bucket.

        Returns:
            dict: Bucket stats including total files, total size,
                  folder breakdown, region, and bucket name.
        """
        logger.info(f"[S3Manager] Getting bucket stats for: {self._bucket_name}")

        try:
            all_files = self.list_files()

            total_size = sum(f["size_bytes"] for f in all_files)
            total_files = len(all_files)

            # Build folder breakdown
            folders = {}
            for f in all_files:
                parts = f["key"].split("/")
                folder = parts[0] + "/" if len(parts) > 1 else "root/"
                if folder not in folders:
                    folders[folder] = {"file_count": 0, "total_size_bytes": 0}
                folders[folder]["file_count"] += 1
                folders[folder]["total_size_bytes"] += f["size_bytes"]

            # Convert folder sizes to KB
            for folder_info in folders.values():
                folder_info["total_size_kb"] = round(
                    folder_info["total_size_bytes"] / 1024, 2
                )

            stats = {
                "bucket_name": self._bucket_name,
                "region": self._region,
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_kb": round(total_size / 1024, 2),
                "folder_breakdown": folders,
            }

            logger.info(
                f"[S3Manager] Bucket stats: {total_files} files, "
                f"{stats['total_size_kb']} KB total"
            )
            return stats

        except Exception as e:
            logger.error(f"[S3Manager] Error getting bucket stats: {e}")
            raise

    def clear_cache(self):
        """Clear all cached S3 data."""
        cache_size = len(self._cache)
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info(f"[S3Manager] Cache cleared ({cache_size} entries removed)")
