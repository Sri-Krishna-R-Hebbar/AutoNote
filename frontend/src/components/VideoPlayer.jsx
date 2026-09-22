import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { loadYouTubeApi } from '../utils/youtube';

const VideoPlayer = forwardRef(function VideoPlayer({ video, onTimeUpdate }, ref) {
  const videoElRef = useRef(null);
  const ytContainerRef = useRef(null);
  const ytPlayerRef = useRef(null);
  const pollTimer = useRef(null);

  useImperativeHandle(ref, () => ({
    seek(seconds) {
      if (video?.kind === 'upload' && videoElRef.current) {
        videoElRef.current.currentTime = seconds;
        videoElRef.current.play().catch(() => {});
      } else if (video?.kind === 'youtube' && ytPlayerRef.current?.seekTo) {
        ytPlayerRef.current.seekTo(seconds, true);
        ytPlayerRef.current.playVideo();
      }
    },
  }));

  // HTML5 <video> playback (uploaded files)
  useEffect(() => {
    if (video?.kind !== 'upload') return undefined;
    const el = videoElRef.current;
    if (!el) return undefined;
    const handler = () => onTimeUpdate?.(el.currentTime);
    el.addEventListener('timeupdate', handler);
    return () => el.removeEventListener('timeupdate', handler);
  }, [video, onTimeUpdate]);

  // YouTube iframe playback (video URLs)
  useEffect(() => {
    if (video?.kind !== 'youtube' || !video.youtube_id) return undefined;
    let cancelled = false;

    loadYouTubeApi().then((YT) => {
      if (cancelled || !ytContainerRef.current) return;
      ytPlayerRef.current = new YT.Player(ytContainerRef.current, {
        videoId: video.youtube_id,
        playerVars: { rel: 0 },
        events: {
          onReady: () => {
            pollTimer.current = setInterval(() => {
              const t = ytPlayerRef.current?.getCurrentTime?.();
              if (typeof t === 'number') onTimeUpdate?.(t);
            }, 500);
          },
        },
      });
    });

    return () => {
      cancelled = true;
      clearInterval(pollTimer.current);
      ytPlayerRef.current?.destroy?.();
      ytPlayerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video?.kind, video?.youtube_id]);

  if (!video || video.kind === 'none') {
    return (
      <div className="video-empty">
        <p>Preview isn't available for this source, but your notes are ready below.</p>
      </div>
    );
  }

  if (video.kind === 'youtube') {
    return (
      <div className="video-frame">
        <div ref={ytContainerRef} />
      </div>
    );
  }

  return (
    <div className="video-frame">
      {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
      <video ref={videoElRef} src={video.src} controls playsInline />
    </div>
  );
});

export default VideoPlayer;
