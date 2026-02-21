import React, { useState } from "react";

const API_BASE = "http://localhost:8000";

function Section({ title, children }) {
  return (
    <div className="card">
      <div className="section-title">{title}</div>
      {children}
    </div>
  );
}

export default function App() {
  const [versionA, setVersionA] = useState(null);
  const [versionB, setVersionB] = useState(null);
  const [loading, setLoading] = useState(false);
  const [compare, setCompare] = useState(null);
  const [integrity, setIntegrity] = useState(null);
  const [error, setError] = useState(null);
  const [runId, setRunId] = useState(null);
  const [stats, setStats] = useState(null);
  const [aiSummary, setAiSummary] = useState(null);

  const runVerification = async () => {
    if (!versionA || !versionB) {
      setError("Please upload both Version A and Version B.");
      return;
    }
    setError(null);
    setLoading(true);
    setCompare(null);
    setIntegrity(null);
    setRunId(null);
    setStats(null);
    setAiSummary(null);

    const formData = new FormData();
    formData.append("version_a", versionA);
    formData.append("version_b", versionB);

    try {
      const compareRes = await fetch(`${API_BASE}/compare`, {
        method: "POST",
        body: formData
      });
      const compareJson = await compareRes.json();
      setRunId(compareJson.run?.run_id || null);
      const derivedStats = {
        modified_count: compareJson.changes?.length || 0,
        added_count: 0,
        deleted_count: 0,
        high_risk_count: compareJson.materiality?.length || 0,
        obligation_shift_count:
          compareJson.materiality?.filter((m) => m.category === "Obligation Strength").length || 0
      };
      setStats(derivedStats);

      const integrityRes = await fetch(
        `${API_BASE}/scan-integrity?run_id=${encodeURIComponent(compareJson.run?.run_id || "")}`,
        { method: "POST" }
      );
      const integrityJson = await integrityRes.json();

      setCompare(compareJson);
      setIntegrity(integrityJson);

      const aiRes = await fetch(
        `${API_BASE}/ai/insights?run_id=${encodeURIComponent(compareJson.run?.run_id || "")}&ai_enabled=true`,
        { method: "POST" }
      );
      const aiJson = await aiRes.json();
      setAiSummary(aiJson);
    } catch (err) {
      setError("Verification failed. Check backend server.");
    } finally {
      setLoading(false);
    }
  };

  const exportPdf = () => {
    if (!runId) {
      setError("Run verification first to generate a report.");
      return;
    }
    window.open(`${API_BASE}/report?run_id=${encodeURIComponent(runId)}`, "_blank");
  };

  return (
    <div className="app">
      <div className="hero">
        <div>
          <div className="badge">ChangeSense</div>
          <h1>The Verification Layer for High-Stakes Documentation</h1>
          <p>
            Deterministic clause-level comparison to expose obligation shifts,
            ghost edits, and numeric deltas.
          </p>
        </div>
        <button onClick={runVerification}>Run Deterministic Verification</button>
      </div>

      <div className="grid">
        <Section title="Upload Versions">
          <label className="mono">Version A</label>
          <input type="file" accept=".txt,.docx" onChange={(e) => setVersionA(e.target.files[0])} />
          <label className="mono">Version B</label>
          <input type="file" accept=".txt,.docx" onChange={(e) => setVersionB(e.target.files[0])} />
          {error && <p className="mono">{error}</p>}
          {loading && (
            <div className="loader">
              <span></span>
            </div>
          )}
        </Section>

        <Section title="Verification Summary">
          {compare ? (
            <div>
              <p className="mono">Run ID: {runId}</p>
              <p className="mono">Modified Clauses: {stats?.modified_count ?? 0}</p>
              <p className="mono">Added Clauses: {stats?.added_count ?? 0}</p>
              <p className="mono">Deleted Clauses: {stats?.deleted_count ?? 0}</p>
              <p className="mono">High Risk Changes: {stats?.high_risk_count ?? 0}</p>
              <p className="mono">Obligation Shifts: {stats?.obligation_shift_count ?? 0}</p>
              <button className="secondary" onClick={exportPdf}>Generate Verified Report</button>
            </div>
          ) : (
            <p className="mono">Upload files to generate verification stats.</p>
          )}
        </Section>

        <Section title="High-Risk Changes">
          {compare ? (
            <div className="report-list">
              {compare.materiality?.length ? (
                compare.materiality.map((m, idx) => (
                  <div key={`${m.clause_id}-${idx}`} className="clause risk">
                    <h4>{m.category}</h4>
                    <span className="tag">{m.severity}</span>
                    <p className="mono">{m.rationale}</p>
                  </div>
                ))
              ) : (
                <p className="mono">No material changes flagged.</p>
              )}
            </div>
          ) : (
            <p className="mono">No high-risk changes detected yet.</p>
          )}
        </Section>

        <Section title="Modified Clauses">
          {compare ? (
            <div className="report-list">
              {compare.changes?.map((clause) => (
                <div key={clause.clause_id} className="clause" id={clause.clause_id}>
                  <h4>{clause.clause_id}</h4>
                  {clause.substitutions?.length ? (
                    clause.substitutions.slice(0, 3).map((s, idx) => (
                      <div key={idx}>
                        <p className="mono">Before: {s.before}</p>
                        <p className="mono">After: {s.after}</p>
                      </div>
                    ))
                  ) : (
                    <div>
                      <p className="mono">Before: {clause.before_text}</p>
                      <p className="mono">After: {clause.after_text}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="mono">No modified clauses yet.</p>
          )}
        </Section>

        <Section title="Integrity Scan">
          {integrity ? (
            <div className="report-list">
              {integrity.integrity_alerts?.length === 0 ? (
                <p className="mono">No integrity alerts detected.</p>
              ) : (
                integrity.integrity_alerts?.map((alert, idx) => (
                  <div key={`${alert.clause_id}-${idx}`} className="clause risk">
                    <h4>{alert.clause_id}</h4>
                    <p className="mono">{alert.alert_type}</p>
                    <p className="mono">{alert.rationale}</p>
                  </div>
                ))
              )}
            </div>
          ) : (
            <p className="mono">Run verification to see integrity risks.</p>
          )}
        </Section>

        <Section title="AI Summary">
          {aiSummary ? (
            <div className="report-list">
              {(aiSummary.summaries || []).map((sum, idx) => (
                <div key={idx} className="clause">
                  <h4>{sum.type}</h4>
                  {(sum.bullets || []).map((b, i) => (
                    <p key={i} className="mono">{b}</p>
                  ))}
                </div>
              ))}
              {(!aiSummary.summaries || aiSummary.summaries.length === 0) && (
                <p className="mono">No AI summary returned.</p>
              )}
            </div>
          ) : (
            <p className="mono">AI summary will appear after verification.</p>
          )}
        </Section>
      </div>
    </div>
  );
}
