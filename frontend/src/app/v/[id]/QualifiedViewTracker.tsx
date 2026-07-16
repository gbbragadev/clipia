"use client";

import { useEffect } from "react";

import { qualifyPublicShareView } from "@/lib/public-shares";
import {
  getDurableAnonymousSessionId,
  isTransientQualifiedViewError,
  QualifiedViewScheduler,
  type QualifiedViewClock,
} from "@/lib/qualified-view-scheduler";

let volatileSessionId: string | null = null;

function browserAnonymousSessionId(): string {
  if (volatileSessionId) return volatileSessionId;
  try {
    return (volatileSessionId = getDurableAnonymousSessionId(localStorage, () => crypto.randomUUID()));
  } catch {
    return (volatileSessionId = crypto.randomUUID());
  }
}

const browserClock: QualifiedViewClock = {
  now: () => performance.now(),
  setTimeout: (callback, delayMs) => window.setTimeout(callback, delayMs),
  clearTimeout: (handle) => window.clearTimeout(handle as number),
};

export default function QualifiedViewTracker({ token }: { token: string }) {
  useEffect(() => {
    const scheduler = new QualifiedViewScheduler({
      token,
      anonymousSessionId: browserAnonymousSessionId(),
      clock: browserClock,
      transport: qualifyPublicShareView,
      retryDelaysMs: [500, 1500, 3000],
      shouldRetry: isTransientQualifiedViewError,
    });

    const syncVisibility = () => scheduler.setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", syncVisibility);
    syncVisibility();

    return () => {
      document.removeEventListener("visibilitychange", syncVisibility);
      scheduler.dispose();
    };
  }, [token]);

  return null;
}
