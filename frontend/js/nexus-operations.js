(function () {
  "use strict";

  class NexusOperationError extends Error {
    constructor(message, details = null) {
      super(message);
      this.name = "NexusOperationError";
      this.details = details;
    }
  }

  async function parseResponse(response) {
    const contentType =
      response.headers.get("content-type") || "";

    let payload;

    if (contentType.includes("application/json")) {
      payload = await response.json();
    } else {
      payload = {
        error: await response.text(),
      };
    }

    if (!response.ok) {
      throw new NexusOperationError(
        payload.error ||
          payload.message ||
          `Operation request failed with HTTP ${response.status}.`,
        payload
      );
    }

    return payload;
  }

  async function list() {
    const response = await fetch("/api/operations", {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
    });

    return parseResponse(response);
  }

  async function run(action, target = {}) {
    if (!action || typeof action !== "string") {
      throw new NexusOperationError(
        "A valid operation action is required."
      );
    }

    if (
      target === null ||
      typeof target !== "object" ||
      Array.isArray(target)
    ) {
      throw new NexusOperationError(
        "Operation target must be an object."
      );
    }

    const response = await fetch("/api/operations/run", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        action,
        target,
      }),
    });

    return parseResponse(response);
  }

  function statusLabel(status) {
    switch (String(status || "").toLowerCase()) {
      case "pass":
        return "Passed";
      case "warn":
        return "Completed with warnings";
      case "fail":
        return "Failed";
      case "error":
        return "Error";
      case "running":
        return "Running";
      default:
        return "Unknown";
    }
  }

  window.NexusOperations = Object.freeze({
    list,
    run,
    statusLabel,
    NexusOperationError,
  });
})();
