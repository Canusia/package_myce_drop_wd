// drop_wd/staticfiles/drop_wd/js/requests_summary.js
/* CE Summary tab: term-filtered aggregates of Drop/WD requests.
 *
 * Tables are client-side on purpose. One row per term / school / course is a
 * small result set, and it means the CSV and PDF buttons export every row —
 * a serverSide table would silently export only the page on screen.
 *
 * initDropWdRequestsSummary(opts) where opts = {summaryUrl, formSelector,
 * containerSelector, headlineSelector, trendSelector}.
 */
(function () {
  'use strict';

  var tables = {};

  function escapeHtml(value) {
    return $('<div>').text(value == null ? '' : value).html();
  }

  function barCell(pct) {
    // Proportion bar drawn with a div — no charting dependency, and it degrades
    // to the plain number in CSV/PDF because those read the raw data, not HTML.
    var width = Math.max(0, Math.min(100, pct));
    return '<div class="dw-bar-track" title="' + pct + '% of all requests">' +
           '<div class="dw-bar-fill" style="width:' + width + '%"></div>' +
           '</div><small class="text-muted">' + pct + '%</small>';
  }

  function buildButtons(title) {
    return [
      { extend: 'csv', className: 'btn btn-sm btn-primary text-white text-light',
        text: '<i class="fas fa-file-csv text-white"></i>&nbsp;CSV',
        title: title, titleAttr: 'Export every row to CSV',
        exportOptions: { columns: ':not(.dw-no-export)' } },
      { extend: 'pdfHtml5', className: 'btn btn-sm btn-primary text-white text-light',
        text: '<i class="fas fa-file-pdf text-white"></i>&nbsp;PDF',
        title: title, titleAttr: 'Export every row to PDF',
        orientation: 'portrait', pageSize: 'LETTER',
        exportOptions: { columns: ':not(.dw-no-export)' } },
      { extend: 'print', className: 'btn btn-sm btn-primary text-white text-light',
        text: '<i class="fas fa-print text-white"></i>&nbsp;Print',
        title: title, exportOptions: { columns: ':not(.dw-no-export)' } },
    ];
  }

  function renderBreakdown($container, breakdown) {
    var id = 'dw-summary-' + breakdown.key;
    var $card = $(
      '<div class="card mb-3">' +
        '<div class="card-header bg-white"><strong>' + escapeHtml(breakdown.title) + '</strong></div>' +
        '<div class="card-body">' +
          '<table id="' + id + '" class="table table-striped table-sm" style="width:100%"></table>' +
        '</div>' +
      '</div>');
    $container.append($card);

    if (tables[id]) { tables[id].destroy(); }

    tables[id] = $('#' + id).DataTable({
      dom: 'B<"float-left mt-2 mb-2"l><"float-right mt-2"f><"row clear">rt<"row"<"col-6"i><"col-6 float-right"p>>',
      buttons: buildButtons(breakdown.title),
      data: breakdown.rows,
      lengthMenu: [10, 25, 50, 100],
      order: [[1, 'desc']],
      deferRender: true,
      columns: [
        { data: 'name', title: breakdown.name_label,
          render: function (d, t) { return t === 'display' ? escapeHtml(d) : d; } },
        { data: 'total', title: 'Requests' },
        { data: 'requested', title: 'Open' },
        { data: 'processed', title: 'Processed' },
        { data: 'pct', title: '% of Total' },
        { data: 'pct', title: '', orderable: false, searchable: false,
          className: 'dw-no-export',
          render: function (d, t) { return t === 'display' ? barCell(d) : d; } },
      ],
    });
  }

  function renderHeadline($el, headline) {
    var tiles = [
      ['Total Requests', headline.total],
      ['Open', headline.requested],
      ['Processed', headline.processed],
      ['High Schools', headline.highschools],
      ['Courses', headline.courses],
    ];
    $el.html(tiles.map(function (t) {
      return '<div class="col"><div class="card text-center mb-3"><div class="card-body py-3">' +
             '<div class="h3 mb-0">' + escapeHtml(t[1]) + '</div>' +
             '<small class="text-muted">' + escapeHtml(t[0]) + '</small>' +
             '</div></div></div>';
    }).join(''));
  }

  function renderTrend($el, byMonth) {
    if (!byMonth.length) { $el.empty(); return; }
    var max = Math.max.apply(null, byMonth.map(function (m) { return m.total; }));
    var bars = byMonth.map(function (m) {
      var height = max ? Math.round(m.total * 100 / max) : 0;
      return '<div class="dw-trend-col" title="' + escapeHtml(m.month) + ': ' + m.total + '">' +
             '<div class="dw-trend-bar" style="height:' + Math.max(height, 2) + '%"></div>' +
             '<small class="text-muted dw-trend-label">' + escapeHtml(m.month) + '</small>' +
             '</div>';
    }).join('');
    $el.html(
      '<div class="card mb-3"><div class="card-header bg-white"><strong>Requests by Month Submitted</strong></div>' +
      '<div class="card-body"><div class="dw-trend">' + bars + '</div></div></div>');
  }

  function load(opts) {
    var $form = $(opts.formSelector);
    var $container = $(opts.containerSelector);
    var url = opts.summaryUrl + (opts.summaryUrl.indexOf('?') === -1 ? '?' : '&') + $form.serialize();

    $container.html('<p class="text-muted">Loading…</p>');

    $.getJSON(url, function (data) {
      renderHeadline($(opts.headlineSelector), data.headline);
      renderTrend($(opts.trendSelector), data.by_month);
      $container.empty();
      Object.keys(tables).forEach(function (k) { tables[k].destroy(); delete tables[k]; });
      data.breakdowns.forEach(function (b) { renderBreakdown($container, b); });
      if (!data.headline.total) {
        $container.html('<p class="text-muted">No requests match the selected term(s).</p>');
      }
    }).fail(function () {
      $container.html('<p class="text-danger">Could not load the summary. Please try again.</p>');
    });
  }

  window.initDropWdRequestsSummary = function (opts) {
    // Lazy: the tab is not visible on page load, and DataTables measures every
    // column as zero-width when it initialises inside a hidden pane.
    var loaded = false;
    $(document).on('shown.bs.tab', 'a[href="' + opts.tabSelector + '"]', function () {
      if (!loaded) { loaded = true; load(opts); }
      else { Object.keys(tables).forEach(function (k) { tables[k].columns.adjust(); }); }
    });
    $(document).on('change', opts.formSelector + ' :input', function () {
      loaded = true;
      load(opts);
    });
  };
})();
