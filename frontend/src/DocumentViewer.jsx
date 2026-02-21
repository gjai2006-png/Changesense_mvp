import React, { useEffect, useMemo, useRef, useState } from "react";

const API_BASE = "http://localhost:8000";

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

function renderSegments(segments, keyPrefix) {
  return segments.map((seg, i) => {
    if (seg.type === "added") return <span key={`${keyPrefix}-a-${i}`} className="hl-add">{seg.text}</span>;
    if (seg.type === "removed") return <span key={`${keyPrefix}-r-${i}`} className="hl-remove">{seg.text}</span>;
    return <span key={`${keyPrefix}-p-${i}`}>{seg.text}</span>;
  });
}

export default function DocumentViewer({ change, onClose }) {
  const [activeTab, setActiveTab] = useState("side");
  const [syncScroll, setSyncScroll] = useState(true);
  const [showSimilarityInfo, setShowSimilarityInfo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [docA, setDocA] = useState(null);
  const [docB, setDocB] = useState(null);

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
    return extractByRange(docA, start, end, beforeText);
  }, [change.type, docA, start, end, beforeText]);

  const cleanB = useMemo(() => {
    if (change.type === "deleted") return "";
    return extractByRange(docB, start, end, afterText);
  }, [change.type, docB, start, end, afterText]);

  const segA = useMemo(() => buildSegments(cleanA, change?.word_diffs?.before_spans, "a"), [cleanA, change?.word_diffs?.before_spans]);
  const segB = useMemo(() => buildSegments(cleanB, change?.word_diffs?.after_spans, "b"), [cleanB, change?.word_diffs?.after_spans]);

  useEffect(() => {
    let active = true;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);

        const [aRes, bRes] = await Promise.all([fetch(`${API_BASE}/document/a`), fetch(`${API_BASE}/document/b`)]);
        if (!aRes.ok || !bRes.ok) throw new Error("Unable to load documents for viewer.");

        const [a, b] = await Promise.all([aRes.json(), bRes.json()]);
        if (!active) return;
        setDocA(a);
        setDocB(b);
      } catch (e) {
        if (!active) return;
        setError(e.message || "Viewer load failed.");
      } finally {
        if (active) setLoading(false);
      }
    };

    load();
    return () => {
      active = false;
    };
  }, []);

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
          <div className="viewer-state">Loading clause view...</div>
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
            <div className="viewer-id">{change?.id || "Clause"}</div>
            <h3>{change?.heading || "Clause Review"}</h3>
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
              {cleanA ? <pre>{cleanA}</pre> : <div className="empty-line">Clause not present in Version A.</div>}
            </section>
          )}

          {activeTab === "b" && (
            <section className="viewer-single" ref={soloBRef}>
              <div data-anchor="clause-anchor" />
              {cleanB ? <pre>{cleanB}</pre> : <div className="empty-line">Clause not present in Version B.</div>}
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
