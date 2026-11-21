export type SourceType = 'local_file' | 'youtube';

export type ProjectStatus =
  | 'created'
  | 'ingested'
  | 'processing'
  | 'ready_for_review'
  | 'completed'
  | 'failed';

export type PipelineStage =
  | 'idle'
  | 'importing'
  | 'extracting_audio'
  | 'transcribing'
  | 'analyzing'
  | 'finding_clips'
  | 'reframing'
  | 'captioning'
  | 'rendering'
  | 'completed'
  | 'failed';

export interface MediaMetadata {
  duration: number;
  width: number;
  height: number;
  aspect_ratio: string;
  fps: number;
  video_codec: string;
  audio_codec: string;
  has_audio: boolean;
  file_size_bytes: number;
}

export interface ProjectSettings {
  min_clip_duration: number;
  max_clip_duration: number;
  candidate_count: number;
  whisper_model: string;
  llm_model: string;
}

export interface Project {
  id: string;
  title: string;
  source_type: SourceType;
  source_path?: string;
  source_url?: string;
  status: ProjectStatus;
  created_at: string;
  metadata?: MediaMetadata;
  settings: ProjectSettings;
  error?: string;
}

export type LayoutStrategy =
  | 'AUTO_GAMING'
  | 'GAMING_SPLIT'
  | 'GAMEPLAY_FOCUS'
  | 'STREAMER_FOCUS'
  | 'STANDARD_FACE_TRACK'
  | 'CENTER_CROP';

export type GameplayCompositionMode = 'AUTO' | 'FIT_WITH_BLUR' | 'CROP_FILL';

export type CaptionPreset = 'GAMING_KARAOKE' | 'CLEAN' | 'MINIMAL';

export type CaptionPlacement = 'AUTO' | 'TOP' | 'CENTER' | 'LOWER_CENTER' | 'BOTTOM';

export type CanvasResolution = '1080x1920' | '1440x2560' | '2160x3840';

export type ReactionCategory =
  | 'FUNNY_REACTION'
  | 'SURPRISE'
  | 'CHAOTIC_MOMENT'
  | 'FAIL'
  | 'RAGE'
  | 'EPIC_MOMENT'
  | 'WIN'
  | 'FUNNY_DIALOGUE'
  | 'STORY_MOMENT'
  | 'GENERAL_HIGHLIGHT';

export interface ScoreBreakdown {
  hook_strength: number;
  standalone_clarity: number;
  information_density: number;
  pacing_and_flow: number;
  total_score: number;
  explanation: string;

  // Multimodal factors
  category?: ReactionCategory;
  transcript_context_score?: number;
  audio_reaction_score?: number;
  streamer_visual_reaction_score?: number;
  gameplay_activity_score?: number;
  hook_score?: number;
  payoff_score?: number;
  penalties?: number;
  peak_z_score?: number;
  reaction_density?: number;
}

export interface CandidateClip {
  id: string;
  project_id: string;
  title: string;
  start_time: number;
  end_time: number;
  duration: number;
  transcript_excerpt: string;
  hook_assessment: string;
  standalone_context: string;
  reasoning: string;
  score: ScoreBreakdown;
  selected_for_rendering: boolean;
  rendered_clip_path?: string;

  // Phase 14 Layout, Composition, Quality, and Caption Overrides:
  layout_strategy?: LayoutStrategy;
  gameplay_composition?: GameplayCompositionMode;
  split_ratio?: number;
  exclude_chat_overlay?: boolean;
  caption_preset?: CaptionPreset;
  caption_placement?: CaptionPlacement;
  resolution?: CanvasResolution;
}

export interface CandidateList {
  project_id: string;
  candidates: CandidateClip[];
  model_used: string;
}

export interface HardwareCapabilities {
  device: 'cpu' | 'cuda';
  compute_type: string;
  cuda_available: boolean;
  device_name: string;
  gpu_count: number;
  total_memory_gb?: number;
  description: string;
}
