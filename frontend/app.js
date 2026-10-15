(() => {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const byId = (id) => document.getElementById(id);
    const tabGenerate = byId("tab-generate");
    const tabVerify = byId("tab-verify");
    const secGenerate = byId("section-generate");
    const secVerify = byId("section-verify");
    const jobForm = byId("job-form");
    const dropzone = byId("dropzone");
    const inputFile = byId("input-file");
    const fileLabel = byId("file-label");
    const btnSubmit = byId("btn-submit");
    const submitMessage = byId("submit-message");
    const progressCard = byId("progress-card");
    const displayJobId = byId("display-job-id");
    const displayJobStatus = byId("display-job-status");
    const progressBar = byId("progress-bar");
    const progressTrack = byId("progress-track");
    const progressPercent = byId("progress-percent");
    const valTotal = byId("val-total");
    const valSuccess = byId("val-success");
    const valFailed = byId("val-failed");
    const tableBody = byId("table-body");
    const verifyForm = byId("verify-form");
    const inputVerifyId = byId("input-verify-id");
    const verifyResult = byId("verify-result");
    const btnVerify = byId("btn-verify");

    let pollTimer = null;
    let activeJobId = null;
    let polling = false;

    const terminalStatuses = new Set(["completed", "completed_with_errors", "failed"]);

    function switchTab(tab) {
      const showGenerate = tab === "generate";
      tabGenerate.classList.toggle("active", showGenerate);
      tabVerify.classList.toggle("active", !showGenerate);
      tabGenerate.setAttribute("aria-selected", String(showGenerate));
      tabVerify.setAttribute("aria-selected", String(!showGenerate));
      secGenerate.classList.toggle("active", showGenerate);
      secVerify.classList.toggle("active", !showGenerate);
    }
    tabGenerate.addEventListener("click", () => switchTab("generate"));
    tabVerify.addEventListener("click", () => switchTab("verify"));

    const inputDate = byId("input-date");
    if (inputDate && !inputDate.value) {
      const now = new Date();
      const localDate = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
        .toISOString().slice(0, 10);
      inputDate.value = localDate;
    }

    function getApiBase() {
      const raw = byId("input-api-url").value.trim();
      if (!raw) return window.location.origin;
      let parsed;
      try { parsed = new URL(raw); } catch { throw new Error("Enter a valid backend API URL."); }
      if (!["http:", "https:"].includes(parsed.protocol)) {
        throw new Error("The API URL must start with http:// or https://.");
      }
      return parsed.href.replace(/\/+$/, "");
    }

    function formatFile(file) {
      fileLabel.textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
      dropzone.classList.remove("invalid-file");
    }
    function acceptFile(file) {
      if (!file) return false;
      if (!file.name.toLowerCase().endsWith(".csv")) {
        showSubmitMessage("Please select a .csv file.");
        return false;
      }
      formatFile(file);
      showSubmitMessage("");
      return true;
    }
    function showSubmitMessage(message) {
      submitMessage.textContent = message || "";
    }

    dropzone.addEventListener("click", (event) => {
      if (event.target !== inputFile) inputFile.click();
    });
    dropzone.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        inputFile.click();
      }
    });
    inputFile.addEventListener("change", () => {
      if (inputFile.files.length) acceptFile(inputFile.files[0]);
    });
    ["dragenter", "dragover"].forEach((name) => dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragover");
    }));
    ["dragleave", "drop"].forEach((name) => dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragover");
    }));
    dropzone.addEventListener("drop", (event) => {
      const file = event.dataTransfer && event.dataTransfer.files[0];
      if (!file || !acceptFile(file)) return;
      try {
        const transfer = new DataTransfer();
        transfer.items.add(file);
        inputFile.files = transfer.files;
      } catch {
        showSubmitMessage("Your browser could not attach the dropped file. Please use Choose file instead.");
      }
    });

    function setSubmitState(disabled, label) {
      btnSubmit.disabled = disabled;
      btnSubmit.querySelector("span").textContent = label;
    }
    function setVerifyMessage(message, type = "error") {
      verifyResult.replaceChildren();
      verifyResult.className = `verify-result ${type === "success" ? "success-result" : "error-result"}`;
      verifyResult.classList.remove("hidden");
      const p = document.createElement("p");
      p.textContent = message;
      verifyResult.appendChild(p);
    }
    function makeCell(text, className) {
      const td = document.createElement("td");
      td.textContent = text == null ? "" : String(text);
      if (className) td.className = className;
      return td;
    }
    function makeStatus(status) {
      const span = document.createElement("span");
      const safeStatus = String(status || "unknown").toLowerCase().replace(/[^a-z0-9_-]/g, "");
      span.className = `status-badge status-${safeStatus}`;
      span.textContent = String(status || "unknown").replaceAll("_", " ");
      return span;
    }
    function safeApiLink(apiBase, path) {
      try {
        const url = new URL(path, `${apiBase}/`);
        const base = new URL(apiBase);
        if (url.origin !== base.origin || !["http:", "https:"].includes(url.protocol)) return null;
        return url.href;
      } catch { return null; }
    }
    function renderResults(results, apiBase) {
      tableBody.replaceChildren();
      if (!Array.isArray(results) || results.length === 0) {
        const tr = document.createElement("tr");
        const td = makeCell("No recipient results available yet.");
        td.colSpan = 4;
        td.className = "empty-state";
        tr.appendChild(td);
        tableBody.appendChild(tr);
        return;
      }
      results.forEach((result) => {
        const tr = document.createElement("tr");
        tr.appendChild(makeCell(result.row));
        tr.appendChild(makeCell(result.name || "—"));
        const statusCell = document.createElement("td");
        statusCell.appendChild(makeStatus(result.status));
        tr.appendChild(statusCell);
        const actionCell = document.createElement("td");
        if (result.download_url) {
          const href = safeApiLink(apiBase, result.download_url);
          if (href) {
            const link = document.createElement("a");
            link.className = "small-link";
            link.href = href;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = "Download PDF";
            actionCell.appendChild(link);
          } else {
            actionCell.textContent = "Download link unavailable";
          }
        } else if (result.error) {
          const error = document.createElement("span");
          error.className = "result-error";
          error.textContent = String(result.error);
          actionCell.appendChild(error);
        } else {
          actionCell.textContent = "—";
        }
        tr.appendChild(actionCell);
        tableBody.appendChild(tr);
      });
    }

    async function pollJobStatus(apiBase, apiKey, jobId) {
      if (pollTimer) clearInterval(pollTimer);
      activeJobId = jobId;
      polling = false;

      const updateUI = async () => {
        if (polling || activeJobId !== jobId) return;
        polling = true;
        try {
          const response = await fetch(`${apiBase}/jobs/${encodeURIComponent(jobId)}`, {
            headers: { "X-Api-Key": apiKey }
          });
          if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
              showSubmitMessage("The API rejected the key while checking job status. Check your credentials.");
            }
            return;
          }
          const data = await response.json();
          const status = String(data.status || "unknown").toLowerCase();
          displayJobStatus.className = `status-badge status-${status.replace(/[^a-z0-9_-]/g, "")}`;
          displayJobStatus.textContent = status.replaceAll("_", " ");
          valTotal.textContent = String(data.total ?? 0);
          valSuccess.textContent = String(data.success ?? 0);
          valFailed.textContent = String(data.failed ?? 0);

          const total = Number(data.total) || 0;
          const done = Number(data.done) || 0;
          const percent = total > 0 ? Math.max(0, Math.min(100, Math.round(done / total * 100))) : 0;
          progressBar.style.width = `${percent}%`;
          progressPercent.textContent = `${percent}%`;
          progressTrack.setAttribute("aria-valuenow", String(percent));
          renderResults(data.results, apiBase);

          if (terminalStatuses.has(status)) {
            clearInterval(pollTimer);
            pollTimer = null;
            activeJobId = null;
            setSubmitState(false, "Start new batch");
            showSubmitMessage(status === "failed" ? "The batch failed. Review the status and try again." :
              status === "completed_with_errors" ? "Batch finished with some errors. Review the recipient results." : "Batch completed successfully.");
          }
        } catch (error) {
          console.error("Polling error:", error);
        } finally {
          polling = false;
        }
      };

      await updateUI();
      if (activeJobId === jobId) pollTimer = setInterval(updateUI, 2500);
    }

    jobForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      showSubmitMessage("");
      if (!inputFile.files || !inputFile.files[0]) {
        showSubmitMessage("Choose a recipient CSV file before submitting.");
        return;
      }
      let apiBase;
      try { apiBase = getApiBase(); } catch (error) {
        showSubmitMessage(error.message);
        return;
      }
      const apiKey = byId("input-api-key").value.trim();
      if (!apiKey) {
        showSubmitMessage("Enter your API key.");
        return;
      }

      const formData = new FormData();
      formData.append("title", byId("input-title").value.trim());
      formData.append("course", byId("input-course").value.trim());
      formData.append("org", byId("input-org").value.trim());
      formData.append("issue_date", inputDate.value);
      formData.append("recipients_file", inputFile.files[0]);

      setSubmitState(true, "Uploading and submitting…");
      try {
        const response = await fetch(`${apiBase}/jobs`, {
          method: "POST",
          headers: { "X-Api-Key": apiKey },
          body: formData
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          showSubmitMessage(`Submission failed (${response.status}): ${data.detail || "Please check the API settings and try again."}`);
          setSubmitState(false, "Start batch generation");
          return;
        }
        if (!data.job_id) throw new Error("The API response did not include a job ID.");
        displayJobId.textContent = String(data.job_id);
        progressCard.classList.remove("hidden");
        progressCard.scrollIntoView({ behavior: "smooth", block: "start" });
        setSubmitState(true, "Batch submitted");
        showSubmitMessage("Batch submitted. This page will update as processing continues.");
        pollJobStatus(apiBase, apiKey, String(data.job_id));
      } catch (error) {
        showSubmitMessage(`Network error: ${error.message}. Check the API URL, CORS settings, and network connection.`);
        setSubmitState(false, "Start batch generation");
      }
    });

    verifyForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const certId = inputVerifyId.value.trim();
      if (!certId) return;
      let apiBase;
      try { apiBase = getApiBase(); } catch (error) {
        setVerifyMessage(error.message);
        return;
      }
      btnVerify.disabled = true;
      btnVerify.textContent = "Verifying…";
      verifyResult.classList.remove("hidden");
      verifyResult.className = "verify-result";
      verifyResult.textContent = "Checking certificate records…";
      try {
        const response = await fetch(`${apiBase}/certificates/${encodeURIComponent(certId)}/verify`);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          setVerifyMessage(data.detail || "Certificate not found or not valid.");
          return;
        }
        verifyResult.replaceChildren();
        verifyResult.className = "verify-result success-result";
        const heading = document.createElement("h3");
        heading.textContent = "Certificate verified";
        verifyResult.appendChild(heading);
        const fields = [
          ["Recipient", data.recipient_name],
          ["Course / program", data.course],
          ["Issuing organization", data.org],
          ["Issue date", data.issue_date],
          ["Certificate ID", data.certificate_id]
        ];
        fields.forEach(([label, value]) => {
          const p = document.createElement("p");
          const strong = document.createElement("strong");
          strong.textContent = `${label}: `;
          p.append(strong, document.createTextNode(value == null ? "—" : String(value)));
          verifyResult.appendChild(p);
        });
        const downloadUrl = safeApiLink(apiBase, `/certificates/${encodeURIComponent(data.certificate_id)}`);
        if (downloadUrl) {
          const row = document.createElement("div");
          row.className = "download-row";
          const link = document.createElement("a");
          link.className = "small-link";
          link.href = downloadUrl;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = "Download verified PDF";
          row.appendChild(link);
          verifyResult.appendChild(row);
        }
      } catch (error) {
        setVerifyMessage(`Network error: ${error.message}. Check the API URL and CORS settings.`);
      } finally {
        btnVerify.disabled = false;
        btnVerify.textContent = "Verify certificate";
      }
    });

    window.addEventListener("beforeunload", () => {
      if (pollTimer) clearInterval(pollTimer);
    });
  });
})();
