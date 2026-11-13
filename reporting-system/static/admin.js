(function () {
  var $ = function (id) { return document.getElementById(id); };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmt(n) {
    if (n == null || n === '') return '0';
    return (Math.round(n * 100) / 100).toString();
  }
  function toast(msg, kind) {
    var el = $('toast');
    el.textContent = msg;
    el.className = 'toast show' + (kind ? ' ' + kind : '');
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.className = 'toast'; }, 2200);
  }
  function get(url) {
    return fetch(url).then(function (r) { return r.json(); });
  }

  function loadSummary() {
    get('/api/summary').then(function (d) {
      $('statCnt').innerHTML = fmt(d.total.cnt) + '<small>条</small>';
      $('statOk').innerHTML = fmt(d.total.ok) + '<small>件</small>';
      $('statNg').innerHTML = fmt(d.total.ng) + '<small>件</small>';
      $('statParts').innerHTML = fmt(d.total.parts) + '<small>个</small>';
    });
  }

  function loadReports() {
    var q = [];
    var wo = $('fWo').value.trim();
    var pn = $('fPn').value.trim();
    var proc = $('fProc').value;
    if (wo) q.push('wo=' + encodeURIComponent(wo));
    if (pn) q.push('pn=' + encodeURIComponent(pn));
    q.push('limit=500');
    get('/api/reports?' + q.join('&')).then(function (d) {
      var items = (d.items || []).filter(function (r) {
        return !proc || r.process === proc;
      });
      render(items);
    });
  }

  function render(items) {
    var tb = $('tbody');
    if (!items.length) {
      tb.innerHTML = '<tr><td colspan="10" style="text-align:center;color:#64748b;padding:30px">暂无符合条件的报工记录</td></tr>';
      return;
    }
    tb.innerHTML = items.map(function (r) {
      return '<tr>' +
        '<td class="num">' + r.id + '</td>' +
        '<td>' + esc(r.created_at) + '</td>' +
        '<td>' + esc(r.wo) + '</td>' +
        '<td>' + esc(r.pn) + '</td>' +
        '<td>' + esc(r.process) + '</td>' +
        '<td class="num">' + fmt(r.qty_ok) + '</td>' +
        '<td class="num' + (r.qty_ng ? ' tag-ng' : '') + '">' + fmt(r.qty_ng) + '</td>' +
        '<td>' + esc(r.worker) + '</td>' +
        '<td>' + esc(r.machine || '—') + '</td>' +
        '<td>' + esc(r.note || '') + '</td>' +
        '</tr>';
    }).join('');
  }

  function initFilters() {
    get('/api/processes').then(function (d) {
      var sel = $('fProc');
      (d.items || []).forEach(function (name) {
        var o = document.createElement('option');
        o.value = name;
        o.textContent = name;
        sel.appendChild(o);
      });
    });
    get('/api/parts').then(function (d) {
      var dl = $('pnList');
      (d.items || []).forEach(function (it) {
        var o = document.createElement('option');
        o.value = it.pn;
        dl.appendChild(o);
      });
    });
    get('/api/meta').then(function (d) {
      if (d.meta && d.meta.order) $('fWo').value = d.meta.order;
    });
  }

  $('btnQuery').addEventListener('click', loadReports);
  $('btnReset').addEventListener('click', function () {
    $('fWo').value = '';
    $('fPn').value = '';
    $('fProc').value = '';
    loadReports();
  });
  $('fProc').addEventListener('change', loadReports);
  $('fWo').addEventListener('keydown', function (e) { if (e.key === 'Enter') loadReports(); });
  $('fPn').addEventListener('keydown', function (e) { if (e.key === 'Enter') loadReports(); });

  initFilters();
  loadSummary();
  loadReports();
})();
