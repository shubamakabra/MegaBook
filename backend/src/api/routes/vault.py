"""Vault management API routes.

Endpoints for getting/setting the active vault path,
opening the vault folder in the OS file explorer,
and browsing for a folder via a native OS dialog.
"""
import asyncio
import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core import FilesystemService, GitService, settings
from src.dependencies import get_filesystem, get_git_service, get_services


router = APIRouter()

# App-level config file — persists vault path across restarts
_CONFIG_FILE = Path(__file__).parent.parent.parent.parent / "megabook_config.json"


def _load_app_config() -> dict:
    """Load the app-level config file."""
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_app_config(config: dict) -> None:
    """Save the app-level config file."""
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


class SetVaultRequest(BaseModel):
    """Request body for setting the vault path."""
    path: str


class VaultInfo(BaseModel):
    """Response model for vault information."""
    path: Optional[str] = None
    exists: bool = False
    is_obsidian_vault: bool = False
    has_megabook: bool = False
    has_git: bool = False


@router.get("")
async def get_vault() -> VaultInfo:
    """Get the current vault information."""
    fs = get_filesystem()
    
    if fs is None:
        return VaultInfo()
    
    vault_path = Path(fs.repo_path).resolve()
    
    return VaultInfo(
        path=str(vault_path),
        exists=vault_path.exists(),
        is_obsidian_vault=(vault_path / ".obsidian").is_dir(),
        has_megabook=(vault_path / ".megabook").is_dir(),
        has_git=(vault_path / ".git").is_dir(),
    )


@router.post("")
async def set_vault(request: SetVaultRequest) -> VaultInfo:
    """Set the active vault path.
    
    This re-initializes the filesystem and git services to point
    at the new vault, and persists the choice to the config file.
    """
    vault_path = Path(request.path).resolve()
    
    if not vault_path.exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {vault_path}")
    
    if not vault_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {vault_path}")
    
    # Update the settings object
    settings.repo_path = vault_path
    
    services = get_services()
    
    # Re-initialize filesystem service
    try:
        new_fs = FilesystemService(vault_path)
        services["filesystem"] = new_fs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize filesystem: {e}")
    
    # Re-initialize git service
    try:
        new_git = GitService(vault_path)
        services["git"] = new_git
    except Exception as e:
        print(f"Warning: Git not available for vault: {e}")
        services["git"] = None
    
    # Persist to config file
    config = _load_app_config()
    config["vault_path"] = str(vault_path)
    _save_app_config(config)
    
    print(f"[VAULT] Switched to: {vault_path}")
    
    return VaultInfo(
        path=str(vault_path),
        exists=True,
        is_obsidian_vault=(vault_path / ".obsidian").is_dir(),
        has_megabook=(vault_path / ".megabook").is_dir(),
        has_git=(vault_path / ".git").is_dir(),
    )


@router.post("/open-explorer")
async def open_in_explorer():
    """Open the current vault folder in the OS file explorer."""
    fs = get_filesystem()
    
    if fs is None:
        raise HTTPException(status_code=400, detail="No vault configured")
    
    vault_path = Path(fs.repo_path).resolve()
    
    if not vault_path.exists():
        raise HTTPException(status_code=400, detail=f"Vault path does not exist: {vault_path}")
    
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(vault_path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(vault_path)])
        else:
            subprocess.Popen(["xdg-open", str(vault_path)])
        
        return {"status": "ok", "path": str(vault_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open explorer: {e}")


class BrowseResponse(BaseModel):
    """Response from the folder browse dialog."""
    path: Optional[str] = None
    cancelled: bool = False


def _open_folder_dialog(initial_dir: Optional[str] = None) -> Optional[str]:
    """Open a native OS folder picker dialog using tkinter.

    Runs tkinter in its own short-lived root window on the calling
    thread.  Returns the selected absolute path, or None if the user
    cancelled.
    """
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()          # Hide the root window
    root.attributes("-topmost", True)  # Bring dialog to front
    root.update()            # Process pending events so it actually appears

    kwargs: dict = {"title": "Select Vault Folder"}
    if initial_dir and Path(initial_dir).is_dir():
        kwargs["initialdir"] = initial_dir

    selected = filedialog.askdirectory(**kwargs)
    root.destroy()

    return selected if selected else None


@router.post("/browse")
async def browse_for_vault():
    """Open a native OS folder picker and return the chosen path.

    The dialog blocks a worker thread; the async handler awaits the
    result so the event loop stays responsive.  Returns the selected
    path, or ``cancelled: true`` if the user closed the dialog.
    """
    # Determine a sensible initial directory
    fs = get_filesystem()
    initial_dir: Optional[str] = None
    if fs is not None:
        vault_path = Path(fs.repo_path).resolve()
        if vault_path.exists():
            initial_dir = str(vault_path)

    try:
        # tkinter must not run on the asyncio event loop thread — offload
        loop = asyncio.get_running_loop()
        selected = await loop.run_in_executor(None, _open_folder_dialog, initial_dir)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to open folder dialog: {e}",
        )

    if selected is None:
        return BrowseResponse(cancelled=True)

    return BrowseResponse(path=str(Path(selected).resolve()))
