import React, { useEffect, useMemo, useRef, useState } from "react";

function similarityBand(value) {
  if (value >= 95) return "good";
  if (value >= 85) return "warn";
  return "bad";
}

function riskBand(tags) {
  if (!tags || tags.length === 0) return "low";
  if (tags.includes("obligation_shift") || tags.includes("numeric_change") || tags.includes("date_change")) return "high";
  return "medium";
}

function rangeFromChange(change) {
  if (typeof change?.paragraph_index_start === "number" && typeof change?.paragraph_index_end === "number") {
    return [change.paragraph_index_start, change.paragraph_index_end];
  }
  return [null, null];
}

function extractByRange(document, start, end, fallback = "") {
  if (!document?.paragraphs || start === null || end === null) return fallback;
  const lines = document.paragraphs
    .filter((p) => p.index >= start && p.index <= end)
    .map((p) => p.text);
  return lines.length ? lines.join("\n") : fallback;
}

function buildSegments(text, spans, side) {
  if (!Array.isArray(spans) || spans.length === 0) return [{ type: "plain", text }];
  const target = side === "a" ? "removed" : "added";
  return spans.map((span) => ({ type: span.type === target ? target : "plain", text: span.text }));
}

function tokenizeWithWhitespace(text) {
  return (text || "").match(/\w+|\s+|[^\w\s]/g) || [];
}

function buildDiffSpansFallback(before, after) {
  const beforeTokens = tokenizeWithWhitespace(before);
  const afterTokens = tokenizeWithWhitespace(after);

  const lcs = Array.from({ length: beforeTokens.length + 1 }, () =>
    Array(afterTokens.length + 1).fill(0)
  );

  for (let i = beforeTokens.length - 1; i >= 0; i -= 1) {
    for (let j = afterTokens.length - 1; j >= 0; j -= 1) {
      if (beforeTokens[i] === afterTokens[j]) {
        lcs[i][j] = 1 + lcs[i + 1][j + 1];
      } else {
        lcs[i][j] = Math.max(lcs[i + 1][j], lcs[i][j + 1]);
      }
    }
  }

  const beforeSpans = [];
  const afterSpans = [];
  let i = 0;
  let j = 0;

  while (i < beforeTokens.length && j < afterTokens.length) {
    if (beforeTokens[i] === afterTokens[j]) {
      beforeSpans.push({ text: beforeTokens[i], type: "unchanged" });
      afterSpans.push({ text: afterTokens[j], type: "unchanged" });
      i += 1;
      j += 1;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      beforeSpans.push({ text: beforeTokens[i], type: "removed" });
      i += 1;
    } else {
      afterSpans.push({ text: afterTokens[j], type: "added" });
      j += 1;
    }
  }

  while (i < beforeTokens.length) {
    beforeSpans.push({ text: beforeTokens[i], type: "removed" });
    i += 1;
  }
  while (j < afterTokens.length) {
    afterSpans.push({ text: afterTokens[j], type: "added" });
    j += 1;
  }

  return { before_spans: beforeSpans, after_spans: afterSpans };
}

function renderSegments(segments, keyPrefix) {
  return segments.map((seg, i) => {
    if (seg.type === "added") return <span key={`${keyPrefix}-a-${i}`} className="hl-add">{seg.text}</span>;
    if (seg.type === "removed") return <span key={`${keyPrefix}-r-${i}`} className="hl-remove">{seg.text}</span>;
    return <span key={`${keyPrefix}-p-${i}`}>{seg.text}</span>;
  });
}

