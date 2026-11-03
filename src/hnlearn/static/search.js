// Client-side search over search.json. Builds DOM nodes with textContent only.
(function () {
  "use strict";
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
