import React, { useState, useEffect } from 'react';
import { Navbar } from '../components/Navbar';
import { ImportCard } from '../components/ImportCard';
import { JobProgress } from '../components/JobProgress';
import { CandidateCard } from '../components/CandidateCard';
import { ClipEditorModal } from '../components/ClipEditorModal';
import { api } from '../services/api';
import {
  Project,
  CandidateClip,
  HardwareCapabilities,
  PipelineStage,
  SourceType,
  LayoutStrategy,
  GameplayCompositionMode,
  CaptionPreset,
  CaptionPlacement,
  CanvasResolution,
} from '../types';
import { Sparkles, Video, DownloadCloud, RefreshCw } from 'lucide-react';

export const Dashboard: React.FC = () => {
  const [hardware, setHardware] = useState<HardwareCapabilities | null>(null);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [candidates, setCandidates] = useState<CandidateClip[]>([]);
  const [currentStage, setCurrentStage] = useState<PipelineStage>('idle');
  const [stageMessage, setStageMessage] = useState('Ready for input video');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [editingClip, setEditingClip] = useState<CandidateClip | null>(null);

  useEffect(() => {
    api.getHardware()
      .then(setHardware)
      .catch((err) => console.error('Error fetching hardware info:', err));

    const params = new URLSearchParams(window.location.search);
    const requestedProject = params.get('project');

    if (requestedProject) {
      loadProject(requestedProject);
    }
  }, []);

  const loadProject = async (projectId: string) => {
    try {
      const proj = await api.getProject(projectId);
      setActiveProject(proj);
      const cands = await api.getCandidates(projectId);
      setCandidates(cands.candidates || []);
    } catch (err: any) {
      console.warn('Could not auto-load project candidates:', err);
    }
  };

  const handleStartProcessing = async (params: {
    sourceType: SourceType;
    sourceValue: string;
    whisperModel: string;
    llmModel: string;
    minDuration: number;
    maxDuration: number;
    candidateCount: number;
  }) => {
    setIsProcessing(true);
    setErrorMessage(null);
    setCandidates([]);

    try {
      // Step 1: Create Project
      setCurrentStage('importing');
      setStageMessage('Initializing project workspace...');
      const project = await api.createProject({
        source_type: params.sourceType,
        source_url: params.sourceType === 'youtube' ? params.sourceValue : undefined,
        min_clip_duration: params.minDuration,
        max_clip_duration: params.maxDuration,
        candidate_count: params.candidateCount,
        whisper_model: params.whisperModel,
        llm_model: params.llmModel,
      });
      setActiveProject(project);

      // Step 2: Ingestion
      if (params.sourceType === 'local_file') {
        setStageMessage(`Validating and importing local video: ${params.sourceValue}`);
        await api.ingestLocalFile(project.id, params.sourceValue);
      } else {
        setStageMessage(`Downloading authorized YouTube video: ${params.sourceValue}`);
        await api.ingestYouTube(project.id, params.sourceValue);
      }

      // Step 3: Audio Extraction & Transcription
      setCurrentStage('transcribing');
      setStageMessage(`Extracting audio and transcribing locally with Whisper (${params.whisperModel})...`);
      await api.transcribe(project.id, params.whisperModel);

      // Step 4: AI Highlight Discovery
      setCurrentStage('analyzing');
      setStageMessage(`Discovering highlight candidates via Ollama (${params.llmModel})...`);
      const candidatesData = await api.analyzeHighlights(
        project.id,
        params.llmModel,
        params.candidateCount
      );
      setCandidates(candidatesData.candidates);

      // Step 5: Precision Cutting
      setCurrentStage('finding_clips');
      setStageMessage('Performing frame-accurate FFmpeg cuts on candidate highlights...');
      await api.cutClips(project.id);

      // Step 6: 9:16 Vertical Reframing
      setCurrentStage('reframing');
      setStageMessage('Detecting speaker faces and reframing clips to vertical 9:16...');
      await api.reframeClips(project.id);

      // Step 7: Captioning & Filtergraph Burning
      setCurrentStage('captioning');
      setStageMessage('Generating word-synchronized subtitles and burning into final MP4...');
      await api.burnCaptions(project.id);

      // Final: Refresh Candidates with Rendered Paths
      const refreshed = await api.getCandidates(project.id);
      setCandidates(refreshed.candidates);

      setCurrentStage('completed');
      setStageMessage('All candidate clips successfully processed, reframed, and captioned!');
    } catch (err: any) {
      console.error('Pipeline processing error:', err);
      setCurrentStage('failed');
      setErrorMessage(err.message || 'Pipeline encountered an unexpected error.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleEditSave = async (
    clipId: string,
    updates: {
      title: string;
      start_time: number;
      end_time: number;
      layout_strategy?: LayoutStrategy;
      gameplay_composition?: GameplayCompositionMode;
      split_ratio?: number;
      exclude_chat_overlay?: boolean;
      caption_preset?: CaptionPreset;
      caption_placement?: CaptionPlacement;
      resolution?: CanvasResolution;
    }
  ) => {
    if (!activeProject) return;
    try {
      const updated = await api.updateCandidate(activeProject.id, clipId, updates);
      setCandidates((prev) =>
        prev.map((c) => (c.id === clipId ? { ...c, ...updated } : c))
      );
    } catch (err: any) {
      alert(`Failed to save adjustments: ${err.message}`);
    }
  };

  const handleRenderSingle = async (clipId: string) => {
    if (!activeProject) return;
    try {
      setIsProcessing(true);
      setCurrentStage('rendering');
      setStageMessage(`Re-rendering clip '${clipId}' with custom bounds and captions...`);

      const targetClip = candidates.find((c) => c.id === clipId);

      // Re-cut bounds if needed
      await api.cutClips(activeProject.id, clipId);

      // Reframe with per-clip layout overrides
      await api.reframeClips(activeProject.id, clipId, {
        layout_strategy: targetClip?.layout_strategy,
        gameplay_composition: targetClip?.gameplay_composition,
        split_ratio: targetClip?.split_ratio,
        exclude_chat_overlay: targetClip?.exclude_chat_overlay,
        resolution: targetClip?.resolution,
        force_recompute: true,
      });

      // Burn captions with per-clip styling overrides
      await api.burnCaptions(activeProject.id, clipId, {
        preset: targetClip?.caption_preset,
        placement: targetClip?.caption_placement,
        force_recompute: true,
      });

      const refreshed = await api.getCandidates(activeProject.id);
      setCandidates(refreshed.candidates);

      setCurrentStage('completed');
      setStageMessage(`Clip '${clipId}' re-rendered successfully!`);
    } catch (err: any) {
      alert(`Failed to render clip: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Navbar hardware={hardware} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Hero Section */}
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <h2 className="text-3xl font-extrabold text-white tracking-tight sm:text-4xl">
            Free, Local AI Video Clipping
          </h2>
          <p className="text-slate-400 text-sm">
            Convert long videos into 9:16 vertical short-form clips with animated captions—completely
            on your machine without cloud subscriptions.
          </p>
        </div>

        {/* Active Project Banner */}
        {activeProject && (
          <div className="bg-slate-900/90 border border-indigo-500/30 rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-lg shadow-indigo-950/20">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/20">
                <Video className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-white text-base">{activeProject.title || activeProject.id}</h3>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                    {activeProject.id}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Source: {activeProject.metadata?.width || 1920}x{activeProject.metadata?.height || 1080} @ {activeProject.metadata?.fps || 60} FPS • {activeProject.source_type}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-indigo-300 bg-indigo-500/10 px-3 py-1.5 rounded-lg border border-indigo-500/20 font-medium">
                {candidates.length} Reaction Candidates
              </span>
            </div>
          </div>
        )}

        {/* Import Card */}
        <ImportCard onStartProcessing={handleStartProcessing} isLoading={isProcessing} />

        {/* Live Stage Progress */}
        {currentStage !== 'idle' && (
          <JobProgress
            currentStage={currentStage}
            stageMessage={stageMessage}
            error={errorMessage}
          />
        )}

        {/* Results Gallery */}
        {candidates.length > 0 && (
          <div className="space-y-6 pt-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-indigo-400" />
                  Generated Candidate Highlights ({candidates.length})
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Preview 9:16 vertical video with burned captions. Edit bounds or download MP4/SRT files.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-xs text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20 font-medium">
                  {candidates.filter((c) => c.selected_for_rendering).length} Selected for Export
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {candidates.map((clip) => (
                <CandidateCard
                  key={clip.id}
                  clip={clip}
                  projectId={activeProject?.id || ''}
                  onEdit={(c) => setEditingClip(c)}
                  onRenderSingle={handleRenderSingle}
                  isRendering={isProcessing}
                />
              ))}
            </div>
          </div>
        )}

        {/* Clip Editor Modal */}
        {editingClip && (
          <ClipEditorModal
            clip={editingClip}
            isOpen={true}
            onClose={() => setEditingClip(null)}
            onSave={handleEditSave}
            metadata={activeProject?.metadata}
          />
        )}
      </main>
    </div>
  );
};
