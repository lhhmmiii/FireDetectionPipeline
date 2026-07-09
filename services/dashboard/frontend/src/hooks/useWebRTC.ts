import { useEffect, useRef, useState } from 'react';

const RECONNECT_DELAY_MS = 5000;

export function useWebRTC(baseUrl: string, streamName: string) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let dead = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function connect() {
      if (dead) return;

      const pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
      });

      pc.ontrack = (event) => {
        if (event.track.kind === 'video' && videoRef.current && !dead) {
          videoRef.current.srcObject = event.streams[0];
          setConnected(true);
        }
      };

      pc.oniceconnectionstatechange = () => {
        const state = pc.iceConnectionState;
        if ((state === 'disconnected' || state === 'failed') && !dead) {
          setConnected(false);
          pc.close();
          timer = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      try {
        pc.addTransceiver('video', { direction: 'recvonly' });
        pc.addTransceiver('audio', { direction: 'recvonly' });

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        await new Promise<void>((resolve) => {
          if (pc.iceGatheringState === 'complete') { resolve(); return; }
          pc.onicegatheringstatechange = () => {
            if (pc.iceGatheringState === 'complete') resolve();
          };
        });

        if (dead) { pc.close(); return; }

        const whepUrl = `${baseUrl}/${streamName}/whep`;
        const response = await fetch(whepUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/sdp' },
          body: pc.localDescription!.sdp,
        });

        if (!response.ok) throw new Error(`WHEP ${response.status}`);

        const answerSdp = await response.text();
        await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });
      } catch {
        pc.close();
        if (!dead) {
          setConnected(false);
          timer = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      }
    }

    connect();

    return () => {
      dead = true;
      if (timer) clearTimeout(timer);
    };
  }, [baseUrl, streamName]);

  return { connected, videoRef };
}
