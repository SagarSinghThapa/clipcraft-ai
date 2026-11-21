import {
  Project,
  CandidateList,
  CandidateClip,
  HardwareCapabilities,
  SourceType,
  LayoutStrategy,
  GameplayCompositionMode,
  CaptionPreset,
  CaptionPlacement,
  CanvasResolution,
} from '../types';

const API_BASE = '/api';

export const api = {
  async getHardware(): Promise<HardwareCapabilities> {
    const res = await fetch(`${API_BASE}/hardware`);
    if (!res.ok) throw new Error('Failed to fetch hardware status');
    return res.json();
  },

  async createProject(params: {
    title?: string;
    source_type: SourceType;
    source_url?: string;
    min_clip_duration: number;
    max_clip_duration: number;
    candidate_count: number;
    whisper_model: string;
    llm_model: string;
  }): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create project');
    }
    return res.json();
  },

  async listProjects(): Promise<Project[]> {
    const res = await fetch(`${API_BASE}/projects`);
    if (!res.ok) throw new Error('Failed to list projects');
    return res.json();
  },

  async getProject(projectId: string): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${projectId}`);
    if (!res.ok) throw new Error('Failed to get project');
    return res.json();
  },

  async ingestLocalFile(projectId: string, filePath: string): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/ingest/file`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: filePath }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to ingest local file');
    }
    return res.json();
  },

  async ingestYouTube(projectId: string, url: string): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/ingest/youtube`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to download YouTube video');
    }
    return res.json();
  },

  async transcribe(projectId: string, modelSize = 'base'): Promise<any> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/transcribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_size: modelSize }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Transcription failed');
    }
    return res.json();
  },

  async analyzeHighlights(
    projectId: string,
    llmModel = 'llama3.2:3b',
    maxCandidates = 5
  ): Promise<CandidateList> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        llm_model: llmModel,
        max_candidates: maxCandidates,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Analysis failed');
    }
    return res.json();
  },

  async getCandidates(projectId: string): Promise<CandidateList> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/candidates`);
    if (!res.ok) throw new Error('Failed to load candidate clips');
    return res.json();
  },

  async updateCandidate(
    projectId: string,
    clipId: string,
    updates: Partial<{
      title: string;
      start_time: number;
      end_time: number;
      selected_for_rendering: boolean;
      layout_strategy: LayoutStrategy;
      gameplay_composition: GameplayCompositionMode;
      split_ratio: number;
      exclude_chat_overlay: boolean;
      caption_preset: CaptionPreset;
      caption_placement: CaptionPlacement;
      resolution: CanvasResolution;
    }>
  ): Promise<CandidateClip> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/candidates/${clipId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error('Failed to update candidate');
    return res.json();
  },

  async cutClips(projectId: string, clipId?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/clips/cut`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clip_id: clipId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Video cutting failed');
    }
    return res.json();
  },

  async reframeClips(
    projectId: string,
    clipId?: string,
    options?: {
      layout_strategy?: LayoutStrategy;
      gameplay_composition?: GameplayCompositionMode;
      split_ratio?: number;
      exclude_chat_overlay?: boolean;
      resolution?: CanvasResolution;
      force_recompute?: boolean;
    }
  ): Promise<any> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/reframe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        clip_id: clipId,
        force_recompute: options?.force_recompute ?? (clipId ? true : false),
        ...options,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Reframing failed');
    }
    return res.json();
  },

  async burnCaptions(
    projectId: string,
    clipId?: string,
    options?: {
      preset?: CaptionPreset;
      placement?: CaptionPlacement;
      force_recompute?: boolean;
    }
  ): Promise<any> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/captions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        clip_id: clipId,
        force_recompute: options?.force_recompute ?? (clipId ? true : false),
        ...options,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Caption burning failed');
    }
    return res.json();
  },

  getMediaUrl(projectId: string, relativeSubPath: string): string {
    return `/media/${projectId}/${relativeSubPath.replace(/\\/g, '/')}`;
  },
};
