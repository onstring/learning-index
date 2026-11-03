// Client-side search (search.json) and on-page card filters. DOM is built with
// textContent only; no HTML is injected from data.
(function () {
  "use strict";

  // ---- filters: narrow the cards already on the page by topic, type and level ----
  var form = document.querySelector("[data-filters]");
  if (form) {
    var cards = Array.prototype.slice.call(document.querySelectorAll(".card"));
    var shown = form.querySelector("[data-shown]");
    var selects = Array.prototype.slice.call(form.querySelectorAll("select"));

    function applyFilters() {
      var want = {};
      selects.forEach(function (s) { if (s.value) { want[s.name] = s.value; } });
      var visible = 0;
      cards.forEach(function (c) {
        var ok = Object.keys(want).every(function (k) {
          return c.getAttribute("data-" + k) === want[k];
        });
        c.hidden = !ok;
        if (ok) { visible += 1; }
      });
      if (shown) {
        shown.textContent = Object.keys(want).length
          ? visible + " of " + cards.length + " shown" : "";
      }
    }
    selects.forEach(function (s) { s.addEventListener("change", applyFilters); });
  }

  // ---- search: filter search.json by terms, render a result list ----
  var input = document.getElementById("q");
  var list = document.getElementById("results");
  if (!input || !list) { return; }
  var index = null;
  var MAX = 30;

  function load(cb) {
    if (index) { cb(index); return; }
    fetch("search.json").then(function (r) { return r.json(); }).then(function (data) {
      index = Array.isArray(data) ? data : [];
      cb(index);
    }).catch(function () { index = []; cb(index); });
  }

  function render(hits) {
    while (list.firstChild) { list.removeChild(list.firstChild); }
    if (!hits.length) { list.hidden = true; return; }
    hits.slice(0, MAX).forEach(function (h) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = h.u;
      a.textContent = h.t;
      var b = document.createElement("span");
      b.className = "b";
      b.textContent = (h.b ? h.b + " " : "") + "(" + h.h + ")";
      li.appendChild(a);
      li.appendChild(b);
      list.appendChild(li);
    });
    list.hidden = false;
  }

  function search(q) {
    var terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) { render([]); return; }
    load(function (items) {
      render(items.filter(function (it) {
        var hay = (it.t + " " + it.b + " " + it.h + " " + it.k).toLowerCase();
        return terms.every(function (t) { return hay.indexOf(t) !== -1; });
      }));
    });
  }

  var timer = null;
  input.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(function () { search(input.value); }, 120);
  });
})();
