"""Git service abstraction for MegaBook.

Provides controlled Git operations with manual commit requirements.
"""
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import git
from git import Repo


class GitError(Exception):
    """Base exception for Git operations."""
    pass


class GitService:
    """Service for Git operations with manual commit enforcement."""
    
    def __init__(self, repo_path: Path) -> None:
        """Initialize the Git service.
        
        Args:
            repo_path: Path to the Git repository
            
        Raises:
            GitError: If the path is not a valid Git repository
        """
        self.repo_path = Path(repo_path).resolve()
        
        try:
            self.repo = Repo(self.repo_path)
        except git.InvalidGitRepositoryError:
            raise GitError(f"{repo_path} is not a valid Git repository")
    
    @classmethod
    def init_repository(cls, repo_path: Path) -> "GitService":
        """Initialize a new Git repository.
        
        Args:
            repo_path: Path where to create the repository
            
        Returns:
            GitService instance for the new repository
        """
        repo_path = Path(repo_path).resolve()
        repo_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize git repo
        repo = Repo.init(repo_path)
        
        # Create .gitignore
        gitignore = repo_path / ".gitignore"
        gitignore.write_text(
            ".megabook/embeddings.sqlite\n"
            ".megabook/processing/\n"
            ".megabook/costs/\n"
            "*.log\n"
            ".env\n"
            "__pycache__/\n"
            "*.pyc\n"
            ".venv/\n"
            "node_modules/\n"
        )
        
        # Create .megabook metadata directory only
        (repo_path / ".megabook").mkdir(exist_ok=True)
        
        # Initial commit
        repo.git.add(".")
        repo.index.commit("Initial commit: MegaBook repository structure")
        
        return cls(repo_path)
    
    def get_status(self) -> dict:
        """Get the current repository status.
        
        Returns:
            Dictionary with status information
        """
        return {
            "is_dirty": self.repo.is_dirty(),
            "untracked_files": self.repo.untracked_files,
            "modified_files": [item.a_path for item in self.repo.index.diff(None)],
            "staged_files": [item.a_path for item in self.repo.index.diff("HEAD")],
            "active_branch": str(self.repo.active_branch),
            "commit_count": len(list(self.repo.iter_commits())),
        }
    
    def stage_files(self, paths: List[str]) -> None:
        """Stage files for commit.
        
        Args:
            paths: List of paths relative to repo root
        """
        for path in paths:
            full_path = self.repo_path / path
            if full_path.exists():
                self.repo.git.add(path)
    
    def stage_all(self) -> None:
        """Stage all changes (modified and untracked files)."""
        self.repo.git.add(".")
    
    def commit(self, message: str, author_name: Optional[str] = None) -> str:
        """Create a commit with the staged changes.
        
        This is the ONLY method that creates commits and MUST be called
        explicitly from the admin interface.
        
        Args:
            message: Commit message
            author_name: Optional author name override
            
        Returns:
            Commit hash
            
        Raises:
            GitError: If there are no staged changes
        """
        if not self.repo.index.diff("HEAD") and not self.repo.untracked_files:
            raise GitError("No changes to commit")
        
        # Stage untracked files if any
        if self.repo.untracked_files:
            self.repo.git.add(".")
        
        # Create commit
        commit = self.repo.index.commit(
            message,
            author=git.Actor(author_name or "MegaBook", "megabook@local")
        )
        
        return str(commit.hexsha)
    
    def get_history(
        self, 
        path: Optional[str] = None, 
        max_count: int = 50
    ) -> List[dict]:
        """Get commit history.
        
        Args:
            path: Optional path to filter history
            max_count: Maximum number of commits to return
            
        Returns:
            List of commit information dictionaries
        """
        commits = []
        
        kwargs = {"max_count": max_count}
        if path:
            kwargs["paths"] = path
        
        for commit in self.repo.iter_commits(**kwargs):
            commits.append({
                "hash": commit.hexsha,
                "short_hash": commit.hexsha[:7],
                "message": commit.message.strip(),
                "author": commit.author.name,
                "date": datetime.fromtimestamp(commit.committed_date).isoformat(),
            })
        
        return commits
    
    def get_diff(self, path: Optional[str] = None) -> str:
        """Get diff of uncommitted changes.
        
        Args:
            path: Optional specific path to diff
            
        Returns:
            Diff as string
        """
        if path:
            return self.repo.git.diff(path)
        return self.repo.git.diff()
    
    def get_file_diff(self, path: str, commit_hash: Optional[str] = None) -> str:
        """Get diff for a specific file.
        
        Args:
            path: Path to the file
            commit_hash: Optional specific commit to compare against
            
        Returns:
            Diff as string
        """
        if commit_hash:
            return self.repo.git.diff(f"{commit_hash}..HEAD", "--", path)
        return self.repo.git.diff("--", path)
    
    def discard_changes(self, paths: Optional[List[str]] = None) -> None:
        """Discard uncommitted changes.
        
        Args:
            paths: Optional list of specific paths to discard
        """
        if paths:
            for path in paths:
                self.repo.git.checkout("--", path)
        else:
            self.repo.git.checkout("--", ".")
    
    def has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        return self.repo.is_dirty() or bool(self.repo.untracked_files)
    
    def get_branches(self) -> List[str]:
        """Get list of branch names."""
        return [str(b) for b in self.repo.branches]