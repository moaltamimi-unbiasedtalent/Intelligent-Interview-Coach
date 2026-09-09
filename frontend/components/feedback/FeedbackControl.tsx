"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { FeedbackRating, FeedbackSurface } from "@/lib/api/types";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";

/**
 * Candidate feedback control (P5): "Helpful / Not helpful" + optional comment for one
 * logical output. Restores a saved rating on mount, persists to the backend, and shows
 * an honest error (never a fake success). Feedback is a human-reviewed signal — it never
 * changes Agent behaviour.
 */
export function FeedbackControl({
  surface,
  targetId,
  prompt = "Was this helpful?",
}: {
  surface: FeedbackSurface;
  targetId: string;
  prompt?: string;
}) {
  const [rating, setRating] = useState<FeedbackRating | null>(null);
  const [comment, setComment] = useState("");
  const [showComment, setShowComment] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const loadedComment = useRef("");

  // Restore any saved rating for this exact target (survives refresh).
  useEffect(() => {
    if (!targetId) return;
    const ctrl = new AbortController();
    api.feedback
      .get(surface, targetId, { signal: ctrl.signal })
      .then((f) => {
        if (f) {
          setRating(f.rating);
          setComment(f.comment ?? "");
          loadedComment.current = f.comment ?? "";
        }
      })
      .catch(() => { /* absent or unreadable → no rating, no error surfaced */ });
    return () => ctrl.abort();
  }, [surface, targetId]);

  const persist = useCallback(
    async (nextRating: FeedbackRating, nextComment: string | null) => {
      setBusy(true);
      setError(null);
      setSaved(false);
      try {
        await api.feedback.submit({ surface, target_id: targetId, rating: nextRating, comment: nextComment });
        setRating(nextRating);
        loadedComment.current = nextComment ?? "";
        setSaved(true);
      } catch (e) {
        // Never pretend success — surface an error and keep the entered text.
        setError((e as ApiError).userMessage ?? "Couldn't save your feedback. Please try again.");
      } finally {
        setBusy(false);
      }
    },
    [surface, targetId],
  );

  const choose = (next: FeedbackRating) => {
    setShowComment(true);
    void persist(next, comment.trim() || null);
  };

  return (
    <div className="mt-2 text-sm" role="group" aria-label={prompt}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted">{prompt}</span>
        <Button size="sm" variant="ghost" aria-pressed={rating === "helpful"} disabled={busy}
          onClick={() => choose("helpful")} aria-label="Helpful">👍 Helpful</Button>
        <Button size="sm" variant="ghost" aria-pressed={rating === "not_helpful"} disabled={busy}
          onClick={() => choose("not_helpful")} aria-label="Not helpful">👎 Not helpful</Button>
        {saved && !error ? <span className="text-xs text-success" role="status" aria-live="polite">Thanks — saved.</span> : null}
      </div>

      {showComment || rating ? (
        <div className="mt-2">
          <label htmlFor={`fb-${surface}-${targetId}`} className="block text-xs text-muted">
            {rating === "not_helpful" ? "What could be better? (optional)" : "Add a comment (optional)"}
          </label>
          <Textarea
            id={`fb-${surface}-${targetId}`}
            value={comment}
            maxLength={1000}
            onChange={(e) => setComment(e.target.value)}
            className="min-h-[60px]"
          />
          <div className="mt-1 flex items-center gap-2">
            <Button size="sm" disabled={busy || !rating || comment.trim() === loadedComment.current}
              onClick={() => rating && persist(rating, comment.trim() || null)}>
              Save comment
            </Button>
          </div>
        </div>
      ) : null}

      {error ? <p role="alert" className="mt-1 text-xs text-danger">{error}</p> : null}
    </div>
  );
}
