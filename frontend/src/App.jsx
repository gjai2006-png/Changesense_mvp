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

  const runVerification = async () => {
    if (!versionA || !versionB) {
      setError("Please upload both Version A and Version B.");
      return;
    }
    setError(null);
    setLoading(true);
    setCompare(null);
    setIntegrity(null);

    const formData = new FormData();
    formData.append("version_a", versionA);
    formData.append("version_b", versionB);

    try {
      const compareRes = await fetch(`${API_BASE}/compare`, {
        method: "POST",
        body: formData
      });
      const compareJson = await compareRes.json();

      const integrityRes = await fetch(`${API_BASE}/scan-integrity`, {
        method: "POST",
        body: formData
      });
      const integrityJson = await integrityRes.json();

      setCompare(compareJson);
      setIntegrity(integrityJson);
    } catch (err) {
      setError("Verification failed. Check backend server.");
    } finally {
      setLoading(false);
    }
  };

  const exportPdf = () => {
    window.open(`${API_BASE}/report`, "_blank");
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
              <p className="mono">Modified Clauses: {compare.stats.modified_count}</p>
              <p className="mono">Added Clauses: {compare.stats.added_count}</p>
              <p className="mono">Deleted Clauses: {compare.stats.deleted_count}</p>
              <p className="mono">High Risk Changes: {compare.stats.high_risk_count}</p>
              <p className="mono">Obligation Shifts: {compare.stats.obligation_shift_count}</p>
              <button className="secondary" onClick={exportPdf}>Generate Verified Report</button>
            </div>
          ) : (
            <p className="mono">Upload files to generate verification stats.</p>
          )}
        </Section>

        <Section title="High-Risk Changes">
          {compare ? (
            <div className="report-list">
              {compare.risks
                .filter((r) => r.risk_tags.length)
                .map((risk) => (
                  <div key={risk.id} className="clause risk">
                    <h4>{risk.heading}</h4>
                    {risk.risk_tags.map((tag) => (
                      <span key={tag} className="tag">{tag}</span>
                    ))}
                  </div>
                ))}
            </div>
          ) : (
            <p className="mono">No high-risk changes detected yet.</p>
          )}
        </Section>

        <Section title="Modified Clauses">
          {compare ? (
            <div className="report-list">
              {compare.clauses.modified.map((clause) => (
                <div key={clause.id} className="clause" id={clause.id}>
                  <h4>{clause.heading}</h4>
                  <p className="mono">Before: {clause.before}</p>
                  <p className="mono">After: {clause.after}</p>
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
              {integrity.ghost_changes.length === 0 ? (
                <p className="mono">No ghost changes detected.</p>
              ) : (
                integrity.ghost_changes.map((clause) => (
                  <div key={clause.id} className="clause risk">
                    <h4>{clause.heading}</h4>
                    <p className="mono">{clause.reason}</p>
                  </div>
                ))
              )}
            </div>
          ) : (
            <p className="mono">Run verification to see integrity risks.</p>
          )}
        </Section>
      </div>
    </div>
  );
}
