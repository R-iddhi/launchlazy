import { useState } from "react";
import axios from "axios";

const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";


function parseAIAnalysis(text = "") {
  const headings = [
    "OVERALL ASSESSMENT:",
    "PRIORITY:",
    "WHY THIS SCORE:",
    "REMAINING MANUAL CHECKS:",
    "NEXT ACTIONS:",
  ];

  const result = {
    status: "",
    assessment: "",
    priority: "",
    why: "",
    manualChecks: [],
    nextActions: [],
  };

  if (!text) return result;

  const statusMatch = text.match(
    /AUTOMATED CHECK STATUS:\s*([\s\S]*?)(?=OVERALL ASSESSMENT:|$)/
  );

  if (statusMatch) {
    result.status = statusMatch[1].trim();
  }

  const getSection = (start, end) => {
    const startIndex = text.indexOf(start);

    if (startIndex === -1) {
      return "";
    }

    const contentStart =
      startIndex + start.length;

    let endIndex = text.length;

    if (end) {
      const foundEnd =
        text.indexOf(
          end,
          contentStart
        );

      if (foundEnd !== -1) {
        endIndex = foundEnd;
      }
    }

    return text
      .slice(
        contentStart,
        endIndex
      )
      .trim();
  };

  result.assessment =
    getSection(
      headings[0],
      headings[1]
    );

  result.priority =
    getSection(
      headings[1],
      headings[2]
    );

  result.why =
    getSection(
      headings[2],
      headings[3]
    );

  const manualText =
    getSection(
      headings[3],
      headings[4]
    );

  result.manualChecks =
    manualText
      .split("\n")
      .map((item) =>
        item
          .replace(
            /^[-•]\s*/,
            ""
          )
          .trim()
      )
      .filter(Boolean);

  const actionText =
    getSection(
      headings[4],
      null
    );

  result.nextActions =
    actionText
      .split("\n")
      .map((item) =>
        item
          .replace(
            /^\d+[.)]\s*/,
            ""
          )
          .trim()
      )
      .filter(Boolean);

  return result;
}


