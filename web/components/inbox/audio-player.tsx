'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Play, Pause, Volume2, VolumeX, RotateCcw, FastForward, Disc } from 'lucide-react';

interface AudioPlayerProps {
  audioUrl?: string | null;
  durationSeconds?: number;
}

export function AudioPlayer({ audioUrl, durationSeconds = 0 }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(durationSeconds || 0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackRate;
    }
  }, [playbackRate]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().then(() => setIsPlaying(true)).catch(() => {
        // Fallback for browser autoplay policies or invalid audio
        setIsPlaying(false);
      });
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
      if (audioRef.current.duration && !isNaN(audioRef.current.duration)) {
        setDuration(audioRef.current.duration);
      }
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    setCurrentTime(time);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
    }
  };

  const cycleSpeed = () => {
    const speeds = [1, 1.25, 1.5, 2];
    const nextIdx = (speeds.indexOf(playbackRate) + 1) % speeds.length;
    setPlaybackRate(speeds[nextIdx]);
  };

  const formatTime = (secs: number) => {
    if (isNaN(secs) || secs < 0) return '0:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  if (!audioUrl) {
    return (
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex items-center justify-between text-slate-500">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-slate-200/60 flex items-center justify-center text-slate-400">
            <Disc className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-700">Audio Recording Not Available</p>
            <p className="text-[11px] text-slate-400">
              Live streamed or simulated call duration: {formatTime(durationSeconds)}
            </p>
          </div>
        </div>
        <span className="text-xs bg-slate-200/60 text-slate-600 px-2 py-1 rounded">Text Session</span>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 text-white rounded-xl p-4 space-y-3 shadow-sm border border-slate-800">
      <audio
        ref={audioRef}
        src={audioUrl}
        onTimeUpdate={handleTimeUpdate}
        onEnded={() => setIsPlaying(false)}
      />

      {/* Scrubber & Timers */}
      <div className="flex items-center space-x-3 text-xs text-slate-400">
        <span className="tabular-nums font-mono">{formatTime(currentTime)}</span>
        <input
          type="range"
          min={0}
          max={duration || 100}
          value={currentTime}
          onChange={handleSeek}
          className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
        />
        <span className="tabular-nums font-mono">{formatTime(duration)}</span>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between pt-1">
        <div className="flex items-center space-x-2">
          <button
            onClick={() => {
              if (audioRef.current) audioRef.current.currentTime = Math.max(0, currentTime - 5);
            }}
            title="Rewind 5s"
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <button
            onClick={togglePlay}
            className="w-9 h-9 rounded-full bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center shadow transition"
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
          </button>

          <button
            onClick={() => {
              if (audioRef.current) audioRef.current.currentTime = Math.min(duration, currentTime + 5);
            }}
            title="Forward 5s"
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
          >
            <FastForward className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={cycleSpeed}
            className="text-xs font-mono font-semibold px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300"
          >
            {playbackRate}x
          </button>

          <button
            onClick={() => {
              if (audioRef.current) {
                audioRef.current.muted = !isMuted;
                setIsMuted(!isMuted);
              }
            }}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
          >
            {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}
