/* Shared DropWDRequest DataTable wiring.
 *
 * Used by the Django partial drop_wd/templates/drop_wd/_requests_table.html
 * via initDropWdRequestsTable(tableId, opts).
 *
 * Companion: drop_wd/services/requests_table.py owns the matching <th> markup
 * and the named profiles. Column keys are shared between the two registries.
 *
 * XSS trust boundary: renderers concatenate serializer fields (course name,
 * status HTML, next step) directly into HTML strings. This matches the
 * pre-refactor template verbatim — DropWDRequestSerializer is the
 * sanitization boundary.
 */
(function () {
  'use strict';

  function buildColumns(keys, opts) {
    var portalDefs = {
      select: {
        searchable: false,
        render: function () { return ''; },
      },
      submitted_on: {
        searchable: false,
      },
      submitted_by: {
        searchable: false,
        render: function (_d, _t, row) {
          if (row.created_by === null) return '-';
          return row.created_by.last_name + ', ' + row.created_by.first_name;
        },
      },
      term: {
        render: function (_d, _t, row) { return row.registration.class_section.term.label; },
      },
      student: {
        render: function (_d, _t, row) {
          return row.registration.student.user.first_name + ' ' +
                 row.registration.student.user.last_name;
        },
      },
      course: {},
      class_number: {},
      section_number: {
        render: function (_d, _t, row) { return row.registration.class_section.section_number; },
      },
      approvals: {
        orderable: false,
        searchable: false,
      },
      status: {
        render: function (_d, _t, row) {
          var col = row.sexy_status;
          if (row.next_step != '') {
            col += "<br><small class='text-muted'>Next Step - " + row.next_step + '</small>';
          }
          return col;
        },
      },
      edit_action: {
        searchable: false,
        orderable: false,
        render: function (_d, _t, row) {
          return "<a class='btn btn-sm btn-primary' href='" +
                 (opts.detailsPrefix || '') + row.id + "'>View Details</a>";
        },
      },
    };

    // The CE table (records_drop_wd_requests) renders a few shared columns
    // differently and adds two of its own. Everything here is verbatim from
    // the pre-refactor drop_wd/ce/requests_table.html.
    var ceDefs = {
      submitted_on: {},        // CE never marked this unsearchable
      highschool: {
        render: function (_d, _t, row) { return row.registration.student.highschool.name; },
      },
      student: {
        render: function (_d, _t, row) {
          return row.registration.student.user.last_name + ', ' +
                 row.registration.student.user.first_name;
        },
      },
      course: {
        render: function (_d, _t, row) { return row.registration.class_section.course.name; },
      },
      class_number: {
        render: function (_d, _t, row) { return row.registration.class_section.class_number; },
      },
      instructor: {
        render: function (_d, _t, row) {
          if (row.registration.class_section.teacher !== null) {
            return row.registration.class_section.teacher.user.last_name + ', ' +
                   row.registration.class_section.teacher.user.first_name;
          }
          return '';
        },
      },
      approvals: {
        // Bug fix (behaviour change): the pre-refactor CE template passed the
        // STRING 'false' here. A non-empty string is truthy, so DataTables kept
        // the column searchable and sent its data-name ('approvals') as a
        // search target — but 'approvals' is a serializer field, not an ORM
        // path, so the API raised FieldError (500). A real boolean makes the
        // column genuinely non-searchable, matching searchable="0" on its <th>.
        searchable: false,
        orderable: false,
      },
      status: {
        // CE shows the status badge only — no "Next Step" line.
        render: function (_d, _t, row) { return row.sexy_status; },
      },
      edit_action: {
        searchable: false,
        orderable: false,
        render: function (_d, _t, row) {
          // opts.linkStyle replaces the old `window.frameElement !== null`
          // sniff: 'modal' adds record-details (cis main.js opens the iframe
          // modal), 'plain' is what the iframe-embedded detail tabs get.
          var cls = 'btn btn-sm btn-primary';
          if (opts.linkStyle === 'modal') cls += ' record-details';
          return "<a class='" + cls + "' refresh-target='table_drop_wd_requests' href='" +
                 (opts.detailsPrefix || '') + row.id + "'>View Details</a>";
        },
      },
    };

    var defs = portalDefs;
    if (opts.columnSet === 'ce') {
      defs = {};
      Object.keys(portalDefs).forEach(function (k) { defs[k] = portalDefs[k]; });
      Object.keys(ceDefs).forEach(function (k) { defs[k] = ceDefs[k]; });
    }

    return keys.map(function (k) {
      if (!(k in defs)) throw new Error('Unknown drop_wd requests_table column: ' + k);
      return defs[k];
    });
  }

  /* Column (footer-style) search row: clone the header row and turn every
   * searchable="1" cell into a search input. Verbatim from the pre-refactor CE
   * template; runs before DataTable init, as it did there. */
  function initColumnSearch($table, getTable) {
    var $thead = $table.find('thead');
    $thead.find('tr').clone(true).appendTo($thead);
    $thead.find('tr:eq(1) th').each(function (i) {
      if ($(this).attr('searchable') != '1') {
        $(this).html('');
      } else {
        var title = $(this).text();
        $(this).html('<input type="text" class="form-control" placeholder="Search ' + title + '" />');
        $('input', this).on('keyup change', function () {
          var table = getTable();
          if (table && table.column(i).search() !== this.value) {
            table.column(i).search(this.value).draw();
          }
        });
      }
    });
  }

  var BULK_ACTIONS = {
    mark_as_approved: {
      icon: 'fa-check',
      label: 'Mark as Approved',
      titleAttr: 'Change Status',
      action: 'mark_as_approved',
    },
  };

  function buildButtons(bulkActions) {
    var buttons = [
      {
        extend: 'csv',
        className: 'btn btn-sm btn-primary text-white text-light',
        text: '<i class="fas fa-file-csv text-white"></i>&nbsp;CSV',
        titleAttr: 'Export results to CSV',
      },
      {
        extend: 'print',
        className: 'btn btn-sm btn-primary text-white text-light',
        text: '<i class="fas fa-print text-white"></i>&nbsp;Print',
        titleAttr: 'Print',
      },
    ];
    (bulkActions || []).forEach(function (k) {
      var spec = BULK_ACTIONS[k];
      if (!spec) return;
      buttons.push({
        className: 'btn btn-sm btn-primary text-white text-light',
        text: '<i class="fas ' + spec.icon + ' text-white"></i>&nbsp;' + spec.label,
        titleAttr: spec.titleAttr,
        action: function (e, dt) {
          // do_bulk_action is defined by the page (it needs a {% url %} tag).
          if (typeof window.do_bulk_action === 'function') {
            window.do_bulk_action(spec.action, dt);
          }
        },
      });
    });
    return buttons;
  }

  window.initDropWdRequestsTable = function (tableId, opts) {
    var $table = $(tableId);
    if (!$table.length) {
      throw new Error('initDropWdRequestsTable: no element matches ' + tableId);
    }

    var hasSelect = opts.columns.indexOf('select') !== -1;
    var baseURL = opts.apiUrl;
    var table = null;

    if (opts.columnSearch) {
      initColumnSearch($table, function () { return table; });
    }

    var dtConfig = {
      fnDrawCallback: function () { $.unblockUI(); },
      ajax: baseURL,
      serverSide: true,
      processing: true,
      stateSave: true,
      language: { loadingRecords: '&nbsp;' },
      rowId: 'id',
      dom: 'B<"float-left mt-3 mb-3"l><"float-right mt-3"f><"row clear">rt<"row"<"col-6"i><"col-6 float-right"p>>',
      buttons: buildButtons(opts.bulkActions),
      createdRow: function (row, data) {
        if (data['status'] == 'requested') $(row).addClass('highlight-row');
      },
      lengthMenu: [30, 50, 100],
      order: [opts.defaultOrder || [hasSelect ? 1 : 0, 'desc']],
      columns: buildColumns(opts.columns, opts),
    };
    if (hasSelect) {
      dtConfig.columnDefs = [{ orderable: false, className: 'select-checkbox', targets: 0 }];
      dtConfig.select = { style: 'os', selector: 'td:first-child' };
    }

    var $form = opts.filterFormSelector ? $(opts.filterFormSelector) : $();
    if ($form.length) {
      dtConfig.ajax = baseURL + '&' + $form.serialize();
    }

    table = $table.DataTable(dtConfig);

    if (opts.filterFormSelector) {
      $(document).on('change', opts.filterFormSelector + ' :input', function () {
        table.ajax.url(baseURL + '&' + $(opts.filterFormSelector).serialize()).load();
      });
    }

    if (opts.autoReloadMinutes) {
      setInterval(function () {
        table.ajax.reload(null, false);
      }, opts.autoReloadMinutes * 60 * 1000);
    }

    // Back-compat: the page's do_bulk_action success path and the detail-modal
    // close handler both call `table_records_all_drop_requests.ajax.reload()`.
    // Keep that global pointing at the live handle, plus a generic alias.
    window.table_records_all_drop_requests = table;
    window.dropWdRequestsTable = table;

    // The CE table's View Details links carry refresh-target='table_drop_wd_requests';
    // cis main.js resolves that through window[...] when the modal closes, so the
    // global the old inline script declared has to keep existing.
    if (opts.tableGlobal) window[opts.tableGlobal] = table;

    return table;
  };
})();
