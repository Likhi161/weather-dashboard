"""
WeatherVault - S3 Bucket Setup Script
=======================================
Creates the S3 bucket with the required folder structure
and uploads all configuration files.

Usage:
  1. Replace PASTE_YOUR_BUCKET_NAME_HERE with your actual bucket name.
  2. Ensure AWS CLI is configured: aws configure
  3. Run: python s3_setup/setup_s3.py

This script only needs to be run ONCE during initial setup.
"""

import json
import os
import sys
import boto3
from botocore.exceptions import ClientError

# ═══════════════════════════════════════════════════════════════
# *** REPLACE THIS PLACEHOLDER WITH YOUR ACTUAL BUCKET NAME ***
# ═══════════════════════════════════════════════════════════════

BUCKET_NAME = "weathervault-dashboard-2026-60ebb"
AWS_REGION = "us-east-1"

# S3 folder structure to create
FOLDERS = [
    "weather-data/",
    "app-config/",
    "backgrounds/",
    "city-images/",
    "logs/",
]

# ─── Configuration Files ─────────────────────────────────────

CITIES_DATA = {
    "featured_cities": [
        {
            "name": "London",
            "emoji": "🇬🇧",
            "description": "The historic capital of England, known for its iconic landmarks and rainy weather.",
            "timezone": "Europe/London",
            "country": "GB",
        },
        {
            "name": "New York",
            "emoji": "🇺🇸",
            "description": "The city that never sleeps, featuring dramatic seasonal weather changes.",
            "timezone": "America/New_York",
            "country": "US",
        },
        {
            "name": "Tokyo",
            "emoji": "🇯🇵",
            "description": "Japan's bustling capital with cherry blossoms in spring and humid summers.",
            "timezone": "Asia/Tokyo",
            "country": "JP",
        },
        {
            "name": "Paris",
            "emoji": "🇫🇷",
            "description": "The City of Light, with mild winters and warm, sunny summers.",
            "timezone": "Europe/Paris",
            "country": "FR",
        },
        {
            "name": "Sydney",
            "emoji": "🇦🇺",
            "description": "Australia's harbour city with warm beaches and mild winters.",
            "timezone": "Australia/Sydney",
            "country": "AU",
        },
        {
            "name": "Dubai",
            "emoji": "🇦🇪",
            "description": "A desert metropolis known for extreme heat and modern architecture.",
            "timezone": "Asia/Dubai",
            "country": "AE",
        },
        {
            "name": "Mumbai",
            "emoji": "🇮🇳",
            "description": "India's financial capital with tropical monsoon climate and vibrant culture.",
            "timezone": "Asia/Kolkata",
            "country": "IN",
        },
        {
            "name": "Toronto",
            "emoji": "🇨🇦",
            "description": "Canada's largest city with cold winters, warm summers, and stunning fall colors.",
            "timezone": "America/Toronto",
            "country": "CA",
        },
    ],
    "app_config": {
        "default_city": "London",
        "max_featured": 8,
        "source": "AWS S3",
        "last_updated": "2026-06-05",
    },
}

WEATHER_TIPS_DATA = {
    "tips": {
        "sunny": {
            "text": "☀️ Beautiful sunny day! Don't forget sunscreen and stay hydrated. UV index may be high.",
            "color": "#f59e0b",
        },
        "rainy": {
            "text": "🌧️ Rain expected! Carry an umbrella and wear waterproof shoes. Roads may be slippery.",
            "color": "#3b82f6",
        },
        "snowy": {
            "text": "❄️ Snow is falling! Dress in warm layers and watch for icy surfaces. Drive carefully.",
            "color": "#93c5fd",
        },
        "windy": {
            "text": "💨 Strong winds today! Secure loose outdoor items and be cautious while driving.",
            "color": "#6ee7b7",
        },
        "cloudy": {
            "text": "☁️ Overcast skies today. It might rain later, so keep an umbrella handy just in case.",
            "color": "#9ca3af",
        },
        "stormy": {
            "text": "⛈️ Storms approaching! Stay indoors if possible and avoid open areas. Charge your devices.",
            "color": "#ef4444",
        },
        "hot": {
            "text": "🔥 Extreme heat warning! Stay in shade, drink plenty of water, and avoid outdoor exercise.",
            "color": "#dc2626",
        },
        "cold": {
            "text": "🥶 Freezing temperatures! Wear heavy layers, cover extremities, and limit time outdoors.",
            "color": "#60a5fa",
        },
    },
    "source": "AWS S3",
    "version": "1.0.0",
}

