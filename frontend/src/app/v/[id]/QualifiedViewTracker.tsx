"use client";

import { useEffect, useRef } from "react";

import { qualifyPublicShareView } from "@/lib/public-shares";

const SESSION_STORAGE_KEY = "clipia_public_share_session_id";
const QUALIFIED_DWELL_MS = 5000;
let volatileSessionId: string | null = null;

function durableAnonymousSessionId(): string {
  if (volatileSessionId) return volatileSessionId;
  try {
    const stored = localStorage.getItem(SESSION_STORAGE_KEY);
    if (stored) return (volatileSessionId = stored);
    volatileSessionId = crypto.randomUUID();
    localStorage.setItem(SESSION_STORAGE_KEY, volatileSessionId);
    return volatileSessionId;
  } catch {
    return (volatileSessionId = crypto.randomUUID());
  }
}

export default function QualifiedViewTracker({ token }: { token: string }) {
  const sentRef = useRef(false);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    let visibleSince: number | null = null;
    let visibleDwellMs = 0;
    let disposed = false;

    function stopVisibleClock() {
      if (visibleSince !== null) {
        visibleDwellMs += performance.now() - visibleSince;
        visibleSince = null;
      }
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
    }

    function startVisibleClock() {
      if (disposed || sentRef.current || document.visibilityState !== "visible" || visibleSince !== null) return;
      visibleSince = performance.now();
      timer = setTimeout(sendQualifiedView, Math.max(0, QUALIFIED_DWELL_MS - visibleDwellMs));
    }

    function sendQualifiedView() {
      stopVisibleClock();
      if (disposed || sentRef.current || document.visibilityState !== "visible") {
        startVisibleClock();
        return;
      }
      sentRef.current = true;
      void qualifyPublicShareView(token, {
        anonymous_session_id: durableAnonymousSessionId(),
        dwell_ms: Math.max(QUALIFIED_DWELL_MS, Math.round(visibleDwellMs)),
        page_visible: true,
      }).catch(() => {
        // A recompensa é best-effort e não deve interromper o player público.
      });
    }

    function handleVisibilityChange() {
      if (document.visibilityState === "visible") startVisibleClock();
      else stopVisibleClock();
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);
    startVisibleClock();

    return () => {
      disposed = true;
      stopVisibleClock();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [token]);

  return null;
}
