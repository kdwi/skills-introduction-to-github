(function () {
  var $ = function (id) { return document.getElementById(id); };
  var params = new URLSearchParams(location.search);
  var wo = (params.get('wo') || '').trim();
  var pn = (params.get('pn') || '').trim();

  var state = {
    part: null,
    process: null,
    submitting: false,
    meta: null
  };

  function toast(msg, kind) {
    var el = $('toast');
    el.textContent = msg;
    el.className = 'toast show' + (kind ? ' ' + kind : '');
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.className = 'toast'; }, 2600);
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function fmtNum(n) {
    if (n == null || n === '') return '—';
    return (Math.round(n * 100) / 100).toString();
  }

  function request(url, opts) {
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) throw new Error(data.error || ('请求失败 ' + r.status));
        return data;
      });
    });
  }

  function showPicker() {
    $('loadingCard').hidden = true;
    $('pickerCard').hidden = false;
    Promise.all([request('/api/meta'), request('/api/parts')]).then(function (res) {
      state.meta = res[0].meta;
      var items = res[1].items || [];
      $('pickerCount').textContent = items.length + ' 个零件';
      renderParts(items);
      $('searchInput').addEventListener('input', function () {
        var q = this.value.trim().toLowerCase();
        renderParts(items.filter(function (it) {
          return (it.pn + ' ' + (it.project || '')).toLowerCase().indexOf(q) >= 0;
        }));
      });
    }).catch(function (e) {
      $('loadingText').textContent = e.message || '加载失败';
    });
  }

  function renderParts(items) {
    var box = $('partList');
    if (!items.length) {
      box.innerHTML = '<div class="empty">没有匹配的零件</div>';
      return;
    }
    box.innerHTML = items.map(function (it) {
      var href = '/r?wo=' + encodeURIComponent((state.meta && state.meta.order) || '') + '&pn=' + encodeURIComponent(it.pn);
      return '<a class="part-item" href="' + href + '">' +
        '<div class="pi-main"><div class="pi-pn">' + esc(it.pn) + '</div>' +
        '<div class="pi-sub">订单 ' + fmtNum(it.orderQty) + ' · 单套 ' + fmtNum(it.perSet) + ' · ' + it.processCount + ' 道工序</div></div>' +
        '<div class="pi-go">›</div></a>';
    }).join('');
  }

  function loadPart(keepProcess) {
    return request('/api/part?wo=' + encodeURIComponent(wo) + '&pn=' + encodeURIComponent(pn))
      .then(function (data) {
        state.part = data.part;
        $('loadingCard').hidden = true;
        $('pickerCard').hidden = true;
        $('detailWrap').hidden = false;
        renderPart(data.part, data.reports || []);
        var names = data.part.processes.map(function (p) { return p.name; });
        if (keepProcess && names.indexOf(keepProcess) >= 0) {
          selectProcess(keepProcess, true);
        } else {
          var first = data.part.processes.filter(function (p) { return p.name.indexOf('转') !== 0; })[0] || data.part.processes[0];
          if (first) selectProcess(first.name, true);
        }
      })
      .catch(function (e) {
        $('loadingCard').hidden = false;
        $('loadingText').textContent = e.message || '加载流程卡失败';
      });
  }

  function renderPart(part, reports) {
    $('partPn').textContent = part.pn;
    $('partProject').textContent = part.project || '';
    $('infoOrder').textContent = part.order || wo || '—';
    $('infoQty').textContent = fmtNum(part.planQty) + ' 件';
    $('infoPer').textContent = fmtNum(part.perSet) + ' / ' + fmtNum(part.nestQty) + ' 套';
    $('infoMaterial').textContent = part.material || '—';
    $('infoSpec').textContent = part.spec || '—';
    $('infoDue').textContent = part.due || '—';
    document.title = part.pn + ' · 工序报工';

    var chips = $('processChips');
    chips.innerHTML = part.processes.map(function (p) {
      var done = part.planQty > 0 && p.reportedOk >= part.planQty;
      var label = p.name;
      if (p.reportedOk > 0) label += ' ' + fmtNum(p.reportedOk);
      return '<button type="button" class="chip' + (done ? ' done' : '') + '" data-proc="' + esc(p.name) + '">' +
        '<span class="dot"></span>' + esc(label) + '</button>';
    }).join('');
    Array.prototype.forEach.call(chips.querySelectorAll('.chip'), function (btn) {
      btn.addEventListener('click', function () { selectProcess(btn.getAttribute('data-proc')); });
    });

    var finished = part.processes.filter(function (p) { return part.planQty > 0 && p.reportedOk >= part.planQty; }).length;
    $('processBadge').textContent = finished + ' / ' + part.processes.length + ' 已齐';

    renderReports(reports);
  }

  function selectProcess(name, silent) {
    if (!state.part) return;
    var proc = state.part.processes.filter(function (p) { return p.name === name; })[0];
    if (!proc) return;
    state.process = proc;
    Array.prototype.forEach.call($('processChips').querySelectorAll('.chip'), function (btn) {
      var on = btn.getAttribute('data-proc') === name;
      btn.classList.toggle('active', on);
      if (on && btn.scrollIntoView) {
        btn.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
      }
    });
    if (proc.machine && proc.machine !== '—') {
      $('machine').value = proc.machine;
    } else {
      $('machine').value = '';
    }
    $('machine').placeholder = proc.machine === '—' ? '该工序无固定设备，可留空' : '自动带出，可修改';
    updateProgress();
    if (!silent) {
      var el = $('progressOk');
      el.style.transition = 'none';
      el.style.color = '#1a73e8';
      setTimeout(function () { el.style.transition = 'color .6s'; el.style.color = ''; }, 120);
    }
  }

  function updateProgress() {
    var part = state.part, proc = state.process;
    if (!part || !proc) return;
    var plan = part.planQty || 0;
    var ok = proc.reportedOk || 0;
    var pct = plan > 0 ? Math.min(100, ok / plan * 100) : 0;
    $('progressOk').textContent = fmtNum(ok);
    $('progressPlan').textContent = fmtNum(plan);
    $('progressBar').classList.toggle('over', plan > 0 && ok > plan);
    $('progressBar').firstElementChild.style.width = pct + '%';
    $('progressLeft').textContent = plan > 0 ? '剩余 ' + fmtNum(Math.max(0, plan - ok)) + ' 件' : '未设置计划数量';
    $('progressNg').textContent = (proc.reportedNg || 0) > 0 ? '不良 ' + fmtNum(proc.reportedNg) : '';
  }

  function renderReports(reports) {
    $('recentCount').textContent = reports.length + ' 条';
    if (!reports.length) {
      $('recentList').innerHTML = '<div class="empty">暂无报工记录</div>';
      return;
    }
    $('recentList').innerHTML = reports.map(function (r) {
      var total = (r.qty_ok || 0) + (r.qty_ng || 0);
      return '<div class="rec">' +
        '<div class="rec-icon">' + esc((r.worker || '?').slice(0, 1)) + '</div>' +
        '<div class="rec-main"><div class="rec-title">' + esc(r.process) +
        ' <span>' + esc(r.worker) + (r.machine ? ' · ' + esc(r.machine) : '') + '</span></div>' +
        '<div class="rec-meta">' + esc(r.created_at) + (r.note ? ' · ' + esc(r.note) : '') + '</div></div>' +
        '<div class="rec-qty"><b>' + fmtNum(r.qty_ok) + '</b><small>' + (r.qty_ng ? '不良 ' + fmtNum(r.qty_ng) : '合格') + '</small></div>' +
        '</div>';
    }).join('');
  }

  function bindForm() {
    $('worker').value = localStorage.getItem('baogong.worker') || '';

    Array.prototype.forEach.call(document.querySelectorAll('[data-step]'), function (btn) {
      btn.addEventListener('click', function () {
        var el = $('qtyOk');
        var v = Math.max(0, (parseFloat(el.value) || 0) + parseFloat(btn.getAttribute('data-step')));
        el.value = v;
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-stepng]'), function (btn) {
      btn.addEventListener('click', function () {
        var el = $('qtyNg');
        var v = Math.max(0, (parseFloat(el.value) || 0) + parseFloat(btn.getAttribute('data-stepng')));
        el.value = v;
      });
    });
    $('fillRest').addEventListener('click', function () {
      var plan = (state.part && state.part.planQty) || 0;
      var ok = (state.process && state.process.reportedOk) || 0;
      $('qtyOk').value = Math.max(0, plan - ok);
    });
    $('fillFive').addEventListener('click', function () {
      $('qtyOk').value = (parseFloat($('qtyOk').value) || 0) + 5;
    });
    $('fillTen').addEventListener('click', function () {
      $('qtyOk').value = (parseFloat($('qtyOk').value) || 0) + 10;
    });
    $('reportForm').addEventListener('submit', submit);
  }

  function submit(e) {
    e.preventDefault();
    if (state.submitting || !state.part || !state.process) return;
    var ok = parseFloat($('qtyOk').value) || 0;
    var ng = parseFloat($('qtyNg').value) || 0;
    var worker = $('worker').value.trim();
    var plan = state.part.planQty || 0;
    var reported = state.process.reportedOk || 0;

    if (!worker) { toast('请填写报工人', 'err'); $('worker').focus(); return; }
    if (ok < 0 || ng < 0 || ok + ng <= 0) { toast('报工数量必须大于 0', 'err'); return; }
    if (plan > 0 && reported + ok + ng > plan) {
      if (!confirm('本次报工后将超过计划数量（计划 ' + plan + '，已报 ' + reported + '）。仍要提交吗？')) return;
    }

    state.submitting = true;
    $('submitBtn').disabled = true;
    $('submitBtn').textContent = '提交中…';
    localStorage.setItem('baogong.worker', worker);

    request('/api/reports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        wo: wo || state.part.order,
        pn: state.part.pn,
        process: state.process.name,
        qty_ok: ok,
        qty_ng: ng,
        worker: worker,
        machine: $('machine').value.trim(),
        note: $('note').value.trim()
      })
    }).then(function () {
      toast('报工成功：' + state.process.name + ' +' + ok + (ng ? '（不良 ' + ng + '）' : ''), 'ok');
      $('qtyOk').value = 1;
      $('qtyNg').value = 0;
      $('note').value = '';
      return loadPart(state.process.name);
    }).catch(function (err) {
      toast(err.message || '提交失败，请重试', 'err');
    }).finally(function () {
      state.submitting = false;
      $('submitBtn').disabled = false;
      $('submitBtn').textContent = '提交报工';
    });
  }

  if (!pn) {
    showPicker();
  } else if (!wo) {
    request('/api/meta').then(function (d) {
      wo = (d.meta && d.meta.order) || '';
      loadPart();
    }).catch(function () { loadPart(); });
  } else {
    loadPart();
  }
  bindForm();
})();
