// Types for MegaBook frontend

export interface FileInfo {
  path: string;
  layer: 'prompts' | 'notes' | 'wiki';
  relative_path: string;
  size: number;
  modified: number;
}

export interface FileTreeNode {
  type: 'file' | 'directory';
  path?: string;
  size?: number;
  modified?: number;
  children?: Record<string, FileTreeNode>;
}

export interface FileContent {
  path: string;
  content: string;
  layer: string;
}

export interface GitStatus {
  is_dirty: boolean;
  untracked_files: string[];
  modified_files: string[];
  staged_files: string[];
  active_branch: string;
  commit_count: number;
}

export interface CommitInfo {
  hash: string;
  short_hash: string;
  message: string;
  author: string;
  date: string;
}

export interface PipelineStatus {
  pipeline_id: string;
  pipeline_type: string;
  state: 'idle' | 'running' | 'paused' | 'completed' | 'error';
  progress_percentage: number;
  current_step: number;
  total_steps: number;
  current_item: string | null;
  error_message: string | null;
}

export interface CostStats {
  current_session_cost_nok: number;
  current_session_cost_usd: number;
  cost_limit_nok: number;
  is_limit_reached: boolean;
  total_costs_7d: {
    nok: string;
    usd: string;
  };
  total_costs_30d: {
    nok: string;
    usd: string;
  };
}

export interface SearchResult {
  id: string;
  content: string;
  metadata: Record<string, unknown>;
  distance: number;
  score: number;
}

export interface RAGResponse {
  query: string;
  answer: string;
  sources: SearchResult[];
}

export interface ProposedChange {
  operation: 'create' | 'update' | 'merge';
  target_path: string;
  current_content: string | null;
  proposed_content: string;
  reason: string;
  confidence: number;
}

export type AdminTab = 
  | 'import'
  | 'structure'
  | 'wiki'
  | 'embeddings'
  | 'costs'
  | 'diff'
  | 'git';