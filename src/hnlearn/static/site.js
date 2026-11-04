// Client-side search (search.json) and on-page card filters. DOM is built with
// textContent only; no HTML is injected from data.
(function () {
  "use strict";

  // ---- favourites: a set of resource slugs kept in this browser's localStorage ----
  var FAV_KEY = "hnlearn:favourites";
  var SLUG_OK = /^[a-z0-9-]{1,80}$/;

  function loadFavs() {
    try {
      var raw = window.localStorage.getItem(FAV_KEY);
      var arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr.filter(function (s) {
        return typeof s === "string" && SLUG_OK.test(s);
      }) : [];
    } catch (e) {
      return [];
    }
  }

  function saveFavs(favs) {
    try { window.localStorage.setItem(FAV_KEY, JSON.stringify(favs)); } catch (e) { /* private mode */ }
  }

  function paintFavs(favs) {
    var buttons = Array.prototype.slice.call(document.querySelectorAll("[data-fav]"));
    buttons.forEach(function (b) {
      var on = favs.indexOf(b.getAttribute("data-fav")) !== -1;
      b.setAttribute("aria-pressed", on ? "true" : "false");
      b.setAttribute("aria-label", on ? "Remove from favourites" : "Add to favourites");
      b.textContent = on ? "★" : "☆";
    });
    var count = document.querySelector("[data-fav-count]");
    if (count) { count.textContent = favs.length ? String(favs.length) : ""; }
    var box = document.querySelector("[data-favourites]");
    if (box) {
      var any = false;
      Array.prototype.slice.call(box.querySelectorAll(".card")).forEach(function (c) {
        var keep = favs.indexOf(c.getAttribute("data-slug")) !== -1;
        c.hidden = !keep;
        any = any || keep;
      });
      box.hidden = !any;
      var empty = document.querySelector("[data-fav-empty]");
      if (empty) { empty.hidden = any; }
    }
  }

  document.addEventListener("click", function (ev) {
    var b = ev.target.closest ? ev.target.closest("[data-fav]") : null;
    if (!b) { return; }
    var slug = b.getAttribute("data-fav");
    if (!SLUG_OK.test(slug)) { return; }
    var favs = loadFavs();
    var next = favs.indexOf(slug) === -1
      ? favs.concat([slug])
      : favs.filter(function (s) { return s !== slug; });
    saveFavs(next);
    paintFavs(next);
  });
  paintFavs(loadFavs());

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
