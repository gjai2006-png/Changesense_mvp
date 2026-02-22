import React, { useMemo, useState } from "react";
import DocumentViewer from "./DocumentViewer";

const API_BASE = "http://localhost:8000";

function titleCaseTag(tag) {
  return tag
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function similarityClass(score) {
  if (score >= 95) return "good";
  if (score >= 85) return "warn";
  return "bad";
}

function StatBlock({ value, label }) {
  return (
    <div className="stat-block">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function ChangeCard({ change, type, onOpen, defaultOpen = false }) {
  const similarity = typeof change.similarity === "number" ? Math.round(change.similarity * 100) : null;
  const before = change.before || change.before_text || "";
  const after = change.after || change.after_text || "";
  const riskTags = change.risk_tags || [];

  return (
    <details className="change-card" open={defaultOpen}>
      <summary className="change-card-summary">
        <div>
          <div className="change-card-topline">
            <span className="change-id">{change.heading || "Change"}</span>
            <span className={`change-pill type-${type}`}>{type}</span>
            {similarity !== null && <span className={`change-pill similarity-${similarityClass(similarity)}`}>{similarity}%</span>}
          </div>
          <h4>{change.heading || "Change"}</h4>
        </div>
        <span className="change-expand">View</span>
      </summary>

      <div className="change-card-body">
        {riskTags.length > 0 && (
          <div className="risk-tags">
            {riskTags.map((tag) => (
              <span key={tag} className="risk-tag">
                {titleCaseTag(tag)}
              </span>
            ))}
          </div>
        )}

        {type === "integrity" && change.reason && <div className="integrity-note">{change.reason}</div>}

        <div className="change-diff-preview">
          <div>
            <div className="preview-label">Before</div>
            <pre className="preview-box before">{before || "Not present"}</pre>
          </div>
          <div>
            <div className="preview-label">After</div>
            <pre className="preview-box after">{after || "Not present"}</pre>
          </div>
        </div>

        <button className="btn btn-primary" onClick={() => onOpen(change, type)}>
          Open In Viewer
        </button>
      </div>
    </details>
  );
}

function EvidencePanel({ title, type, changes, onOpen }) {
  return (
    <section className="evidence-panel">
      <header>
        <h3>{title}</h3>
        <span>{changes.length}</span>
      </header>
      <div className="evidence-list">
        {changes.length === 0 ? (
          <div className="empty-line">No {title.toLowerCase()}.</div>
        ) : (
          changes.map((change, idx) => (
            <ChangeCard key={`${type}-${change.id}-${idx}`} change={change} type={type} onOpen={onOpen} />
          ))
        )}
      </div>
    </section>
  );
}

export default function App() {
  const [versionA, setVersionA] = useState(null);
  const [versionB, setVersionB] = useState(null);
  const [compare, setCompare] = useState(null);
  const [integrity, setIntegrity] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [viewerChange, setViewerChange] = useState(null);
  const [runId, setRunId] = useState(null);
  const [aiSummary, setAiSummary] = useState(null);

  const clauseMap = useMemo(() => {
    const map = new Map();
    if (!compare?.clauses) return map;

    compare.clauses.modified.forEach((clause) => map.set(clause.id, { ...clause, type: "modified" }));
    compare.clauses.added.forEach((clause) =>
      map.set(clause.id, {
        ...clause,
        before: "",
        after: clause.text,
        before_text: "",
        after_text: clause.text,
        type: "added",
      })
    );
    compare.clauses.deleted.forEach((clause) =>
      map.set(clause.id, {
        ...clause,
        before: clause.text,
        after: "",
        before_text: clause.text,
        after_text: "",
        type: "deleted",
      })
    );

    return map;
  }, [compare]);

  const confidence = useMemo(() => {
    if (!compare) return "Not Available";
    const density = compare.stats.modified_count > 0 ? compare.stats.high_risk_count / compare.stats.modified_count : 0;
    if (density <= 0.2) return "High";
    if (density <= 0.45) return "Medium";
    return "Review Required";
  }, [compare]);

  const highRiskChanges = useMemo(() => {
    if (!compare?.risks) return [];
    return compare.risks
      .filter((risk) => Array.isArray(risk.risk_tags) && risk.risk_tags.length > 0)
      .map((risk) => {
        const clause = clauseMap.get(risk.id);
        return {
          ...(clause || risk),
          id: risk.id,
          heading: risk.heading,
          risk_tags: risk.risk_tags,
          riskAnalysis: risk,
          type: clause?.type || "modified",
        };
      });
  }, [compare?.risks, clauseMap]);

  const integrityItems = useMemo(() => {
    if (!integrity?.integrity_alerts) return [];
    return integrity.integrity_alerts.map((item) => {
      const clause = clauseMap.get(item.id);
      return {
        ...(clause || item),
        ...item,
        type: clause?.type || "integrity",
      };
    });
  }, [integrity?.integrity_alerts, clauseMap]);

  const flattenClauseTree = (node, acc = {}) => {
    if (!node) return acc;
    if (node.clause_id && node.label && node.clause_id !== "root") {
      acc[node.clause_id] = node.label;
    }
    if (node.children) {
      node.children.forEach((child) => flattenClauseTree(child, acc));
    }
    return acc;
  };

  const runVerification = async () => {
    if (!versionA || !versionB) {
      setError("Upload both Version A and Version B first.");
      return;
    }

    setLoading(true);
    setError(null);
    setCompare(null);
    setIntegrity(null);
    setRunId(null);
    setAiSummary(null);

    try {
      const compareBody = new FormData();
      compareBody.append("version_a", versionA);
      compareBody.append("version_b", versionB);

      const compareRes = await fetch(`${API_BASE}/compare`, { method: "POST", body: compareBody });
      if (!compareRes.ok) throw new Error("Clause verification failed.");

      const compareJson = await compareRes.json();
      
      // Transform backend response to frontend expected structure
      const transformedCompare = transformBackendResponse(compareJson);
      
      setRunId(compareJson.run?.run_id || null);

      // Extract integrity alerts
      const integrityJson = {
        integrity_alerts: compareJson.integrity_alerts || [],
      };

      setCompare(transformedCompare);
      setIntegrity(integrityJson);

      if (compareJson.run?.run_id) {
        const aiRes = await fetch(
          `${API_BASE}/ai/insights?run_id=${encodeURIComponent(compareJson.run.run_id)}&ai_enabled=true`,
          { method: "POST" }
        );
        const aiJson = await aiRes.json();
        setAiSummary(aiJson);
      }
    } catch (runError) {
      setError(runError.message || "Verification failed.");
    } finally {
      setLoading(false);
    }
  };

  const transformBackendResponse = (backendResponse) => {
    const { changes = [], materiality = [], clause_tree_b } = backendResponse;
    const clauseLabels = flattenClauseTree(clause_tree_b?.root);
    
    // Group changes by type
    const modified = [];
    const added = [];
    const deleted = [];
    
    changes.forEach((change) => {
      const transformedChange = {
        id: change.clause_id,
        heading: clauseLabels[change.clause_id] || "Change",
        before: change.before_text || "",
        after: change.after_text || "",
        before_text: change.before_text || "",
        after_text: change.after_text || "",
        similarity: 1.0, // Default similarity
        risk_tags: [],
      };
      
      // Determine if added, deleted, or modified
      if (!change.before_text || change.before_text.trim() === "") {
        added.push(transformedChange);
      } else if (!change.after_text || change.after_text.trim() === "") {
        deleted.push(transformedChange);
      } else {
        modified.push(transformedChange);
      }
    });
    
    // Create risk entries from materiality findings
    const risks = materiality.map((finding) => ({
      id: finding.clause_id,
      heading: clauseLabels[finding.clause_id] || "Change",
      risk_tags: [finding.category] || [],
      before_text: "",
      after_text: "",
    }));
    
    // Calculate stats
    const stats = {
      modified_count: modified.length,
      added_count: added.length,
      deleted_count: deleted.length,
      high_risk_count: risks.length,
      obligation_shift_count: risks.filter((r) => r.risk_tags.includes("obligation")).length,
    };
    
    return {
      clauses: {
        modified,
        added,
        deleted,
      },
      risks,
      stats,
    };
  };

  const openViewer = (change, type) => {
    const base = clauseMap.get(change.id) || { ...change, type };
    const riskAnalysis = compare?.risks?.find((risk) => risk.id === change.id);

    setViewerChange({
      ...base,
      ...change,
      type: base.type || type,
      risk_tags: riskAnalysis?.risk_tags || base.risk_tags || change.risk_tags || [],
      riskAnalysis: riskAnalysis || base.riskAnalysis,
      before: change.before ?? base.before ?? base.before_text ?? "",
      after: change.after ?? base.after ?? base.after_text ?? "",
      before_text: change.before ?? base.before ?? base.before_text ?? "",
      after_text: change.after ?? base.after ?? base.after_text ?? "",
    });
  };

  const showLanding = !compare && !loading;

  return (
    <div className="app">
      {showLanding && (
        <section className="landing">
          <div className="landing-content">
            <div className="kicker">ChangeSense</div>
            <h1>Change Verification</h1>
            <p>Deterministic structural comparison for high-stakes documents.</p>
          </div>

          <div className="upload-sheet">
            <div className="upload-grid">
              <label>
                <span>Version A</span>
                <div className="file-picker">
                  <span className="file-picker-btn">Choose File</span>
                  <span className="file-picker-name">{versionA?.name || "No file selected"}</span>
                </div>
                <input
                  className="file-input-hidden"
                  type="file"
                  accept=".txt,.docx,.pdf"
                  onChange={(e) => setVersionA(e.target.files?.[0] || null)}
                />
              </label>
              <label>
                <span>Version B</span>
                <div className="file-picker">
                  <span className="file-picker-btn">Choose File</span>
                  <span className="file-picker-name">{versionB?.name || "No file selected"}</span>
                </div>
                <input
                  className="file-input-hidden"
                  type="file"
                  accept=".txt,.docx,.pdf"
                  onChange={(e) => setVersionB(e.target.files?.[0] || null)}
                />
              </label>
            </div>
            <button className="btn btn-primary large" onClick={runVerification} disabled={loading}>
              {loading ? "Running..." : "Run Change Verification"}
            </button>
          </div>
        </section>
      )}

      {(compare || loading) && (
        <section className="topbar">
          <div className="upload-grid compact">
            <label>
              <span>Version A</span>
              <div className="file-picker">
                <span className="file-picker-btn">Choose File</span>
                <span className="file-picker-name">{versionA?.name || "No file selected"}</span>
              </div>
              <input
                className="file-input-hidden"
                type="file"
                accept=".txt,.docx,.pdf"
                onChange={(e) => setVersionA(e.target.files?.[0] || null)}
              />
            </label>
            <label>
              <span>Version B</span>
              <div className="file-picker">
                <span className="file-picker-btn">Choose File</span>
                <span className="file-picker-name">{versionB?.name || "No file selected"}</span>
              </div>
              <input
                className="file-input-hidden"
                type="file"
                accept=".txt,.docx,.pdf"
                onChange={(e) => setVersionB(e.target.files?.[0] || null)}
              />
            </label>
          </div>
          <button className="btn btn-primary" onClick={runVerification} disabled={loading}>
            {loading ? "Running..." : "Run Change Verification"}
          </button>
          <div className="run-meta">
            <span className={`status ${compare ? "done" : "idle"}`}>{compare ? "Complete" : "Idle"}</span>
            <span className="confidence">Confidence: {confidence}</span>
          </div>
        </section>
      )}

      {error && <div className="error">{error}</div>}
      {loading && <div className="loading">Analyzing changes and integrity signals...</div>}

      {compare && (
        <>
          <section className="overview">
            <article className="high-risk">
              <header>
                <h2>High-Risk Changes</h2>
                <span>{compare.stats.high_risk_count}</span>
              </header>

              <div className="high-risk-body">
                {highRiskChanges.length === 0 ? (
                  <div className="empty-line">No high-risk changes detected.</div>
                ) : (
                  highRiskChanges.map((change, idx) => (
                    <ChangeCard
                      key={`high-${change.id}-${idx}`}
                      change={change}
                      type={change.type || "modified"}
                      onOpen={openViewer}
                      defaultOpen={idx === 0}
                    />
                  ))
                )}
              </div>
            </article>

            <aside className="summary">
              <h3>Verification Summary</h3>
              <div className="summary-stats">
                <StatBlock value={compare.stats.modified_count} label="Modified" />
                <StatBlock value={compare.stats.added_count} label="Added" />
                <StatBlock value={compare.stats.deleted_count} label="Deleted" />
                <StatBlock value={compare.stats.high_risk_count} label="High Risk" />
                <StatBlock value={compare.stats.obligation_shift_count} label="Obligation Shifts" />
              </div>
              <button
                className="btn btn-ghost"
                onClick={() => runId && window.open(`${API_BASE}/report?run_id=${encodeURIComponent(runId)}`, "_blank")}
              >
                Export PDF Report
              </button>
            </aside>
          </section>

          <section className="evidence">
            <EvidencePanel title="Modified" type="modified" changes={compare.clauses.modified} onOpen={openViewer} />
            <EvidencePanel title="Added" type="added" changes={compare.clauses.added} onOpen={openViewer} />
            <EvidencePanel title="Deleted" type="deleted" changes={compare.clauses.deleted} onOpen={openViewer} />
            <EvidencePanel title="Integrity" type="integrity" changes={integrityItems} onOpen={openViewer} />
          </section>

          <section className="ai-summary">
            <header>
              <h2>AI Semantic Summary</h2>
            </header>
            {!aiSummary && <div className="empty-line">Run verification to see AI insights.</div>}
            {aiSummary?.summaries?.length === 0 && !aiSummary?.raw_text && (
              <div className="empty-line">No AI summary returned.</div>
            )}
            {aiSummary?.raw_text && (
              <div className="empty-line">AI returned non-JSON output. Showing raw response below.</div>
            )}
            {aiSummary?.raw_text && <pre className="preview-box">{aiSummary.raw_text}</pre>}
            {aiSummary?.summaries?.map((summary, idx) => (
              <article key={`ai-${idx}`} className="change-card">
                <h4>{summary.type}</h4>
                {summary.bullets?.map((bullet, i) => (
                  <p key={`${idx}-${i}`}>{bullet}</p>
                ))}
              </article>
            ))}
          </section>

          <section className="ai-summary">
            <header>
              <h2>AI Change Meaning</h2>
            </header>
            {!aiSummary && <div className="empty-line">Run verification to see AI meaning per change.</div>}
            {aiSummary?.insights?.length === 0 && !aiSummary?.raw_text && (
              <div className="empty-line">No AI change insights returned.</div>
            )}
            {aiSummary?.insights?.map((insight, idx) => (
              <article key={`insight-${idx}`} className="change-card">
                <h4>{insight.semantic_label}</h4>
                <p>Risk Direction: {insight.risk_direction}</p>
                <p>{insight.explanation}</p>
                <p>Confidence: {Math.round((insight.confidence || 0) * 100)}%</p>
              </article>
            ))}
          </section>

          <section className="ai-summary">
            <header>
              <h2>AI Use-Case Impact</h2>
            </header>
            {!aiSummary && <div className="empty-line">Run verification to see AI impact analysis.</div>}
            {aiSummary?.impacts?.length === 0 && !aiSummary?.raw_text && (
              <div className="empty-line">No AI impact analysis returned.</div>
            )}
            {aiSummary?.impacts?.map((impact, idx) => (
              <article key={`impact-${idx}`} className="change-card">
                <h4>Impacted Clause: {impact.impacted_clause_id}</h4>
                <p>Trigger: {impact.trigger_change_id}</p>
                <p>{impact.impact_summary}</p>
                <p>Why Linked: {impact.why_linked}</p>
                <p>Confidence: {Math.round((impact.confidence || 0) * 100)}%</p>
              </article>
            ))}
          </section>
        </>
      )}

      {viewerChange && (
        <DocumentViewer change={viewerChange} aiSummary={aiSummary} onClose={() => setViewerChange(null)} />
      )}
    </div>
  );
}
