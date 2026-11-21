import React, { useState } from 'react';
import {
  X,
  Save,
  Clock,
  Type,
  Layout,
  Sliders,
  Subtitles,
  Tv,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Sparkles
} from 'lucide-react';
import {
  CandidateClip,
  LayoutStrategy,
  GameplayCompositionMode,
  CaptionPreset,
  CaptionPlacement,
  CanvasResolution,
  MediaMetadata
} from '../types';

interface ClipEditorModalProps {
  clip: CandidateClip;
  isOpen: boolean;
  onClose: () => void;
  onSave: (
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
  ) => void;
  metadata?: MediaMetadata;
}

export const ClipEditorModal: React.FC<ClipEditorModalProps> = ({
  clip,
  isOpen,
  onClose,
  onSave,
  metadata,
}) => {
  const [title, setTitle] = useState(clip.title);
  const [startTime, setStartTime] = useState(clip.start_time);
  const [endTime, setEndTime] = useState(clip.end_time);

  // Layout & Reframing Overrides
  const [layoutStrategy, setLayoutStrategy] = useState<LayoutStrategy>(
    clip.layout_strategy || 'AUTO_GAMING'
  );
  const [gameplayComposition, setGameplayComposition] = useState<GameplayCompositionMode>(
    clip.gameplay_composition || 'AUTO'
  );
  const [splitRatio, setSplitRatio] = useState<number>(
    clip.split_ratio ?? 0.30
  );
  const [excludeChatOverlay, setExcludeChatOverlay] = useState<boolean>(
    clip.exclude_chat_overlay ?? true
  );

  // Caption Overrides
  const [captionPreset, setCaptionPreset] = useState<CaptionPreset>(
    clip.caption_preset || 'GAMING_KARAOKE'
  );
  const [captionPlacement, setCaptionPlacement] = useState<CaptionPlacement>(
    clip.caption_placement || 'AUTO'
  );

  // Export Quality Overrides
  const [resolution, setResolution] = useState<CanvasResolution>(
    clip.resolution || '1080x1920'
  );

  if (!isOpen) return null;

  const duration = Math.max(0, endTime - startTime);

  // Source-aware Quality calculations
  const targetH = resolution === '2160x3840' ? 3840 : resolution === '1440x2560' ? 2560 : 1920;
  const sourceMaxDim = Math.max(metadata?.width || 1920, metadata?.height || 1080);
  const sourceFps = metadata?.fps ? Math.round(metadata.fps) : 60;
  const isUpscaled = targetH > sourceMaxDim;
  const qualityLabel = isUpscaled
    ? `${resolution === '2160x3840' ? '4K' : '1440p'} — Upscaled from source`
    : 'Native / Source-supported';

  const streamerPercent = Math.round(splitRatio * 100);
  const gameplayPercent = 100 - streamerPercent;
  const streamerPx = Math.round(targetH * splitRatio);
  const gameplayPx = targetH - streamerPx;

  const showGamingControls =
    layoutStrategy === 'AUTO_GAMING' ||
    layoutStrategy === 'GAMING_SPLIT' ||
    layoutStrategy === 'GAMEPLAY_FOCUS';

  const showSplitSlider =
    layoutStrategy === 'AUTO_GAMING' || layoutStrategy === 'GAMING_SPLIT';

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (endTime <= startTime) return;
    onSave(clip.id, {
      title: title.trim(),
      start_time: Number(startTime),
      end_time: Number(endTime),
      layout_strategy: layoutStrategy,
      gameplay_composition: gameplayComposition,
      split_ratio: Number(splitRatio),
      exclude_chat_overlay: excludeChatOverlay,
      caption_preset: captionPreset,
      caption_placement: captionPlacement,
      resolution: resolution,
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl relative my-8 max-h-[90vh] overflow-y-auto">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-5 right-5 p-1.5 rounded-lg text-slate-400 hover:text-white bg-slate-800/60 hover:bg-slate-800 transition"
        >
          <X className="h-4 w-4" />
        </button>

        <h3 className="text-lg font-bold text-white mb-1">Edit Clip & Export Settings</h3>
        <p className="text-xs text-slate-400 mb-5">
          Fine-tune bounds, vertical layout geometry, caption styling, and export resolution.
        </p>

        <form onSubmit={handleSave} className="space-y-6">
          {/* Section 1: Title & Bounds */}
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                <Type className="h-3.5 w-3.5 text-indigo-400" />
                Clip Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-indigo-400" />
                  Start Time (sec)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={startTime}
                  onChange={(e) => setStartTime(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-indigo-400" />
                  End Time (sec)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min={startTime + 1}
                  value={endTime}
                  onChange={(e) => setEndTime(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                  required
                />
              </div>
            </div>

            <div className="p-2.5 bg-slate-950 rounded-xl border border-slate-800 text-xs text-slate-400 flex justify-between items-center">
              <span>Resulting Clip Duration:</span>
              <span className="font-semibold text-white">{duration.toFixed(1)} seconds</span>
            </div>
          </div>

          {/* Section 2: Layout & Composition */}
          <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-4">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
              <Layout className="h-4 w-4 text-indigo-400" />
              <span>Layout & Composition</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Layout Mode</label>
                <select
                  value={layoutStrategy}
                  onChange={(e) => setLayoutStrategy(e.target.value as LayoutStrategy)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                >
                  <option value="AUTO_GAMING">Auto Gaming (Smart Split / Gameplay)</option>
                  <option value="GAMING_SPLIT">Gaming Split (Streamer Top / Game Bottom)</option>
                  <option value="GAMEPLAY_FOCUS">Gameplay Focus (Full Vertical Game)</option>
                  <option value="STREAMER_FOCUS">Streamer Focus (Streamer Reaction)</option>
                  <option value="STANDARD_FACE_TRACK">Single-Speaker Face Track</option>
                  <option value="CENTER_CROP">Center Crop (Static 9:16)</option>
                </select>
              </div>

              {showGamingControls && (
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Gameplay Composition</label>
                  <select
                    value={gameplayComposition}
                    onChange={(e) => setGameplayComposition(e.target.value as GameplayCompositionMode)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                  >
                    <option value="AUTO">Auto (Content-loss driven)</option>
                    <option value="FIT_WITH_BLUR">Fit with Blur (100% Widescreen - Recommended)</option>
                    <option value="CROP_FILL">Crop Fill (Direct 9:10 bottom crop)</option>
                  </select>
                </div>
              )}
            </div>

            {showSplitSlider && (
              <div className="space-y-2 pt-1">
                <div className="flex justify-between text-xs text-slate-300">
                  <span className="flex items-center gap-1">
                    <Sliders className="h-3 w-3 text-indigo-400" />
                    Streamer Split Ratio
                  </span>
                  <span className="font-semibold text-indigo-300">
                    Streamer {streamerPercent}% / Gameplay {gameplayPercent}%
                  </span>
                </div>

                <input
                  type="range"
                  min="0.25"
                  max="0.50"
                  step="0.025"
                  value={splitRatio}
                  onChange={(e) => setSplitRatio(Number(e.target.value))}
                  className="w-full accent-indigo-500 cursor-pointer"
                />

                {/* Dual proportion visual bar */}
                <div className="h-3 w-full bg-slate-900 rounded-full overflow-hidden flex border border-slate-800">
                  <div
                    style={{ width: `${streamerPercent}%` }}
                    className="bg-indigo-500 h-full transition-all duration-150"
                    title={`Streamer Facecam: ${streamerPx}px`}
                  />
                  <div
                    style={{ width: `${gameplayPercent}%` }}
                    className="bg-teal-500 h-full transition-all duration-150"
                    title={`Gameplay: ${gameplayPx}px`}
                  />
                </div>
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span>Streamer: {streamerPx}px</span>
                  <span>Gameplay: {gameplayPx}px</span>
                </div>
              </div>
            )}

            {showGamingControls && (
              <label className="flex items-center gap-2 pt-1 text-xs text-slate-300 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={excludeChatOverlay}
                  onChange={(e) => setExcludeChatOverlay(e.target.checked)}
                  className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 bg-slate-900"
                />
                <span>Exclude Stream Chat / Overlays (Clamps gameplay width to X ≤ 1700px)</span>
              </label>
            )}
          </div>

          {/* Section 3: Captions */}
          <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-4">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
              <Subtitles className="h-4 w-4 text-amber-400" />
              <span>Captions & Placement</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Caption Preset</label>
                <select
                  value={captionPreset}
                  onChange={(e) => setCaptionPreset(e.target.value as CaptionPreset)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                >
                  <option value="GAMING_KARAOKE">Gaming Karaoke (Active Gold Pop - Default)</option>
                  <option value="CLEAN">Clean (Static White / Black Outline)</option>
                  <option value="MINIMAL">Minimal (Subtle / Thin Outline)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">Caption Placement</label>
                <select
                  value={captionPlacement}
                  onChange={(e) => setCaptionPlacement(e.target.value as CaptionPlacement)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                >
                  <option value="AUTO">Auto (Dynamic Split Seam - Default)</option>
                  <option value="LOWER_CENTER">Lower Center (Above Seam)</option>
                  <option value="CENTER">Center (Canvas Middle)</option>
                  <option value="TOP">Top (Streamer Bezel)</option>
                  <option value="BOTTOM">Bottom (Lower Gameplay)</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 4: Export Quality & Resolution */}
          <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-4">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
              <Tv className="h-4 w-4 text-emerald-400" />
              <span>Export Quality & Resolution</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Export Resolution</label>
                <select
                  value={resolution}
                  onChange={(e) => setResolution(e.target.value as CanvasResolution)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                >
                  <option value="1080x1920">Full HD — 1080x1920 (Standard Default)</option>
                  <option value="1440x2560">1440p — 1440x2560 (2K QHD)</option>
                  <option value="2160x3840">4K UHD — 2160x3840 (Explicit choice only)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">Preserved Frame Rate</label>
                <div className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-medium flex items-center justify-between">
                  <span>{sourceFps} FPS</span>
                  <span className="text-[10px] text-slate-400">Preserved from source</span>
                </div>
              </div>
            </div>

            {/* Source-Aware Quality Badge */}
            <div
              className={`p-2.5 rounded-xl border flex items-center gap-2 text-xs font-medium ${
                isUpscaled
                  ? 'bg-amber-950/40 text-amber-300 border-amber-500/30'
                  : 'bg-emerald-950/40 text-emerald-300 border-emerald-500/30'
              }`}
            >
              {isUpscaled ? (
                <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
              ) : (
                <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
              )}
              <span>{qualityLabel}</span>
            </div>
          </div>

          {/* Section 5: Pre-Render Export Summary */}
          <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl space-y-2 text-xs">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
              Pre-Render Export Summary
            </span>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px]">
              <div className="flex justify-between">
                <span className="text-slate-500">Layout:</span>
                <span className="text-slate-200 font-medium">{layoutStrategy}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Split:</span>
                <span className="text-slate-200 font-medium">
                  {showSplitSlider ? `${streamerPercent}% / ${gameplayPercent}%` : 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Gameplay:</span>
                <span className="text-slate-200 font-medium">
                  {showGamingControls ? gameplayComposition : 'Standard Crop'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Stream Chat:</span>
                <span className="text-slate-200 font-medium">
                  {excludeChatOverlay ? 'Excluded' : 'Included'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Captions:</span>
                <span className="text-slate-200 font-medium">
                  {captionPreset} ({captionPlacement})
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Resolution:</span>
                <span className="text-slate-200 font-medium">{resolution}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Frame Rate:</span>
                <span className="text-slate-200 font-medium">{sourceFps} FPS</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Quality:</span>
                <span className="text-slate-200 font-medium">{isUpscaled ? 'Upscaled' : 'Native'}</span>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 shadow-lg shadow-indigo-600/30 flex items-center gap-1.5 transition"
            >
              <Save className="h-3.5 w-3.5" />
              Save Adjustments
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
