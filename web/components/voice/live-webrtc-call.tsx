'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  PhoneCall,
  PhoneOff,
  Mic,
  MicOff,
  Loader2,
  Sparkles,
  Volume2,
  AlertCircle,
  CheckCircle2,
  Radio,
} from 'lucide-react';
import { Room, RoomEvent, RemoteAudioTrack, LocalAudioTrack, createLocalAudioTrack } from 'livekit-client';
import { apiClient } from '@/lib/api';

interface LiveKitTokenResponse {
  server_url: string;
  room_name: string;
  token: string;
  participant_identity: string;
  call_id: string;
}

interface LiveWebRTCCallProps {
  businessName: string;
  greeting?: string | null;
  onCallEnded?: (callId: string | null) => void;
}

export function LiveWebRTCCall({ businessName, greeting, onCallEnded }: LiveWebRTCCallProps) {
  const [status, setStatus] = useState<'idle' | 'connecting' | 'connected' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [callDuration, setCallDuration] = useState(0);
  const [isAgentSpeaking, setIsAgentSpeaking] = useState(false);
  const [volumeLevel, setVolumeLevel] = useState<number[]>(new Array(16).fill(15));
  const [callId, setCallId] = useState<string | null>(null);

  const roomRef = useRef<Room | null>(null);
  const localTrackRef = useRef<LocalAudioTrack | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      disconnectCall();
    };
  }, []);

  // Call timer interval
  useEffect(() => {
    if (status === 'connected') {
      timerRef.current = setInterval(() => {
        setCallDuration((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setCallDuration(0);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [status]);

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const startVisualizer = (stream: MediaStream) => {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioCtx();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      analyser.smoothingTimeConstant = 0.6;

      const source = ctx.createMediaStreamSource(stream);
      source.connect(analyser);

      audioContextRef.current = ctx;
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const render = () => {
        analyser.getByteFrequencyData(dataArray);
        // Sample 16 bins for visualizer bars
        const bars = [];
        for (let i = 0; i < 16; i++) {
          const raw = dataArray[i * 2] || 0;
          // Scale to percentage height (15% to 100%)
          const height = Math.max(15, Math.min(100, (raw / 255) * 100));
          bars.push(height);
        }
        setVolumeLevel(bars);
        animFrameRef.current = requestAnimationFrame(render);
      };

      render();
    } catch {
      // AudioContext may be restricted in non-user-gesture contexts
    }
  };

  const stopVisualizer = () => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    setVolumeLevel(new Array(16).fill(15));
  };

  const startCall = async () => {
    setErrorMessage(null);
    setStatus('connecting');

    try {
      // 1. Fetch short-lived LiveKit WebRTC access token from backend API
      const tokenData = await apiClient<LiveKitTokenResponse>('/api/onboarding/test-agent/webrtc-token', {
        method: 'POST',
      });

      setCallId(tokenData.call_id);

      // 2. Request microphone audio track
      const micTrack = await createLocalAudioTrack({
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      });
      localTrackRef.current = micTrack;

      // Start audio waveform visualizer from caller mic
      const mediaStream = new MediaStream([micTrack.mediaStreamTrack]);
      startVisualizer(mediaStream);

      // 3. Connect to LiveKit WebRTC Room
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });

      // Handle remote audio from AI agent
      room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        if (track.kind === 'audio') {
          const remoteAudio = track as RemoteAudioTrack;
          if (audioElementRef.current) {
            remoteAudio.attach(audioElementRef.current);
            audioElementRef.current.play().catch((err) => {
              console.warn('Autoplay prevented or failed:', err);
            });
          } else {
            const el = remoteAudio.attach();
            document.body.appendChild(el);
          }
          setIsAgentSpeaking(true);
        }
      });

      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        track.detach();
      });

      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        const isAgent = speakers.some((s) => s.identity !== tokenData.participant_identity);
        setIsAgentSpeaking(isAgent);
      });

      room.on(RoomEvent.Disconnected, () => {
        disconnectCall();
      });

      await room.connect(tokenData.server_url, tokenData.token);
      await room.localParticipant.publishTrack(micTrack);

      roomRef.current = room;
      setStatus('connected');
    } catch (err: any) {
      disconnectCall();
      setStatus('error');
      setErrorMessage(
        err.message || 'Failed to connect to LiveKit WebRTC server. Please verify credentials and microphone permissions.'
      );
    }
  };

  const toggleMute = () => {
    if (!localTrackRef.current) return;
    if (isMuted) {
      localTrackRef.current.unmute();
      setIsMuted(false);
    } else {
      localTrackRef.current.mute();
      setIsMuted(true);
    }
  };

  const disconnectCall = () => {
    stopVisualizer();

    if (localTrackRef.current) {
      localTrackRef.current.stop();
      localTrackRef.current = null;
    }

    if (roomRef.current) {
      roomRef.current.disconnect();
      roomRef.current = null;
    }

    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.srcObject = null;
    }

    const endedId = callId;
    setStatus('idle');
    setIsMuted(false);
    setIsAgentSpeaking(false);

    if (onCallEnded) {
      onCallEnded(endedId);
    }
  };

  return (
    <div className="w-full bg-white brutal-border-3 rounded-2xl p-6 sm:p-8 brutal-shadow relative overflow-hidden">
      {/* Top Banner & Status Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b-3 border-black gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-[#ffe600] brutal-border rounded-xl flex items-center justify-center text-black brutal-shadow-xs">
            <Radio className={`w-6 h-6 ${status === 'connected' ? 'animate-pulse text-red-600' : 'text-black'}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-black text-black uppercase tracking-tight">
                Live WebRTC Voice Agent
              </h3>
              <span className="bg-[#a3e635] text-black text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border shadow-xs">
                Sub-300ms Ultra-Fast
              </span>
            </div>
            <p className="text-xs font-semibold text-neutral-600">
              Direct bidirectional WebRTC audio with {businessName} Receptionist
            </p>
          </div>
        </div>

        {/* Live Status Badge / Direct Action */}
        <div className="flex items-center gap-3">
          {status === 'connected' && (
            <div className="inline-flex items-center gap-2 bg-[#a3e635] brutal-border px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-wider brutal-shadow-xs">
              <span className="w-2.5 h-2.5 rounded-full bg-black animate-ping" />
              Live: {formatDuration(callDuration)}
            </div>
          )}
          {status === 'connecting' && (
            <div className="inline-flex items-center gap-2 bg-[#ffe600] brutal-border px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-wider brutal-shadow-xs">
              <Loader2 className="w-4 h-4 animate-spin text-black" />
              Connecting...
            </div>
          )}
          {status === 'idle' && (
            <button
              type="button"
              onClick={startCall}
              className="inline-flex items-center gap-2 bg-[#a3e635] hover:bg-[#86efac] brutal-border px-4 py-2 rounded-xl text-xs font-black uppercase tracking-wider text-black brutal-shadow-xs brutal-shadow-hover transition-all cursor-pointer"
            >
              <PhoneCall className="w-3.5 h-3.5 text-black" />
              Start Call
            </button>
          )}
        </div>
      </div>

      {/* Error Alert Box */}
      {errorMessage && (
        <div className="mt-5 p-4 rounded-xl bg-rose-100 brutal-border text-xs font-bold text-rose-950 flex items-start gap-3 brutal-shadow-xs">
          <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          <div>
            <p className="font-black uppercase tracking-wider">Connection Error</p>
            <p className="mt-0.5">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Active Equalizer & Waveform Display */}
      <div className="mt-4 mb-4 p-4 sm:p-5 bg-[#fbfaf6] brutal-border rounded-2xl flex flex-col items-center justify-center min-h-[150px] relative">
        {status === 'connected' ? (
          <div className="w-full flex flex-col items-center">
            {/* Equalizer Frequency Bars */}
            <div className="flex items-end justify-center gap-1.5 sm:gap-2 h-20 sm:h-24 w-full max-w-md px-4">
              {volumeLevel.map((height, i) => (
                <div
                  key={i}
                  style={{ height: `${height}%` }}
                  className={`w-3 sm:w-4 brutal-border rounded-t transition-all duration-75 ${
                    isAgentSpeaking
                      ? 'bg-[#38bdf8]'
                      : isMuted
                      ? 'bg-neutral-300'
                      : 'bg-[#ffe600]'
                  }`}
                />
              ))}
            </div>

            {/* Speaking State Indicator */}
            <div className="mt-4 flex items-center gap-2 text-xs font-black uppercase tracking-wider">
              {isAgentSpeaking ? (
                <span className="inline-flex items-center gap-1.5 text-blue-700 bg-blue-100 px-3 py-1 rounded-full brutal-border brutal-shadow-xs">
                  <Volume2 className="w-4 h-4 animate-bounce" /> Receptionist Speaking...
                </span>
              ) : isMuted ? (
                <span className="inline-flex items-center gap-1.5 text-neutral-700 bg-neutral-200 px-3 py-1 rounded-full brutal-border">
                  <MicOff className="w-4 h-4 text-red-600" /> Microphone Muted
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-emerald-800 bg-emerald-100 px-3 py-1 rounded-full brutal-border brutal-shadow-xs">
                  <Mic className="w-4 h-4 text-emerald-600 animate-pulse" /> Listening to your microphone...
                </span>
              )}
            </div>
          </div>
        ) : (
          <div className="text-center py-4 px-4">
            <div className="w-14 h-14 bg-[#ffe600] brutal-border rounded-2xl flex items-center justify-center text-black brutal-shadow mx-auto mb-3 rotate-[-3deg]">
              <PhoneCall className="w-7 h-7" />
            </div>
            <h4 className="text-base font-black text-black uppercase tracking-wider">
              Talk directly to your AI receptionist
            </h4>
            <p className="text-xs font-semibold text-neutral-600 max-w-sm mt-1 mx-auto">
              Test natural speech, interruption, appointment booking, and knowledge retrieval live over WebRTC.
            </p>
            <button
              type="button"
              onClick={startCall}
              className="mt-4 inline-flex items-center justify-center gap-2.5 bg-[#a3e635] hover:bg-[#86efac] text-black font-black uppercase text-sm tracking-wider px-8 py-3.5 rounded-2xl brutal-border brutal-shadow brutal-shadow-hover transition-all transform hover:-translate-y-0.5 cursor-pointer"
            >
              <PhoneCall className="w-5 h-5 text-black" />
              Start Live Voice Call
            </button>
          </div>
        )}
      </div>

      {/* Control Actions */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
        {status === 'idle' || status === 'error' ? (
          <button
            type="button"
            onClick={startCall}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-[#a3e635] hover:bg-[#86efac] text-black font-black uppercase text-sm tracking-wider px-8 py-4 rounded-xl brutal-border brutal-shadow brutal-shadow-hover transition-all"
          >
            <PhoneCall className="w-5 h-5 text-black" />
            Start Live Voice Call
          </button>
        ) : status === 'connecting' ? (
          <button
            type="button"
            disabled
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-neutral-200 text-neutral-600 font-black uppercase text-sm tracking-wider px-8 py-4 rounded-xl brutal-border opacity-70 cursor-not-allowed"
          >
            <Loader2 className="w-5 h-5 animate-spin" />
            Connecting to LiveKit...
          </button>
        ) : (
          <div className="flex items-center gap-4 w-full sm:w-auto justify-center">
            {/* Mute Button */}
            <button
              type="button"
              onClick={toggleMute}
              className={`inline-flex items-center justify-center gap-2 font-black uppercase text-xs tracking-wider px-5 py-3.5 rounded-xl brutal-border brutal-shadow-xs brutal-shadow-hover transition-all ${
                isMuted ? 'bg-rose-500 text-white' : 'bg-white text-black'
              }`}
            >
              {isMuted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              {isMuted ? 'Unmute Mic' : 'Mute Mic'}
            </button>

            {/* End Call Button */}
            <button
              type="button"
              onClick={disconnectCall}
              className="inline-flex items-center justify-center gap-2 bg-rose-600 hover:bg-rose-500 text-white font-black uppercase text-xs tracking-wider px-6 py-3.5 rounded-xl brutal-border brutal-shadow brutal-shadow-hover transition-all"
            >
              <PhoneOff className="w-4 h-4" />
              End Call
            </button>
          </div>
        )}
      </div>

      {/* Info Footnote */}
      <div className="mt-4 pt-3 border-t-2 border-black/10 flex items-center justify-between text-[11px] font-bold text-neutral-500">
        <span className="flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Web Audio Opus Codec 48kHz
        </span>
        <span>Silero VAD Interruption Enabled</span>
      </div>

      {/* Hidden Audio element for WebRTC playback */}
      <audio ref={audioElementRef} autoPlay playsInline className="hidden" />
    </div>
  );
}
