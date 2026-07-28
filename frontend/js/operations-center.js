(function () {
  "use strict";

  const state = {
    rows: [],
    filtered: [],
    worker: {}
  };

  const byId = (id) => document.getElementById(id);

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function normalizeStatus(value) {
    return String(value || "unknown").toLowerCase();
  }

  function normalizeType(value) {
    return String(value || "").toLowerCase();
  }

  function evidenceTime(row) {
    return (
      row.completed_at ||
      row.started_at ||
      row.created_at ||
      row.updated_at
    );
  }

  function formatTime(value) {
    if (!value) return "Unknown time";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return String(value);
    }

    return date.toLocaleString();
  }

  function cardClass(value) {
    const current = normalizeStatus(value);

    if (
      ["failed", "error", "rollback-required"].includes(current)
    ) {
      return "failed";
    }

    if (
      [
        "warning",
        "partial",
        "pending",
        "queued",
        "running"
      ].includes(current)
    ) {
      return "warning";
    }

    if (
      [
        "passed",
        "completed",
        "succeeded",
        "rolled-back"
      ].includes(current)
    ) {
      return "success";
    }

    return "";
  }

  function isFailure(row) {
    return [
      "failed",
      "error",
      "rollback-required"
    ].includes(normalizeStatus(row.status));
  }

  function isPending(row) {
    return [
      "pending",
      "queued",
      "running"
    ].includes(normalizeStatus(row.status));
  }

  function isSuccess(row) {
    return [
      "passed",
      "completed",
      "succeeded",
      "rolled-back"
    ].includes(normalizeStatus(row.status));
  }

  function setChipState(chipId, stateName) {
    const chip = byId(chipId);

    if (!chip) return;

    chip.classList.remove(
      "healthy",
      "warning",
      "critical",
      "unknown"
    );

    chip.classList.add(stateName);
  }

  function setChipText(valueId, metaId, value, meta) {
    const valueNode = byId(valueId);
    const metaNode = byId(metaId);

    if (valueNode) valueNode.textContent = value;
    if (metaNode) metaNode.textContent = meta;
  }

  function updateLiveStatusStrip() {
    const rows = state.rows;

    const executions = rows.filter(
      (row) => normalizeType(row.operation_type) === "execution"
    );

    const verifications = rows.filter(
      (row) => normalizeType(row.operation_type) === "verification"
    );

    const rollbacks = rows.filter(
      (row) => normalizeType(row.operation_type) === "rollback"
    );

    const recoveries = rows.filter((row) => {
      const type = normalizeType(row.operation_type);
      const name = String(row.operation_name || "").toLowerCase();
      const summary = String(row.summary || "").toLowerCase();

      return (
        type === "recovery" ||
        name.includes("recovery") ||
        summary.includes("recovery") ||
        (
          type === "rollback" &&
          isSuccess(row)
        )
      );
    });

    const executionFailures = executions.filter(isFailure).length;
    const executionPending = executions.filter(isPending).length;
    const executionSuccesses = executions.filter(isSuccess).length;

    if (!executions.length) {
      setChipState("executionStatusChip", "unknown");

      setChipText(
        "executionStatusValue",
        "executionStatusMeta",
        "No activity",
        "No execution evidence"
      );
    } else if (executionFailures) {
      setChipState("executionStatusChip", "critical");

      setChipText(
        "executionStatusValue",
        "executionStatusMeta",
        `${executionFailures} failed`,
        `${executionSuccesses} completed · ${executionPending} active`
      );
    } else if (executionPending) {
      setChipState("executionStatusChip", "warning");

      setChipText(
        "executionStatusValue",
        "executionStatusMeta",
        `${executionPending} active`,
        `${executionSuccesses} completed`
      );
    } else {
      setChipState("executionStatusChip", "healthy");

      setChipText(
        "executionStatusValue",
        "executionStatusMeta",
        `${executionSuccesses} completed`,
        "No failed executions"
      );
    }

    const verificationFailures = verifications.filter(isFailure).length;
    const verificationPending = verifications.filter(isPending).length;
    const verificationSuccesses = verifications.filter(isSuccess).length;

    if (!verifications.length) {
      setChipState("verificationStatusChip", "unknown");

      setChipText(
        "verificationStatusValue",
        "verificationStatusMeta",
        "No activity",
        "No verification evidence"
      );
    } else if (verificationFailures) {
      setChipState("verificationStatusChip", "critical");

      setChipText(
        "verificationStatusValue",
        "verificationStatusMeta",
        `${verificationFailures} failed`,
        `${verificationSuccesses} passed · ${verificationPending} pending`
      );
    } else if (verificationPending) {
      setChipState("verificationStatusChip", "warning");

      setChipText(
        "verificationStatusValue",
        "verificationStatusMeta",
        `${verificationPending} pending`,
        `${verificationSuccesses} passed`
      );
    } else {
      setChipState("verificationStatusChip", "healthy");

      setChipText(
        "verificationStatusValue",
        "verificationStatusMeta",
        `${verificationSuccesses} passed`,
        "No failed verifications"
      );
    }

    const rollbackFailures = rollbacks.filter(isFailure).length;
    const rollbackPending = rollbacks.filter(isPending).length;
    const rollbackSuccesses = rollbacks.filter(isSuccess).length;

    if (!rollbacks.length) {
      setChipState("rollbackStatusChip", "healthy");

      setChipText(
        "rollbackStatusValue",
        "rollbackStatusMeta",
        "None required",
        "No rollback records"
      );
    } else if (rollbackFailures) {
      setChipState("rollbackStatusChip", "critical");

      setChipText(
        "rollbackStatusValue",
        "rollbackStatusMeta",
        `${rollbackFailures} failed`,
        `${rollbackSuccesses} completed · ${rollbackPending} active`
      );
    } else if (rollbackPending) {
      setChipState("rollbackStatusChip", "warning");

      setChipText(
        "rollbackStatusValue",
        "rollbackStatusMeta",
        `${rollbackPending} active`,
        `${rollbackSuccesses} completed`
      );
    } else {
      setChipState("rollbackStatusChip", "healthy");

      setChipText(
        "rollbackStatusValue",
        "rollbackStatusMeta",
        `${rollbackSuccesses} completed`,
        "Rollback evidence available"
      );
    }

    const recoveryFailures = recoveries.filter(isFailure).length;
    const recoverySuccesses = recoveries.filter(isSuccess).length;

    if (!recoveries.length) {
      setChipState("recoveryStatusChip", "healthy");

      setChipText(
        "recoveryStatusValue",
        "recoveryStatusMeta",
        "Stable",
        "No recovery actions required"
      );
    } else if (recoveryFailures) {
      setChipState("recoveryStatusChip", "critical");

      setChipText(
        "recoveryStatusValue",
        "recoveryStatusMeta",
        `${recoveryFailures} failed`,
        `${recoverySuccesses} successful`
      );
    } else {
      setChipState("recoveryStatusChip", "healthy");

      setChipText(
        "recoveryStatusValue",
        "recoveryStatusMeta",
        `${recoverySuccesses} successful`,
        "Recovery evidence recorded"
      );
    }

    const worker = state.worker || {};

    if (worker.last_error) {
      setChipState("evidenceStatusChip", "critical");

      setChipText(
        "evidenceStatusValue",
        "evidenceStatusMeta",
        `${rows.length} records`,
        "Evidence worker error"
      );
    } else if (worker.last_success_at) {
      setChipState("evidenceStatusChip", "healthy");

      setChipText(
        "evidenceStatusValue",
        "evidenceStatusMeta",
        `${rows.length} records`,
        `Updated ${formatTime(worker.last_success_at)}`
      );
    } else {
      setChipState("evidenceStatusChip", "warning");

      setChipText(
        "evidenceStatusValue",
        "evidenceStatusMeta",
        `${rows.length} records`,
        "Evidence worker online"
      );
    }
  }

  function updateMetrics() {
    const rows = state.rows;

    byId("metricRecent").textContent = rows.length;

    byId("metricFailed").textContent =
      rows.filter(isFailure).length;

    byId("metricPending").textContent =
      rows.filter(isPending).length;

    byId("metricRollbacks").textContent =
      rows.filter(
        (row) =>
          normalizeType(row.operation_type) === "rollback"
      ).length;

    updateLiveStatusStrip();
  }

  function filterRows() {
    const query =
      byId("searchInput").value.toLowerCase();

    const selectedStatus =
      byId("statusFilter").value;

    const selectedType =
      byId("typeFilter").value;

    const selectedAsset =
      byId("assetFilter").value.toLowerCase();

    state.filtered = state.rows.filter((row) => {
      const haystack = [
        row.operation_name,
        row.operation_type,
        row.summary,
        row.asset_id,
        row.correlation_id,
        row.source_type
      ]
        .join(" ")
        .toLowerCase();

      return (
        (!query || haystack.includes(query)) &&
        (
          !selectedStatus ||
          normalizeStatus(row.status) === selectedStatus
        ) &&
        (
          !selectedType ||
          normalizeType(row.operation_type) === selectedType
        ) &&
        (
          !selectedAsset ||
          String(row.asset_id || "")
            .toLowerCase()
            .includes(selectedAsset)
        )
      );
    });

    renderTimeline();
  }

  function renderTimeline() {
    updateMetrics();

    byId("resultSummary").textContent =
      `${state.filtered.length} of ${state.rows.length} evidence records`;

    byId("emptyState").hidden =
      Boolean(state.filtered.length);

    byId("opsTimeline").innerHTML = state.filtered
      .map((row) => {
        const operationName =
          row.operation_name ||
          row.operation_type ||
          "Operation";

        const summary =
          row.summary ||
          "Operational evidence";

        const asset =
          row.asset_id ||
          "No asset";

        const operationType =
          row.operation_type ||
          row.source_type ||
          "operation";

        return `
          <button
            class="op-card ${cardClass(row.status)}"
            data-id="${escapeHtml(row.evidence_id)}"
          >
            <div class="card-top">
              <div>
                <strong>
                  ${escapeHtml(operationName)}
                </strong>

                <p class="summary">
                  ${escapeHtml(summary)}
                </p>
              </div>

              <span class="badge">
                ${escapeHtml(row.status || "unknown")}
              </span>
            </div>

            <p class="meta">
              ${escapeHtml(formatTime(evidenceTime(row)))}
              ·
              ${escapeHtml(asset)}
              ·
              ${escapeHtml(operationType)}
            </p>
          </button>
        `;
      })
      .join("");

    document
      .querySelectorAll("[data-id]")
      .forEach((button) => {
        button.onclick = () =>
          openDetail(button.dataset.id);
      });
  }

  async function openDetail(id) {
    byId("opsDrawer").classList.add("open");
    byId("opsDrawer").setAttribute("aria-hidden", "false");

    byId("drawerBody").innerHTML =
      '<div class="detail">Loading…</div>';

    try {
      const payload = await NexusEvidence.get(id);
      const evidence = payload.evidence || {};

      byId("drawerTitle").textContent =
        evidence.operation_name ||
        "Evidence detail";

      const detailRow = (key, value) => `
        <dt>${escapeHtml(key)}</dt>
        <dd>${escapeHtml(value ?? "—")}</dd>
      `;

      byId("drawerBody").innerHTML = `
        <section class="detail">
          <h3>
            ${escapeHtml(evidence.summary || "Operation")}
          </h3>

          <span class="badge">
            ${escapeHtml(evidence.status || "unknown")}
          </span>
        </section>

        <section class="detail">
          <dl class="detail-grid">
            ${detailRow("Evidence ID", evidence.evidence_id)}
            ${detailRow("Type", evidence.operation_type)}
            ${detailRow("Asset", evidence.asset_id)}
            ${detailRow("Service", evidence.service_id)}
            ${detailRow("Correlation", evidence.correlation_id)}
            ${detailRow("Score", evidence.score)}
            ${detailRow("Started", formatTime(evidence.started_at))}
            ${detailRow("Completed", formatTime(evidence.completed_at))}
          </dl>
        </section>

        <section class="detail">
          <h3>Captured evidence</h3>

          <pre>${escapeHtml(
            JSON.stringify(evidence.evidence || {}, null, 2)
          )}</pre>
        </section>
      `;
    } catch (error) {
      byId("drawerBody").innerHTML = `
        <div class="detail">
          ${escapeHtml(error.message)}
        </div>
      `;
    }
  }

  async function loadOperations() {
    const refreshButton = byId("refreshButton");
    refreshButton.disabled = true;

    try {
      const timelinePayload =
        await NexusEvidence.timeline({ limit: 250 });

      state.rows =
        timelinePayload.timeline ||
        timelinePayload.evidence ||
        [];

      const workerPayload =
        await NexusEvidence.status();

      state.worker =
        workerPayload.worker ||
        {};

      if (state.worker.last_error) {
        byId("workerState").textContent =
          "Evidence worker error";
      } else if (state.worker.last_success_at) {
        byId("workerState").textContent =
          `Worker healthy · ${formatTime(
            state.worker.last_success_at
          )}`;
      } else {
        byId("workerState").textContent =
          "Evidence worker online";
      }

      filterRows();
    } catch (error) {
      byId("opsTimeline").innerHTML = `
        <div class="detail">
          ${escapeHtml(error.message)}
        </div>
      `;

      setChipState("evidenceStatusChip", "critical");

      setChipText(
        "evidenceStatusValue",
        "evidenceStatusMeta",
        "Unavailable",
        "Could not load evidence"
      );
    } finally {
      refreshButton.disabled = false;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    ["searchInput", "assetFilter"].forEach((id) => {
      byId(id).addEventListener("input", filterRows);
    });

    ["statusFilter", "typeFilter"].forEach((id) => {
      byId(id).addEventListener("change", filterRows);
    });

    byId("refreshButton").onclick = loadOperations;

    byId("drawerClose").onclick = () => {
      byId("opsDrawer").classList.remove("open");
      byId("opsDrawer").setAttribute("aria-hidden", "true");
    };

    loadOperations();

    window.setInterval(loadOperations, 30000);
  });
})();
