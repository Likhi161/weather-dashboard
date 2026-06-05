"""
WeatherVault - S3 Asset Upload Utility
========================================
Uploads additional assets (images, files) to the S3 bucket.
Can be used to upload background images, city images, or
other static assets to the appropriate S3 folders.

Usage:
  python s3_setup/upload_assets.py

Requires: AWS CLI configured and bucket already created via setup_s3.py
"""

import os
import json
import boto3
import mimetypes
from botocore.exceptions import ClientError

# ═══════════════════════════════════════════════════════════════
# *** REPLACE WITH YOUR ACTUAL BUCKET NAME ***
# ═══════════════════════════════════════════════════════════════

BUCKET_NAME = "weathervault-dashboard-2026-60ebb"
AWS_REGION = "us-east-1"

# Asset folders mapping: local path → S3 prefix
ASSET_MAPPINGS = {
    "backgrounds": "backgrounds/",
    "city-images": "city-images/",
}


def upload_file(s3_client, local_path, s3_key):
    """
    Upload a single file to S3.

    Args:
        s3_client: boto3 S3 client
        local_path (str): Local file path
        s3_key (str): Destination S3 key

    Returns:
        dict: Upload result with path and size info
    """
    content_type, _ = mimetypes.guess_type(local_path)
    if content_type is None:
        content_type = "application/octet-stream"

    file_size = os.path.getsize(local_path)

    try:
        s3_client.upload_file(
            local_path,
            BUCKET_NAME,
            s3_key,
            ExtraArgs={"ContentType": content_type},
        )
        return {
            "local_path": local_path,
            "s3_key": s3_key,
            "size_kb": round(file_size / 1024, 2),
            "content_type": content_type,
            "status": "success",
        }
    except ClientError as e:
        return {
            "local_path": local_path,
            "s3_key": s3_key,
            "size_kb": 0,
            "content_type": content_type,
            "status": f"error: {e.response['Error']['Message']}",
        }


def upload_directory(s3_client, local_dir, s3_prefix):
    """
    Upload all files from a local directory to S3.

    Args:
        s3_client: boto3 S3 client
        local_dir (str): Local directory path
        s3_prefix (str): S3 key prefix (folder)

    Returns:
        list: List of upload result dicts
    """
    results = []

    if not os.path.exists(local_dir):
        print(f"   ⚠️  Directory not found: {local_dir} (skipping)")
        return results

    for root, dirs, files in os.walk(local_dir):
        for filename in files:
            local_path = os.path.join(root, filename)
            # Build S3 key preserving subdirectory structure
            relative_path = os.path.relpath(local_path, local_dir)
            s3_key = s3_prefix + relative_path.replace("\\", "/")

            result = upload_file(s3_client, local_path, s3_key)
            results.append(result)
            status_icon = "✅" if result["status"] == "success" else "❌"
            print(f"   {status_icon} {s3_key} ({result['size_kb']} KB)")

    return results


def main():
    """Upload all assets to S3."""
    print("=" * 60)
    print("  WeatherVault - Asset Upload Utility")
    print("=" * 60)

    if BUCKET_NAME == "PASTE_YOUR_BUCKET_NAME_HERE":
        print("\n⚠️  Replace PASTE_YOUR_BUCKET_NAME_HERE with your bucket name!")
        return

    s3_client = boto3.client("s3", region_name=AWS_REGION)
    all_results = []

    # Get the script's directory to resolve relative paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    for local_folder, s3_prefix in ASSET_MAPPINGS.items():
        local_path = os.path.join(project_root, local_folder)
        print(f"\n📤 Uploading from {local_folder}/ → s3://{BUCKET_NAME}/{s3_prefix}")

        results = upload_directory(s3_client, local_path, s3_prefix)
        all_results.extend(results)

    # Print summary
    success_count = sum(1 for r in all_results if r["status"] == "success")
    error_count = len(all_results) - success_count
    total_size = sum(r["size_kb"] for r in all_results if r["status"] == "success")

    print(f"\n{'=' * 60}")
    print(f"  Upload Summary")
    print(f"{'=' * 60}")
    print(f"\n  {'S3 Path':<40} {'Size':>8} {'Status':>10}")
    print(f"  {'─' * 40} {'─' * 8} {'─' * 10}")
    for r in all_results:
        status = "✅" if r["status"] == "success" else "❌"
        print(f"  {r['s3_key']:<40} {r['size_kb']:>6} KB {status:>10}")
    print(f"  {'─' * 40} {'─' * 8} {'─' * 10}")
    print(f"  Total: {success_count} uploaded, {error_count} errors, {round(total_size, 2)} KB")

    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    main()