function App() {
  const [
    projectPath,
    setProjectPath,
  ] = useState("");

  const [
    result,
    setResult,
  ] = useState(null);

  const [
    error,
    setError,
  ] = useState("");

  const [
    loading,
    setLoading,
  ] = useState(false);

  const [
    aiLoading,
    setAiLoading,
  ] = useState(false);


  const inspectProject =
    async () => {
      if (!projectPath.trim()) {
        setError(
          "Please enter a project folder path."
        );

        return;
      }

      try {
        setError("");
        setResult(null);

        setLoading(true);
        setAiLoading(false);

        const response =
          await axios.post(
            `${API_URL}/inspect`,
            {
              path: projectPath,
            }
          );

        const scanResult =
          response.data;

        setResult({
          ...scanResult,
          ai_analysis: "",
        });

        setLoading(false);
        setAiLoading(true);

        try {
          const aiResponse =
            await axios.post(
              `${API_URL}/analyze-ai`,
              {
                project_name:
                  scanResult.project_name,

                project_types:
                  scanResult.project_types,

                components:
                  scanResult.components,

                important_files:
                  scanResult.important_files,

                launch_readiness_score:
                  scanResult.launch_readiness_score,

                priority:
                  scanResult.priority,

                risks:
                  scanResult.risks,
              }
            );

          setResult(
            (current) => ({
              ...current,

              ai_analysis:
                aiResponse.data
                  .ai_analysis,
            })
          );

        } catch (aiError) {
          setResult(
            (current) => ({
              ...current,

              ai_analysis:
                "AI analysis unavailable. Scanner results are still valid.",
            })
          );

        } finally {
          setAiLoading(false);
        }

      } catch (err) {
        setError(
          err.response?.data
            ?.detail ||
            "Could not inspect the project folder."
        );

        setLoading(false);
        setAiLoading(false);
      }
    };


  const getScoreLabel =
    (score) => {
      if (score >= 90) {
        return "Strong";
      }

      if (score >= 70) {
        return "Needs Attention";
      }

      return "High Risk";
    };


  const downloadReport =
    () => {
      if (!result) {
        return;
      }

      const componentText =
        result.components?.length >
        0
          ? result.components
              .map(
                (component) =>
                  `- ${component.path}: ${component.types.join(
                    ", "
                  )}`
              )
              .join("\n")
          : "- No components detected";

      const riskText =
        result.risks?.length >
        0
          ? result.risks
              .map(
                (
                  risk,
                  index
                ) => {
                  const files =
                    risk.files?.length >
                    0
                      ? `\n  Files: ${risk.files.join(
                          ", "
                        )}`
                      : "";

                  return `${index + 1}. [${risk.severity.toUpperCase()}] ${
                    risk.title
                  }
Reason: ${risk.reason}
Fix: ${risk.fix}${files}`;
                }
              )
              .join("\n\n")
          : "No automated launch risks detected.";

      const fileText =
        result.important_files
          ?.length > 0
          ? result.important_files
              .map(
                (file) =>
                  `- ${file}`
              )
              .join("\n")
          : "- No important files detected";

      const report = `# LaunchLazy Launch Readiness Report

## Project

Name: ${result.project_name}
Path: ${result.project_path}

## Readiness

Score: ${result.launch_readiness_score}/100
Priority: ${result.priority}
Automated risks found: ${result.risks_found}

Important:
This score represents only the currently implemented LaunchLazy automated checks.
It is not a guarantee of production readiness, security, or correctness.

## Detected Technology Stack

${
  result.project_types
    ?.map(
      (type) =>
        `- ${type}`
    )
    .join("\n")
}

## Detected Components

${componentText}

## Automated Launch Risks

${riskText}

## AI Launch Assessment

${
  result.ai_analysis ||
  "AI assessment was not generated."
}

## Important Project Files

${fileText}

---

Generated by LaunchLazy
Local reasoning model: Qwen 2.5
`;

      const blob =
        new Blob(
          [report],
          {
            type:
              "text/markdown;charset=utf-8",
          }
        );

      const url =
        URL.createObjectURL(
          blob
        );

      const link =
        document.createElement(
          "a"
        );

      link.href = url;

      link.download =
        `${result.project_name}-launchlazy-report.md`;

      document.body.appendChild(
        link
      );

      link.click();

      document.body.removeChild(
        link
      );

      URL.revokeObjectURL(
        url
      );
    };


  const ai =
    result?.ai_analysis
      ? parseAIAnalysis(
          result.ai_analysis
        )
      : null;


  return (
    <div className="app-shell">

      <header className="topbar">

        <div>
          <div className="brand">
            LaunchLazy
          </div>

          <div className="subtitle">
            AI-assisted launch readiness auditor
          </div>
        </div>

        <div className="local-ai-badge">

          <span className="status-dot" />

          Local AI · Qwen 2.5

        </div>

      </header>


      <main className="page">

        <section className="hero">

          <p className="eyebrow">
            PROJECT INSPECTION
          </p>

          <h1>
            Find launch risks before
            your project leaves
            localhost.
          </h1>

          <p className="hero-copy">
            Inspect your software
            architecture,
            configuration and
            launch readiness using
            deterministic checks
            and grounded local AI
            reasoning.
          </p>


          <div className="scanner">

            <input
              value={projectPath}
              onChange={(e) =>
                setProjectPath(
                  e.target.value
                )
              }
              placeholder="C:\Users\...\my-project"
              onKeyDown={(e) => {
                if (
                  e.key ===
                  "Enter"
                ) {
                  inspectProject();
                }
              }}
            />

            <button
              onClick={
                inspectProject
              }
              disabled={
                loading ||
                !projectPath.trim()
              }
            >
              {loading
                ? "Scanning Project..."
                : "Inspect Project"}
            </button>

          </div>


          {loading && (
            <div className="scan-loading-message">
              Scanning project
              structure and running
              automated checks...
            </div>
          )}


          {error && (
            <div className="error-box">
              {error}
            </div>
          )}

        </section>


        {result && (
          <>

            <section className="result-toolbar">

              <div>

                <p className="eyebrow">
                  ANALYSIS COMPLETE
                </p>

                <p className="toolbar-copy">
                  Automated scanner
                  results are ready.
                  Review the findings
                  while local AI prepares
                  the assessment.
                </p>

              </div>


              <button
                className="download-button"
                onClick={
                  downloadReport
                }
              >
                ↓ Download Report
              </button>

            </section>


            <section className="summary-grid">

              <div className="card project-card">

                <p className="card-label">
                  PROJECT
                </p>

                <h2>
                  {
                    result.project_name
                  }
                </h2>

                <p className="muted path-text">
                  {
                    result.project_path
                  }
                </p>


                <div className="stack-list">

                  {result.project_types
                    ?.map(
                      (type) => (
                        <span
                          className="stack-badge"
                          key={
                            type
                          }
                        >
                          {
                            type
                          }
                        </span>
                      )
                    )}

                </div>

              </div>


              <div className="card score-card">

                <p className="card-label">
                  READINESS SCORE
                </p>

                <div className="score-number">

                  {
                    result.launch_readiness_score
                  }

                  <span>
                    /100
                  </span>

                </div>

                <p className="score-label">

                  {getScoreLabel(
                    result.launch_readiness_score
                  )}

                </p>

              </div>


              <div className="card priority-card">

                <p className="card-label">
                  ACTION PRIORITY
                </p>

                <div
                  className={`priority-badge priority-${result.priority?.toLowerCase()}`}
                >
                  {
                    result.priority
                  }
                </div>


                <p className="muted">

                  {
                    result.risks_found
                  }{" "}

                  automated risk

                  {
                    result.risks_found ===
                    1
                      ? ""
                      : "s"
                  }{" "}

                  detected

                </p>

              </div>

            </section>


            <section className="section">

              <div className="section-heading">

                <div>

                  <p className="eyebrow">
                    ARCHITECTURE MAP
                  </p>

                  <h2>
                    Detected Components
                  </h2>

                </div>

              </div>


              <div className="component-flow">

                {result.components?.map(
                  (
                    component,
                    index
                  ) => (

                    <div
                      className="component-wrapper"
                      key={`${component.path}-${index}`}
                    >

                      <div className="card component-card">

                        <div className="component-icon">

                          {
                            index === 0
                              ? "UI"
                              : "API"
                          }

                        </div>


                        <div>

                          <p className="component-number">

                            COMPONENT{" "}

                            {String(
                              index +
                                1
                            ).padStart(
                              2,
                              "0"
                            )}

                          </p>


                          <h3>

                            {
                              component.path ===
                              "."
                                ? "Project Root"
                                : component.path
                            }

                          </h3>


                          <div className="stack-list">

                            {component.types?.map(
                              (
                                type
                              ) => (

                                <span
                                  className="stack-badge"
                                  key={
                                    type
                                  }
                                >
                                  {
                                    type
                                  }
                                </span>

                              )
                            )}

                          </div>

                        </div>

                      </div>


                      {index <
                        result.components
                          .length -
                          1 && (

                        <div className="flow-arrow">
                          →
                        </div>

                      )}

                    </div>

                  )
                )}

              </div>

            </section>


            <section className="section">

              <div className="section-heading">

                <div>

                  <p className="eyebrow">
                    AUTOMATED CHECKS
                  </p>

                  <h2>
                    Launch Risks
                  </h2>

                </div>


                <span className="risk-count">

                  {
                    result.risks_found
                  }{" "}

                  found

                </span>

              </div>


              {result.risks?.length >
              0 ? (

                <div className="risk-list">

                  {result.risks.map(
                    (
                      risk,
                      index
                    ) => (

                      <div
                        className={`card risk-card risk-${risk.severity}`}
                        key={
                          index
                        }
                      >

                        <div className="risk-top">

                          <span
                            className={`severity severity-${risk.severity}`}
                          >
                            {
                              risk.severity
                            }
                          </span>

                          <span className="risk-number">

                            #

                            {String(
                              index +
                                1
                            ).padStart(
                              2,
                              "0"
                            )}

                          </span>

                        </div>


                        <h3>
                          {
                            risk.title
                          }
                        </h3>


                        <p>
                          {
                            risk.reason
                          }
                        </p>


                        <div className="fix-box">

                          <span className="fix-label">
                            RECOMMENDED FIX
                          </span>

                          <p>
                            {
                              risk.fix
                            }
                          </p>

                        </div>


                        {risk.files &&
                          risk.files
                            .length >
                            0 && (

                            <div className="file-list">

                              {risk.files.map(
                                (
                                  file
                                ) => (

                                  <code
                                    key={
                                      file
                                    }
                                  >
                                    {
                                      file
                                    }
                                  </code>

                                )
                              )}

                            </div>

                          )}

                      </div>

                    )
                  )}

                </div>

              ) : (

                <div className="card success-card">

                  <div className="success-icon">
                    ✓
                  </div>

                  <div>

                    <h3>
                      Automated checks passed
                    </h3>

                    <p>
                      No risks were found
                      by the currently
                      implemented scanner.
                      Manual verification
                      is still required.
                    </p>

                  </div>

                </div>

              )}

            </section>


            <section className="section ai-section">

              <div className="section-heading">

                <div>

                  <p className="eyebrow">
                    LOCAL AI REVIEW
                  </p>

                  <h2>
                    AI Launch Intelligence
                  </h2>

                </div>


                <div className="ai-model-tag">
                  Qwen 2.5 · Local
                </div>

              </div>


              <div className="ai-status-banner">

                <div className="ai-status-icon">
                  AI
                </div>

                <div>

                  <strong>
                    Evidence-grounded review
                  </strong>

                  <p>
                    Qwen receives verified
                    scanner findings instead
                    of inspecting your project
                    blindly.
                  </p>

                </div>

              </div>


              {aiLoading ? (

                <div className="ai-loading-state">

                  <div className="ai-loading-dot" />

                  <div>

                    <strong>
                      Generating AI assessment...
                    </strong>

                    <p>
                      Scanner results are ready.
                      Qwen is now reviewing the
                      verified findings and preparing
                      the next actions.
                    </p>

                  </div>

                </div>

              ) : result.ai_analysis ? (

                <div className="ai-dashboard">

                  <div className="ai-card-main">

                    <p className="ai-label">
                      OVERALL ASSESSMENT
                    </p>

                    <h3>
                      Project Launch Review
                    </h3>

                    <p>
                      {
                        ai?.assessment ||
                        result.ai_analysis
                      }
                    </p>

                  </div>


                  <div className="ai-mini-grid">

                    <div className="ai-mini-card">

                      <p className="ai-label">
                        PRIORITY
                      </p>

                      <div
                        className={`ai-priority priority-${result.priority?.toLowerCase()}`}
                      >
                        {
                          ai?.priority ||
                          result.priority
                        }
                      </div>

                    </div>


                    <div className="ai-mini-card">

                      <p className="ai-label">
                        WHY THIS SCORE
                      </p>

                      <p>
                        {
                          ai?.why ||
                          "Score explanation unavailable."
                        }
                      </p>

                    </div>

                  </div>


                  <div className="ai-two-column">

                    <div className="ai-check-panel">

                      <p className="ai-label">
                        MANUAL VERIFICATION
                      </p>


                      <div className="check-list">

                        {ai?.manualChecks
                          ?.length >
                        0 ? (

                          ai.manualChecks.map(
                            (
                              check,
                              index
                            ) => (

                              <div
                                className="check-item"
                                key={
                                  index
                                }
                              >

                                <span className="check-circle">
                                  ○
                                </span>

                                <span>
                                  {
                                    check
                                  }
                                </span>

                              </div>

                            )
                          )

                        ) : (

                          <div className="check-item">

                            <span className="check-circle">
                              ○
                            </span>

                            <span>
                              Manual checks
                              unavailable.
                            </span>

                          </div>

                        )}

                      </div>

                    </div>


                    <div className="ai-action-panel">

                      <p className="ai-label">
                        RECOMMENDED ACTION PLAN
                      </p>


                      <div className="action-list">

                        {ai?.nextActions
                          ?.length >
                        0 ? (

                          ai.nextActions.map(
                            (
                              action,
                              index
                            ) => (

                              <div
                                className="action-item"
                                key={
                                  index
                                }
                              >

                                <div className="action-number">

                                  {
                                    index +
                                    1
                                  }

                                </div>

                                <span>
                                  {
                                    action
                                  }
                                </span>

                              </div>

                            )
                          )

                        ) : (

                          <div className="action-item">

                            <div className="action-number">
                              1
                            </div>

                            <span>
                              Review the detected
                              risks above.
                            </span>

                          </div>

                        )}

                      </div>

                    </div>

                  </div>

                </div>

              ) : (

                <div className="ai-loading-state">

                  <div>

                    <strong>
                      AI assessment unavailable
                    </strong>

                    <p>
                      The deterministic scanner
                      results above are still valid.
                    </p>

                  </div>

                </div>

              )}

            </section>


            <section className="section">

              <div className="section-heading">

                <div>

                  <p className="eyebrow">
                    PROJECT EVIDENCE
                  </p>

                  <h2>
                    Files Used in Analysis
                  </h2>

                </div>

              </div>


              <div className="card file-card">

                {result.important_files
                  ?.map(
                    (file) => (

                      <div
                        className="file-row"
                        key={
                          file
                        }
                      >

                        <span className="file-icon">
                          ◇
                        </span>

                        <code>
                          {
                            file
                          }
                        </code>

                      </div>

                    )
                  )}

              </div>

            </section>

          </>
        )}

      </main>

    </div>
  );
}

export default App;