import React, { useMemo, useState } from "react";
import DocumentViewer from "./DocumentViewer";

const API_BASE = "http://localhost:8000";

function titleCaseTag(tag) {
  return String(tag || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function severityWeight(severity) {
  if (severity === "high") return 3;
  if (severity === "medium") return 2;
  return 1;
}

function severityLabel(severity) {
  if (severity === "high") return "Critical";
  if (severity === "medium") return "Elevated";
  return "Routine";
}

function severityClass(severity) {
  if (severity === "high") return "critical";
  if (severity === "medium") return "elevated";
  return "routine";
}

function similarityClass(score) {
  if (score >= 95) return "good";
  if (score >= 85) return "warn";
  return "bad";
}

function computeSimilarity(change) {
  const before = change.before_text || "";
  const after = change.after_text || "";
  if (!before || !after) return 0;

  const beforeWords = before.trim().split(/\s+/).length;
  const afterWords = after.trim().split(/\s+/).length;
  const insertions = (change.insertions || []).reduce((sum, item) => sum + (item.after?.trim().split(/\s+/).filter(Boolean).length || 0), 0);
  const deletions = (change.deletions || []).reduce((sum, item) => sum + (item.before?.trim().split(/\s+/).filter(Boolean).length || 0), 0);
  const substitutions = (change.substitutions || []).reduce((sum, item) => {
    const beforeCount = item.before?.trim().split(/\s+/).filter(Boolean).length || 0;
    const afterCount = item.after?.trim().split(/\s+/).filter(Boolean).length || 0;
    return sum + Math.max(beforeCount, afterCount);
  }, 0);
  const total = Math.max(beforeWords, afterWords, 1);
  const changed = Math.min(total, insertions + deletions + substitutions);
  return Math.max(0, Math.min(1, 1 - changed / total));
}

function verdictFor(compare, integrityCount) {
  if (!compare) return { label: "Pending", tone: "pending" };
  if (integrityCount > 0 || compare.stats.high_risk_count >= 3) {
    return { label: "Escalate Review", tone: "critical" };
  }
  if (compare.stats.high_risk_count > 0 || compare.stats.modified_count > 0) {
    return { label: "Targeted Review", tone: "elevated" };
  }
  return { label: "Verified Clean", tone: "clean" };
}

function StatBlock({ value, label, helper }) {
  return (
    <div className="stat-block">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {helper ? <div className="stat-helper">{helper}</div> : null}
    </div>
  );
}

function UploadField({ label, file, onChange }) {
  return (
    <label className="upload-field">
      <span>{label}</span>
      <div className="file-picker">
        <span className="file-picker-btn">Choose File</span>
        <span className="file-picker-name">{file?.name || "DOCX, TXT, or PDF"}</span>
      </div>
      <input className="file-input-hidden" type="file" accept=".txt,.docx,.pdf" onChange={(e) => onChange(e.target.files?.[0] || null)} />
    </label>
  );
}

function ChangeCard({ change, type, onOpen, defaultOpen = false }) {
  const similarity = typeof change.similarity === "number" ? Math.round(change.similarity * 100) : null;
  const before = change.before || change.before_text || "";
  const after = change.after || change.after_text || "";
  const riskTags = change.risk_tags || [];
  const findings = change.findings || [];
  const severity = change.severity || (type === "integrity" ? "high" : "low");

  return (
    <details className="change-card" open={defaultOpen}>
      <summary className="change-card-summary">
        <div>
          <div className="change-card-topline">
            <span className="change-id">{change.heading || "Change"}</span>
            <span className={`change-pill type-${type}`}>{type}</span>
            <span className={`change-pill severity-${severityClass(severity)}`}>{severityLabel(severity)}</span>
            {similarity !== null && similarity > 0 ? (
              <span className={`change-pill similarity-${similarityClass(similarity)}`}>{similarity}%</span>
            ) : null}
          </div>
          <h4>{change.heading || "Change"}</h4>
        </div>
        <span className="change-expand">Proof</span>
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

        {type === "integrity" && change.reason ? <div className="integrity-note">{change.reason}</div> : null}

        {findings.length > 0 ? (
          <div className="finding-list">
            {findings.slice(0, 2).map((finding, idx) => (
              <div key={`${change.id}-${idx}`} className="finding-item">
                <strong>{titleCaseTag(finding.category)}</strong>
                <span>{finding.rationale}</span>
              </div>
            ))}
          </div>
        ) : null}

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
          Open Deep-Link Proof
        </button>
      </div>
    </details>
  );
}

function EvidencePanel({ title, subtitle, type, changes, onOpen }) {
  return (
    <section className="evidence-panel">
      <header>
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
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

function ReviewQueue({ items, integrityItems, onOpen }) {
  return (
    <section className="queue-panel">
      <header className="section-header">
        <div>
          <div className="eyebrow">Review Queue</div>
          <h2>What counsel should look at first</h2>
        </div>
      </header>

      <div className="queue-list">
        {items.length === 0 && integrityItems.length === 0 ? (
          <div className="empty-line">No priority review items detected.</div>
        ) : null}

        {items.map((item, idx) => (
          <button key={`queue-${item.id}-${idx}`} className="queue-item" onClick={() => onOpen(item, item.type || "modified")}>
            <div className="queue-rank">{idx + 1}</div>
            <div className="queue-copy">
              <div className="queue-title">{item.heading}</div>
              <div className="queue-meta">
                <span className={`mini-pill severity-${severityClass(item.severity || "high")}`}>{severityLabel(item.severity || "high")}</span>
                {(item.risk_tags || []).slice(0, 2).map((tag) => (
                  <span key={`${item.id}-${tag}`} className="mini-pill">
                    {titleCaseTag(tag)}
                  </span>
                ))}
              </div>
            </div>
            <div className="queue-arrow">›</div>
          </button>
        ))}

        {integrityItems.map((item, idx) => (
          <button key={`integrity-${item.id}-${idx}`} className="queue-item integrity" onClick={() => onOpen(item, "integrity")}>
            <div className="queue-rank">!</div>
            <div className="queue-copy">
              <div className="queue-title">{item.heading || "Integrity Risk"}</div>
              <div className="queue-meta">
                <span className="mini-pill severity-critical">Integrity Risk</span>
                <span className="mini-pill">{item.reason}</span>
              </div>
            </div>
            <div className="queue-arrow">›</div>
          </button>
        ))}
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

  const transformBackendResponse = (backendResponse) => {
    const { changes = [], materiality = [], clause_tree_b } = backendResponse;
    const clauseLabels = flattenClauseTree(clause_tree_b?.root);

    const riskByClause = new Map();
    materiality.forEach((finding) => {
      const key = finding.clause_id || "__unknown__";
      const existing = riskByClause.get(key);
      if (!existing) {
        riskByClause.set(key, {
          id: key,
          clause_id: key,
          heading: clauseLabels[key] || "Change",
          risk_tags: finding.category ? [finding.category] : [],
          findings: [finding],
          severity: finding.severity || "low",
        });
        return;
      }

      if (finding.category && !existing.risk_tags.includes(finding.category)) {
        existing.risk_tags.push(finding.category);
      }
      existing.findings.push(finding);
      if (severityWeight(finding.severity) > severityWeight(existing.severity)) {
        existing.severity = finding.severity;
      }
    });

    const decorateChange = (change) => {
      const risk = riskByClause.get(change.clause_id);
      return {
        id: change.clause_id,
        clause_id: change.clause_id,
        heading: change.heading || clauseLabels[change.clause_id] || "Change",
        before: change.before_text || "",
        after: change.after_text || "",
        before_text: change.before_text || "",
        after_text: change.after_text || "",
        word_diffs: change.word_diffs || null,
        similarity: computeSimilarity(change),
        risk_tags: risk?.risk_tags || [],
        findings: risk?.findings || [],
        severity: risk?.severity || (change.change_type === "modified" ? "low" : "medium"),
        type: change.change_type || "modified",
      };
    };

    const modified = [];
    const added = [];
    const deleted = [];

    changes
      .filter((change) => change.clause_id !== "table-changes")
      .forEach((change) => {
        const transformed = decorateChange(change);
        if (!change.before_text || change.before_text.trim() === "") {
          added.push(transformed);
        } else if (!change.after_text || change.after_text.trim() === "") {
          deleted.push(transformed);
        } else {
          modified.push(transformed);
        }
      });

    const risks = Array.from(riskByClause.values()).sort((a, b) => {
      const severityDelta = severityWeight(b.severity) - severityWeight(a.severity);
      if (severityDelta !== 0) return severityDelta;
      return (b.risk_tags?.length || 0) - (a.risk_tags?.length || 0);
    });

    const stats = {
      modified_count: modified.length,
      added_count: added.length,
      deleted_count: deleted.length,
      high_risk_count: risks.filter((risk) => risk.severity === "high").length,
      obligation_shift_count: risks.filter((risk) => (risk.risk_tags || []).some((tag) => /obligation/i.test(String(tag)))).length,
      elevated_count: risks.length,
    };

    return {
      clauses: { modified, added, deleted },
      risks,
      stats,
    };
  };

  const clauseMap = useMemo(() => {
    const map = new Map();
    if (!compare?.clauses) return map;
    compare.clauses.modified.forEach((clause) => map.set(clause.id, { ...clause, type: "modified" }));
    compare.clauses.added.forEach((clause) => map.set(clause.id, { ...clause, type: "added" }));
    compare.clauses.deleted.forEach((clause) => map.set(clause.id, { ...clause, type: "deleted" }));
    return map;
  }, [compare]);

  const confidence = useMemo(() => {
    if (!compare) return "Not Available";
    if (integrity?.integrity_alerts?.length) return "Review Required";
    const density = compare.stats.modified_count > 0 ? compare.stats.elevated_count / compare.stats.modified_count : 0;
    if (density <= 0.15) return "High";
    if (density <= 0.4) return "Medium";
    return "Review Required";
  }, [compare, integrity]);

  const highRiskChanges = useMemo(() => {
    if (!compare?.risks) return [];
    return compare.risks
      .map((risk) => {
        const clause = clauseMap.get(risk.id);
        return {
          ...(clause || risk),
          ...risk,
          type: clause?.type || "modified",
        };
      })
      .sort((a, b) => severityWeight(b.severity) - severityWeight(a.severity));
  }, [compare?.risks, clauseMap]);

  const integrityItems = useMemo(() => {
    if (!integrity?.integrity_alerts) return [];
    return integrity.integrity_alerts.map((item) => {
      const clause = clauseMap.get(item.id);
      return {
        ...(clause || item),
        ...item,
        type: "integrity",
        severity: "high",
      };
    });
  }, [integrity?.integrity_alerts, clauseMap]);

  const viewerSequence = useMemo(() => {
    const items = [];
    highRiskChanges.forEach((change) => items.push({ change, type: change.type || "modified" }));
    compare?.clauses?.modified?.forEach((change) => items.push({ change, type: "modified" }));
    compare?.clauses?.added?.forEach((change) => items.push({ change, type: "added" }));
    compare?.clauses?.deleted?.forEach((change) => items.push({ change, type: "deleted" }));
    integrityItems.forEach((change) => items.push({ change, type: "integrity" }));
    return items;
  }, [compare?.clauses, highRiskChanges, integrityItems]);

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
      const transformedCompare = transformBackendResponse(compareJson);

      setRunId(compareJson.run?.run_id || null);
      setCompare(transformedCompare);
      const nextClauseMap = new Map();
      [
        ...transformedCompare.clauses.modified,
        ...transformedCompare.clauses.added,
        ...transformedCompare.clauses.deleted,
      ].forEach((item) => nextClauseMap.set(item.clause_id, item));
      setIntegrity({
        integrity_alerts: (compareJson.integrity_alerts || []).map((item) => ({
          id: item.clause_id,
          clause_id: item.clause_id,
          heading: nextClauseMap.get(item.clause_id)?.heading || item.clause_id,
          reason: item.rationale,
          alert_type: item.alert_type,
        })),
      });

      if (compareJson.run?.run_id) {
        const aiRes = await fetch(`${API_BASE}/ai/insights?run_id=${encodeURIComponent(compareJson.run.run_id)}&ai_enabled=true`, {
          method: "POST",
        });
        const aiJson = await aiRes.json();
        if (aiJson?.raw_text) {
          try {
            const parsed = JSON.parse(aiJson.raw_text);
            setAiSummary({ ...parsed, ai_enabled: true });
          } catch {
            setAiSummary({ error: "AI returned non-JSON output. Please retry." });
          }
        } else {
          setAiSummary(aiJson);
        }
      }
    } catch (runError) {
      setError(runError.message || "Verification failed.");
    } finally {
      setLoading(false);
    }
  };

  const openViewer = (change, type) => {
    const changeId = change.clause_id || change.id;
    const base = clauseMap.get(changeId) || { ...change, type };
    const riskAnalysis = compare?.risks?.find((risk) => risk.id === changeId);

    setViewerChange({
      ...base,
      ...change,
      id: changeId,
      clause_id: changeId,
      type: base.type || type,
      risk_tags: riskAnalysis?.risk_tags || base.risk_tags || change.risk_tags || [],
      findings: riskAnalysis?.findings || base.findings || change.findings || [],
      severity: riskAnalysis?.severity || base.severity || change.severity || "low",
      before: change.before ?? base.before ?? base.before_text ?? "",
      after: change.after ?? base.after ?? base.after_text ?? "",
      before_text: change.before ?? base.before ?? base.before_text ?? "",
      after_text: change.after ?? base.after ?? base.after_text ?? "",
    });
  };

  const viewerSequenceKey = (item) => `${item?.type || "modified"}::${item?.clause_id || item?.id || ""}`;

  const currentViewerIndex = useMemo(() => {
    if (!viewerChange) return -1;
    const key = viewerSequenceKey(viewerChange);
    return viewerSequence.findIndex(({ change, type }) => viewerSequenceKey({ ...change, type }) === key);
  }, [viewerChange, viewerSequence]);

  const openViewerAtIndex = (index) => {
    const target = viewerSequence[index];
    if (!target) return;
    openViewer(target.change, target.type);
  };

  const showLanding = !compare && !loading;
  const verdict = verdictFor(compare, integrityItems.length);

  return (
    <div className="app">
      <section className={`hero-shell ${showLanding ? "landing" : "compact"}`}>
        <div className="hero-copy">
          <div className="kicker">ChangeSense</div>
          <h1>The Verification Layer for High-Stakes Documentation</h1>
          <p>
            Deterministic clause-by-clause verification for deal teams that need proof before signing, not a probabilistic
            summary after the fact.
          </p>
          <div className="hero-points">
            <div>Ghost edit detection</div>
            <div>Obligation and numeric shift tagging</div>
            <div>Deep-linked proof view for every flagged clause</div>
          </div>
        </div>

        <div className="upload-sheet">
          <div className="sheet-header">
            <div>
              <div className="eyebrow">New Verification</div>
              <h2>Compare two drafts before a client call</h2>
            </div>
            {!showLanding ? <span className={`verdict-badge ${verdict.tone}`}>{verdict.label}</span> : null}
          </div>

          <div className="upload-grid">
            <UploadField label="Version A" file={versionA} onChange={setVersionA} />
            <UploadField label="Version B" file={versionB} onChange={setVersionB} />
          </div>

          <div className="upload-actions">
            <button className="btn btn-primary large" onClick={runVerification} disabled={loading}>
              {loading ? "Running Deterministic Verification..." : "Run Deterministic Verification"}
            </button>
            {compare ? (
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setCompare(null);
                  setIntegrity(null);
                  setAiSummary(null);
                  setRunId(null);
                  setViewerChange(null);
                  setError(null);
                }}
              >
                Start New Review
              </button>
            ) : null}
          </div>

          <div className="upload-footnote">
            ChangeSense compares structure, clause language, numeric terms, and integrity signals entirely in-memory for this
            prototype run.
          </div>
        </div>
      </section>

      {error ? <div className="error">{error}</div> : null}
      {loading ? <div className="loading">Analyzing clause evolution, integrity signals, and deterministic risk rules...</div> : null}

      {compare ? (
        <>
          <section className="verification-strip">
            <div className="verification-intro">
              <div className="eyebrow">Verification Outcome</div>
              <h2>{verdict.label}</h2>
              <p>
                Compared <strong>{versionA?.name || "Version A"}</strong> against <strong>{versionB?.name || "Version B"}</strong>.
                Use the priority queue to review what changed materially and where integrity risk may exist.
              </p>
            </div>

            <div className="verification-actions">
              <div className="run-meta">
                <span className="status done">Run Complete</span>
                <span className="confidence">Verification confidence: {confidence}</span>
                {runId ? <span className="run-id">Run ID: {runId}</span> : null}
              </div>
              <button
                className="btn btn-secondary"
                onClick={() => runId && window.open(`${API_BASE}/report?run_id=${encodeURIComponent(runId)}`, "_blank")}
              >
                Export Verified PDF
              </button>
            </div>
          </section>

          <section className="overview-grid">
            <article className="summary-panel">
              <header className="section-header">
                <div>
                  <div className="eyebrow">Verification Summary</div>
                  <h2>Material changes at a glance</h2>
                </div>
              </header>
              <div className="summary-stats">
                <StatBlock value={compare.stats.modified_count} label="Modified Clauses" helper="Language changed in both versions" />
                <StatBlock value={compare.stats.added_count} label="Inserted Clauses" helper="New clauses in Version B" />
                <StatBlock value={compare.stats.deleted_count} label="Deleted Clauses" helper="Clauses removed from Version A" />
                <StatBlock value={compare.stats.high_risk_count} label="Critical Risks" helper="Immediate legal review advised" />
                <StatBlock value={compare.stats.obligation_shift_count} label="Obligation Shifts" helper="May/shall and similar changes" />
                <StatBlock value={integrityItems.length} label="Integrity Alerts" helper="Potential ghost edits or moved content" />
              </div>
            </article>

            <article className="checklist-panel">
              <header className="section-header">
                <div>
                  <div className="eyebrow">Verification Checklist</div>
                  <h2>Review order for a pressured team</h2>
                </div>
              </header>
              <div className="checklist">
                <div className="check-item">
                  <span>1</span>
                  <div>Start with critical risk tags such as obligation, numeric, and date changes.</div>
                </div>
                <div className="check-item">
                  <span>2</span>
                  <div>Inspect integrity alerts separately to catch edits that track changes may miss.</div>
                </div>
                <div className="check-item">
                  <span>3</span>
                  <div>Export the verified report as a closing-file artifact once review is complete.</div>
                </div>
              </div>
            </article>
          </section>

          <section className="workbench-grid">
            <ReviewQueue items={highRiskChanges.slice(0, 6)} integrityItems={integrityItems.slice(0, 3)} onOpen={openViewer} />

            <section className="high-risk">
              <header className="section-header">
                <div>
                  <div className="eyebrow alert">High-Risk Clauses</div>
                  <h2>Proof-backed changes that could alter deal meaning</h2>
                </div>
                <span>{highRiskChanges.length}</span>
              </header>
              <div className="high-risk-body">
                {highRiskChanges.length === 0 ? (
                  <div className="empty-line">No critical rule-triggered changes detected.</div>
                ) : (
                  highRiskChanges.slice(0, 8).map((change, idx) => (
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
            </section>
          </section>

          <section className="evidence">
            <EvidencePanel
              title="Modified Clauses"
              subtitle="Clause text changed across both versions."
              type="modified"
              changes={compare.clauses.modified}
              onOpen={openViewer}
            />
            <EvidencePanel
              title="Inserted Clauses"
              subtitle="New text introduced in Version B."
              type="added"
              changes={compare.clauses.added}
              onOpen={openViewer}
            />
            <EvidencePanel
              title="Deleted Clauses"
              subtitle="Clauses removed from the prior draft."
              type="deleted"
              changes={compare.clauses.deleted}
              onOpen={openViewer}
            />
            <EvidencePanel
              title="Integrity Scan"
              subtitle="Potential ghost edits or silent structural shifts."
              type="integrity"
              changes={integrityItems}
              onOpen={openViewer}
            />
          </section>

          <section className="ai-summary">
            <header>
              <div>
                <div className="eyebrow">Interpretive Appendix</div>
                <h2>Optional AI synthesis layered on top of deterministic findings</h2>
              </div>
            </header>
            {!aiSummary ? <div className="empty-line">Run verification to see AI insights.</div> : null}
            {aiSummary?.error ? <div className="empty-line">{aiSummary.error}</div> : null}
            {aiSummary && !aiSummary.error && aiSummary?.summaries?.length === 0 ? (
              <div className="empty-line">No AI summary returned.</div>
            ) : null}
            {aiSummary?.summaries?.length > 0 ? (
              <div className="ai-summary-grid">
                {aiSummary.summaries.map((summary, idx) => (
                  <article className="ai-report-card" key={`${summary.type}-${idx}`}>
                    <div className="ai-report-card-top">
                      <span className="ai-report-kind">{summary.type}</span>
                      <span className="ai-report-count">{summary.bullets?.length || 0} items</span>
                    </div>
                    <h4>{titleCaseTag(summary.type)} View</h4>
                    <div className="ai-bullet-list">
                      {(summary.bullets || []).map((bullet, bulletIdx) => (
                        <div className="ai-bullet" key={`${summary.type}-bullet-${bulletIdx}`}>
                          {bullet}
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            ) : null}
          </section>
        </>
      ) : null}

      {viewerChange ? (
        <DocumentViewer
          change={viewerChange}
          aiSummary={aiSummary}
          onClose={() => setViewerChange(null)}
          onPrev={currentViewerIndex > 0 ? () => openViewerAtIndex(currentViewerIndex - 1) : undefined}
          onNext={currentViewerIndex >= 0 && currentViewerIndex < viewerSequence.length - 1 ? () => openViewerAtIndex(currentViewerIndex + 1) : undefined}
          canPrev={currentViewerIndex > 0}
          canNext={currentViewerIndex >= 0 && currentViewerIndex < viewerSequence.length - 1}
        />
      ) : null}
    </div>
  );
}
