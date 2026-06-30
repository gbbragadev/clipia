import { useEffect, useRef, useState } from "react";

/** Reactive prefers-reduced-motion. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener?.("change", update);
    return () => mq.removeEventListener?.("change", update);
  }, []);
  return reduced;
}

interface InViewOptions {
  threshold?: number;
  rootMargin?: string;
  once?: boolean;
}

/** IntersectionObserver hook for scroll reveal. `once` defaults to true. */
export function useInView<T extends HTMLElement = HTMLDivElement>(opts: InViewOptions = {}) {
  const { threshold = 0.15, rootMargin = "0px 0px -8% 0px", once = true } = opts;
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          if (once) observer.disconnect();
        } else if (!once) {
          setInView(false);
        }
      },
      { threshold, rootMargin }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold, rootMargin, once]);

  return { ref, inView };
}

/** Returns true once the page has scrolled past a target element's bottom. */
export function useScrolledPast(targetId: string): boolean {
  const [past, setPast] = useState(false);
  useEffect(() => {
    const el = document.getElementById(targetId);
    if (!el) return;
    const onScroll = () => {
      const rect = el.getBoundingClientRect();
      setPast(rect.bottom < 80);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [targetId]);
  return past;
}