export default function DocumentViewer({ change, aiSummary, onClose }) {
  const [activeTab, setActiveTab] = useState("side");
  const [syncScroll, setSyncScroll] = useState(true);
  const [showSimilarityInfo, setShowSimilarityInfo] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const paneARef = useRef(null);
  const paneBRef = useRef(null);
  const soloARef = useRef(null);
  const soloBRef = useRef(null);
  const syncingRef = useRef(false);

  const similarity = typeof change?.similarity === "number" ? Math.round(change.similarity * 100) : 0;
  const risk = riskBand(change?.risk_tags || []);

  const [start, end] = rangeFromChange(change);
  const beforeText = change?.before || change?.before_text || change?.text || "";
  const afterText = change?.after || change?.after_text || change?.text || "";

  const cleanA = useMemo(() => {
    if (change.type === "added") return "";
    return beforeText;
  }, [change.type, beforeText]);

  const cleanB = useMemo(() => {
    if (change.type === "deleted") return "";
    return afterText;
  }, [change.type, afterText]);

  const wordDiffs = useMemo(() => {
    if (change?.word_diffs?.before_spans?.length || change?.word_diffs?.after_spans?.length) {
      return change.word_diffs;
    }
    if (!cleanA && !cleanB) return null;
    return buildDiffSpansFallback(cleanA, cleanB);
  }, [change?.word_diffs, cleanA, cleanB]);

  const segA = useMemo(() => buildSegments(cleanA, wordDiffs?.before_spans, "a"), [cleanA, wordDiffs?.before_spans]);
  const segB = useMemo(() => buildSegments(cleanB, wordDiffs?.after_spans, "b"), [cleanB, wordDiffs?.after_spans]);

  const aiInsight = useMemo(() => {
    if (!aiSummary?.insights) return null;
    const key = change?.clause_id || change?.id;
    const matches = aiSummary.insights.filter((i) => i.change_id === key);
    if (matches.length === 0) return null;
    const combined = matches.map((m) => m.explanation).join(" ");
    return { ...matches[0], explanation: combined };
  }, [aiSummary, change?.id, change?.clause_id]);

  const aiImpacts = useMemo(() => {
    if (!aiSummary?.impacts) return [];
    const key = change?.clause_id || change?.id;
    return aiSummary.impacts.filter((i) => i.trigger_change_id === key);
  }, [aiSummary, change?.id, change?.clause_id]);

  const aiParagraph = useMemo(() => {
    if (!aiInsight && aiImpacts.length === 0) return null;
    const parts = [];
    if (aiInsight) {
      const direction =
        aiInsight.risk_direction === "buyer-friendly"
          ? "leans buyer-friendly"
          : aiInsight.risk_direction === "seller-friendly"
          ? "leans seller-friendly"
          : "";
      parts.push(`${aiInsight.semantic_label}: ${aiInsight.explanation}${direction ? ` This change ${direction}.` : ""}`);
    }
    if (aiImpacts.length > 0) {
      const impactText = aiImpacts
        .map((impact) => `${impact.impact_summary} (linked via ${impact.why_linked})`)
        .join(" ");
      parts.push(`Potential downstream impacts: ${impactText}`);
    }
    return parts.join(" ");
  }, [aiInsight, aiImpacts]);

  useEffect(() => {
    if (activeTab !== "side" || !syncScroll) return;

    const left = paneARef.current;
    const right = paneBRef.current;
    if (!left || !right) return;

    const syncFromLeft = () => {
      if (syncingRef.current) return;
      syncingRef.current = true;
      const ratio = left.scrollTop / Math.max(1, left.scrollHeight - left.clientHeight);
      right.scrollTop = ratio * Math.max(0, right.scrollHeight - right.clientHeight);
      syncingRef.current = false;
    };

    const syncFromRight = () => {
      if (syncingRef.current) return;
      syncingRef.current = true;
      const ratio = right.scrollTop / Math.max(1, right.scrollHeight - right.clientHeight);
      left.scrollTop = ratio * Math.max(0, left.scrollHeight - left.clientHeight);
      syncingRef.current = false;
    };

    left.addEventListener("scroll", syncFromLeft, { passive: true });
    right.addEventListener("scroll", syncFromRight, { passive: true });

    return () => {
      left.removeEventListener("scroll", syncFromLeft);
      right.removeEventListener("scroll", syncFromRight);
    };
  }, [activeTab, syncScroll]);

  useEffect(() => {
    if (loading || start === null) return;

    const scrollToAnchor = (ref) => {
      const node = ref.current;
      if (!node) return;
      const anchor = node.querySelector(`[data-anchor=\"clause-anchor\"]`);
      if (anchor) anchor.scrollIntoView({ block: "start", behavior: "smooth" });
    };

    if (activeTab === "a") scrollToAnchor(soloARef);
    if (activeTab === "b") scrollToAnchor(soloBRef);
    if (activeTab === "side") {
      scrollToAnchor(paneARef);
      scrollToAnchor(paneBRef);
    }
  }, [activeTab, loading, start]);

  if (loading) {
    return (
      <div className="viewer-backdrop" onClick={onClose}>
        <div className="viewer-sheet" onClick={(e) => e.stopPropagation()}>
          <div className="viewer-state">Loading change view...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="viewer-backdrop" onClick={onClose}>
        <div className="viewer-sheet" onClick={(e) => e.stopPropagation()}>
          <div className="viewer-error">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="viewer-backdrop" onClick={onClose}>
      <div className="viewer-sheet" onClick={(e) => e.stopPropagation()}>
        <header className="viewer-header">
          <div>
            <div className="viewer-id">{change?.heading || "Change"}</div>
            <h3>Change Review</h3>
          </div>

          <div className="viewer-meta">
            <button className={`meta-pill ${similarityBand(similarity)}`} onClick={() => setShowSimilarityInfo((v) => !v)}>
              Similarity {similarity}%
            </button>
            <span className={`meta-pill risk-${risk}`}>Risk {risk.toUpperCase()}</span>
          </div>

          <button className="btn btn-ghost" onClick={onClose}>Close</button>

          {showSimilarityInfo && (
            <div className="similarity-note">
              Similarity uses deterministic token and structure matching.
            </div>
          )}
        </header>

        {aiParagraph && (
          <section className="viewer-ai">
            <div className="viewer-ai-label">AI Interpretation</div>
            <p className="viewer-ai-text">{aiParagraph}</p>
          </section>
        )}
        {!aiParagraph && (
          <section className="viewer-ai">
            <div className="viewer-ai-label">AI Interpretation</div>
            <p className="viewer-ai-text">AI summary not available for this change.</p>
          </section>
        )}

        <div className="viewer-tabs">
          <button className={activeTab === "a" ? "active" : ""} onClick={() => setActiveTab("a")}>Version A</button>
          <button className={activeTab === "b" ? "active" : ""} onClick={() => setActiveTab("b")}>Version B</button>
          <button className={activeTab === "side" ? "active" : ""} onClick={() => setActiveTab("side")}>Side-by-Side</button>
          {activeTab === "side" && (
            <label className="sync-toggle">
              <input type="checkbox" checked={syncScroll} onChange={(e) => setSyncScroll(e.target.checked)} />
              Sync Scroll
            </label>
          )}
        </div>

        <main className="viewer-content">
          {activeTab === "a" && (
            <section className="viewer-single" ref={soloARef}>
              <div data-anchor="clause-anchor" />
              {cleanA ? <pre>{renderSegments(segA, "single-a")}</pre> : <div className="empty-line">Clause not present in Version A.</div>}
            </section>
          )}

          {activeTab === "b" && (
            <section className="viewer-single" ref={soloBRef}>
              <div data-anchor="clause-anchor" />
              {cleanB ? <pre>{renderSegments(segB, "single-b")}</pre> : <div className="empty-line">Clause not present in Version B.</div>}
            </section>
          )}

          {activeTab === "side" && (
            <section className="viewer-side">
              <div className="side-col">
                <div className="side-head">Version A</div>
                <div className="side-body" ref={paneARef}>
                  <div data-anchor="clause-anchor" />
                  {change.type === "added" ? <div className="empty-line">Clause not present in Version A.</div> : <pre>{renderSegments(segA, "a")}</pre>}
                </div>
              </div>
              <div className="side-col">
                <div className="side-head">Version B</div>
                <div className="side-body" ref={paneBRef}>
                  <div data-anchor="clause-anchor" />
                  {change.type === "deleted" ? <div className="empty-line">Clause not present in Version B.</div> : <pre>{renderSegments(segB, "b")}</pre>}
                </div>
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
