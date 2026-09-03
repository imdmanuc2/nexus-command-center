"use strict";

const NEXUS_PRIMARY_NAV = [
  { label: "Command Center", href: "/", routes: ["/", "/index.html", "/home-v2.html"] },
  { label: "CMDB", href: "/assets.html", routes: ["/assets.html", "/cmdb-object.html"] },
  { label: "Blockchain", href: "/blockchain.html", routes: ["/blockchain.html"] },
  { label: "Operations Center", href: "/operations-center.html", routes: ["/operations-center.html", "/service-operations.html"] },
  { label: "Infrastructure Explorer", href: "/graph.html", routes: ["/graph.html", "/service-topology.html"] },
  { label: "Alerts", href: "/alerts.html", routes: ["/alerts.html"] },
  { label: "Timeline", href: "/timeline.html", routes: ["/timeline.html"] }
];

const NEXUS_SECONDARY_NAV = [
  { label: "Pools", href: "/pools.html" },
  { label: "Discovery", href: "/discovery.html" },
  { label: "Peers", href: "/peers.html" },
  { label: "Analytics", href: "/analytics.html" },
  { label: "Settings", href: "/settings.html" }
];

const NEXUS_WORKFLOW_STEPS = [
  {
    key: "health",
    label: "Fleet Health",
    question: "Is the environment healthy?",
    href: "/home-v2.html",
    routes: ["/", "/index.html", "/home-v2.html"]
  },
  {
    key: "inventory",
    label: "Fleet",
    question: "What do I have?",
    href: "/assets.html",
    routes: ["/assets.html"]
  },
  {
    key: "object",
    label: "Digital Twin",
    question: "What is this object doing?",
    href: "/cmdb-object.html",
    routes: ["/cmdb-object.html"]
  },
  {
    key: "operations",
    label: "Operations",
    question: "What should I do next?",
    href: "/operations-center.html",
    routes: ["/operations-center.html", "/service-operations.html"]
  },
  {
    key: "topology",
    label: "Explorer",
    question: "How is everything connected?",
    href: "/graph.html",
    routes: ["/graph.html", "/service-topology.html"]
  }
];

function currentPath() {
  const path = window.location.pathname || "/";
  return path.endsWith("/") && path !== "/" ? path.slice(0, -1) : path;
}

function routeMatches(item, path) {
  return (item.routes || [item.href]).includes(path);
}

function activeNavItem(path) {
  return NEXUS_PRIMARY_NAV.find(item => routeMatches(item, path)) || null;
}

function renderNav(activeLabel) {
  const nav = document.getElementById("topNav");
  if (!nav) return;

  const path = currentPath();
  const inferred = activeNavItem(path)?.label;
  const active = activeLabel || inferred || "";

  const primary = NEXUS_PRIMARY_NAV.map(item => `
    <a
      class="${item.label === active ? "active" : ""}"
      href="${item.href}"
      data-nexus-nav="primary"
    >${item.label}</a>
  `).join("");

  const secondary = NEXUS_SECONDARY_NAV.map(item => `
    <a
      class="${routeMatches(item, path) ? "active" : ""}"
      href="${item.href}"
      data-nexus-nav="secondary"
    >${item.label}</a>
  `).join("");

  nav.innerHTML = `
    <div class="nexus-nav-primary">${primary}</div>
    <details class="nexus-nav-more">
      <summary>More</summary>
      <div class="nexus-nav-more-menu">${secondary}</div>
    </details>
  `;
}

function workflowStepState(step, path, activeIndex, index) {
  if (step.routes.includes(path)) return "active";
  if (activeIndex >= 0 && index < activeIndex) return "complete";
  return "available";
}

function renderWorkflowRibbon() {
  const nav = document.getElementById("topNav");
  if (!nav || document.getElementById("nexusWorkflowRibbon")) return;

  const path = currentPath();
  const activeIndex = NEXUS_WORKFLOW_STEPS.findIndex(step => step.routes.includes(path));
  const activeStep = activeIndex >= 0 ? NEXUS_WORKFLOW_STEPS[activeIndex] : NEXUS_WORKFLOW_STEPS[0];

  const ribbon = document.createElement("section");
  ribbon.id = "nexusWorkflowRibbon";
  ribbon.className = "nexus-workflow-ribbon";
  ribbon.setAttribute("aria-label", "Operator workflow");

  ribbon.innerHTML = `
    <div class="nexus-workflow-purpose">
      <span>Operator focus</span>
      <strong>${activeStep.question}</strong>
    </div>
    <div class="nexus-workflow-steps">
      ${NEXUS_WORKFLOW_STEPS.map((step, index) => {
        const state = workflowStepState(step, path, activeIndex, index);
        return `
          <a class="nexus-workflow-step ${state}" href="${step.href}">
            <span>${index + 1}</span>
            <b>${step.label}</b>
          </a>
        `;
      }).join("")}
    </div>
  `;

  nav.insertAdjacentElement("afterend", ribbon);
}

function bindGlobalOperatorShortcuts() {
  document.addEventListener("keydown", event => {
    if (event.defaultPrevented) return;
    const target = event.target;
    const editable = target && (
      target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.isContentEditable
    );
    if (editable) return;

    if (event.key === "/") {
      const search = document.querySelector(
        "#fleetSearch, #graphSearch, input[type='search'], input[placeholder*='Search']"
      );
      if (search) {
        event.preventDefault();
        search.focus();
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  renderNav();
  renderWorkflowRibbon();
  bindGlobalOperatorShortcuts();
});
