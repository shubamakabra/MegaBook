"""Quick test of Azure OpenAI connectivity."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core import settings
from src.services.azure_openai_provider import AzureOpenAIProvider

async def test_azure():
    print("\n" + "="*60)
    print("🧪 Testing Azure OpenAI Connection")
    print("="*60)
    
    if not settings.azure_endpoint or not settings.azure_api_key:
        print("\n❌ Missing Azure credentials!")
        print("Make sure your .env file has:")
        print("  AZURE_ENDPOINT=https://your-resource.openai.azure.com/")
        print("  AZURE_API_KEY=your-key")
        return
    
    print(f"\n📍 Endpoint: {settings.azure_endpoint}")
    print(f"🔑 API Key: {'*' * 20} (hidden)")
    print(f"🤖 Model: {settings.azure_deployment or 'gpt-4'}")
    
    try:
        provider = AzureOpenAIProvider(
            model=settings.azure_deployment or "gpt-4",
            endpoint=settings.azure_endpoint,
            api_key=settings.azure_api_key,
        )
        
        print("\n✅ Client initialized successfully!")
        
        print("\n💬 Testing chat completion...")
        response = await provider.generate_text(
            prompt="Say 'Azure is working!' and nothing else.",
            system_prompt="You are a helpful assistant.",
            temperature=0.0,
        )
        
        print(f"\n📝 Response: {response.content}")
        print(f"📊 Tokens: {response.usage.total_tokens} (prompt: {response.usage.prompt_tokens}, completion: {response.usage.completion_tokens})")
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_azure())
