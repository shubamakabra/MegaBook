"""Test script to verify Azure connectivity."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import settings

print("🔧 MegaBook Configuration Check")
print("=" * 50)

# Check image generation config
print("\n📸 Image Generation:")
if settings.azure_image_endpoint:
    print(f"  ✓ Endpoint: {settings.azure_image_endpoint[:40]}...")
else:
    print("  ✗ No endpoint configured")

if settings.azure_image_api_key:
    print(f"  ✓ API Key: {'*' * 20} (hidden)")
else:
    print("  ✗ No API key configured")

# Check LLM config
print("\n💬 LLM/Chat:")
if settings.azure_endpoint:
    print(f"  ✓ Endpoint: {settings.azure_endpoint[:40]}...")
else:
    print("  ✗ No endpoint configured")

if settings.azure_api_key:
    print(f"  ✓ API Key: {'*' * 20} (hidden)")
else:
    print("  ✗ No API key configured")

print("\n" + "=" * 50)

# Test image generation service
if settings.azure_image_endpoint and settings.azure_image_api_key:
    print("\n🎨 Testing Image Generation Service...")
    try:
        from src.services.image_generation_service import ImageGenerationService
        from src.core.filesystem import FilesystemService
        
        fs = FilesystemService(settings.repo_path)
        service = ImageGenerationService(
            endpoint=settings.azure_image_endpoint,
            api_key=settings.azure_image_api_key,
            filesystem=fs,
            storage_path=settings.repo_path / "generated-images",
        )
        
        if service._use_mock:
            print("  ⚠ Service initialized in MOCK mode")
        else:
            print("  ✓ Service initialized with REAL Azure API")
            print(f"  ✓ Client ready: {service.endpoint}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
else:
    print("\n⚠ Skipping image service test (no credentials)")

print("\n✅ Configuration check complete!")
