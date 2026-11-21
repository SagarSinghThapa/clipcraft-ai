import React from 'react';
import {
  Download,
  Music,
  FileText,
  BrainCircuit,
  Scissors,
  Smartphone,
  Subtitles,
  CheckCircle2,
  Loader2,
  AlertCircle
} from 'lucide-react';
import { PipelineStage } from '../types';

interface JobProgressProps {
  currentStage: PipelineStage;
  stageMessage: string;
  error?: string | null;
}

interface StageStep {
  key: PipelineStage;
  label: string;
  icon: React.ElementType;
}

const STAGES: StageStep[] = [
  { key: 'importing', label: 'Importing Media', icon: Download },
  { key: 'extracting_audio', label: 'Extracting 16kHz Audio', icon: Music },
  { key: 'transcribing', label: 'Local Whisper Transcription', icon: FileText },
  { key: 'analyzing', label: 'AI Highlight Discovery', icon: BrainCircuit },
  { key: 'finding_clips', label: 'Precision FFmpeg Cutting', icon: Scissors },
  { key: 'reframing', label: '9:16 Face Reframing', icon: Smartphone },
  { key: 'captioning', label: 'Burning Synchronized Captions', icon: Subtitles },
  { key: 'completed', label: 'Clips Ready', icon: CheckCircle2 },
];

export const JobProgress: React.FC<JobProgressProps> = ({ currentStage, stageMessage, error }) => {
  const currentIndex = STAGES.findIndex((s) => s.key === currentStage);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            {error ? (
              <span className="text-rose-400 flex items-center gap-2">
                <AlertCircle className="h-5 w-5" /> Pipeline Error
              </span>
            ) : currentStage === 'completed' ? (
              <span className="text-emerald-400 flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5" /> Pipeline Completed
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin text-indigo-400" /> Live Processing Pipeline
              </span>
            )}
          </h3>
          <p className="text-xs text-slate-400 mt-1">{stageMessage}</p>
        </div>

        {error && (
          <div className="text-xs font-semibold px-3 py-1 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
            Failed
          </div>
        )}
      </div>

      {error ? (
        <div className="p-4 bg-rose-950/40 border border-rose-800/60 rounded-xl text-rose-200 text-xs">
          <strong>Error Details:</strong> {error}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {STAGES.map((step, idx) => {
            const Icon = step.icon;
            const isDone = currentIndex > idx || currentStage === 'completed';
            const isCurrent = currentStage === step.key;

            return (
              <div
                key={step.key}
                className={`p-3 rounded-xl border flex items-center gap-3 transition ${
                  isCurrent
                    ? 'bg-indigo-600/15 border-indigo-500/40 text-white shadow-sm shadow-indigo-500/10'
                    : isDone
                    ? 'bg-slate-950 border-emerald-500/30 text-emerald-300'
                    : 'bg-slate-950/50 border-slate-800/80 text-slate-600'
                }`}
              >
                <div
                  className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${
                    isCurrent
                      ? 'bg-indigo-600 text-white animate-pulse'
                      : isDone
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'bg-slate-800 text-slate-500'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium truncate">{step.label}</p>
                  <span className="text-[10px] text-slate-500">
                    {isDone ? 'Finished' : isCurrent ? 'Active...' : 'Pending'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
