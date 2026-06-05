"""
WeatherVault - AWS Secrets Manager Module
==========================================
Singleton class that securely fetches and caches secrets
from AWS Secrets Manager with 5-minute TTL.

All credentials are fetched dynamically at runtime.
Zero hardcoded secrets anywhere in the codebase.
Works with both local AWS CLI credentials and EC2 IAM roles.
"""

import json
import time
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SecretsManager:
    """Singleton class for AWS Secrets Manager interactions with in-memory caching."""

    _instance = None
    _CACHE_TTL = 300  # 5 minutes in seconds

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SecretsManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._cache = {}
        self._cache_timestamps = {}
        self._client = None
        self._region = "us-east-1"  # Default region, overridden by AWS config
        logger.info("[SecretsManager] Singleton instance initialized")

    def _get_client(self):
        """Lazily create the Secrets Manager boto3 client."""
        if self._client is None:
            try:
                self._client = boto3.client("secretsmanager", region_name=self._region)
                logger.info("[SecretsManager] boto3 client created successfully")
            except Exception as e:
                logger.error(f"[SecretsManager] Failed to create boto3 client: {e}")
                raise
        return self._client

    def _is_cache_valid(self, secret_name):
        """Check if cached secret is still within TTL."""
        if secret_name not in self._cache:
            return False
        if secret_name not in self._cache_timestamps:
            return False
        elapsed = time.time() - self._cache_timestamps[secret_name]
        return elapsed < self._CACHE_TTL

    def get_secret(self, secret_name):
        """
        Fetch a secret from AWS Secrets Manager.

        Args:
            secret_name (str): The name/ARN of the secret.

        Returns:
            dict: Parsed JSON secret values.

        Raises:
            Exception: On AWS API errors with meaningful messages.
        """
        # Check cache first
        if self._is_cache_valid(secret_name):
            logger.info(f"[SecretsManager] Cache HIT for secret: {secret_name}")
            return self._cache[secret_name]

        logger.info(f"[SecretsManager] Cache MISS - Fetching secret: {secret_name}")

        try:
            client = self._get_client()
            response = client.get_secret_value(SecretId=secret_name)
            secret_string = response["SecretString"]
            secret_data = json.loads(secret_string)

            # Update cache
            self._cache[secret_name] = secret_data
            self._cache_timestamps[secret_name] = time.time()

            logger.info(f"[SecretsManager] Successfully fetched and cached secret: {secret_name}")
            return secret_data

        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            if error_code == "ResourceNotFoundException":
                logger.error(
                    f"[SecretsManager] Secret not found: {secret_name}. "
                    "Run setup_secrets.py first to create the secret."
                )
                raise Exception(
                    f"Secret '{secret_name}' not found in AWS Secrets Manager. "
                    "Please run setup_secrets.py to create it."
                )
            elif error_code == "AccessDeniedException":
                logger.error(
                    f"[SecretsManager] Access denied for secret: {secret_name}. "
                    "Check IAM permissions for SecretsManagerReadWrite."
                )
                raise Exception(
                    f"Access denied to secret '{secret_name}'. "
                    "Ensure your IAM role/user has SecretsManagerReadWrite permissions."
                )
            elif error_code == "DecryptionFailureException":
                logger.error(
                    f"[SecretsManager] Decryption failed for secret: {secret_name}. "
                    "Check KMS key permissions."
                )
                raise Exception(
                    f"Failed to decrypt secret '{secret_name}'. "
                    "Check that your IAM role has access to the KMS key."
                )
            else:
                logger.error(
                    f"[SecretsManager] Unexpected AWS error for secret {secret_name}: "
                    f"{error_code} - {e.response['Error']['Message']}"
                )
                raise Exception(
                    f"AWS Secrets Manager error ({error_code}): {e.response['Error']['Message']}"
                )
        except json.JSONDecodeError as e:
            logger.error(f"[SecretsManager] Failed to parse secret JSON for {secret_name}: {e}")
            raise Exception(f"Secret '{secret_name}' contains invalid JSON: {e}")
        except Exception as e:
            logger.error(f"[SecretsManager] Unexpected error fetching secret {secret_name}: {e}")
            raise

    def get_key(self, secret_name, key):
        """
        Get a specific key value from a secret.

        Args:
            secret_name (str): The name/ARN of the secret.
            key (str): The key to retrieve from the secret.

        Returns:
            str: The value of the requested key.

        Raises:
            KeyError: If the key doesn't exist in the secret.
        """
        secret_data = self.get_secret(secret_name)

        if key not in secret_data:
            available_keys = list(secret_data.keys())
            logger.error(
                f"[SecretsManager] Key '{key}' not found in secret '{secret_name}'. "
                f"Available keys: {available_keys}"
            )
            raise KeyError(
                f"Key '{key}' not found in secret '{secret_name}'. "
                f"Available keys: {available_keys}"
            )

        logger.info(f"[SecretsManager] Retrieved key '{key}' from secret '{secret_name}'")
        return secret_data[key]

    def clear_cache(self):
        """Clear all cached secrets."""
        cache_size = len(self._cache)
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info(f"[SecretsManager] Cache cleared ({cache_size} entries removed)")

    def get_cache_info(self):
        """
        Get information about the current cache state.

        Returns:
            dict: Cache metadata including size, TTL, and entry ages.
        """
        now = time.time()
        entries = {}
        for secret_name, timestamp in self._cache_timestamps.items():
            age = now - timestamp
            entries[secret_name] = {
                "age_seconds": round(age, 1),
                "ttl_remaining_seconds": round(max(0, self._CACHE_TTL - age), 1),
                "is_valid": age < self._CACHE_TTL,
            }

        return {
            "cache_size": len(self._cache),
            "ttl_seconds": self._CACHE_TTL,
            "entries": entries,
        }
