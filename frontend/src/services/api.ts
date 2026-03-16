import axios, { AxiosInstance } from 'axios';
import { VaultInfo } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // Health check
  async healthCheck() {
    const response = await this.client.get('/health');
    return response.data;
  }

  // Filesystem API
  async listFiles(folder?: string) {
    const params = folder ? { folder } : {};
    const response = await this.client.get('/api/filesystem/files', { params });
    return response.data;
  }

  async getFileTree(folder?: string) {
    const params = folder ? { folder } : {};
    const response = await this.client.get('/api/filesystem/tree', { params });
    return response.data;
  }

  async readFile(path: string) {
    const response = await this.client.get(`/api/filesystem/files/${encodeURIComponent(path)}`);
    return response.data;
  }

  async writeFile(path: string, content: string) {
    const response = await this.client.post('/api/filesystem/files', { path, content });
    return response.data;
  }

  async deleteFile(path: string) {
    const response = await this.client.delete(`/api/filesystem/files/${encodeURIComponent(path)}`);
    return response.data;
  }

  async renameFile(oldPath: string, newPath: string) {
    const response = await this.client.post('/api/filesystem/rename', { old_path: oldPath, new_path: newPath });
    return response.data;
  }

  async copyFile(sourcePath: string, targetPath: string) {
    const response = await this.client.post('/api/filesystem/copy', { source_path: sourcePath, target_path: targetPath });
    return response.data;
  }

  async createFolder(path: string) {
    const response = await this.client.post('/api/filesystem/mkdir', { path });
    return response.data;
  }

  async uploadFile(file: File, path: string, onProgress?: (progress: number) => void) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await this.client.post(`/api/filesystem/upload?path=${encodeURIComponent(path)}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: onProgress ? (progressEvent) => {
        const percentCompleted = progressEvent.total 
          ? Math.round((progressEvent.loaded * 100) / progressEvent.total)
          : 0;
        onProgress(percentCompleted);
      } : undefined,
    });
    return response.data;
  }

  // Git API
  async getGitStatus() {
    const response = await this.client.get('/api/git/status');
    return response.data;
  }

  async createCommit(message: string, authorName?: string) {
    const response = await this.client.post('/api/git/commit', { message, author_name: authorName });
    return response.data;
  }

  async getGitHistory(path?: string, maxCount: number = 50) {
    const params: { max_count: number; path?: string } = { max_count: maxCount };
    if (path) params.path = path;
    const response = await this.client.get('/api/git/history', { params });
    return response.data;
  }

  async getDiff(path?: string) {
    const params = path ? { path } : {};
    const response = await this.client.get('/api/git/diff', { params });
    return response.data;
  }

  async stageFiles(paths: string[]) {
    const response = await this.client.post('/api/git/stage', paths);
    return response.data;
  }

  async stageAll() {
    const response = await this.client.post('/api/git/stage-all');
    return response.data;
  }

  // Pipeline API
  async startImportPipeline(sourcePath?: string, targetSubdir: string = '') {
    const params: { source_path?: string; target_subdir: string } = { target_subdir: targetSubdir };
    if (sourcePath) params.source_path = sourcePath;
    const response = await this.client.post('/api/pipelines/import/start', null, { params });
    return response.data;
  }

  async uploadFileToPipeline(file: File, targetSubdir: string = '') {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await this.client.post('/api/pipelines/import/upload', formData, {
      params: { target_subdir: targetSubdir },
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async startStructuringPipeline(promptPaths?: string[]) {
    const params = promptPaths ? { prompt_paths: promptPaths } : {};
    const response = await this.client.post('/api/pipelines/structuring/start', null, { params });
    return response.data;
  }

  async processSessionNotes(content: string, sessionId?: string) {
    const response = await this.client.post('/api/pipelines/structuring/session', {
      content,
      session_id: sessionId,
    });
    return response.data;
  }

  async getProposedChanges(pipelineId: string) {
    const response = await this.client.get(`/api/pipelines/structuring/${pipelineId}/changes`);
    return response.data;
  }

  async applyChanges(pipelineId: string, changeIndices?: number[]) {
    const response = await this.client.post('/api/pipelines/structuring/apply', {
      pipeline_id: pipelineId,
      change_indices: changeIndices,
    });
    return response.data;
  }

  async startWikiPipeline(notePaths?: string[], audienceLevels: string[] = ['dm']) {
    const params: { note_paths?: string[]; audience_levels: string[] } = { audience_levels: audienceLevels };
    if (notePaths) params.note_paths = notePaths;
    const response = await this.client.post('/api/pipelines/wiki/start', null, { params });
    return response.data;
  }

  async startEmbeddingPipeline(notePaths?: string[], rebuild: boolean = false) {
    const params: { note_paths?: string[]; rebuild: boolean } = { rebuild };
    if (notePaths) params.note_paths = notePaths;
    const response = await this.client.post('/api/pipelines/embedding/start', null, { params });
    return response.data;
  }

  async runPipeline(pipelineId: string, resume: boolean = false) {
    const response = await this.client.post(`/api/pipelines/run/${pipelineId}`, null, {
      params: { resume },
    });
    return response.data;
  }

  async pausePipeline(pipelineId: string) {
    const response = await this.client.post(`/api/pipelines/pause/${pipelineId}`);
    return response.data;
  }

  async resumePipeline(pipelineId: string) {
    const response = await this.client.post(`/api/pipelines/resume/${pipelineId}`);
    return response.data;
  }

  async stopPipeline(pipelineId: string) {
    const response = await this.client.post(`/api/pipelines/stop/${pipelineId}`);
    return response.data;
  }

  async getPipelineStatus(pipelineId: string) {
    const response = await this.client.get(`/api/pipelines/status/${pipelineId}`);
    return response.data;
  }

  async listActivePipelines() {
    const response = await this.client.get('/api/pipelines/active');
    return response.data;
  }

  // Query API
  async searchNotes(query: string, nResults: number = 5) {
    const response = await this.client.post('/api/query/search', {
      query,
      n_results: nResults,
    });
    return response.data;
  }

  async ragQuery(query: string, nResults: number = 5, audienceLevel: string = 'dm') {
    const response = await this.client.post('/api/query/rag', {
      query,
      n_results: nResults,
      audience_level: audienceLevel,
    });
    return response.data;
  }

  async getEmbeddingStats() {
    const response = await this.client.get('/api/query/stats');
    return response.data;
  }

  // Cost API
  async getCurrentSessionCosts() {
    const response = await this.client.get('/api/costs/current-session');
    return response.data;
  }

  async getCostStats() {
    const response = await this.client.get('/api/costs/stats');
    return response.data;
  }

  async listCostSessions() {
    const response = await this.client.get('/api/costs/sessions');
    return response.data;
  }

  async updateCostLimit(costLimitNok: number) {
    const response = await this.client.post('/api/costs/limit', { cost_limit_nok: costLimitNok });
    return response.data;
  }

  // Entity Extraction API
  async startEntityExtraction(notePath: string) {
    const response = await this.client.post('/api/pipelines/extraction/start', {
      note_path: notePath,
    });
    return response.data;
  }

  async runEntityExtraction(pipelineId: string) {
    const response = await this.client.post(`/api/pipelines/extraction/${pipelineId}/run`);
    return response.data;
  }

  // Sync Status API
  async getSyncStatus(path: string) {
    const response = await this.client.get('/api/filesystem/sync-status', {
      params: { path },
    });
    return response.data;
  }

  async getSyncStatusBatch(paths: string[]) {
    const response = await this.client.post('/api/filesystem/sync-status/batch', paths);
    return response.data;
  }

  // Entity & Alias API
  async listEntities(entityType?: string) {
    const params = entityType ? { entity_type: entityType } : {};
    const response = await this.client.get('/api/entities', { params });
    return response.data;
  }

  async getEntity(canonicalName: string) {
    const response = await this.client.get(`/api/entities/${encodeURIComponent(canonicalName)}`);
    return response.data;
  }

  async createEntityAlias(canonicalName: string, alias: string, entityType: string, disambiguationNote?: string) {
    const response = await this.client.post('/api/entities', {
      canonical_name: canonicalName,
      alias,
      entity_type: entityType,
      disambiguation_note: disambiguationNote,
    });
    return response.data;
  }

  async resolveEntityName(name: string) {
    const response = await this.client.post('/api/entities/resolve', { name });
    return response.data;
  }

  async searchEntities(query: string, entityType?: string) {
    const params: { query: string; entity_type?: string } = { query };
    if (entityType) params.entity_type = entityType;
    const response = await this.client.get('/api/entities/search', { params });
    return response.data;
  }

  async mergeEntities(keepName: string, mergeName: string) {
    const response = await this.client.post('/api/entities/merge', {
      keep_name: keepName,
      merge_name: mergeName,
    });
    return response.data;
  }

  async removeAlias(canonicalName: string, alias: string) {
    const response = await this.client.delete(
      `/api/entities/${encodeURIComponent(canonicalName)}/aliases/${encodeURIComponent(alias)}`
    );
    return response.data;
  }

  async suggestAliases(canonicalName: string, entityType: string) {
    const response = await this.client.get(
      `/api/entities/${encodeURIComponent(canonicalName)}/suggestions`,
      { params: { entity_type: entityType } }
    );
    return response.data;
  }

  // Image Generation API
  async getStyleTemplates() {
    const response = await this.client.get('/api/imagegen/styles');
    return response.data;
  }

  async countImageTokens(filePaths: string[]) {
    const response = await this.client.post('/api/imagegen/count-tokens', {
      file_paths: filePaths,
    });
    return response.data;
  }

  async generateImage(data: {
    prompt: string;
    context_files: string[];
    style_template_id?: string;
  }) {
    const response = await this.client.post('/api/imagegen/generate', data);
    return response.data;
  }

  async getImageHistory(limit: number = 20) {
    const response = await this.client.get('/api/imagegen/history', {
      params: { limit },
    });
    return response.data;
  }

  async getImageGallery(limit: number = 50, offset: number = 0) {
    const response = await this.client.get('/api/imagegen/gallery', {
      params: { limit, offset },
    });
    return response.data;
  }

  async createImagePrompt(data: {
    name: string;
    category: string;
    description: string;
    base_prompt: string;
    style_suffix?: string;
    negative_prompt?: string;
  }) {
    const response = await this.client.post('/api/imagegen/prompts', data);
    return response.data;
  }

  async updateImagePrompt(promptId: string, data: {
    name: string;
    category: string;
    description: string;
    base_prompt: string;
    style_suffix?: string;
    negative_prompt?: string;
  }) {
    const response = await this.client.put(`/api/imagegen/prompts/${encodeURIComponent(promptId)}`, data);
    return response.data;
  }

  async deleteImagePrompt(promptId: string) {
    const response = await this.client.delete(`/api/imagegen/prompts/${encodeURIComponent(promptId)}`);
    return response.data;
  }

  // Simple Chat API (no RAG, just LLM)
  async generateSimpleChat(message: string) {
    console.log('📝 [Chat] Sending message:', message);
    const startTime = Date.now();
    try {
      const response = await this.client.post('/api/chat/simple', {
        message,
      });
      const duration = Date.now() - startTime;
      console.log(`🤖 [Chat] Response received in ${duration}ms:`, response.data);
      return response.data;
    } catch (error) {
      console.error('❌ [Chat] Error:', error);
      throw error;
    }
  }

  // Conversation Chat API with history
  async generateConversationChat(
    message: string,
    chatId?: string,
    history?: Array<{ role: string; content: string }>,
    accessMode: string = 'dm',
    characterName?: string,
  ) {
    console.log('📝 [ConversationChat] Sending message:', message, 'Chat ID:', chatId, 'Access:', accessMode, characterName || '');
    const startTime = Date.now();
    try {
      const response = await this.client.post('/api/chat/conversation', {
        message,
        chat_id: chatId,
        history: history,
        access_mode: accessMode,
        character_name: characterName || null,
      });
      const duration = Date.now() - startTime;
      console.log(`🤖 [ConversationChat] Response received in ${duration}ms:`, response.data);
      return response.data as {
        content: string;
        model: string;
        tokens_used: number;
        prompt_tokens: number;
        completion_tokens: number;
        context_window: number;
        chat_id: string;
        history: Array<{ role: string; content: string }>;
        tool_usage: Array<{ tool_name: string; arguments: Record<string, any>; result_preview: string }>;
        agent_iterations: number;
      };
    } catch (error) {
      console.error('❌ [ConversationChat] Error:', error);
      throw error;
    }
  }

  async getChatHistory(chatId: string) {
    console.log('📚 [Chat] Loading history for chat:', chatId);
    try {
      const response = await this.client.get(`/api/chat/history/${encodeURIComponent(chatId)}`);
      return response.data as Array<{ role: string; content: string }>;
    } catch (error) {
      console.error('❌ [Chat] Failed to load history:', error);
      throw error;
    }
  }

  async deleteChatHistory(chatId: string) {
    console.log('[Chat] Deleting chat history:', chatId);
    try {
      const response = await this.client.delete(`/api/chat/history/${encodeURIComponent(chatId)}`);
      return response.data;
    } catch (error) {
      console.error('[Chat] Failed to delete history:', error);
      throw error;
    }
  }

  async listChatSessions() {
    console.log('[Chat] Loading session list');
    try {
      const response = await this.client.get('/api/chat/sessions');
      return response.data as {
        sessions: Array<{
          id: string;
          title: string;
          created_at: string;
          updated_at: string;
          message_count: number;
          preview: string;
        }>;
      };
    } catch (error) {
      console.error('[Chat] Failed to load sessions:', error);
      throw error;
    }
  }

  async renameChatSession(chatId: string, title: string) {
    console.log('[Chat] Renaming session:', chatId, 'to:', title);
    try {
      const response = await this.client.patch(`/api/chat/sessions/${encodeURIComponent(chatId)}`, {
        title,
      });
      return response.data as {
        id: string;
        title: string;
        created_at: string;
        updated_at: string;
        message_count: number;
        preview: string;
      };
    } catch (error) {
      console.error('[Chat] Failed to rename session:', error);
      throw error;
    }
  }

  async compactChat(chatId: string) {
    console.log('[Chat] Compacting chat:', chatId);
    const startTime = Date.now();
    try {
      const response = await this.client.post('/api/chat/compact', {
        chat_id: chatId,
      });
      const duration = Date.now() - startTime;
      console.log(`[Chat] Compaction completed in ${duration}ms:`, response.data);
      return response.data as {
        new_chat_id: string;
        old_chat_id: string;
        summary: string;
        history: Array<{ role: string; content: string }>;
        prompt_tokens: number;
        context_window: number;
      };
    } catch (error) {
      console.error('[Chat] Compaction failed:', error);
      throw error;
    }
  }

  // Vault API
  async getVault(): Promise<VaultInfo> {
    const response = await this.client.get('/api/vault');
    return response.data;
  }

  async setVault(path: string): Promise<VaultInfo> {
    const response = await this.client.post('/api/vault', { path });
    return response.data;
  }

  async openVaultInExplorer(): Promise<{ status: string; path: string }> {
    const response = await this.client.post('/api/vault/open-explorer');
    return response.data;
  }

  async browseForVault(): Promise<{ path: string | null; cancelled: boolean }> {
    const response = await this.client.post('/api/vault/browse');
    return response.data;
  }
}

export const api = new ApiService();