APP_METADATA = {
    "app_name": "WeatherVault",
    "version": "2.0.0",
    "description": "AWS-powered weather dashboard with real-time data, secure credential management, and cloud storage.",
    "aws_services": [
        {
            "name": "EC2",
            "type": "t2.micro",
            "os": "Ubuntu 22.04 LTS",
            "purpose": "Hosts Flask API and serves frontend via Nginx",
        },
        {
            "name": "S3",
            "purpose": "Stores app config, weather search logs, and static assets",
        },
        {
            "name": "Secrets Manager",
            "purpose": "Securely stores API keys and app credentials with encryption",
        },
    ],
    "features": [
        "Real-time weather search powered by OpenWeatherMap",
        "5-step weather forecast",
        "Dynamic city chips loaded from S3",
        "Weather tips per condition from S3",
        "Automatic weather search logging to S3",
        "Search history from S3",
        "AWS Secrets Manager integration with in-memory caching",
        "S3 bucket statistics and file browser",
        "Dark glassmorphism UI with responsive design",
        "Health check monitoring for all AWS services",
    ],
    "deployment": {
        "server": "Nginx reverse proxy + Flask (Gunicorn in production)",
        "platform": "AWS EC2 t2.micro",
        "os": "Ubuntu 22.04 LTS",
        "method": "GitHub clone via EC2 user data script",
    },
    "api_provider": {
        "name": "OpenWeatherMap",
        "url": "https://openweathermap.org/api",
        "tier": "Free",
    },
    "source": "AWS S3",
}


def setup_bucket():
    """Create bucket, folder structure, and upload config files."""
    print("=" * 60)
    print("  WeatherVault - S3 Bucket Setup")
    print("=" * 60)

    if BUCKET_NAME == "PASTE_YOUR_BUCKET_NAME_HERE":
        print("\n⚠️  WARNING: You haven't replaced the bucket name placeholder!")
        print("   Edit this file and replace PASTE_YOUR_BUCKET_NAME_HERE")
        print("   with your actual S3 bucket name.")
        print()
        proceed = input("Continue anyway? (y/N): ").strip().lower()
        if proceed != "y":
            print("Aborted. Replace the placeholder and try again.")
            return

    s3 = boto3.client("s3", region_name=AWS_REGION)

    # Step 1: Create bucket
    print(f"\n📦 Creating bucket: {BUCKET_NAME} in {AWS_REGION}...")
    try:
        if AWS_REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
            )
        print(f"   ✅ Bucket '{BUCKET_NAME}' created successfully")
    except ClientError as e:
        if e.response["Error"]["Code"] in (
            "BucketAlreadyOwnedByYou",
            "BucketAlreadyExists",
        ):
            print(f"   ℹ️  Bucket '{BUCKET_NAME}' already exists, continuing...")
        else:
            print(f"   ❌ Error creating bucket: {e.response['Error']['Message']}")
            raise

    # Step 2: Create folder structure
    print(f"\n📁 Creating folder structure...")
    for folder in FOLDERS:
        try:
            s3.put_object(Bucket=BUCKET_NAME, Key=folder, Body=b"")
            print(f"   ✅ Created: {folder}")
        except ClientError as e:
            print(f"   ❌ Error creating {folder}: {e.response['Error']['Message']}")

    # Step 3: Upload config files
    uploaded_files = []

    config_files = {
        "app-config/cities.json": CITIES_DATA,
        "app-config/weather_tips.json": WEATHER_TIPS_DATA,
        "app-config/app_metadata.json": APP_METADATA,
    }

    print(f"\n📤 Uploading configuration files...")
    for s3_key, data in config_files.items():
        try:
            json_body = json.dumps(data, indent=2, ensure_ascii=False)
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=json_body.encode("utf-8"),
                ContentType="application/json",
            )
            size_kb = round(len(json_body.encode("utf-8")) / 1024, 2)
            uploaded_files.append({"path": s3_key, "size_kb": size_kb})
            print(f"   ✅ Uploaded: {s3_key} ({size_kb} KB)")
        except ClientError as e:
            print(f"   ❌ Error uploading {s3_key}: {e.response['Error']['Message']}")

    # Step 4: Print summary table
    print(f"\n{'=' * 60}")
    print(f"  Upload Summary")
    print(f"{'=' * 60}")
    print(f"\n  {'S3 Path':<40} {'Size':>8}")
    print(f"  {'─' * 40} {'─' * 8}")
    total_size = 0
    for f in uploaded_files:
        print(f"  {f['path']:<40} {f['size_kb']:>6} KB")
        total_size += f["size_kb"]
    print(f"  {'─' * 40} {'─' * 8}")
    print(f"  {'TOTAL':<40} {round(total_size, 2):>6} KB")

    print(f"\n  Bucket  : {BUCKET_NAME}")
    print(f"  Region  : {AWS_REGION}")
    print(f"  Files   : {len(uploaded_files)} uploaded")
    print(f"  Folders : {len(FOLDERS)} created")

    print(f"\n🔗 View in AWS Console:")
    print(
        f"   https://s3.console.aws.amazon.com/s3/buckets/"
        f"{BUCKET_NAME}?region={AWS_REGION}"
    )

    print(f"\n{'=' * 60}")
    print(f"  S3 setup complete!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    setup_bucket()
