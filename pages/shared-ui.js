/* ============================================================
   KBE Issue Dashboard — Shared UI
   Column sorting, resizing, filtering, tooltips, keyboard nav
   ============================================================ */

(function () {
  "use strict";

  // --- Utilities ---

  function debounce(fn, ms) {
    let timer;
    return function () {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, arguments), ms);
    };
  }

  function parseNumeric(text) {
    if (!text || text === "—" || text === "never") return -Infinity;
    const n = parseFloat(text.replace(/,/g, ""));
    return isNaN(n) ? -Infinity : n;
  }

  // --- Column Sorting ---

  function initSorting() {
    const table = document.querySelector(".data-table");
    if (!table) return;

    const headers = table.querySelectorAll("th[data-sortable]");
    let currentCol = null;
    let ascending = true;

    headers.forEach(function (th, idx) {
      const indicator = th.querySelector(".sort-indicator");

      th.addEventListener("click", function (e) {
        if (e.target.classList.contains("col-resize")) return;

        if (currentCol === idx) {
          ascending = !ascending;
        } else {
          currentCol = idx;
          ascending = true;
        }

        // Reset all indicators
        headers.forEach(function (h) {
          h.classList.remove("sorted");
          var si = h.querySelector(".sort-indicator");
          if (si) si.textContent = "⇅";
        });

        th.classList.add("sorted");
        if (indicator) indicator.textContent = ascending ? "▲" : "▼";

        sortTable(table, idx, ascending, th.dataset.sortType || "text");
        updateRowCount();
      });
    });
  }

  function sortTable(table, colIdx, ascending, sortType) {
    const tbody = table.querySelector("tbody");
    if (!tbody) return;

    const rows = Array.from(tbody.querySelectorAll("tr"));

    rows.sort(function (a, b) {
      const cellA = a.cells[colIdx];
      const cellB = b.cells[colIdx];
      if (!cellA || !cellB) return 0;

      const textA = (cellA.dataset.sortValue || cellA.textContent || "").trim();
      const textB = (cellB.dataset.sortValue || cellB.textContent || "").trim();

      let result;
      if (sortType === "number") {
        result = parseNumeric(textA) - parseNumeric(textB);
      } else {
        result = textA.localeCompare(textB, undefined, { numeric: true, sensitivity: "base" });
      }

      return ascending ? result : -result;
    });

    rows.forEach(function (row) {
      tbody.appendChild(row);
    });
  }

  // --- Column Resizing ---

  function initResizing() {
    const table = document.querySelector(".data-table");
    if (!table) return;

    const storageKey = "kbe-col-widths-" + (document.body.dataset.report || "default");
    const savedWidths = loadWidths(storageKey);

    const headers = table.querySelectorAll("th");
    headers.forEach(function (th, idx) {
      // Apply saved width
      if (savedWidths[idx]) {
        th.style.width = savedWidths[idx] + "px";
      }

      const handle = th.querySelector(".col-resize");
      if (!handle) return;

      let startX, startWidth;

      handle.addEventListener("mousedown", function (e) {
        e.preventDefault();
        startX = e.pageX;
        startWidth = th.offsetWidth;
        handle.classList.add("resizing");

        function onMouseMove(e) {
          const newWidth = Math.max(50, startWidth + (e.pageX - startX));
          th.style.width = newWidth + "px";
        }

        function onMouseUp() {
          handle.classList.remove("resizing");
          document.removeEventListener("mousemove", onMouseMove);
          document.removeEventListener("mouseup", onMouseUp);
          saveWidths(table, storageKey);
        }

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);
      });
    });
  }

  function loadWidths(key) {
    try {
      return JSON.parse(localStorage.getItem(key)) || {};
    } catch (e) {
      return {};
    }
  }

  function saveWidths(table, key) {
    var widths = {};
    table.querySelectorAll("th").forEach(function (th, idx) {
      if (th.style.width) {
        widths[idx] = parseInt(th.style.width, 10);
      }
    });
    try {
      localStorage.setItem(key, JSON.stringify(widths));
    } catch (e) { /* storage full or unavailable */ }
  }

  // --- Filtering ---

  var activeLabelFilter = null;

  function applyFilters() {
    var input = document.getElementById("filter-input");
    var checkbox = document.getElementById("mobile-filter-checkbox");
    var tbody = document.querySelector(".data-table tbody");
    if (!tbody) return;

    var term = input ? input.value.toLowerCase().trim() : "";
    var showOnlyMobile = checkbox ? checkbox.checked : false;

    var rows = tbody.querySelectorAll("tr");
    rows.forEach(function (row) {
      var hidden = false;

      // Mobile filter
      if (showOnlyMobile && row.getAttribute("data-mobile") !== "true") {
        hidden = true;
      }

      // Text filter
      if (!hidden && term) {
        var text = row.textContent.toLowerCase();
        if (text.indexOf(term) === -1) {
          hidden = true;
        }
      }

      // Label filter
      if (!hidden && activeLabelFilter) {
        var badges = row.querySelectorAll(".label-badge[data-label]");
        var hasLabel = false;
        for (var i = 0; i < badges.length; i++) {
          if (badges[i].getAttribute("data-label") === activeLabelFilter) {
            hasLabel = true;
            break;
          }
        }
        if (!hasLabel) hidden = true;
      }

      row.style.display = hidden ? "none" : "";
    });

    updateRowCount();
  }

  function updateLabelFilterIndicator() {
    var el = document.getElementById("active-label-filter");
    if (!el) return;
    if (activeLabelFilter) {
      el.innerHTML = "Filtering: " + activeLabelFilter + ' <span class="label-filter-clear">✕</span>';
      el.style.display = "";
    } else {
      el.innerHTML = "";
      el.style.display = "none";
    }
  }

  function initLabelFilter() {
    document.addEventListener("click", function (e) {
      // Clear button
      var clearBtn = e.target.closest(".label-filter-clear");
      if (clearBtn) {
        activeLabelFilter = null;
        updateLabelFilterIndicator();
        applyFilters();
        return;
      }

      // Label badge click
      var badge = e.target.closest(".label-badge[data-label]");
      if (badge) {
        var label = badge.getAttribute("data-label");
        if (activeLabelFilter === label) {
          activeLabelFilter = null;
        } else {
          activeLabelFilter = label;
        }
        updateLabelFilterIndicator();
        applyFilters();
      }
    });
  }

  function initFiltering() {
    var input = document.getElementById("filter-input");
    if (!input) return;

    var debouncedFilter = debounce(applyFilters, 200);
    input.addEventListener("input", debouncedFilter);
  }

  // --- Mobile Filter Toggle ---

  function initMobileFilter() {
    var checkbox = document.getElementById("mobile-filter-checkbox");
    if (!checkbox) return;

    // Restore saved state
    try {
      var saved = localStorage.getItem("kbe-show-mobile-only");
      if (saved === "true") {
        checkbox.checked = true;
      }
    } catch (e) { /* storage unavailable */ }

    checkbox.addEventListener("change", function () {
      try {
        localStorage.setItem("kbe-show-mobile-only", checkbox.checked ? "true" : "false");
      } catch (e) { /* storage unavailable */ }
      applyFilters();
    });

    // Apply on load if restored
    if (checkbox.checked) {
      applyFilters();
    }
  }

  // --- Row Count ---

  function updateRowCount() {
    var el = document.getElementById("row-count");
    if (!el) return;

    var tbody = document.querySelector(".data-table tbody");
    if (!tbody) return;

    var total = tbody.querySelectorAll("tr").length;
    var visible = tbody.querySelectorAll("tr:not([style*='display: none'])").length;

    if (visible === total) {
      el.textContent = "Showing " + total + " issues";
    } else {
      el.textContent = "Showing " + visible + " of " + total + " issues";
    }
  }

  // --- Tooltips ---

  function initTooltips() {
    // Toggle tooltip on click (for mobile / persistent view)
    document.addEventListener("click", function (e) {
      var trigger = e.target.closest(".tooltip-trigger");

      // Close all other active tooltips
      document.querySelectorAll(".tooltip-trigger.active").forEach(function (el) {
        if (el !== trigger) el.classList.remove("active");
      });

      if (trigger) {
        trigger.classList.toggle("active");
        e.stopPropagation();
      }
    });

    // Close tooltips when clicking outside
    document.addEventListener("click", function () {
      document.querySelectorAll(".tooltip-trigger.active").forEach(function (el) {
        el.classList.remove("active");
      });
    });
  }

  // --- Keyboard Navigation ---

  function initKeyboardNav() {
    var tbody = document.querySelector(".data-table tbody");
    if (!tbody) return;

    var rows = tbody.querySelectorAll("tr");
    rows.forEach(function (row) {
      row.setAttribute("tabindex", "0");
    });

    tbody.addEventListener("keydown", function (e) {
      var row = e.target.closest("tr");
      if (!row) return;

      if (e.key === "Enter") {
        var link = row.querySelector("a[href]");
        if (link) window.open(link.href, "_blank");
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        var next = row.nextElementSibling;
        while (next && next.style.display === "none") next = next.nextElementSibling;
        if (next) next.focus();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        var prev = row.previousElementSibling;
        while (prev && prev.style.display === "none") prev = prev.previousElementSibling;
        if (prev) prev.focus();
      }
    });
  }

  // --- Last Updated Indicator ---

  function initTimestamp() {
    var el = document.getElementById("last-updated");
    if (!el) return;

    var iso = el.dataset.timestamp;
    if (!iso) return;

    var generated = new Date(iso);

    function update() {
      var diff = Math.floor((Date.now() - generated.getTime()) / 60000);
      var text;
      if (diff < 1) {
        text = "just now";
      } else if (diff < 60) {
        text = diff + " minute" + (diff === 1 ? "" : "s") + " ago";
      } else if (diff < 1440) {
        var hours = Math.floor(diff / 60);
        text = hours + " hour" + (hours === 1 ? "" : "s") + " ago";
      } else {
        var days = Math.floor(diff / 1440);
        text = days + " day" + (days === 1 ? "" : "s") + " ago";
      }
      el.textContent = "Updated " + text;
    }

    update();
    setInterval(update, 60000);
  }

  // --- Sparklines (index page) ---

  function drawSparkline(canvas, values, color) {
    if (!canvas || !values || values.length < 2) return;
    var ctx = canvas.getContext("2d");
    var w = canvas.width = canvas.offsetWidth * 2;
    var h = canvas.height = canvas.offsetHeight * 2;
    ctx.scale(2, 2);

    var displayW = canvas.offsetWidth;
    var displayH = canvas.offsetHeight;

    var max = Math.max.apply(null, values);
    var min = Math.min.apply(null, values);
    var range = max - min || 1;

    ctx.strokeStyle = color || "#0969da";
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    ctx.beginPath();

    values.forEach(function (v, i) {
      var x = (i / (values.length - 1)) * displayW;
      var y = displayH - ((v - min) / range) * (displayH - 4) - 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.stroke();
  }

  // Expose for use in index.html
  window.KBE = {
    drawSparkline: drawSparkline,
  };

  // --- Init ---

  function init() {
    initSorting();
    initResizing();
    initFiltering();
    initMobileFilter();
    initLabelFilter();
    initTooltips();
    initKeyboardNav();
    initTimestamp();
    updateRowCount();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
