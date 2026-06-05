"""
WeatherVault - AWS Secrets Manager Setup Script
=================================================
Creates the 'weather-dashboard/api-credentials' secret
in AWS Secrets Manager with all required configuration values.

Usage:
  1. Replace placeholder values below with your actual credentials.
  2. Ensure AWS CLI is configured: aws configure
  3. Run: python setup_secrets.py

This script only needs to be run ONCE during initial setup.
"""

import json
import boto3
from botocore.exceptions import ClientError

# ═══════════════════════════════════════════════════════════════
# *** REPLACE THESE PLACEHOLDER VALUES WITH YOUR OWN ***
# ═══════════════════════════════════════════════════════════════

SECRET_VALUES = {
    "weather_api_key": "60ebb0d26352145feeeb2294f5e2dca1",
    "app_id": "weathervault-dashboard-v2",
    "s3_bucket_name": "weathervault-dashboard-2026-60ebb",
    "s3_region": "us-east-1",
    "default_units": "metric",
    "api_base_url": "https://api.openweathermap.org/data/2.5",
    "app_version": "2.0.0",
    "max_requests_per_day": "1000",
}

SECRET_NAME = "weather-dashboard/api-credentials"
AWS_REGION = "us-east-1"


def create_or_update_secret():
    """Create or update the secret in AWS Secrets Manager."""
    print("=" * 60)
    print("  WeatherVault - Secrets Manager Setup")
    print("=" * 60)

    # Validate placeholders have been replaced
    if SECRET_VALUES["weather_api_key"] == "PASTE_YOUR_OPENWEATHERMAP_KEY":
        print("\n⚠️  WARNING: You haven't replaced the placeholder values!")
        print("   Edit this file and replace:")
        print("   - PASTE_YOUR_OPENWEATHERMAP_KEY → Your actual OpenWeatherMap API key")
        print("   - PASTE_YOUR_BUCKET_NAME → Your actual S3 bucket name")
        print()
        proceed = input("Continue anyway? (y/N): ").strip().lower()
        if proceed != "y":
            print("Aborted. Replace placeholders and try again.")
            return

    client = boto3.client("secretsmanager", region_name=AWS_REGION)
    secret_string = json.dumps(SECRET_VALUES)

    try:
        # Try to create the secret
        response = client.create_secret(
            Name=SECRET_NAME,
            Description="WeatherVault API credentials and configuration",
            SecretString=secret_string,
            Tags=[
                {"Key": "App", "Value": "WeatherVault"},
                {"Key": "Environment", "Value": "production"},
                {"Key": "ManagedBy", "Value": "setup_secrets.py"},
            ],
        )

        arn = response["ARN"]
        print(f"\n✅ Secret CREATED successfully!")
        print(f"\n📋 Secret Details:")
        print(f"   Name : {SECRET_NAME}")
        print(f"   ARN  : {arn}")
        print(f"   Region: {AWS_REGION}")
        print(f"\n🔗 Verify in AWS Console:")
        print(
            f"   https://{AWS_REGION}.console.aws.amazon.com/secretsmanager/"
            f"secret?name={SECRET_NAME}&region={AWS_REGION}"
        )

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceExistsException":
            # Secret already exists, update it
            print(f"\n📝 Secret '{SECRET_NAME}' already exists. Updating...")
            response = client.update_secret(
                SecretId=SECRET_NAME,
                SecretString=secret_string,
            )
            arn = response["ARN"]
            print(f"\n✅ Secret UPDATED successfully!")
            print(f"\n📋 Secret Details:")
            print(f"   Name : {SECRET_NAME}")
            print(f"   ARN  : {arn}")
            print(f"   Region: {AWS_REGION}")
            print(f"\n🔗 Verify in AWS Console:")
            print(
                f"   https://{AWS_REGION}.console.aws.amazon.com/secretsmanager/"
                f"secret?name={SECRET_NAME}&region={AWS_REGION}"
            )
        else:
            print(f"\n❌ Error: {e.response['Error']['Code']}")
            print(f"   {e.response['Error']['Message']}")
            raise

    # Print stored keys summary
    print(f"\n📦 Stored Keys ({len(SECRET_VALUES)}):")
    print("   ─" * 25)
    for key, value in SECRET_VALUES.items():
        # Mask sensitive values
        if "key" in key.lower() or "secret" in key.lower():
            display = value[:8] + "..." if len(value) > 8 else "***"
        else:
            display = value
        print(f"   {key:<25} = {display}")

    print("\n" + "=" * 60)
    print("  Setup complete! Your secrets are stored securely.")
    print("=" * 60)


if __name__ == "__main__":
    create_or_update_secret()
