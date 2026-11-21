import React, { useState } from 'react';
import {
  Sparkles,
  Clock,
  Edit2,
  CheckCircle,
  FileText,
  ChevronDown,
  ChevronUp,
  Flame,
  Smartphone,
  Subtitles,
  Download
} from 'lucide-react';
import { CandidateClip } from '../types';
import { VideoPlayer } from './VideoPlayer';

interface CandidateCardProps {
  clip: CandidateClip;
  projectId: string;
  onEdit: (clip: CandidateClip) => void;
  onRenderSingle: (clipId: string) => void;
  isRendering: boolean;
}

export const CandidateCard: React.FC<CandidateCardProps> = ({
  clip,
  projectId,
  onEdit,
  onRenderSingle,
  isRendering,
}) => {
  const [showDetails, setShowDetails] = useState(false);

  // Score color helper
  const getScoreColor = (score: number) => {
    if (score >= 85) return 'from-emerald-500 to-teal-400 text-emerald-300 border-emerald-500/30';
    if (score >= 70) return 'from-indigo-500 to-violet-400 text-indigo-300 border-indigo-500/30';
    return 'from-amber-500 to-orange-400 text-amber-300 border-amber-500/30';
  };

  const getCategoryBadge = (category?: string) => {
    switch (category) {
      case 'SURPRISE':
        return { label: 'Surprise', color: 'bg-purple-900/40 text-purple-300 border-purple-500/30' };
      case 'RAGE':
        return { label: 'Rage', color: 'bg-rose-900/40 text-rose-300 border-rose-500/30' };
      case 'FAIL':
        return { label: 'Fail', color: 'bg-red-900/40 text-red-300 border-red-500/30' };
      case 'CHAOTIC_MOMENT':
        return { label: 'Chaotic', color: 'bg-amber-900/40 text-amber-300 border-amber-500/30' };
      case 'FUNNY_REACTION':
        return { label: 'Funny Reaction', color: 'bg-yellow-900/40 text-yellow-300 border-yellow-500/30' };
      case 'EPIC_MOMENT':
      case 'WIN':
        return { label: 'Epic Win', color: 'bg-emerald-900/40 text-emerald-300 border-emerald-500/30' };
      case 'FUNNY_DIALOGUE':
        return { label: 'Funny Dialogue', color: 'bg-cyan-900/40 text-cyan-300 border-cyan-500/30' };
      default:
        return { label: 'Highlight', color: 'bg-slate-800 text-slate-300 border-slate-700' };
    }
  };

  const categoryInfo = getCategoryBadge(clip.score.category);

  const finalVideoUrl = clip.rendered_clip_path
    ? `/media/${projectId}/clips/${clip.id}/final_clip.mp4`
    : `/media/${projectId}/clips/${clip.id}/reframed.mp4`;

  const srtUrl = `/api/projects/${projectId}/captions/${clip.id}/srt`;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 sm:p-6 shadow-xl flex flex-col justify-between space-y-5 hover:border-slate-700 transition">
      <div>
        {/* Header with Title and Score Badge */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="min-w-0">
            <h3 className="text-base font-bold text-white truncate" title={clip.title}>
              {clip.title}
            </h3>
            <div className="flex items-center gap-3 text-xs text-slate-400 mt-1">
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3 text-indigo-400" />
                {clip.duration.toFixed(1)}s ({clip.start_time.toFixed(1)}s – {clip.end_time.toFixed(1)}s)
              </span>
            </div>

            {/* Layout and Category Pills */}
            <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
              <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${categoryInfo.color}`}>
                {categoryInfo.label}
              </span>
              <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-950 text-indigo-300 border border-indigo-500/20">
                {clip.layout_strategy || 'GAMING_SPLIT'} {clip.split_ratio ? `${Math.round(clip.split_ratio * 100)}%` : '30%'}
              </span>
              <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-950 text-teal-300 border border-teal-500/20">
                {clip.gameplay_composition || 'FIT_WITH_BLUR'}
              </span>
              <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-950 text-slate-400 border border-slate-800">
                {clip.resolution ? clip.resolution.split('x')[1] + 'p' : '1080p'}
              </span>
            </div>
          </div>

          <div
            className={`px-3 py-1.5 rounded-xl border bg-gradient-to-tr bg-slate-950 font-bold text-sm flex items-center gap-1.5 shrink-0 ${getScoreColor(
              clip.score.total_score
            )}`}
          >
            <Flame className="h-4 w-4" />
            <span>{clip.score.total_score}</span>
            <span className="text-[10px] text-slate-400 font-normal">/100</span>
          </div>
        </div>

        {/* Video Preview or Placeholder */}
        <div className="my-4">
          <VideoPlayer
            src={finalVideoUrl}
            title={clip.title}
            subtitleSrc={srtUrl}
          />
        </div>

        {/* Excerpt */}
        <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3 text-xs text-slate-300 italic mb-4 line-clamp-3">
          "{clip.transcript_excerpt || clip.reasoning}"
        </div>

        {/* Expandable Score Breakdown */}
        <div className="border border-slate-800/80 rounded-xl overflow-hidden mb-4">
          <button
            type="button"
            onClick={() => setShowDetails(!showDetails)}
            className="w-full px-3 py-2 bg-slate-950/60 hover:bg-slate-950 text-xs font-medium text-slate-400 hover:text-slate-200 flex items-center justify-between transition"
          >
            <span>Score Rubric & Multimodal Metrics</span>
            {showDetails ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>

          {showDetails && (
            <div className="p-3 bg-slate-950/90 text-xs space-y-2.5 border-t border-slate-800">
              <p className="text-slate-300 text-[11px] leading-relaxed">
                {clip.score.explanation}
              </p>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="p-2 bg-slate-900 rounded border border-slate-800">
                  <span className="text-slate-500 block">Audio Reaction Surge:</span>
                  <span className="font-semibold text-white">
                    {clip.score.audio_reaction_score !== undefined ? `${clip.score.audio_reaction_score}/100` : `${clip.score.hook_strength}/25`}
                  </span>
                  {clip.score.peak_z_score !== undefined && (
                    <span className="text-[10px] text-indigo-400 block mt-0.5">Peak Z: {clip.score.peak_z_score.toFixed(2)}</span>
                  )}
                </div>
                <div className="p-2 bg-slate-900 rounded border border-slate-800">
                  <span className="text-slate-500 block">Streamer Motion:</span>
                  <span className="font-semibold text-white">
                    {clip.score.streamer_visual_reaction_score !== undefined ? `${clip.score.streamer_visual_reaction_score}/100` : `${clip.score.standalone_clarity}/25`}
                  </span>
                </div>
                <div className="p-2 bg-slate-900 rounded border border-slate-800">
                  <span className="text-slate-500 block">Gameplay Motion:</span>
                  <span className="font-semibold text-white">
                    {clip.score.gameplay_activity_score !== undefined ? `${clip.score.gameplay_activity_score}/100` : `${clip.score.information_density}/25`}
                  </span>
                </div>
                <div className="p-2 bg-slate-900 rounded border border-slate-800">
                  <span className="text-slate-500 block">Hook & Payoff:</span>
                  <span className="font-semibold text-white">
                    {clip.score.hook_score !== undefined && clip.score.payoff_score !== undefined
                      ? `${clip.score.hook_score} / ${clip.score.payoff_score}`
                      : `${clip.score.pacing_and_flow}/25`}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Action Footer */}
      <div className="flex items-center gap-2 pt-2 border-t border-slate-800/80">
        <button
          type="button"
          onClick={() => onEdit(clip)}
          className="flex-1 py-2 px-3 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 flex items-center justify-center gap-1.5 transition"
        >
          <Edit2 className="h-3.5 w-3.5 text-indigo-400" />
          Edit & Export
        </button>

        <button
          type="button"
          onClick={() => onRenderSingle(clip.id)}
          disabled={isRendering}
          className={`flex-1 py-2 px-3 rounded-xl text-xs font-semibold text-white flex items-center justify-center gap-1.5 shadow-md transition ${
            isRendering
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-600/20'
          }`}
        >
          <Subtitles className="h-3.5 w-3.5" />
          {clip.rendered_clip_path ? 'Re-Render' : 'Render 9:16'}
        </button>
      </div>
    </div>
  );
};
