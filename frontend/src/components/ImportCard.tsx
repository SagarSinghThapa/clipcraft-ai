import React, { useState } from 'react';
import { Upload, Youtube, Settings, Sliders, Film, Sparkles } from 'lucide-react';
import { SourceType } from '../types';

interface ImportCardProps {
  onStartProcessing: (params: {
    sourceType: SourceType;
    sourceValue: string;
    whisperModel: string;
    llmModel: string;
    minDuration: number;
    maxDuration: number;
    candidateCount: number;
  }) => void;
  isLoading: boolean;
}

export const ImportCard: React.FC<ImportCardProps> = ({ onStartProcessing, isLoading }) => {
  const [activeTab, setActiveTab] = useState<SourceType>('local_file');
  const [filePath, setFilePath] = useState('');
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [showSettings, setShowSettings] = useState(false);

  // Settings
  const [whisperModel, setWhisperModel] = useState('base');
  const [llmModel, setLlmModel] = useState('llama3.2:3b');
  const [minDuration, setMinDuration] = useState(15);
  const [maxDuration, setMaxDuration] = useState(60);
  const [candidateCount, setCandidateCount] = useState(5);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const sourceValue = activeTab === 'local_file' ? filePath.trim() : youtubeUrl.trim();
    if (!sourceValue) return;

    onStartProcessing({
      sourceType: activeTab,
      sourceValue,
      whisperModel,
      llmModel,
      minDuration,
      maxDuration,
      candidateCount,
    });
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-xl p-6 sm:p-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Film className="h-5 w-5 text-indigo-400" />
            Import Source Video
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Choose a local video file from your disk or provide an authorized YouTube link.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setShowSettings(!showSettings)}
          className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border transition ${
            showSettings
              ? 'bg-indigo-600/20 text-indigo-300 border-indigo-500/30'
              : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
          }`}
        >
          <Sliders className="h-3.5 w-3.5" />
          <span>Pipeline Settings</span>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 mb-6">
        <button
          type="button"
          onClick={() => setActiveTab('local_file')}
          className={`flex items-center gap-2 pb-3 px-4 text-sm font-semibold border-b-2 transition ${
            activeTab === 'local_file'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Upload className="h-4 w-4" />
          Local Video File
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('youtube')}
          className={`flex items-center gap-2 pb-3 px-4 text-sm font-semibold border-b-2 transition ${
            activeTab === 'youtube'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Youtube className="h-4 w-4" />
          YouTube URL
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {activeTab === 'local_file' ? (
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-2">
              Absolute or Relative Video File Path
            </label>
            <input
              type="text"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              placeholder="e.g. C:\Videos\podcast_episode_12.mp4 or sample.mp4"
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition"
              required
            />
            <p className="text-xs text-slate-500 mt-2">
              Supported formats: MP4, MOV, MKV, WebM, AVI. File is verified and copied into an isolated workspace.
            </p>
          </div>
        ) : (
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-2">
              YouTube Video URL
            </label>
            <input
              type="url"
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition"
              required
            />
            <p className="text-xs text-slate-500 mt-2">
              Only authorized public videos are supported via yt-dlp. DRM and platform locks are strictly respected.
            </p>
          </div>
        )}

        {/* Collapsible Settings */}
        {showSettings && (
          <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-5 space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Settings className="h-3.5 w-3.5" />
              Advanced AI & Pipeline Configuration
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-300 mb-1">Whisper Transcription Model</label>
                <select
                  value={whisperModel}
                  onChange={(e) => setWhisperModel(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="tiny">Tiny (Fastest, low VRAM)</option>
                  <option value="base">Base (Balanced - Recommended)</option>
                  <option value="small">Small (Higher accuracy)</option>
                  <option value="medium">Medium (Detailed transcription)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-slate-300 mb-1">Local LLM Highlight Model (Ollama)</label>
                <select
                  value={llmModel}
                  onChange={(e) => setLlmModel(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="llama3.2:3b">Llama 3.2 3B (Fast, high quality)</option>
                  <option value="mistral">Mistral 7B (Deep reasoning)</option>
                  <option value="qwen2.5:3b">Qwen 2.5 3B (Compact)</option>
                  <option value="phi3">Phi-3 Mini (Ultra-lightweight)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-slate-300 mb-1">
                  Duration Range: {minDuration}s – {maxDuration}s
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="10"
                    max="40"
                    value={minDuration}
                    onChange={(e) => setMinDuration(Number(e.target.value))}
                    className="w-full accent-indigo-500"
                  />
                  <input
                    type="range"
                    min="40"
                    max="90"
                    value={maxDuration}
                    onChange={(e) => setMaxDuration(Number(e.target.value))}
                    className="w-full accent-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs text-slate-300 mb-1">
                  Candidate Highlights: {candidateCount} clips
                </label>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={candidateCount}
                  onChange={(e) => setCandidateCount(Number(e.target.value))}
                  className="w-full accent-indigo-500"
                />
              </div>
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className={`w-full py-3.5 px-6 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 shadow-lg transition ${
            isLoading
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
              : 'bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white shadow-indigo-500/25'
          }`}
        >
          <Sparkles className="h-4 w-4" />
          <span>{isLoading ? 'Processing Pipeline Active...' : 'Generate AI Highlights'}</span>
        </button>
      </form>
    </div>
  );
};
