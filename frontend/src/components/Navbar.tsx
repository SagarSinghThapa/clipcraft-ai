import React from 'react';
import { Scissors, Cpu, Zap, ShieldCheck } from 'lucide-react';
import { HardwareCapabilities } from '../types';

interface NavbarProps {
  hardware?: HardwareCapabilities | null;
}

export const Navbar: React.FC<NavbarProps> = ({ hardware }) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Scissors className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
              ClipCraft AI
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Local-First
              </span>
            </h1>
            <p className="text-xs text-slate-400">Automated 9:16 Highlights & Captions</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <div className="hidden sm:flex items-center space-x-2 text-xs text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Zero API Fees</span>
          </div>

          {hardware && (
            <div className="flex items-center space-x-2 text-xs bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
              {hardware.cuda_available ? (
                <>
                  <Zap className="h-3.5 w-3.5 text-amber-400" />
                  <span className="text-slate-200 font-medium">
                    {hardware.device_name} ({hardware.compute_type})
                  </span>
                </>
              ) : (
                <>
                  <Cpu className="h-3.5 w-3.5 text-sky-400" />
                  <span className="text-slate-200 font-medium">
                    CPU Quantized ({hardware.compute_type})
                  </span>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
