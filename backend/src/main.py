"""MegaBook FastAPI application."""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Depends
from fastapi.middleware.cors import CORSMiddleware

from src.core import FilesystemService, GitService, settings
from src.services import LLMProviderFactory, ProviderType, CostTrackingService
from src.services.embedding_service import EmbeddingService
from src.services.llm_call_logger import LLMCallLogger
from src.api.routes import filesystem, git, pipelines, query, costs, entities, imagegen, chat
from src.api.routes import vault as vault_routes
from src.dependencies import set_services


# Global service instances
_services: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print("Starting MegaBook backend...")
    
    # Load persisted vault path from config if available
    config_file = Path(__file__).parent.parent / "megabook_config.json"
    if config_file.exists():
        try:
            import json as _json
            with open(config_file, "r", encoding="utf-8") as f:
                app_config = _json.load(f)
            saved_vault = app_config.get("vault_path")
            if saved_vault and Path(saved_vault).exists():
                settings.repo_path = Path(saved_vault)
                print(f"[VAULT] Loaded saved vault: {saved_vault}")
            elif saved_vault:
                print(f"[VAULT] Saved vault path no longer exists: {saved_vault}")
        except Exception as e:
            print(f"[VAULT] Failed to load config: {e}")
    
    # Initialize services
    _services["filesystem"] = FilesystemService(settings.repo_path)
    
    try:
        _services["git"] = GitService(settings.repo_path)
    except Exception as e:
        print(f"Warning: Git repository not initialized: {e}")
        _services["git"] = None
    
    # Initialize LLM provider
    try:
        provider_type = ProviderType(settings.llm_provider)
        print(f"\n{'='*60}")
        print(f"[INIT] Initializing LLM provider: {provider_type.value}")
        print(f"{'='*60}")
        
        if provider_type == ProviderType.MOCK:
            # Mock provider needs no config
            print("[INIT] Provider type: MOCK")
            _services["llm_provider"] = LLMProviderFactory.create(
                provider_type=provider_type,
                model="mock-gpt-4",
            )
            print("[OK] Mock LLM provider initialized")
            
        elif provider_type == ProviderType.OPENAI_COMPATIBLE:
            # Generic OpenAI-compatible provider (Kimi, Together AI, etc.)
            # Support both new format (OPENAI_*) and legacy Azure format (AZURE_*)
            base_url = settings.openai_base_url or settings.azure_endpoint
            api_key = settings.openai_api_key or settings.azure_api_key
            model = settings.chat_model or settings.azure_deployment or "gpt-4"
            
            print(f"[INIT] Provider type: OPENAI_COMPATIBLE")
            print(f"   DEBUG - settings.chat_model: {settings.chat_model}")
            print(f"   DEBUG - settings.azure_deployment: {settings.azure_deployment}")
            print(f"   DEBUG - Final model: {model}")
            print(f"   Base URL: {base_url or 'NOT SET'}")
            print(f"   API Key: {'*' * 20 if api_key else 'NOT SET'}")
            print(f"   (Using AZURE_ENDPOINT: {settings.azure_endpoint is not None})")
            print(f"   (Using AZURE_API_KEY: {settings.azure_api_key is not None})")
            
            if not base_url or not api_key:
                print("\n[WARN] ERROR: Missing OpenAI-compatible credentials!")
                print("   Checked the following:")
                print(f"   - openai_base_url: {settings.openai_base_url}")
                print(f"   - azure_endpoint: {settings.azure_endpoint}")
                print(f"   - openai_api_key: {'SET' if settings.openai_api_key else 'NOT SET'}")
                print(f"   - azure_api_key: {'SET' if settings.azure_api_key else 'NOT SET'}")
                print("\n   Falling back to mock provider...")
                _services["llm_provider"] = LLMProviderFactory.create(
                    provider_type=ProviderType.MOCK,
                    model="mock-gpt-4",
                )
                print("[OK] Mock provider initialized (chat will work but with fake responses)")
            else:
                print("\n[INIT] Creating OpenAI-compatible provider...")
                try:
                    _services["llm_provider"] = LLMProviderFactory.create(
                        provider_type=provider_type,
                        model=model,
                        base_url=base_url,
                        api_key=api_key,
                    )
                    print("[OK] OpenAI-compatible provider initialized successfully")
                except Exception as provider_error:
                    print(f"\n[ERROR] ERROR: Failed to create OpenAI-compatible provider!")
                    print(f"   Error: {provider_error}")
                    import traceback
                    print(f"   Traceback: {traceback.format_exc()}")
                    print("\n   Falling back to mock provider...")
                    _services["llm_provider"] = LLMProviderFactory.create(
                        provider_type=ProviderType.MOCK,
                        model="mock-gpt-4",
                    )
                    print("[OK] Mock provider initialized as fallback")
        else:
            # Azure provider (legacy)
            print(f"[INIT] Provider type: AZURE (legacy)")
            print(f"   Model: {settings.azure_deployment or 'gpt-4'}")
            print(f"   Endpoint: {settings.azure_endpoint or 'NOT SET'}")
            print(f"   API Key: {'*' * 20 if settings.azure_api_key else 'NOT SET'}")
            
            if not settings.azure_endpoint or not settings.azure_api_key:
                print("\n[WARN] ERROR: Missing Azure credentials!")
                print("\n   Falling back to mock provider...")
                _services["llm_provider"] = LLMProviderFactory.create(
                    provider_type=ProviderType.MOCK,
                    model="mock-gpt-4",
                )
                print("[OK] Mock provider initialized")
            else:
                print("\n[INIT] Creating Azure OpenAI provider...")
                try:
                    _services["llm_provider"] = LLMProviderFactory.create(
                        provider_type=provider_type,
                        model=settings.azure_deployment or "gpt-4",
                        base_url=settings.azure_endpoint,
                        api_key=settings.azure_api_key,
                    )
                    print("[OK] Azure OpenAI provider initialized")
                except Exception as provider_error:
                    print(f"\n[ERROR] ERROR: Failed to create Azure provider!")
                    print(f"   Error: {provider_error}")
                    import traceback
                    print(f"   Traceback: {traceback.format_exc()}")
                    print("\n   Falling back to mock provider...")
                    _services["llm_provider"] = LLMProviderFactory.create(
                        provider_type=ProviderType.MOCK,
                        model="mock-gpt-4",
                    )
                    print("[OK] Mock provider initialized as fallback")
        
        print(f"{'='*60}\n")
    except Exception as e:
        import traceback
        print(f"\n{'='*60}")
        print(f"[ERROR] CRITICAL ERROR initializing LLM provider: {e}")
        print(f"{'='*60}")
        print(traceback.format_exc())
        print("[WARN] Chat will not work - provider set to None")
        print(f"{'='*60}\n")
        _services["llm_provider"] = None
    
    # Initialize cost tracking
    _services["cost_tracking"] = CostTrackingService(
        storage_path=settings.costs_path,
        cost_limit_nok=settings.cost_limit_nok,
    )
    
    # Initialize LLM call logger and attach to provider
    llm_logger = LLMCallLogger(log_dir=settings.logs_path)
    _services["llm_logger"] = llm_logger
    
    if _services.get("llm_provider"):
        _services["llm_provider"].set_logger(llm_logger)
        print(f"[OK] LLM call logger initialized: {settings.logs_path}")
    
    # Initialize embedding service
    _services["embedding"] = EmbeddingService(
        db_path=settings.vector_db_path,
        llm_provider=_services.get("llm_provider"),
    )
    
    # Initialize active pipelines storage
    _services["active_pipelines"] = {}
    
    # Set services in dependency injection module
    set_services(_services)
    
    print("MegaBook backend started successfully")
    
    yield
    
    # Shutdown
    print("Shutting down MegaBook backend...")


# Create FastAPI app
app = FastAPI(
    title="MegaBook API",
    description="Local-first, Git-backed, AI-assisted knowledge management system",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    filesystem.router,
    prefix="/api/filesystem",
    tags=["filesystem"],
)

app.include_router(
    git.router,
    prefix="/api/git",
    tags=["git"],
)

app.include_router(
    pipelines.router,
    prefix="/api/pipelines",
    tags=["pipelines"],
)

app.include_router(
    query.router,
    prefix="/api/query",
    tags=["query"],
)

app.include_router(
    costs.router,
    prefix="/api/costs",
    tags=["costs"],
)

app.include_router(
    entities.router,
    prefix="/api/entities",
    tags=["entities"],
)

app.include_router(
    imagegen.router,
    prefix="/api/imagegen",
    tags=["imagegen"],
)

app.include_router(
    chat.router,
    prefix="/api/chat",
    tags=["chat"],
)

app.include_router(
    vault_routes.router,
    prefix="/api/vault",
    tags=["vault"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MegaBook API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "filesystem": _services.get("filesystem") is not None,
            "git": _services.get("git") is not None,
            "llm": _services.get("llm_provider") is not None,
            "embeddings": _services.get("embedding") is not None,
        },
    }