import asyncio
import sys
from app.core.settings import settings
from app.services.llm import get_embedding_provider, get_llm_provider

async def main():
    print("=" * 60)
    print("LLM & Embedding Infrastructure Verification Tool")
    print("=" * 60)
    print(f"GCP Project:          {settings.GCP_PROJECT_ID}")
    print(f"GCP Location:         {settings.GCP_LOCATION}")
    print(f"Embedding Model:      {settings.VERTEX_EMBEDDING_MODEL or 'text-embedding-004 (Default)'}")
    print(f"Generative LLM Model: {settings.VERTEX_GENERATIVE_MODEL or 'gemini-2.5-flash (Default)'}")
    print("=" * 60)

    # 1. Test Embedding Functionality
    print("\n--- Testing Embedding Provider ---")
    try:
        embed_provider = get_embedding_provider()
        sample_text = "Smart Data Landing Platform testing vector embedding."
        print(f"Input Text: '{sample_text}'")
        
        embedding = await embed_provider.get_embedding(sample_text)
        print(f"Success! Retrieved embedding vector.")
        print(f"Vector dimensions: {len(embedding)}")
        print(f"Sample values (first 5): {embedding[:5]}")
    except Exception as e:
        print(f"Error testing Embedding Provider: {e}", file=sys.stderr)

    # 2. Test LLM Call Infrastructure
    print("\n--- Testing LLM Provider ---")
    try:
        llm_provider = get_llm_provider()
        sample_prompt = "Say 'LLM infra is working' in exactly 4 words."
        print(f"Prompt: '{sample_prompt}'")
        
        response = await llm_provider.generate_response(sample_prompt)
        print(f"Success! Model response:")
        print(f"'{response.strip()}'")
    except Exception as e:
        print(f"Error testing LLM Provider: {e}", file=sys.stderr)
        
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
