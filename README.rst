MyCE - Drop WD
====================

models/sections.py
 def __str__(self):
        return f"{self.student.user.last_name}, {self.student.user.first_name} ({self.status})"

instructor/class.html

                        <li class="nav-item">
                            <a class="nav-link" data-toggle="tab" href="#drop_wd">Drop/WD Request(s)</a>
                        </li>


                        <div class="tab-pane" id="drop_wd">
                            <div class="card">
                                <div class="card-body">

<script>
    let baseURL = '{{drop_api_url}}'

    var table_records_all_drop_requests;
    jQuery(document).ready(function($) {
        table_records_all_drop_requests = $('#records_all_drop_requests')
.DataTable({
"fnDrawCallback": function( oSettings ) {
$.unblockUI();
},
ajax: '{{drop_api_url}}&class_section_id' + '{{class_section.id}}',
serverSide: true,
processing: true,
stateSave: true,
language: {
'loadingRecords': '&nbsp;',
},
'lengthMenu': [30, 50, 100],
'columns': [
{
    'searchable': false,
},
{
    'render': function (data, type, row, meta) {
        if(row.created_by === null)
            return '-'

        return row.created_by.last_name + ", " + row.created_by.first_name
    }
},
{
    'render': function (data, type, row, meta) {
        return row.registration.class_section.term.label
    }
},
{
    'render': function (data, type, row, meta) {
        return row.registration.student.user.first_name + ' ' + row.registration.student.user.last_name;
    }
},
null,
null,
{
    'render': function (data, type, row, meta) {
        return row.sexy_status
    }
},
]
}
);

    })
    </script>
                                    <table id="records_all_drop_requests" class="table table-striped responsive" style="width:100%">
                                        <thead>
                                            <tr>
                                                <th data-data="created_on"
                                                    data-name="created_on">Submitted On
                                                </th>
                                                <th data-data="created_by"
                                                    data-name="created_by">Submitted By
                                                </th>
                                                <th data-data="registration.class_section.term.code"
                                                    data-name="registration.class_section.term.code">Term
                                                </th>
                                                <th data-data="registration.student.user.last_name"
                                                    data-name="registration.student.user.last_name">Student</th>
                                                <th data-data="registration.class_section.course.name"
                                                    data-name="registration.class_section.course.name">Course
                                                </th>
                                                <th data-data="registration.class_section.class_number"
                                                    data-name="registration.class_section.class_number">Section
                                                </th>
                                                <th data-data="status" data-name='status'>Status</th>
                                            </tr>
                                        </thead>
                                    </table>
                                    <hr>
                                    <h3>Submit New Request</h3>
                                    {% include 'drop_wd/instructor/start_request.html' %}
                                </div>
                            </div>
                        </div>

instructor/views/home.py
In def class_section(self)

    from drop_wd.forms import DropWDRequestForm
    drop_form = DropWDRequestForm(class_section=class_section_info)

    return render(
        request,
        'instructor/class_section.html',
        {
            'menu': menu,
            'class_section': class_section_info,
            'students_in_class': students_in_class,
            'syllabi': syllabi,
            'verify_roster_form': roster_verify_form,
            'intro': portal_lang(request).from_db().get('class_blurb', 'Change me'),
            'drop_api_url': '/instructor/drop_wd/api/requests/?format=datatables',
            # 'syllabi_note': syl_review.from_db().get('instructor_message'),
            'schedule_form': schedule_form,
            'notes': notes,
            'roster_intro': roster_settings.get('intro'),
            'submit_new_drop_request_form': drop_form,
            'syllabi_form': syllabi_form
        })

In myce/urls.py

    path('ce/drop_wd/', include('drop_wd.urls.ce')),
    path('student/drop_wd/', include('drop_wd.urls.student')),


For Drop Table
ALTER TABLE drop_wd_dropwdrequest ADD COLUMN IF NOT EXISTS created_by_id INTEGER;
ALTER TABLE drop_wd_dropwdrequest ADD COLUMN IF NOT EXISTS processed_by_id INTEGER;

-- Foreign key constraints
ALTER TABLE drop_wd_dropwdrequest ADD CONSTRAINT drop_wd_dropwdrequest_created_by_id_7952d899_fk FOREIGN KEY (created_by_id) REFERENCES cis_customuser(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE drop_wd_dropwdrequest ADD CONSTRAINT drop_wd_dropwdrequest_processed_by_id_b00e0e76_fk FOREIGN KEY (processed_by_id) REFERENCES cis_customuser(id) DEFERRABLE INITIALLY DEFERRED;

-- Indexes
CREATE INDEX drop_wd_dropwdrequest_created_by_id_7952d899 ON drop_wd_dropwdrequest(created_by_id);
CREATE INDEX drop_wd_dropwdrequest_processed_by_id_b00e0e76 ON drop_wd_dropwdrequest(processed_by_id);

ALTER TABLE public.drop_wd_dropwdrequest     ADD COLUMN IF NOT EXISTS instructor_note text,     ADD COLUMN IF NOT EXISTS ce_note text,     ADD COLUMN IF NOT EXISTS student_signature jsonb,     ADD COLUMN IF NOT EXISTS parent_signature jsonb,     ADD COLUMN IF NOT EXISTS instructor_signature jsonb,     ADD COLUMN IF NOT EXISTS counselor_signature jsonb;